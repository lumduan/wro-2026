"""Invariants on sim/scoring.py.

These are the rules a plausible-looking scorer gets wrong. Each test names the
rule it defends, because in every case the *intuitive* implementation is the
incorrect one:

* a damaged object scores 0 even when perfectly placed (S4 §7.7 — and S1's own
  scoring sheet never says so)
* partial credit is 33.3 % for a cable and 50 % for a note, not a uniform half
* doing nothing scores 40, not 0
* an object still in the gripper scores half, not nothing
"""

from __future__ import annotations

import pytest

from sim.geometry import min_area_rect
from sim.scoring import Scorer, ScoringParams
from sim.world import ObjectState, WorldState

BONUS_OBJECTS = ("clef", "amp", "speaker_a", "speaker_b")


@pytest.fixture(scope="module")
def scorer() -> Scorer:
    return Scorer.load()


@pytest.fixture(scope="module")
def perfect(scorer: Scorer) -> WorldState:
    return scorer.perfect_world()


# --------------------------------------------------------------------------- #
# The two anchors
# --------------------------------------------------------------------------- #


def test_a_perfect_run_scores_exactly_the_maximum(scorer: Scorer, perfect: WorldState):
    result = scorer.score(perfect)
    assert result.total == result.max_score == 255
    for mission in result.missions:
        assert mission.points == mission.max_points, mission.mission_id


def test_doing_nothing_scores_exactly_the_bonus_floor(scorer: Scorer):
    """S6 2026-06-17: bonus points cannot be earned, only lost."""
    world = WorldState.untouched(sorted(set(scorer.footprints.ids()) | set(BONUS_OBJECTS)))
    result = scorer.score(world)
    assert result.total == 40
    assert result.by_mission()["m4_bonus"] == 40
    assert all(v == 0 for k, v in result.by_mission().items() if k != "m4_bonus")


def test_a_do_nothing_run_has_its_clock_forced_to_120s(scorer: Scorer):
    """S4 §10.12, with A8's reading as the parameter."""
    world = WorldState.untouched(["clef"], elapsed_s=3.0)
    forced = scorer.score(world)
    assert forced.forced_120s is True
    assert forced.elapsed_s == 120.0
    assert "A8" in (forced.forced_120s_reason or "")

    lenient = Scorer.load(params=ScoringParams(bonus_only_forces_120s=False))
    assert lenient.score(world).elapsed_s == 3.0


# --------------------------------------------------------------------------- #
# damaged is GLOBAL, not a bonus-block concern
# --------------------------------------------------------------------------- #


def test_a_perfectly_placed_but_damaged_note_scores_zero(scorer: Scorer,
                                                         perfect: WorldState):
    target, x, y, theta = scorer.nominal_placements()["note_blue"]
    world = perfect.place("note_blue", x, y, theta, damaged=True)
    result = scorer.score(world)
    row = next(r for m in result.missions for r in m.rows if r.object_id == "note_blue")
    assert row.points == 0
    assert row.tier == "zero_damaged"
    assert result.total == 255 - 20


def test_a_damaged_bonus_object_loses_its_bonus(scorer: Scorer, perfect: WorldState):
    world = WorldState(dict(perfect.objects))
    world.objects["speaker_a"] = ObjectState("speaker_a", damaged=True)
    assert scorer.score(world).total == 255 - 10


# --------------------------------------------------------------------------- #
# Partial credit is NOT uniform
# --------------------------------------------------------------------------- #


def test_partial_credit_differs_between_cable_and_note(scorer: Scorer,
                                                       perfect: WorldState):
    """5/15 for a cable against 10/20 for a note — 33.3 % against 50 %."""
    target, x, y, theta = scorer.nominal_placements()["note_blue"]
    sloppy_note = scorer.score(perfect.place("note_blue", x, y, theta, upright=False))
    note_row = next(r for m in sloppy_note.missions for r in m.rows
                    if r.object_id == "note_blue")
    assert note_row.points == 10 and note_row.tier == "partial"

    target, x, y, theta = scorer.nominal_placements()["cable_upper"]
    sloppy_cable = scorer.score(perfect.place("cable_upper", x, y, theta, upright=False))
    cable_row = next(r for m in sloppy_cable.missions for r in m.rows
                     if r.object_id == "cable_upper")
    assert cable_row.points == 5 and cable_row.tier == "partial"


def test_an_instrument_has_no_partial_tier(scorer: Scorer, perfect: WorldState):
    """S1 p10: instruments score 15 or nothing; uprightness is not required."""
    world = perfect.place("instrument_guitar", 2000.0, 900.0, 0.0)
    result = scorer.score(world)
    row = next(r for m in result.missions for r in m.rows
               if r.object_id == "instrument_guitar")
    assert row.points == 0 and row.tier == "none"
    assert result.total == 255 - 15


# --------------------------------------------------------------------------- #
# A5 — held at time-out
# --------------------------------------------------------------------------- #


def test_a_held_note_scores_the_partial_tier_not_zero(scorer: Scorer,
                                                      perfect: WorldState):
    """S6 2026-06-30. The old default was wrong in the costly direction."""
    target, x, y, theta = scorer.nominal_placements()["note_blue"]
    world = perfect.place("note_blue", x, y, theta, held=True)
    row = next(r for m in scorer.score(world).missions for r in m.rows
               if r.object_id == "note_blue")
    assert row.points == 10

    strict = Scorer.load(params=ScoringParams(held_at_timeout="zero"))
    row = next(r for m in strict.score(world).missions for r in m.rows
               if r.object_id == "note_blue")
    assert row.points == 0


# --------------------------------------------------------------------------- #
# A1 — moved semantics
# --------------------------------------------------------------------------- #


def test_moved_semantics_changes_a_toppled_in_place_clef(scorer: Scorer,
                                                         perfect: WorldState):
    """The clef that fell over but never left its spot: OR loses, AND keeps."""
    world = WorldState(dict(perfect.objects))
    world.objects["clef"] = ObjectState("clef", upright=False, displaced=False)

    assert scorer.score(world).total == 255 - 10          # default: OR
    lenient = Scorer.load(params=ScoringParams(moved_semantics="and"))
    assert lenient.score(world).total == 255              # AND: still scores


# --------------------------------------------------------------------------- #
# The cable — one per area, and the orientation is forced
# --------------------------------------------------------------------------- #


def test_only_one_cable_per_area_scores(scorer: Scorer, perfect: WorldState):
    """S1 p8. Both cables in one area is 15 points, not 30."""
    target, x, y, theta = scorer.nominal_placements()["cable_upper"]
    world = perfect.place("cable_lower", x, y, theta)
    result = scorer.score(world)
    assert result.by_mission()["m1_connect_amplifier"] == 15
    reasons = [r.reason for m in result.missions for r in m.rows
               if r.mission_id == "m1_connect_amplifier"]
    assert any("only one cable per area" in r for r in reasons)


def test_the_cable_areas_are_not_axis_aligned(scorer: Scorer):
    """The Phase 4 correction, asserted at the scoring layer."""
    upper = scorer.area_rect("cable_area_upper")
    lower = scorer.area_rect("cable_area_lower")
    assert upper.angle_deg == pytest.approx(80.0, abs=0.01)
    assert lower.angle_deg == pytest.approx(100.0, abs=0.01)
    assert upper.width_mm == pytest.approx(79.700, abs=0.01)
    assert upper.height_mm == pytest.approx(207.201, abs=0.01)


def test_the_two_cables_get_mirrored_nominal_headings(scorer: Scorer):
    placements = scorer.nominal_placements()
    upper = placements["cable_upper"][3]
    lower = placements["cable_lower"][3]
    assert upper == pytest.approx(-10.0, abs=0.01)
    assert lower == pytest.approx(10.0, abs=0.01)
    assert upper == pytest.approx(-lower, abs=0.01)


def test_a_cable_laid_across_its_area_cannot_score_anywhere(scorer: Scorer):
    """128 mm into 79.7 mm: impossible, not improbable.

    Swept across the whole area rather than tested at one point, because the
    claim is about every position, not the centre.
    """
    rect = scorer.area_rect("cable_area_upper")
    across = rect.angle_deg          # cable long axis across the area's short axis
    for du in (-30.0, -15.0, 0.0, 15.0, 30.0):
        for dv in (-80.0, -40.0, 0.0, 40.0, 80.0):
            state = ObjectState("cable_upper", rect.cx + du, rect.cy + dv, across)
            tier, _ = scorer.containment(state, "cable_area_upper")
            assert tier != "full", f"scored at offset ({du}, {dv})"


# --------------------------------------------------------------------------- #
# Footprints
# --------------------------------------------------------------------------- #


def test_the_keyboard_result_is_flagged_as_bounded(scorer: Scorer,
                                                   perfect: WorldState):
    result = scorer.score(perfect)
    row = next(r for m in result.missions for r in m.rows
               if r.object_id == "instrument_keyboard")
    assert row.footprint_is_bound is True
    assert result.any_bounded_footprint is True
    assert scorer.footprints["instrument_keyboard"].width_mm == 56.0


def test_objects_scored_for_not_moving_have_no_footprint(scorer: Scorer):
    """Asking for one is a caller bug, so it raises rather than inventing."""
    for object_id in ("amp", "speaker_a", "speaker_b"):
        with pytest.raises(KeyError, match="NOT being moved"):
            _ = scorer.footprints[object_id]


def test_the_projection_reading_is_never_more_forgiving(scorer: Scorer):
    """A7: the silhouette is the larger extent, so it can only be stricter."""
    projection = Scorer.load(params=ScoringParams(footprint_reading="projection"))
    for object_id in scorer.footprints.ids():
        a, b = scorer.footprints[object_id], projection.footprints[object_id]
        assert b.width_mm >= a.width_mm and b.height_mm >= a.height_mm, object_id


# --------------------------------------------------------------------------- #
# completely_in
# --------------------------------------------------------------------------- #


def test_completely_in_ranges_over_scoring_areas_only(scorer: Scorer):
    """ADR-013. plaza, stage and start_area must not be in the domain."""
    assert set(scorer.scoring_areas) == {
        "backstage", "cable_area_lower", "cable_area_upper", "mic_target",
        "note_target_black", "note_target_blue", "note_target_green",
        "note_target_red", "note_target_white", "note_target_yellow",
    }


def test_a_note_in_the_wrong_target_scores_nothing(scorer: Scorer,
                                                   perfect: WorldState):
    """Colour matching is the mission, not a detail."""
    _t, x, y, theta = scorer.nominal_placements()["note_green"]
    world = perfect.place("note_blue", x, y, theta)
    result = scorer.score(world)
    row = next(r for m in result.missions for r in m.rows if r.object_id == "note_blue")
    assert row.points == 0 and row.tier == "none"


def test_scoring_areas_are_far_enough_apart_that_the_clause_never_bites(
        scorer: Scorer):
    """A7's 'no other area on the mat' costs nothing in practice.

    The closest two scoring areas are 61.90 mm apart, so an object would have to
    miss by ~31 mm before touching a second one — long after containment has
    already failed. Recorded so no later pass treats the clause as a live risk.
    """
    import itertools
    from sim.geometry import bbox as _bbox

    def gap(a: str, b: str) -> float:
        ax0, ay0, ax1, ay1 = _bbox(scorer.scoring_areas[a])
        bx0, by0, bx1, by1 = _bbox(scorer.scoring_areas[b])
        dx = max(ax0 - bx1, bx0 - ax1, 0.0)
        dy = max(ay0 - by1, by0 - ay1, 0.0)
        return (dx * dx + dy * dy) ** 0.5

    closest = min(gap(a, b) for a, b in itertools.combinations(scorer.scoring_areas, 2))
    assert closest == pytest.approx(61.90, abs=0.05)
    largest_object = max(max(scorer.footprints[o].width_mm, scorer.footprints[o].height_mm)
                         for o in scorer.footprints.ids())
    assert closest > 0.0  # sanity
    assert largest_object == 128.0  # the cable, and it lives 168 mm from its neighbour
