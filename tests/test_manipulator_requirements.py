"""Invariants on data/manipulator_requirements.json (Phase 7 part 1).

This artefact answers *what the manipulator must do* and deliberately refuses
*how*. The tests below defend both halves: that the requirement is derived
rather than asserted, and that the mechanism choice is not smuggled in.

The load-bearing result is the **yaw finding**. Every 32 mm object is
indifferent to heading; only the cables have a bounded tolerance, and it is
±31°. That is loose enough to come from chassis heading, so yaw costs zero motor
slots — which is the opposite of what `PHASE7_CONSTRAINTS.md` §7 said before this
unit corrected it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sim.scoring import Scorer
from sim.world import ObjectState

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "data" / "manipulator_requirements.json"
OBJECT_SPEC = ROOT / "data" / "object_spec.json"
SCORING_MODEL = ROOT / "data" / "scoring_model.json"

PLACEMENT_OBJECTS = {
    "cable_upper", "cable_lower", "mic",
    "instrument_guitar", "instrument_keyboard", "instrument_congas",
    "note_red", "note_blue", "note_green", "note_yellow", "note_white", "note_black",
}
#: S1 scores these for NOT being moved, so they are never manipulated.
NO_TOUCH = {"clef", "amp", "speaker_a", "speaker_b"}


@pytest.fixture(scope="module")
def req() -> dict:
    return json.loads(REQUIREMENTS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rows(req: dict) -> dict:
    return {r["object_id"]: r for r in req["objects"]}


# --------------------------------------------------------------------------- #
# Coverage
# --------------------------------------------------------------------------- #


def test_every_placement_object_appears_exactly_once(req: dict, rows: dict):
    assert set(rows) == PLACEMENT_OBJECTS
    assert len(req["objects"]) == len(PLACEMENT_OBJECTS) == 12


def test_no_touch_objects_are_absent(rows: dict):
    """A manipulator requirement for an object you must not touch is a bug."""
    assert not (set(rows) & NO_TOUCH)


def test_the_classes_partition_the_objects(req: dict):
    members = [o for c in req["handling_classes"] for o in c["objects"]]
    assert sorted(members) == sorted(PLACEMENT_OBJECTS)
    assert len(members) == len(set(members)), "an object is in two classes"


def test_class_points_sum_to_the_placement_total(req: dict):
    model = json.loads(SCORING_MODEL.read_text())
    placement_max = sum(m["max"] for m in model["missions"] if m["id"] != "m4_bonus")
    assert sum(c["points"] for c in req["handling_classes"]) == placement_max == 215


# --------------------------------------------------------------------------- #
# The classes are derived, not asserted
# --------------------------------------------------------------------------- #


def test_class_A_is_exactly_the_32mm_objects(req: dict):
    """Eight objects share one footprint and carry 155 of the 215 points."""
    a = next(c for c in req["handling_classes"] if c["class"] == "A")
    assert a["grip_span_min_mm"] == a["grip_span_max_mm"] == 32.0
    assert a["count"] == 8
    assert a["points"] == 155
    assert set(a["objects"]) == {
        "mic", "instrument_guitar",
        "note_red", "note_blue", "note_green", "note_yellow", "note_white", "note_black",
    }


def test_classes_are_separated_by_at_least_one_stud(req: dict):
    spans = sorted(c["grip_span_max_mm"] for c in req["handling_classes"])
    mins = sorted(c["grip_span_min_mm"] for c in req["handling_classes"])
    for upper, lower in zip(spans, mins[1:]):
        assert lower - upper >= req["provenance"]["class_gap_mm"]


def test_the_cables_are_the_largest_class(req: dict):
    largest = max(req["handling_classes"], key=lambda c: c["grip_span_max_mm"])
    assert set(largest["objects"]) == {"cable_upper", "cable_lower"}
    assert largest["grip_span_max_mm"] == 128.0


# --------------------------------------------------------------------------- #
# The yaw finding
# --------------------------------------------------------------------------- #


def test_only_the_cables_have_a_bounded_yaw_tolerance(req: dict, rows: dict):
    bounded = {oid for oid, r in rows.items() if not r["yaw_is_unbounded"]}
    assert bounded == {"cable_upper", "cable_lower"}
    assert set(req["yaw_requirement"]["objects_indifferent_to_yaw"]) == (
        PLACEMENT_OBJECTS - bounded)


def test_the_cable_yaw_tolerance_is_about_thirty_degrees(rows: dict):
    for oid in ("cable_upper", "cable_lower"):
        assert rows[oid]["yaw_tolerance_deg"] == pytest.approx(31.0, abs=1.0), oid


def test_yaw_needs_no_dedicated_actuator(req: dict):
    """The correction this unit makes to PHASE7_CONSTRAINTS §7."""
    yaw = req["yaw_requirement"]
    assert yaw["needs_a_dedicated_actuator"] is False
    assert yaw["tightest_tolerance_deg"] > 15.0


def test_the_measured_yaw_tolerance_agrees_with_the_scorer(rows: dict):
    """Independent re-derivation: the recorded angle must hold, and the next
    degree must not. Guards the scan-then-bisect against an off-by-a-step."""
    scorer = Scorer.load()
    placements = scorer.nominal_placements()
    for oid, row in rows.items():
        target, x, y, theta = placements[oid]
        if row["yaw_is_unbounded"]:
            for probe in (37.0, 90.0, 173.0):
                tier, _ = scorer.containment(ObjectState(oid, x, y, theta + probe), target)
                assert tier == "full", f"{oid} at {probe} deg"
            continue
        inside = row["yaw_tolerance_deg"] - 0.5
        outside = row["yaw_tolerance_deg"] + 1.5
        assert scorer.containment(
            ObjectState(oid, x, y, theta + inside), target)[0] == "full", oid
        assert scorer.containment(
            ObjectState(oid, x, y, theta + outside), target)[0] != "full", oid


def test_the_two_cables_need_two_different_headings(req: dict, rows: dict):
    """Mirrored areas: one mechanism serves both, one heading does not."""
    assert rows["cable_upper"]["nominal_heading_deg"] == pytest.approx(-10.0, abs=0.01)
    assert rows["cable_lower"]["nominal_heading_deg"] == pytest.approx(10.0, abs=0.01)
    assert sorted(req["yaw_requirement"]["distinct_nominal_headings_deg"]) == [
        -10.0, 0.0, 10.0]


# --------------------------------------------------------------------------- #
# The motor budget
# --------------------------------------------------------------------------- #


def test_the_motor_arithmetic_sums_to_the_s4_limit(req: dict):
    mb = req["motor_budget"]
    assert mb["total"] == 4 and "5.2.8" in mb["rule"]
    assert (mb["differential_drive"] + mb["yaw"]
            + mb["available_for_manipulator"]) == mb["total"]
    assert mb["yaw"] == 0, "the measured tolerance makes a yaw actuator unnecessary"


def test_every_exemption_cites_its_rule(req: dict):
    exemptions = req["motor_budget"]["exemptions"]
    assert len(exemptions) == 4
    for e in exemptions:
        assert e["rule"].startswith("S4 5.2"), e
        assert e["counts"], e
    # the two that are genuinely free, and the two that are not
    free = {e["mechanism"] for e in exemptions if e["counts"].startswith("no")}
    assert len(free) == 2


# --------------------------------------------------------------------------- #
# The capability ladder
# --------------------------------------------------------------------------- #


def test_the_ladder_is_monotone_and_ends_at_the_maximum(req: dict):
    ladder = req["grip_requirement"]["capability_ladder"]
    totals = [r["run_total_with_bonus_floor"] for r in ladder]
    assert totals == sorted(totals)
    assert ladder[-1]["run_total_with_bonus_floor"] == 255
    assert ladder[-1]["points_left_on_the_table"] == 0
    assert ladder[-1]["objects_reachable"] == 12


def test_a_32mm_grip_already_reaches_three_quarters_of_the_maximum(req: dict):
    """The headline: 8 of 12 objects share one footprint."""
    rung = next(r for r in req["grip_requirement"]["capability_ladder"]
                if r["span_mm"] == 32.0)
    assert rung["objects_reachable"] == 8
    assert rung["run_total_with_bonus_floor"] == 195
    assert rung["share_of_max"] == pytest.approx(195 / 255, abs=0.001)


def test_the_ladder_includes_the_bonus_floor(req: dict):
    """S6 2026-06-17: a robot that handles nothing still scores 40, not 0."""
    model = json.loads(SCORING_MODEL.read_text())
    bonus = next(m["max"] for m in model["missions"] if m["id"] == "m4_bonus")
    for rung in req["grip_requirement"]["capability_ladder"]:
        assert rung["run_total_with_bonus_floor"] == rung["placement_points"] + bonus


# --------------------------------------------------------------------------- #
# Honesty guards
# --------------------------------------------------------------------------- #


def test_bounded_spans_are_flagged_as_bounds(rows: dict):
    """The keyboard and congas are bounded, not measured. Say so."""
    bounded = {oid for oid, r in rows.items() if r["grip_span_is_bound"]}
    assert bounded == {"instrument_keyboard", "instrument_congas"}
    for oid in bounded:
        assert "bound" in rows[oid]["grip_span_source"].lower()


def test_the_artefact_refuses_to_choose_a_mechanism(req: dict):
    scope = req["scope"]
    assert "must be able to do" in scope["answers"]
    assert "gripper vs fork" in scope["does_not_answer"]
    assert "mass" in scope["why_not"]
    assert req["gated_on"]["measurement"]
    assert "45811" in req["gated_on"]["closed_by"]


def test_no_mass_VALUE_appears_anywhere(req: dict, rows: dict):
    """mass_g is null for all 16 objects; it must not be invented here.

    Checked as a key, not a substring: the phrase "mass_g is null" legitimately
    appears in `gated_on.why`, and a substring test would forbid the artefact
    from explaining its own gap.
    """
    def keys(node) -> set[str]:
        if isinstance(node, dict):
            return set(node) | {k for v in node.values() for k in keys(v)}
        if isinstance(node, list):
            return {k for v in node for k in keys(v)}
        return set()

    assert not {k for k in keys(req) if "mass" in k.lower()}
    for row in rows.values():
        assert not any("mass" in k.lower() for k in row)
    spec = json.loads(OBJECT_SPEC.read_text())
    assert all(o["mass_g"] is None for o in spec["objects"].values())


def test_provenance_pins_every_input(req: dict):
    inputs = req["provenance"]["inputs"]
    assert set(inputs) == {"field_spec", "object_spec", "scoring_model",
                           "placement_sensitivity"}
    assert all(len(v) == 64 for v in inputs.values())


def test_sigma_comes_from_the_sensitivity_sweep_not_recomputed(req: dict, rows: dict):
    """Cross-file: the accuracy column must match the artefact it claims."""
    sens = json.loads((ROOT / "data" / "placement_sensitivity.json").read_text())
    for reading in ("contact", "projection"):
        source = {r["label"]: r["sigma_for_p90_mm"] for r in sens["readings"][reading]}
        for oid, row in rows.items():
            assert row["sigma_for_p90_mm"][reading] == source[oid], (oid, reading)
