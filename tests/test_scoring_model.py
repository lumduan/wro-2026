"""Invariants on data/scoring_model.json.

Rules only — there is no scorer yet (Phase 6). These tests guard the two things
that go wrong silently in a hand-authored rules file: arithmetic that no longer
sums, and a reference to an ID that does not exist.

The arithmetic checks are cheap and catch transcription slips immediately. The
cross-reference checks matter more: a mission pointing at an area ID that
field_spec.json does not define would only surface when the scorer runs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "data" / "scoring_model.json"
SPEC = ROOT / "data" / "field_spec.json"

MAX_SCORE = 255


@pytest.fixture(scope="module")
def model() -> dict:
    return json.loads(MODEL.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def spec() -> dict:
    return json.loads(SPEC.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Arithmetic
# --------------------------------------------------------------------------- #


def test_maxima_sum_to_exactly_255(model: dict):
    total = sum(m["max"] for m in model["missions"])
    assert total == MAX_SCORE == model["max_score"]


def test_each_times_count_equals_max_per_mission(model: dict):
    """Catches a slip in either column that a bare sum-to-255 would hide."""
    for mission in model["missions"]:
        if mission["id"] == "m4_bonus":
            # bonus is three entries with different counts; check them individually
            assert sum(e["max"] for e in mission["entries"]) == mission["max"]
            for entry in mission["entries"]:
                assert entry["each"] * entry["count"] == entry["max"], entry
            continue
        assert mission["each"] * mission["count"] == mission["max"], mission["id"]


def test_partial_ratios_match_their_point_values(model: dict):
    for mission in model["missions"]:
        partial = mission.get("partial")
        if not partial:
            continue
        assert partial["points"] / mission["each"] == pytest.approx(
            partial["ratio"], abs=1e-3
        ), mission["id"]


def test_cable_partial_credit_is_one_third_not_a_half(model: dict):
    """C1. Anti-pattern #7 previously asserted a uniform 50 %."""
    cable = next(m for m in model["missions"] if m["id"] == "m1_connect_amplifier")
    assert cable["partial"]["points"] == 5
    assert cable["each"] == 15
    assert cable["partial"]["ratio"] == pytest.approx(1 / 3, abs=1e-3)


def test_partial_credit_is_documented_as_non_uniform(model: dict):
    ratios = model["derived_facts"]["partial_credit_is_not_uniform"]
    assert ratios["cable"] == pytest.approx(1 / 3, abs=1e-3)
    assert ratios["microphone"] == 0.5 and ratios["note"] == 0.5


def test_notes_are_47_percent_of_the_total(model: dict):
    notes = next(m for m in model["missions"] if m["id"] == "m3_play_the_song")
    assert notes["max"] == 120
    assert notes["max"] / MAX_SCORE == pytest.approx(0.4706, abs=1e-3)


def test_bonus_is_40_and_is_framed_as_a_floor(model: dict):
    """C6: bonus points cannot be earned, only lost."""
    bonus = next(m for m in model["missions"] if m["id"] == "m4_bonus")
    assert bonus["max"] == 40
    floor = bonus["floor_not_prize"]
    assert "P(collision) * 40" in floor["expected_value_form"]


# --------------------------------------------------------------------------- #
# Cross-references into the frozen ID tables and field_spec
# --------------------------------------------------------------------------- #


def test_every_referenced_area_exists_in_field_spec(model: dict, spec: dict):
    known = set(spec["areas"])
    for mission in model["missions"]:
        for target in mission.get("targets", []):
            assert target in known, f"{mission['id']} targets unknown area {target}"


def test_every_referenced_object_exists_in_field_spec(model: dict, spec: dict):
    known = set(spec["object_start_poses"])
    for mission in model["missions"]:
        objects = list(mission.get("objects", []))
        for entry in mission.get("entries", []):
            objects += entry["objects"]
        for obj in objects:
            assert obj in known, f"{mission['id']} references unknown object {obj}"


def test_every_scoring_area_is_the_target_of_some_mission(model: dict, spec: dict):
    """A scoring area nothing targets is either a mis-flag or a missing mission."""
    targeted = {t for m in model["missions"] for t in m.get("targets", [])}
    scoring = {n for n, a in spec["areas"].items() if a["scoring"]}
    assert scoring == targeted, f"scoring-but-untargeted: {sorted(scoring - targeted)}"


def test_speakers_are_distinguishable_instances(model: dict):
    """Bonus is 10 EACH to a max of 20, so a singular `speaker` could not work."""
    bonus = next(m for m in model["missions"] if m["id"] == "m4_bonus")
    speakers = next(e for e in bonus["entries"] if e["count"] == 2)
    assert set(speakers["objects"]) == {"speaker_a", "speaker_b"}
    assert speakers["max"] == 20


# --------------------------------------------------------------------------- #
# Predicates and the corrections they encode
# --------------------------------------------------------------------------- #


def test_damaged_is_a_global_predicate_above_every_mission(model: dict):
    """C2 (S4 7.7). S1's scoring sheet never states this."""
    damaged = model["predicates"]["damaged"]
    assert damaged["rule"] == "S4 7.7"
    assert "GLOBAL" in damaged["scope"]
    assert damaged["effect"] == "score = 0 for that object"


def test_upright_is_a_contact_test_with_the_angle_demoted(model: dict):
    """C4 (S6 2026-06-30)."""
    upright = model["predicates"]["upright"]
    assert "contact" in upright["primary_test"]
    assert upright["parameters"]["upright_tolerance_deg"]["demoted"] is True
    assert upright["parameters"]["upright_tolerance_deg"]["status"] == "ASSUME"


def test_held_objects_score_partial_not_zero(model: dict):
    """C3 - the old conservative default was wrong in the costly direction."""
    held = model["predicates"]["held_by_mechanism"]
    assert "PARTIAL" in held["effect"]
    assert "INVERTS" in held["strategy_consequence"]


def test_completely_in_declares_its_domain(model: dict):
    """ADR-013 - without this the predicate makes nothing scoreable."""
    pred = model["predicates"]["completely_in"]
    assert "scoring == true" in pred["domain"]
    assert pred["ambiguity"] == "A7"
    assert "FORCED" in pred["ambiguity_note"]


def test_moved_compares_against_run_time_state_not_the_spec(model: dict):
    """ADR-014."""
    moved = model["predicates"]["moved"]
    assert moved["reference_pose"]["source"].startswith("run-time state")
    assert moved["parameters"]["moved_semantics"]["value"] == "or"


def test_robot_overlap_evidence_is_marked_as_an_implication(model: dict):
    """C5 - recorded so nobody later cites it as a direct ruling."""
    overlap = model["predicates"]["robot_overlap"]
    assert "IMPLICATION" in overlap["evidence_class"]


# --------------------------------------------------------------------------- #
# Time and randomization
# --------------------------------------------------------------------------- #


def test_time_is_a_pure_tie_break_with_no_return_requirement(model: dict):
    time = model["time"]
    assert time["attempt_seconds"] == 120
    assert time["return_to_start_required"] is False
    assert time["ranking"]["order"] == ["score", "time"]


def test_all_three_forced_120s_conditions_are_present(model: dict):
    rules = {f["rule"] for f in model["time"]["forced_120s"]}
    assert rules == {"S4 10.12", "S4 10.4", "S4 10.11"}


def test_losing_a_motor_or_sensor_also_zeroes_the_score(model: dict):
    """S4 10.4 - part_detachment is a design constraint, not a sim detail."""
    entry = next(f for f in model["time"]["forced_120s"] if f["rule"] == "S4 10.4")
    assert entry["also"] == "score is 0"


def test_randomization_is_24_permutations_and_runtime_only(model: dict):
    rnd = model["randomization"]
    assert rnd["permutations"] == 24
    assert len(rnd["randomized_notes"]) == 4 and len(rnd["slots"]) == 4
    assert set(rnd["fixed"]) == {"note_red", "note_green"}
    assert "RUNTIME SENSING" in rnd["runtime_only"]["consequence"]
    assert set(rnd["runtime_only"]["rules"]) == {"S4 9.6", "S4 10.2", "S4 5.7"}


def test_randomization_agrees_with_field_spec(model: dict, spec: dict):
    assert model["randomization"]["permutations"] == spec["randomization"]["permutations"]
    assert set(model["randomization"]["slots"]) == set(
        spec["randomization"]["randomizable_slots"]
    )
