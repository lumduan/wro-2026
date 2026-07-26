"""Invariants on data/object_spec.json (Phase 4 part 3).

Two load-bearing assertions here.

**Contact vs projection.** Eight models place a 4x8 plate ON TOP of a 4x4 core,
so the plate overhangs at +9.6 mm and is not what touches the mat. Reading the
plate as the base gives a containment slack of 7.85 mm; the true contact patch
gives 23.85 mm. Both fit the 79.699 mm note target, so A7 holds either way —
but the scorer consumes one of them, and these tests pin which is which.

**The cable does not fit sideways.** The cable is 128.0 mm long and its target
area is 114.47 mm across. That single inequality forces the placement
orientation and is worth 30 points, so it is asserted rather than commented.
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
    contact_slack = (NOTE_TARGET_MM - note["contact_footprint_mm"][1]) / 2
    projection_slack = (NOTE_TARGET_MM - note["max_projection_mm"][1]) / 2
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
    """The clef is built on 4x Technic 1x6 bricks and gets no 4x8 plate."""
    clef = objects["clef"]
    assert clef["contact_footprint_studs"] == [4, 6]
    assert clef["overhang_height_mm"] == 0.0


# --------------------------------------------------------------------------- #
# The cable — ADR-017, and the orientation constraint it produces
# --------------------------------------------------------------------------- #


def test_the_cable_carries_the_rigid_footprint_and_flags_the_hose(objects: dict):
    """ADR-017: measure the carrier, and say explicitly what is not covered."""
    for name in ("cable_upper", "cable_lower"):
        cable = objects[name]
        assert cable["contact_footprint_studs"] == [2, 16], name
        assert cable["contact_footprint_mm"] == [16.0, 128.0], name
        assert cable["flexible_element"] is True, name
        assert cable["hose_footprint_studs"] is None, name
        assert "carrier" in cable["footprint_covers"], name


def test_the_cable_cannot_lie_across_its_target_area(spec: dict, objects: dict):
    """128.0 mm of cable into a 79.70 mm gap does not go.

    The constraint the part-3 measurement exists to produce: the cable's
    placement orientation is forced, not chosen. Measured against the area's
    OWN axes — its bounding box is 114.47 mm across and would understate the
    deficit by 34.77 mm.
    """
    import math
    field = json.loads(FIELD_SPEC.read_text())
    length = objects["cable_upper"]["contact_footprint_mm"][1]
    for area in ("cable_area_upper", "cable_area_lower"):
        poly = field["areas"][area]["polygon_visible_mm"]
        edges = [(poly[(i + 1) % len(poly)][0] - poly[i][0],
                  poly[(i + 1) % len(poly)][1] - poly[i][1]) for i in range(len(poly))]
        lengths = sorted(math.hypot(*e) for e in edges)
        across, along = lengths[0], lengths[-1]
        assert length > across, f"{area}: expected the cable NOT to fit across"
        assert length < along, f"{area}: the cable must fit along"
    c = spec["cable_orientation"]
    assert c["fits_across_short_axis"] is False and c["fits_along_long_axis"] is True
    assert c["slack_per_end_along_long_axis_mm"] == pytest.approx(39.60, abs=0.01)
    assert c["binding_slack_mm"] == pytest.approx(31.85, abs=0.01)


def test_the_two_cable_areas_need_mirrored_headings(spec: dict):
    """80 deg and 100 deg: one solution does NOT serve both."""
    c = spec["cable_orientation"]
    assert c["area_angle_upper_deg"] == pytest.approx(80.0, abs=0.01)
    assert c["area_angle_lower_deg"] == pytest.approx(100.0, abs=0.01)
    assert c["area_angle_upper_deg"] != c["area_angle_lower_deg"]
    # mirrored about the vertical
    assert (c["area_angle_upper_deg"] + c["area_angle_lower_deg"]) == pytest.approx(
        180.0, abs=0.01)


# --------------------------------------------------------------------------- #
# ADR-018 — sub-assemblies live beside objects, never inside them
# --------------------------------------------------------------------------- #


def test_subassemblies_are_never_objects(spec: dict):
    assert set(spec["subassemblies"]) & set(spec["objects"]) == set()
    for name, sub in spec["subassemblies"].items():
        assert name not in S3_BUILDABLE
        assert sub["inside"] in spec["objects"] or sub["inside"] in {
            m for m in ("speaker", "cable")}, name
        assert sub["evidence"].strip(), name


def test_every_s3_object_is_present_and_nothing_is_unresolved(spec: dict):
    """Part 3's headline: 16 of 16 mapped, zero unresolved spans."""
    assert set(spec["objects"]) == S3_BUILDABLE
    assert spec["unresolved"] == []


# --------------------------------------------------------------------------- #
# Structure — the step-count defect
# --------------------------------------------------------------------------- #


def test_build_steps_stop_before_the_inventory_pages(spec: dict):
    st = spec["structure"]
    assert st["build_step_pages"] == [2, 175]
    assert st["steps"] == 174
    assert st["inventory_pages"] == [176, 177]


def test_the_runs_tile_the_build_steps(spec: dict):
    runs = spec["structure"]["runs"]
    assert len(runs) == 20
    assert runs[0]["start"] == 2 and runs[-1]["end"] == 175
    for a, b in zip(runs, runs[1:]):
        assert a["end"] + 1 == b["start"]


# --------------------------------------------------------------------------- #
# The parts inventory and its cross-checks
# --------------------------------------------------------------------------- #


def test_the_inventory_crosschecks_all_agree(spec: dict):
    """A hand transcription is only trustworthy if something checks it."""
    checks = spec["parts_inventory"]["crosschecks"]
    assert len(checks) >= 3
    for c in checks:
        assert c["agrees"] is True, c["lego_id"]
    ids = {c["lego_id"] for c in checks}
    assert {"3035", "3703", "78c18"} <= ids


def test_the_note_plate_count_matches_the_pages_that_use_it(spec: dict):
    """8x 3035 in the inventory; the 4x8 plate callout on exactly 8 pages."""
    plate = next(s for s in spec["callout_inventory"]["shapes"]
                 if s["lego_id"] == "3035")
    assert plate["studs"] == 32 and plate["lattice"] == [4, 8]
    assert plate["pages"] == [18, 27, 35, 42, 49, 57, 67, 115]
    entry = next(e for e in spec["parts_inventory"]["elements"]
                 if e["lego_id"] == "3035")
    assert entry["quantity"] == len(plate["pages"]) == 8


def test_the_cable_carrier_is_the_technic_1x16(spec: dict):
    carrier = next(s for s in spec["callout_inventory"]["shapes"]
                   if s["lego_id"] == "3703")
    assert carrier["studs"] == 16
    entry = next(e for e in spec["parts_inventory"]["elements"]
                 if e["lego_id"] == "3703")
    assert entry["quantity"] == 4, "2 cables x 2 carriers each"


def test_inventory_quantities_are_positive_and_total_is_derived(spec: dict):
    inv = spec["parts_inventory"]
    assert all(e["quantity"] > 0 for e in inv["elements"])
    assert inv["total_elements"] == sum(e["quantity"] for e in inv["elements"])


# --------------------------------------------------------------------------- #
# Stud counting: coverage went up, the bar did not move
# --------------------------------------------------------------------------- #


def test_curated_parts_agree_with_the_detected_stud_counts(spec: dict):
    """The builder hard-fails on disagreement; this pins it in CI too."""
    curated = tomllib.loads(PARTS.read_text(encoding="utf-8"))["parts"]
    by_lego: dict[str, dict] = {s["lego_id"]: s for s in spec["callout_inventory"]["shapes"]
                                if s["lego_id"]}
    for entry in curated:
        if "lego_id" not in entry:
            continue  # deliberately ambiguous — see [limitations] in object_parts.toml
        shape = by_lego.get(entry["lego_id"])
        if shape is None or shape["studs"] is None or entry.get("studs") is None:
            continue
        assert shape["studs"] == entry["studs"], entry["part"]


def test_a_transferred_count_always_traces_to_a_self_check(spec: dict):
    """Shape transfer never invents a count; it copies a verified one."""
    for shape in spec["callout_inventory"]["shapes"]:
        if shape["count_source"] == "shape_transfer":
            assert shape["self_checked_from_clusters"], shape["shape_id"]
            assert shape["studs"] is not None
        if shape["count_source"] is None:
            assert shape["part"] is None, \
                f"shape {shape['shape_id']} is named but has no count source"


def test_a_self_checked_shape_satisfies_rows_times_cols(spec: dict):
    for shape in spec["callout_inventory"]["shapes"]:
        if shape["count_source"] in {"self_check", "shape_transfer"}:
            rows, cols = shape["lattice"]
            assert rows * cols == shape["studs"], shape["shape_id"]


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


def test_the_only_missing_containment_footprint_is_bounded(spec: dict):
    """A gap is acceptable only when its size is bounded and stated."""
    gap = spec["scoring_relevance"]["containment_objects_without_a_footprint"]
    for name in gap:
        pending = spec["objects"][name]["footprint_pending"]
        assert pending["upper_bound_mm"], name
        assert pending["upper_bound_is_not_a_measurement"] is True, name
        assert pending["reason"], name


def test_objects_scored_for_not_moving_need_no_footprint(spec: dict):
    """S1 scores clef/amp/speakers for being left alone, so a gap blocks nothing."""
    s = spec["scoring_relevance"]
    assert set(s["scored_by_not_moving"]) == {"clef", "amp", "speaker_a", "speaker_b"}
    assert set(s["needs_containment"]) | set(s["scored_by_not_moving"]) == S3_BUILDABLE
    assert not set(s["containment_objects_without_a_footprint"]) & set(
        s["scored_by_not_moving"])


def test_provenance_pins_both_curated_inputs(spec: dict):
    prov = spec["provenance"]
    for key in ("s3_sha256", "object_map_sha256", "object_parts_sha256"):
        assert len(prov[key]) == 64, key
    assert prov["callout_match_tol"] == 2.0
    assert prov["shape_slack_px"] == 8
    assert prov["shape_agree"] == 0.95


def test_the_1x6_part_attribution_is_withdrawn_not_guessed(spec: dict):
    """3009 and 3894 are the same size, so a silhouette cannot separate them.

    Both 1x6 entries carry candidates rather than an asserted id. The dimensions
    they produce are unaffected — that is exactly why the withdrawal is safe.
    """
    curated = tomllib.loads(PARTS.read_text(encoding="utf-8"))
    ambiguous = [p for p in curated["parts"] if p.get("lego_id_ambiguous")]
    assert len(ambiguous) == 2
    for entry in ambiguous:
        assert "lego_id" not in entry, "an ambiguous part must not assert one id"
        assert set(entry["lego_id_candidates"]) == {"3009", "3894"}
        assert entry["studs"] == 6 and entry["lattice"] == [1, 6]
    limitation = curated["limitations"]["silhouette_cannot_see_interior_detail"]
    assert limitation["dimensional_impact"] == "NONE"
    assert "interior" in limitation["cause"]


# --------------------------------------------------------------------------- #
# Measurement ingestion — the path must exist and must be INERT
# --------------------------------------------------------------------------- #


def test_mass_ingestion_is_wired_but_carries_nothing_yet(objects: dict):
    """Work order A2 lands masses in object_map.toml; the builder reads them.

    Until then every value must be null. A plumbing change that quietly
    introduced a placeholder would be worse than no plumbing at all — which is
    exactly why the work order said "not before".
    """
    for name, obj in objects.items():
        assert obj["mass_g"] is None, name
        assert obj["mass_source"] is None, name
        assert obj["needs_measurement"] is True, name


def test_every_footprint_is_still_stud_derived_not_calipered(objects: dict):
    """Work order A4. No caliper reading has superseded a derived value yet."""
    for name, obj in objects.items():
        if obj["contact_footprint_studs"] is None:
            continue
        assert obj["contact_footprint_source"] == "derived from stud count x 8.00 mm", name
        assert "derived_contact_footprint_mm" not in obj, name
