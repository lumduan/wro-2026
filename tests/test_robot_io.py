"""Invariants on the RobotIO contract, its backends, and the portability lint.

`docs/FIELD_TEST_PLAN.md` Step 1 calls the project's core invariant — *"mission
code imports only ``robot_io.RobotIO``, so one file runs on the simulator and on
hardware"* — **an untested claim**, and assumes testing it needs two hubs.

Most of it does not need hardware. The failure mode is linguistic: the simulator
is CPython 3.13, both hubs are MicroPython, and EV3's dates from May 2020. These
tests cover that half. Hardware still covers the half only hardware can — that
the Pybricks calls behave as documented.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "robot"))

from check_portability import (  # noqa: E402
    ALLOWED_IMPORTS,
    FORBIDDEN_IMPORTS,
    check,
    check_file,
    python_files,
)
from missions import trivial  # noqa: E402
from robot_io import NotOnThisPlatform, RobotIO  # noqa: E402
from robot_io_ev3 import Ev3RobotIO  # noqa: E402
from robot_io_spike import SpikeRobotIO  # noqa: E402
from sim.robot_io_sim import UNMODELLED_REFLECTION, SimRobotIO  # noqa: E402
from sim.scoring import Scorer  # noqa: E402
from sim.world import ObjectState, WorldState  # noqa: E402

HUB_ROOT = ROOT / "robot"

CONTRACT_METHODS = [
    "wait_for_start", "stop", "drive_straight", "turn", "heading",
    "pick_up", "place", "carrying", "read_reflection",
]


# --------------------------------------------------------------------------- #
# The portability lint — the part that makes the claim tested
# --------------------------------------------------------------------------- #


def test_all_hub_bound_code_is_inside_the_micropython_subset():
    findings = check([HUB_ROOT])
    assert findings == [], "\n".join(str(f) for f in findings)


def test_the_lint_actually_covers_the_files_it_claims_to():
    """A lint that silently matched nothing would also report success."""
    files = {p.name for p in python_files([HUB_ROOT])}
    assert {"robot_io.py", "robot_io_ev3.py", "robot_io_spike.py",
            "trivial.py"} <= files


@pytest.mark.parametrize("snippet,rule", [
    ('x = 1\nprint(f"{x}")\n', "no-fstring"),
    ("from typing import Any\n", "forbidden-import"),
    ("import dataclasses\n", "forbidden-import"),
    ("import abc\n", "forbidden-import"),
    ("import numpy\n", "forbidden-import"),
    ("from __future__ import annotations\n", "forbidden-import"),
    ("import requests\n", "unlisted-import"),
    ("from .thing import x\n", "no-relative-import"),
    ("async def go():\n    pass\n", "no-async"),
    ("async def go():\n    await thing()\n", "no-async"),
    ("count: int = 3\n", "no-annotation"),
])
def test_the_lint_rejects_what_it_says_it_rejects(tmp_path, snippet, rule):
    """A lint that has never rejected anything is not evidence."""
    path = tmp_path / "offender.py"
    path.write_text(snippet, encoding="utf-8")
    findings = check_file(path)
    assert rule in {f.rule for f in findings}, snippet


def test_every_finding_carries_its_evidence(tmp_path):
    """A lint rule without a source is a style opinion."""
    path = tmp_path / "offender.py"
    path.write_text('import abc\nx = 1\nprint(f"{x}")\n', encoding="utf-8")
    for finding in check_file(path):
        assert finding.source.strip(), finding.rule
        assert len(finding.source) > 30, "the evidence must actually say something"


def test_the_fstring_rule_cites_the_version_that_makes_it_true(tmp_path):
    """MicroPython 1.17 is Sept 2021; EV3 MicroPython v2.0 is May 2020."""
    path = tmp_path / "offender.py"
    path.write_text('x = 1\nprint(f"{x}")\n', encoding="utf-8")
    finding = next(f for f in check_file(path) if f.rule == "no-fstring")
    assert "1.17" in finding.source
    assert "2020" in finding.source


def test_the_allowlist_and_forbidden_list_do_not_overlap():
    assert not (set(ALLOWED_IMPORTS) & set(FORBIDDEN_IMPORTS))


# --------------------------------------------------------------------------- #
# The contract
# --------------------------------------------------------------------------- #


def test_the_contract_is_a_plain_class_not_an_abc():
    """MicroPython has no `abc`; the contract must not need one."""
    assert RobotIO.__bases__ == (object,)
    assert type(RobotIO) is type


def test_every_contract_method_raises_until_implemented():
    robot = RobotIO()
    for name in CONTRACT_METHODS:
        method = getattr(robot, name)
        with pytest.raises(NotImplementedError):
            method(0) if name in ("drive_straight", "turn") else method()


def test_the_contract_does_not_expose_absolute_colour():
    """S4 7.10 / 9.3: sensing must be ratiometric. `color()` is the trap."""
    surface = {n for n in dir(RobotIO) if not n.startswith("_")}
    assert "read_reflection" in surface
    assert "color" not in surface and "read_colour" not in surface


def test_the_contract_names_a_rule_for_every_method():
    """The surface cannot drift into convenience methods that break a rule."""
    for name in CONTRACT_METHODS:
        doc = getattr(RobotIO, name).__doc__ or ""
        assert doc.strip(), name


# --------------------------------------------------------------------------- #
# Backends implement the whole contract
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("backend", [SimRobotIO, Ev3RobotIO, SpikeRobotIO])
def test_every_backend_implements_every_contract_method(backend):
    for name in CONTRACT_METHODS:
        assert getattr(backend, name) is not getattr(RobotIO, name), \
            f"{backend.__name__} does not override {name}"


@pytest.mark.parametrize("backend", [Ev3RobotIO, SpikeRobotIO])
def test_hardware_backends_refuse_to_run_off_platform(backend):
    """Failing loudly beats half-working on the competition table."""
    with pytest.raises(NotOnThisPlatform, match="pybricks"):
        backend("A", "B", "S1", wheel_mm=56.0, axle_mm=114.0)


@pytest.mark.parametrize("backend", [Ev3RobotIO, SpikeRobotIO])
def test_hardware_stubs_are_marked_unverified(backend):
    module = sys.modules[backend.__module__]
    assert module.VERIFIED_ON_HARDWARE is False
    assert "UNVERIFIED" in module.UNVERIFIED
    for name in CONTRACT_METHODS:
        source = inspect.getsource(getattr(backend, name))
        assert "NotImplementedError" in source, name
        assert "#" in source, f"{name} must record the call it will make"


@pytest.mark.parametrize("backend", [Ev3RobotIO, SpikeRobotIO])
def test_hardware_backends_cite_their_documentation(backend):
    doc = sys.modules[backend.__module__].__doc__ or ""
    assert "pybricks.com" in doc
    assert "2026-07-27" in doc, "the date the docs were read"


def test_the_two_backends_guard_on_different_device_modules():
    """The reason one toolchain cannot serve both hubs.

    Checked on the import guard in __init__, not on the module text: both
    docstrings mention both modules, because each explains the difference.
    """
    ev3 = inspect.getsource(Ev3RobotIO.__init__)
    spike = inspect.getsource(SpikeRobotIO.__init__)
    assert "pybricks.ev3devices" in ev3 and "pybricks.pupdevices" not in ev3
    assert "pybricks.pupdevices" in spike and "pybricks.ev3devices" not in spike


def test_both_backends_flag_the_turn_sign_convention():
    """Pybricks turn() is CW-positive; the MAT frame is CCW-positive.

    Getting this wrong mirrors every mission, so both backends must say so.
    """
    for backend in (Ev3RobotIO, SpikeRobotIO):
        source = inspect.getsource(getattr(backend, "turn"))
        assert "CCW" in source and "negate" in source.lower()


# --------------------------------------------------------------------------- #
# The simulator backend
# --------------------------------------------------------------------------- #


def test_drive_and_turn_move_the_pose_exactly():
    robot = SimRobotIO()
    robot.drive_straight(100.0)
    assert (robot.x_mm, robot.y_mm) == pytest.approx((100.0, 0.0))
    robot.turn(90.0)
    robot.drive_straight(50.0)
    assert (robot.x_mm, robot.y_mm) == pytest.approx((100.0, 50.0))
    assert robot.heading() == pytest.approx(90.0)


def test_turn_is_ccw_positive():
    """CLAUDE.md §5.2. The convention every mission's arithmetic assumes."""
    robot = SimRobotIO()
    robot.turn(90.0)
    robot.drive_straight(10.0)
    assert robot.y_mm > 0 and robot.x_mm == pytest.approx(0.0, abs=1e-9)


def test_a_carried_object_follows_the_robot_and_lands_where_it_is_placed():
    world = WorldState({"note_blue": ObjectState("note_blue", 0.0, 0.0)})
    robot = SimRobotIO(world)
    robot.pick_up()
    assert robot.carrying() and robot.carried_object() == "note_blue"
    robot.drive_straight(300.0)
    assert world.get("note_blue").x_mm == pytest.approx(300.0)
    assert world.get("note_blue").held is True
    robot.place()
    assert not robot.carrying()
    assert world.get("note_blue").held is False
    assert world.get("note_blue").displaced is True


def test_picking_up_nothing_raises_rather_than_silently_succeeding():
    robot = SimRobotIO(WorldState({"note_blue": ObjectState("note_blue", 5000.0, 0.0)}))
    with pytest.raises(RuntimeError, match="nothing within"):
        robot.pick_up()


def test_picking_up_twice_raises():
    robot = SimRobotIO(WorldState({"note_blue": ObjectState("note_blue", 0.0, 0.0)}))
    robot.pick_up()
    with pytest.raises(RuntimeError, match="already carrying"):
        robot.pick_up()


def test_reflection_is_flagged_as_unmodelled_by_default():
    """Nothing here has sampled the mat — that is field test P1."""
    robot = SimRobotIO()
    assert robot.reflection_is_modelled is False
    assert robot.read_reflection() == UNMODELLED_REFLECTION
    modelled = SimRobotIO(surface=lambda x, y: 12.5)
    assert modelled.reflection_is_modelled is True
    assert modelled.read_reflection() == 12.5


# --------------------------------------------------------------------------- #
# The trivial mission — FIELD_TEST_PLAN Step 1
# --------------------------------------------------------------------------- #


def test_the_trivial_mission_imports_only_the_contract():
    """The core invariant, asserted on the actual file."""
    source = (HUB_ROOT / "missions" / "trivial.py").read_text(encoding="utf-8")
    imports = [line.strip() for line in source.splitlines()
               if line.startswith(("import ", "from "))]
    assert imports == ["from robot_io import RobotIO"]


def test_the_trivial_mission_runs_against_the_simulator():
    """drive 500 mm, turn 90°, read a colour — Step 1's exact specification."""
    robot = SimRobotIO()
    reading = trivial.run(robot)
    assert robot.started and robot.stopped
    assert (robot.x_mm, robot.y_mm) == pytest.approx((500.0, 0.0))
    assert robot.heading() == pytest.approx(90.0)
    assert reading == UNMODELLED_REFLECTION
    assert [name for name, _ in robot.log] == [
        "wait_for_start", "drive_straight", "turn", "read_reflection", "stop"]


# --------------------------------------------------------------------------- #
# Contract + backend + scorer compose
# --------------------------------------------------------------------------- #


def test_a_mission_driven_placement_scores_through_the_real_scorer():
    """The end-to-end claim: mission logic is verifiable today, no hardware.

    A synthetic mission — the note's true start pose is `nominal_pending`
    (ADR-014 refuses to invent it), so the robot starts at the object rather
    than driving to a coordinate this repo does not have.
    """
    scorer = Scorer.load()
    target, x, y, theta = scorer.nominal_placements()["note_blue"]

    # A parking spot well away from the origin, where the bonus objects sit
    # because their start poses are `nominal_pending`. Being explicit is now
    # required: SimRobotIO refuses an ambiguous pick_up.
    start_x, start_y = 1000.0, 1000.0
    world = scorer.perfect_world()
    world.objects["note_blue"] = ObjectState("note_blue", start_x, start_y)
    assert scorer.score(world).total == 255 - 20, "the note starts unscored"

    robot = SimRobotIO(world, x_mm=start_x, y_mm=start_y)
    robot.pick_up()
    assert robot.carried_object() == "note_blue"
    # jump to the aim point, then place: heading is irrelevant for a note, which
    # the yaw measurement in data/manipulator_requirements.json confirms
    robot.x_mm, robot.y_mm, robot.heading_deg = x, y, theta
    robot.place()

    assert scorer.score(world).total == 255


def test_leaving_an_object_held_at_timeout_still_scores_the_partial_tier():
    """S6 2026-06-30 (A5), reached through the contract rather than by hand."""
    scorer = Scorer.load()
    target, x, y, theta = scorer.nominal_placements()["note_blue"]
    world = scorer.perfect_world()
    world.objects["note_blue"] = ObjectState("note_blue", 1000.0, 1000.0)

    robot = SimRobotIO(world, x_mm=1000.0, y_mm=1000.0)
    robot.pick_up()
    robot.x_mm, robot.y_mm, robot.heading_deg = x, y, theta
    robot._move_carried()          # clock expires mid-placement; never released

    row = next(r for m in scorer.score(world).missions for r in m.rows
               if r.object_id == "note_blue")
    assert row.points == 10, "held in the area scores partial, not zero"


def test_an_ambiguous_pick_up_raises_rather_than_choosing():
    """The bug this rule exists for: several objects sit at the origin because
    their start poses are `nominal_pending`, and taking the first in dict order
    once carried the amplifier to a note target and called it a pass."""
    world = WorldState({
        "note_blue": ObjectState("note_blue", 0.0, 0.0),
        "amp": ObjectState("amp", 0.0, 0.0),
    })
    robot = SimRobotIO(world, x_mm=0.0, y_mm=0.0)
    with pytest.raises(RuntimeError, match="ambiguous"):
        robot.pick_up()
