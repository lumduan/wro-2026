"""Invariants on data/object_spec.json (Phase 4 part 2).

The load-bearing assertion here is the **contact vs projection** distinction.
Eight models place a 4x8 plate ON TOP of a 4x4 core, so the plate overhangs at
+9.6 mm and is not what touches the mat. Reading the plate as the base gives a
containment slack of 7.85 mm; the true contact patch gives 23.85 mm. Both fit
the 79.699 mm note target, so A7 holds either way — but the scorer consumes one
of them, and these tests pin which is which.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "data" / "object_spec.json"
FIELD_SPEC = ROOT / "data" / "field_spec.json"
OBJECT_MAP = ROOT / "docs" / "object_map.toml"
PARTS = ROOT / "docs" / "object_parts.toml"

STUD_MM = 8.0
NOTE_TARGET_MM = 79.699  # MEASURED(S2), the #4e5252 outer square

S3_BUILDABLE = {
    "cable_upper", "cable_lower", "mic",
    "instrument_guitar", "instrument_keyboard", "instrument_congas",
    "note_red", "note_blue", "note_green", "note_yellow", "note_white", "note_black",
    "clef", "amp", "speaker_a", "speaker_b",
}
NOTES = [f"note_{c}" for c in ("red", "blue", "green", "yellow", "white", "black")]


@pytest.fixture(scope="module")
def spec() -> dict:
    return json.loads(SPEC.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def objects(spec: dict) -> dict:
    return spec["objects"]


# --------------------------------------------------------------------------- #
# Derivation, never transcription
# --------------------------------------------------------------------------- #


def test_footprint_mm_is_exactly_studs_times_pitch(objects: dict):
    for name, obj in objects.items():
        studs = obj["contact_footprint_studs"]
        if studs is None:
            continue
        assert obj["contact_footprint_mm"] == [studs[0] * STUD_MM, studs[1] * STUD_MM], name
        proj = obj["max_projection_studs"]
        assert obj["max_projection_mm"] == [proj[0] * STUD_MM, proj[1] * STUD_MM], name


def test_lego_geometry_constants_come_from_s4(spec: dict):
    geo = spec["lego_geometry"]
    assert (geo["stud_mm"], geo["plate_mm"], geo["brick_mm"]) == (8.0, 3.2, 9.6)
    assert "7.4" in geo["source"]


# --------------------------------------------------------------------------- #
# The contact-vs-projection finding
# --------------------------------------------------------------------------- #


def test_all_six_notes_share_one_identical_base(objects: dict):
    """S1 p5 'the bases of the notes are all the same', as an assertion."""
    footprints = {tuple(objects[n]["contact_footprint_studs"]) for n in NOTES}
    projections = {tuple(objects[n]["max_projection_studs"]) for n in NOTES}
    assert footprints == {(4, 4)}, footprints
    assert projections == {(4, 8)}, projections


def test_the_overhanging_plate_is_not_the_contact_patch(objects: dict):
    """The whole point: the 4x8 plate sits at +9.6 mm, above the mat."""
    for name in NOTES + ["mic", "instrument_guitar"]:
        obj = objects[name]
        assert obj["contact_footprint_studs"] == [4, 4], name
        assert obj["max_projection_studs"] == [4, 8], name
        assert obj["overhang_height_mm"] == 9.6, name
        assert obj["contact_footprint_mm"][1] < obj["max_projection_mm"][1], name


def test_a7_slack_both_readings_fit_the_note_target(objects: dict):
    """A7's default survives whichever reading the scorer takes."""
    note = objects["note_blue"]
    contact_long = note["contact_footprint_mm"][1]
    projection_long = note["max_projection_mm"][1]
    contact_slack = (NOTE_TARGET_MM - contact_long) / 2
    projection_slack = (NOTE_TARGET_MM - projection_long) / 2
    assert contact_slack == pytest.approx(23.85, abs=0.01)
    assert projection_slack == pytest.approx(7.85, abs=0.01)
    assert projection_slack > 0, "even the silhouette must fit, or A7 changes"


def test_contact_patch_matches_the_mat_start_square(objects: dict):
    """Cross-source: S2's note start square is sized to the note's contact patch.

    31.9 mm measured on the mat against 32.0 mm derived from the stud count —
    two independent sources agreeing to 0.1 mm.
    """
    field = json.loads(FIELD_SPEC.read_text())
    start = field["note_starts"]["note_start_rand_0"]["size_mm"]
    contact = objects["note_blue"]["contact_footprint_mm"]
    assert contact[0] == pytest.approx(start[0], abs=0.15)
    assert contact[1] == pytest.approx(start[1], abs=0.15)


def test_clef_does_not_share_the_note_base(objects: dict):
    """The clef is built on 4x 1x6 bricks and gets no 4x8 plate."""
    clef = objects["clef"]
    assert clef["contact_footprint_studs"] == [4, 6]
    assert clef["overhang_height_mm"] == 0.0


# --------------------------------------------------------------------------- #
# Honesty guards
# --------------------------------------------------------------------------- #


def test_mass_is_null_everywhere_with_a_flag(objects: dict):
    """Mass cannot come from a building instruction; it must not appear."""
    for name, obj in objects.items():
        assert obj["mass_g"] is None, name
        assert obj["needs_measurement"] is True, name


def test_objects_without_a_confirmed_base_say_so(objects: dict):
    for name, obj in objects.items():
        if obj["contact_footprint_studs"] is None:
            assert obj.get("footprint_needs_analysis") is True, name


def test_every_s3_object_is_present_or_listed_unresolved(spec: dict):
    present = set(spec["objects"])
    candidates = {c for u in spec["unresolved"] for c in u["candidates"]}
    missing = S3_BUILDABLE - present
    assert missing <= candidates, f"unaccounted: {sorted(missing - candidates)}"


def test_unresolved_spans_claim_no_id(spec: dict):
    for u in spec["unresolved"]:
        assert "id" not in u


# --------------------------------------------------------------------------- #
# The callout extraction itself
# --------------------------------------------------------------------------- #


def test_callout_inventory_matches_the_known_extraction(spec: dict):
    inv = spec["callout_inventory"]
    assert inv["build_pages"] == 176
    assert inv["pages_with_callout"] == 152
    assert inv["distinct_parts"] == 45
    assert len(inv["pages_without_callout"]) == 24


def test_curated_parts_agree_with_the_detected_stud_counts(spec: dict):
    """The builder hard-fails on disagreement; this pins it in CI too."""
    curated = tomllib.loads(PARTS.read_text(encoding="utf-8"))["parts"]
    by_id = {c["cluster_id"]: c for c in spec["callout_inventory"]["clusters"]}
    for entry in curated:
        found = by_id[entry["cluster_id"]]
        if entry.get("studs") is not None:
            assert found["detected_studs"] == entry["studs"], entry["cluster_id"]
            assert found["lattice_consistent"] is True, entry["cluster_id"]


def test_the_note_base_plate_cluster_is_exactly_the_eight_models(spec: dict):
    """Cluster 4 must appear on those 8 second-steps and nowhere else."""
    by_id = {c["cluster_id"]: c for c in spec["callout_inventory"]["clusters"]}
    plate = next(c for c in by_id.values() if c["part"] == "plate_4x8")
    assert plate["detected_studs"] == 32
    assert plate["lattice"] == [4, 8]
    assert plate["pages"] == [18, 27, 35, 42, 49, 57, 67, 115]


def test_provenance_pins_both_curated_inputs(spec: dict):
    prov = spec["provenance"]
    for key in ("s3_sha256", "object_map_sha256", "object_parts_sha256"):
        assert len(prov[key]) == 64, key
    assert prov["callout_match_tol"] == 2.0
