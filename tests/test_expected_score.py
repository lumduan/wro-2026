"""Invariants on data/expected_score.json, and on the correction it carries.

This is the module that connects Phase 6 to Phase 8: the sweep says how often a
placement lands in each containment tier, the scoring model says what each tier
pays, and this multiplies them.

The correction it exists for is subtle enough to be worth stating twice.
`strategy_frame.json` reports a break-even collision probability *at
P(success) = 1*. Those **values are correct** — at σ → 0, `p_full = 1` and
`p_partial = 0`, so `E = points` exactly. What was wrong is the **scaling rule**
printed next to them: *"linear in P(success)"*. A missed placement usually scores
the **partial** tier rather than zero, so EV is not linear, and following that
rule understates it by up to 45 %.

A correct number with a wrong usage instruction attached is a failure mode worth
having tests for.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / "data" / "expected_score.json"
FRAME = ROOT / "data" / "strategy_frame.json"
SCORING_MODEL = ROOT / "data" / "scoring_model.json"

PLACEMENT_OBJECTS = {
    "cable_upper", "cable_lower", "mic",
    "instrument_guitar", "instrument_keyboard", "instrument_congas",
    "note_red", "note_blue", "note_green", "note_yellow", "note_white", "note_black",
}
#: The three missions with no partial tier — a near-miss really does score zero.
NO_PARTIAL = {"instrument_guitar", "instrument_keyboard", "instrument_congas"}


@pytest.fixture(scope="module")
def spec() -> dict:
    return json.loads(EXPECTED.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def contact(spec: dict) -> dict:
    return {m["object_id"]: m for m in spec["readings"]["contact"]["missions"]}


# --------------------------------------------------------------------------- #
# Coverage
# --------------------------------------------------------------------------- #


def test_both_a7_readings_cover_every_placement_mission(spec: dict):
    for reading in ("contact", "projection"):
        ids = {m["object_id"] for m in spec["readings"][reading]["missions"]}
        assert ids == PLACEMENT_OBJECTS, reading


def test_alternate_orientations_are_not_treated_as_missions(spec: dict):
    """`cable_upper@across_area` is a probe, not something anyone attempts."""
    for reading in ("contact", "projection"):
        for mission in spec["readings"][reading]["missions"]:
            assert "@" not in mission["object_id"]


# --------------------------------------------------------------------------- #
# The arithmetic
# --------------------------------------------------------------------------- #


def test_expected_points_is_the_tier_weighted_sum(contact: dict):
    for object_id, mission in contact.items():
        full, partial = mission["full_points"], mission["partial_points"]
        for cell in mission["cells"]:
            expected = cell["p_full"] * full + cell["p_partial"] * partial
            assert cell["expected_points"] == pytest.approx(expected, abs=5e-4), object_id


def test_at_zero_sigma_every_mission_scores_its_full_points(contact: dict):
    """The closed-form anchor: a perfect placement is worth exactly its points."""
    for object_id, mission in contact.items():
        cell = next(c for c in mission["cells"] if c["sigma_mm"] == 0.0)
        assert cell["p_full"] == 1.0, object_id
        assert cell["expected_points"] == float(mission["full_points"]), object_id


def test_at_zero_sigma_the_full_run_scores_the_maximum(spec: dict):
    model = json.loads(SCORING_MODEL.read_text())
    for reading in ("contact", "projection"):
        row = next(r for r in spec["readings"][reading]["full_attempt_run"]
                   if r["sigma_mm"] == 0.0)
        assert row["expected_placement_points"] == pytest.approx(215.0, abs=1e-6)
        clean = next(c for c in row["at_p_collision"] if c["p_collision"] == 0.0)
        assert clean["expected_total"] == pytest.approx(model["max_score"], abs=1e-6)


def test_collision_subtracts_linearly_from_the_total(spec: dict):
    """The one thing that IS linear: the risk term."""
    floor = spec["formula"]["bonus_floor"]
    for reading in ("contact", "projection"):
        for row in spec["readings"][reading]["full_attempt_run"]:
            base = next(c["expected_total"] for c in row["at_p_collision"]
                        if c["p_collision"] == 0.0)
            for cell in row["at_p_collision"]:
                assert cell["expected_total"] == pytest.approx(
                    base - cell["p_collision"] * floor, abs=5e-4)


def test_expected_points_fall_monotonically_with_sigma(contact: dict):
    for object_id, mission in contact.items():
        values = [c["expected_points"] for c in
                  sorted(mission["cells"], key=lambda c: c["sigma_mm"])]
        assert values == sorted(values, reverse=True), object_id


# --------------------------------------------------------------------------- #
# The correction
# --------------------------------------------------------------------------- #


def test_the_partial_tier_raises_ev_wherever_one_exists(contact: dict):
    for object_id, mission in contact.items():
        understatements = [c["understatement"] for c in mission["cells"]]
        if object_id in NO_PARTIAL:
            assert all(u == 0.0 for u in understatements), \
                f"{object_id} has no partial tier; the naive form is exactly right"
        else:
            assert max(understatements) > 0.0, object_id


def test_the_notes_are_understated_by_a_large_margin(contact: dict):
    """note_blue at σ = 20 mm: 10.44 naive against 15.13 true."""
    cell = next(c for c in contact["note_blue"]["cells"] if c["sigma_mm"] == 20.0)
    assert cell["expected_points_ignoring_partial"] == pytest.approx(10.44, abs=0.3)
    assert cell["expected_points"] == pytest.approx(15.13, abs=0.3)
    ratio = cell["expected_points"] / cell["expected_points_ignoring_partial"]
    assert ratio > 1.4, "the understatement must be visible, not marginal"


def test_a_note_almost_never_scores_nothing(contact: dict):
    """The shape that matters more than the size: p_none stays near zero."""
    for colour in ("red", "blue", "green", "yellow", "white", "black"):
        cell = next(c for c in contact[f"note_{colour}"]["cells"] if c["sigma_mm"] == 20.0)
        assert cell["p_none"] < 0.05, colour
        assert cell["p_full"] + cell["p_partial"] > 0.95, colour


def test_the_superseded_scaling_rule_is_recorded_in_both_places(spec: dict):
    assert "understates" in spec["formula"]["supersedes"]
    assert "strategy_frame" in spec["formula"]["supersedes"]
    frame = json.loads(FRAME.read_text())
    risk = frame["risk_model"]
    assert risk["linear_in_p_success"] is False
    assert risk["breakeven_values_are_the_sigma_zero_limit"] is True
    correction = risk["corrected_2026_07_27"]
    assert "stored VALUES are correct" in correction
    assert "SCALING RULE was wrong" in correction
    assert "instruments have no partial tier" in correction


def test_the_correction_is_not_applied_as_a_blanket_factor(spec: dict):
    note = spec["formula"]["not_a_blanket_factor"]
    assert "5/15" in note and "10/20" in note
    assert "ABSENT" in note


def test_breakeven_uses_the_exposed_cluster_not_a_flat_forty(contact: dict):
    """ADR-024 stands: a route exposes 30 or 10, not always 40."""
    assert contact["note_blue"]["bonus_points_exposed"] == 10
    assert contact["cable_upper"]["bonus_points_exposed"] == 30
    for object_id, mission in contact.items():
        for cell in mission["cells"]:
            # 1e-3: the published value is the quotient rounded to 3 decimals
            # (ADR-008), so it may differ from the exact quotient by a full unit
            # in the last place once the division is applied.
            assert cell["breakeven_p_collision"] == pytest.approx(
                cell["expected_points"] / mission["bonus_points_exposed"],
                abs=1e-3), (object_id, cell["sigma_mm"])


# --------------------------------------------------------------------------- #
# Honesty guards
# --------------------------------------------------------------------------- #


def test_neither_free_parameter_is_asserted(spec: dict):
    scope = spec["scope"]
    assert scope["sigma_is_not_measured"] is True
    assert scope["p_collision_is_not_measured"] is True
    assert "B5" in scope["sigma_source"]


def test_the_artefact_refuses_to_rank_subsets(spec: dict):
    scope = spec["scope"]
    assert "which missions to attempt" in scope["does_not_answer"]
    assert "anti-pattern #3" in scope["why_not"]
    assert "B0" in scope["why_not"], "the blocker for routing must be named"


def test_the_bonus_floor_is_carried_not_reinvented(spec: dict):
    model = json.loads(SCORING_MODEL.read_text())
    bonus = next(m["max"] for m in model["missions"] if m["id"] == "m4_bonus")
    assert spec["formula"]["bonus_floor"] == bonus == 40
    assert "S6 2026-06-17" in spec["formula"]["bonus_floor_rule"]


def test_provenance_pins_every_input(spec: dict):
    inputs = spec["provenance"]["inputs"]
    assert set(inputs) == {"scoring_model", "placement_sensitivity", "strategy_frame"}
    assert all(len(v) == 64 for v in inputs.values())
