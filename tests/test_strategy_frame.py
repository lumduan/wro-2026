"""Invariants on data/strategy_frame.json (Phase 8 part 1).

This artefact reports what each mission **costs** in travel and **risks** in
bonus points. It deliberately does not order missions: that is Phase 8 proper,
which additionally needs σ from field tests P2/P3 and the object pickup
locations, 15 of which are `nominal_pending` with null coordinates.

The load-bearing result is the risk decomposition. `CLAUDE.md` §5.6 and
`scoring_model.json` both state the EV form with a flat **× 40** term, but the 40
is four objects that S1 places apart. Whether a route exposes 10, 30 or 40 points
decides whether a mission can ever be not-worth-attempting — and for the notes it
is the difference between "sometimes" and "always".
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FRAME = ROOT / "data" / "strategy_frame.json"
SCORING_MODEL = ROOT / "data" / "scoring_model.json"

PLACEMENT_OBJECTS = {
    "cable_upper", "cable_lower", "mic",
    "instrument_guitar", "instrument_keyboard", "instrument_congas",
    "note_red", "note_blue", "note_green", "note_yellow", "note_white", "note_black",
}
NOTES = {f"note_{c}" for c in ("red", "blue", "green", "yellow", "white", "black")}


@pytest.fixture(scope="module")
def frame() -> dict:
    return json.loads(FRAME.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rows(frame: dict) -> dict:
    return {r["object_id"]: r for r in frame["missions"]}


# --------------------------------------------------------------------------- #
# Coverage
# --------------------------------------------------------------------------- #


def test_every_placement_mission_appears_once(rows: dict):
    assert set(rows) == PLACEMENT_OBJECTS


def test_the_zones_partition_the_missions_and_the_points(frame: dict):
    members = [o for z in frame["zones"] for o in z["objects"]]
    assert sorted(members) == sorted(PLACEMENT_OBJECTS)
    model = json.loads(SCORING_MODEL.read_text())
    placement_max = sum(m["max"] for m in model["missions"] if m["id"] != "m4_bonus")
    assert sum(z["points"] for z in frame["zones"]) == placement_max == 215


def test_the_field_splits_into_two_clusters(frame: dict):
    """95 points two metres away, 120 points near home."""
    zones = {z["zone"]: z for z in frame["zones"]}
    assert set(zones) == {"left_stage_end", "right_staff_end"}
    assert zones["left_stage_end"]["points"] == 95
    assert zones["right_staff_end"]["points"] == 120
    assert zones["left_stage_end"]["distance_min_mm"] > \
        zones["right_staff_end"]["distance_max_mm"], \
        "the two clusters must not overlap in distance from the start area"


def test_backstage_is_zoned_with_the_stage_not_the_notes(rows: dict):
    """The bug this zoning rule exists for.

    `backstage` misses the stage polygon by 6.3 mm, so overlap-based zoning
    filed the three instruments with the notes and credited them the clef's
    10-point risk instead of the stage cluster's 30 — while they sit 2 m from
    the start area at the far left.
    """
    for object_id in ("instrument_guitar", "instrument_keyboard", "instrument_congas"):
        assert rows[object_id]["zone"] == "left_stage_end", object_id
        assert rows[object_id]["bonus_points_exposed"] == 30, object_id
        assert rows[object_id]["distance_from_start_mm"] > 1900, object_id


# --------------------------------------------------------------------------- #
# The risk decomposition
# --------------------------------------------------------------------------- #


def test_the_stated_forty_is_retained_as_the_conservative_default(frame: dict):
    """The refinement must not read as licence to optimise the risk away."""
    risk = frame["risk_model"]
    assert "40" in risk["stated_form"]
    assert 40 in frame["provenance"]["risk_tiers_swept"]
    assert "conservative default" in risk["refinement"]
    assert "CLAUDE.md 5.6" in risk["stated_in"]


def test_the_bonus_clusters_sum_to_forty_and_cite_their_source(frame: dict):
    clusters = frame["risk_model"]["clusters"]
    assert sum(c["points"] for c in clusters) == 40
    assert {o for c in clusters for o in c["objects"]} == {
        "clef", "amp", "speaker_a", "speaker_b"}
    for cluster in clusters:
        assert cluster["source"].startswith("S1"), cluster["id"]


def test_breakeven_matches_the_closed_form(rows: dict):
    """P(collision)* = P(success) × points / risk, reported at P(success) = 1.

    Tolerance is half a unit in the last emitted place: ADR-008 fixes float
    output at 3 decimals, so 20/30 is stored as 0.667, not 0.6666666...
    """
    for object_id, row in rows.items():
        for tier in (10, 30, 40):
            expected = row["points"] / tier
            got = row["breakeven_p_collision_at_p_success_1"]["risk_" + str(tier)]
            assert got == pytest.approx(expected, abs=5e-4), (object_id, tier)


def test_the_notes_are_always_worth_attempting_at_their_exposed_risk(rows: dict):
    """20 points against the clef's 10: break-even exceeds 1, so no collision
    probability makes a note not worth attempting."""
    for object_id in NOTES:
        row = rows[object_id]
        assert row["bonus_points_exposed"] == 10, object_id
        assert row["always_worth_attempting_at_exposed_risk"] is True, object_id
        assert row["breakeven_p_collision_at_p_success_1"]["risk_10"] == 2.0


def test_the_left_side_missions_are_not_unconditionally_worth_attempting(rows: dict):
    """15-20 points against the stage cluster's 30: break-even is below 1."""
    for object_id in ("cable_upper", "cable_lower", "mic",
                      "instrument_guitar", "instrument_keyboard", "instrument_congas"):
        row = rows[object_id]
        assert row["bonus_points_exposed"] == 30, object_id
        assert row["always_worth_attempting_at_exposed_risk"] is False, object_id
        assert row["breakeven_p_collision_at_p_success_1"]["risk_30"] < 1.0


def test_the_forty_tier_is_stricter_than_the_thirty_tier(rows: dict):
    """Sanity: a larger risk term can only lower the break-even threshold."""
    for object_id, row in rows.items():
        be = row["breakeven_p_collision_at_p_success_1"]
        assert be["risk_40"] < be["risk_30"] < be["risk_10"], object_id


# --------------------------------------------------------------------------- #
# Travel
# --------------------------------------------------------------------------- #


def test_distance_is_declared_a_lower_bound(frame: dict):
    """Centre-to-centre Euclidean is not a route length, and must not read as one."""
    assert "LOWER BOUND" in frame["geometry"]["note"]
    assert "route length" in frame["geometry"]["note"]


def test_round_trip_and_point_density_are_derived(rows: dict):
    for object_id, row in rows.items():
        assert row["round_trip_mm"] == pytest.approx(
            2 * row["distance_from_start_mm"], abs=0.01), object_id
        expected = row["points"] / (row["round_trip_mm"] / 1000.0)
        assert row["points_per_metre_round_trip"] == pytest.approx(
            expected, abs=0.05), object_id


def test_the_nearest_note_is_far_denser_in_points_than_a_cable(rows: dict):
    """An eight-fold difference in points per metre travelled."""
    best_note = max(rows[n]["points_per_metre_round_trip"] for n in NOTES)
    cable = rows["cable_upper"]["points_per_metre_round_trip"]
    assert best_note / cable > 5.0


# --------------------------------------------------------------------------- #
# Honesty guards
# --------------------------------------------------------------------------- #


def test_the_artefact_refuses_to_order_missions(frame: dict):
    scope = frame["scope"]
    assert "costs" in scope["answers"] and "risks" in scope["answers"]
    assert "order" in scope["does_not_answer"]
    assert "anti-pattern #3" in scope["why_not"]
    assert "nominal_pending" in scope["why_not"]


def test_no_collision_probability_is_asserted(frame: dict):
    """Nothing here measures how likely a collision is — only the threshold."""
    blob = json.dumps(frame)
    assert "p_collision_estimate" not in blob
    for row in frame["missions"]:
        assert "p_collision" not in row
        assert "breakeven_p_collision_at_p_success_1" in row


def test_provenance_pins_every_input(frame: dict):
    inputs = frame["provenance"]["inputs"]
    assert set(inputs) == {"field_spec", "scoring_model", "placement_sensitivity"}
    assert all(len(v) == 64 for v in inputs.values())
