"""Guards on docs/HARDWARE_SESSION.md and the state it corrects.

Two jobs.

**Keep the work order and the test plan in step.** `HARDWARE_SESSION.md` says
*what order* and `FIELD_TEST_PLAN.md` says *why*; they describe the same work, so
they can drift. Every test the runbook sequences must exist in the plan.

**Stop the stale framing coming back.** From Phase 4 until 2026-07-27 this repo
recorded itself as blocked on procurement in four documents, on the strength of
one undated operator answer (ADR-025). The grep guard below fails if that phrasing
reappears — an inherited claim is exactly the failure mode, so the defence has to
live somewhere a later session cannot skip.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SESSION = ROOT / "docs" / "HARDWARE_SESSION.md"
FIELD_TEST_PLAN = ROOT / "docs" / "FIELD_TEST_PLAN.md"
ROADMAP = ROOT / "docs" / "plans" / "ROADMAP.md"
PHASE7 = ROOT / "docs" / "PHASE7_CONSTRAINTS.md"
DECISIONS = ROOT / "docs" / "DECISIONS.md"

#: Every set the operator holds, confirmed 2026-07-27 (ADR-025).
HELD_SETS = ("45544", "45678", "45681", "45811", "45819")

#: Phrasings that asserted the hardware was unavailable. Each appeared in the
#: repo before 2026-07-27 and none is true. Matched case-insensitively against
#: the documents that carried them.
STALE_BLOCKER_PHRASES = (
    "blocked on physical game objects",
    "does not yet hold",
    "procurement question answered",
    "procurement open",
    "is not yet certain",
    "the parts are not in hand",
    "acquiring wro brick set",
)

GUARDED_DOCS = (SESSION, FIELD_TEST_PLAN, ROADMAP, PHASE7)


@pytest.fixture(scope="module")
def session() -> str:
    return SESSION.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def plan() -> str:
    return FIELD_TEST_PLAN.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# The two documents stay in step
# --------------------------------------------------------------------------- #


def test_the_work_order_exists_and_is_dated(session: str):
    assert "last_reviewed: 2026-07-27" in session


def test_every_field_test_the_runbook_sequences_exists_in_the_plan(
        session: str, plan: str):
    """The runbook may not invent a test, nor rename one."""
    referenced = set(re.findall(r"\bP[1-7]\b", session))
    assert referenced, "the runbook cites no field test at all"
    for test_id in sorted(referenced):
        assert re.search(rf"###\s*{test_id}\s*·", plan), \
            f"{test_id} is sequenced in the work order but absent from the test plan"


def test_the_runbook_covers_every_test_the_plan_defines(session: str, plan: str):
    """And the reverse: a test defined but never sequenced would go undone."""
    defined = set(re.findall(r"###\s*(P[1-7])\s*·", plan))
    referenced = set(re.findall(r"\bP[1-7]\b", session))
    assert defined <= referenced, \
        f"defined in the plan but never sequenced: {sorted(defined - referenced)}"


def test_both_setup_steps_are_sequenced(session: str):
    assert "Step 0" in session and "Count the parts" in session
    assert "trivial.py" in session


#: Work-item heading pattern. The bench block is `MEAS-n`, not `An`: ADR-033
#: renamed it because `A1`-`A5` collided with ambiguities A1-A5, two of which
#: are *resolved* entries — so an unqualified "A5" read as settled fact in one
#: document and an unstarted task in another.
ITEM_RE = r"^### (MEAS-\d|B\d) · (.+)$"


def test_every_work_item_says_what_it_closes(session: str):
    """An item that does not name its consequence is busywork."""
    items = re.findall(ITEM_RE, session, re.M)
    assert len(items) >= 12, f"expected MEAS-1..5 and B0..B6, found {items}"
    blocks = re.split(r"^### (?:MEAS-\d|B\d) · ", session, flags=re.M)[1:]
    for (item_id, _title), body in zip(items, blocks):
        assert "→ closes:" in body or "→ feeds:" in body, item_id


def test_the_bench_block_uses_no_ambiguity_ids(session: str):
    """The collision ADR-033 removed must not come back.

    A bare `### A1 ·` heading in the work order means the same string identifies
    a measurement here and a rule ambiguity in `docs/AMBIGUITIES.md`.
    """
    assert not re.search(r"^### A\d+ ·", session, re.M), \
        "work items must be MEAS-n, never An — see ADR-033"
    # MEAS-6 (robot mass, S4 5.2.1) joined on 2026-07-27. Unlike 1-5 it has a
    # precondition — a chassis must exist — and it is a recurring gate, so it is
    # deliberately NOT in MEASUREMENT_PROTOCOL.md, which is the bench session.
    assert len(re.findall(r"^### MEAS-\d ·", session, re.M)) == 6


def test_the_bench_block_is_marked_as_needing_no_robot(session: str):
    """MEAS-1..3 are the highest-leverage items and need nothing built."""
    assert "No robot needed" in session or "no robot" in session.lower()
    assert "MEAS-1 → MEAS-3 outrank everything" in session


# --------------------------------------------------------------------------- #
# The state correction, and its guard
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("path", GUARDED_DOCS, ids=lambda p: p.name)
def test_no_document_still_asserts_the_hardware_is_unavailable(path: Path):
    """The guard ADR-025 exists to install.

    A stale blocker propagated through four documents because each inherited it
    from the last. This fails if any of that phrasing returns — including inside
    a correction notice, so corrections must quote the old wording in a form that
    does not read as a live claim.
    """
    text = path.read_text(encoding="utf-8").lower()
    for phrase in STALE_BLOCKER_PHRASES:
        assert phrase not in text, (
            f"{path.name} contains {phrase!r}. The hardware is held "
            f"(confirmed 2026-07-27, ADR-025)."
        )


def test_the_work_order_lists_every_set_that_is_held(session: str):
    for number in HELD_SETS:
        assert number in session, number


def test_adr_025_records_the_root_cause_and_the_rule(session: str):
    text = DECISIONS.read_text(encoding="utf-8")
    assert "## ADR-025" in text
    assert "last confirmed" in text
    assert "not sure yet" in text, "the ambiguous answer must be quoted"
    assert "not a synonym for" in text


def test_the_roadmap_shows_nothing_blocked():
    text = ROADMAP.read_text(encoding="utf-8")
    assert "NOTHING IS BLOCKED" in text
    # the diagram must no longer paint anything with the blocked or decision class
    diagram = re.search(r"```mermaid\n(.*?)```", text, re.S).group(1)
    for line in diagram.splitlines():
        stripped = line.strip()
        if stripped.startswith("class ") and not stripped.startswith("classDef"):
            assert not stripped.endswith(" blocked"), stripped
            assert not stripped.endswith(" decision"), stripped


def test_the_manipulator_gate_is_a_measurement_not_a_purchase():
    spec = json.loads((ROOT / "data" / "manipulator_requirements.json").read_text())
    gated = spec["gated_on"]
    assert gated["hardware_held"] is True
    assert gated["hardware_confirmed"] == "2026-07-27"
    assert "HARDWARE_SESSION.md" in gated["work_order"]


# --------------------------------------------------------------------------- #
# Honesty
# --------------------------------------------------------------------------- #


def test_no_measurement_is_invented(session: str):
    """The work order says what to measure. It must not contain results."""
    spec = json.loads((ROOT / "data" / "object_spec.json").read_text())
    assert all(o["mass_g"] is None for o in spec["objects"].values()), \
        "mass must stay null until something is actually weighed"
    assert "MEASURED(scale," in session, "the tag must be named for the operator"
    assert re.search(r"\bMEASURED\(scale, *\d{4}-", session) is None, \
        "a dated MEASURED(scale, ...) value would mean a result was invented"


def test_a7_is_explicitly_marked_as_unreachable_by_measurement(session: str):
    """Calipers confirm both numbers; they cannot pick between two readings."""
    assert "do not close A7" in session
    assert "2.6" in session
