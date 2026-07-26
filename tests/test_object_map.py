"""Invariants on docs/object_map.toml (Phase 4, part 3).

This file records **which S3 pages build which object**. Part 3 re-derived every
boundary from the cream run-preview box, which resolved all three of part 1's
unresolved spans and corrected three of its ranges. The tests below guard the
things that were actually got wrong: a range that stops short of its model, a
step count inflated by counting inventory pages, and a sub-assembly promoted to
an object.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OBJECT_MAP = ROOT / "docs" / "object_map.toml"
FIELD_SPEC = ROOT / "data" / "field_spec.json"

#: CLAUDE.md §5.3, frozen by ADR-012. `robot` is not a game object built in S3.
S3_BUILDABLE_OBJECTS = {
    "cable_upper", "cable_lower", "mic",
    "instrument_guitar", "instrument_keyboard", "instrument_congas",
    "note_red", "note_blue", "note_green", "note_yellow", "note_white", "note_black",
    "clef", "amp", "speaker_a", "speaker_b",
}

FIRST_STEP_PAGE = 2
LAST_STEP_PAGE = 175
INVENTORY_PAGES = [176, 177]


@pytest.fixture(scope="module")
def omap() -> dict:
    return tomllib.loads(OBJECT_MAP.read_text(encoding="utf-8"))


def test_source_sha256_matches_the_extracted_s3(omap: dict):
    import json
    probe = json.loads(
        (ROOT / "docs/extracted/WRO-2026-RM-Elementary-BI-All/probe.json").read_text()
    )
    assert omap["meta"]["source_sha256"] == probe["source"]["sha256"]


def test_lego_constants_are_the_s4_derived_ones(omap: dict):
    """S4 7.4 makes these constants, not measurements."""
    meta = omap["meta"]
    assert meta["stud_pitch_mm"] == 8.0
    assert meta["plate_mm"] == 3.2
    assert meta["brick_mm"] == 9.6


# --------------------------------------------------------------------------- #
# The step count — part 1 over-counted by two
# --------------------------------------------------------------------------- #


def test_the_last_two_pages_are_inventory_not_build_steps(omap: dict):
    """Pages 176-177 carry no step numeral; they are the parts inventory."""
    s = omap["structure"]
    assert s["first_step_page"] == FIRST_STEP_PAGE
    assert s["last_step_page"] == LAST_STEP_PAGE
    assert s["steps"] == LAST_STEP_PAGE - FIRST_STEP_PAGE + 1 == 174
    assert omap["meta"]["inventory_pages"] == "176..177"


def test_step_numbering_is_recorded_as_continuous(omap: dict):
    """The planned per-model reset does not exist; the record must say so."""
    s = omap["structure"]
    assert s["step_numbering"] == "continuous"
    assert s["resets"] is False


def test_the_boundary_signal_is_the_run_preview_not_the_callout(omap: dict):
    s = omap["structure"]
    assert "255,245,218" in s["boundary_signal"]
    assert "RUN-PREVIEW" in s["boundary_signal"].upper()
    # and the caveat must still say a run is not always a model
    assert "not always a model" in s["boundary_caveat"]


def test_every_part_1_correction_is_recorded(omap: dict):
    """The superseded values stay on the record rather than being overwritten."""
    sup = omap["superseded"]
    for key in ("step_count", "instrument_guitar", "cable", "mic",
                "instrument_keyboard", "unresolved_spans"):
        assert sup[key].strip(), key
    assert "114-123" in sup["instrument_guitar"]   # what it used to say
    assert "167-172" in sup["cable"]
    assert "66-72" in sup["mic"]


# --------------------------------------------------------------------------- #
# The map itself
# --------------------------------------------------------------------------- #


def test_models_tile_the_build_steps_with_no_gap_or_overlap(omap: dict):
    spans = sorted(tuple(m["pages"]) for m in omap["models"])
    assert spans[0][0] == FIRST_STEP_PAGE
    assert spans[-1][1] == LAST_STEP_PAGE
    for (_a_lo, a_hi), (b_lo, _b_hi) in zip(spans, spans[1:]):
        assert a_hi + 1 == b_lo, f"gap or overlap at {a_hi}/{b_lo}"


def test_every_model_page_range_is_inside_the_build_steps(omap: dict):
    for m in omap["models"]:
        lo, hi = m["pages"]
        assert FIRST_STEP_PAGE <= lo <= hi <= LAST_STEP_PAGE, m["id"]
        assert m["steps"] == [lo - 1, hi - 1], f"{m['id']}: steps must be page-1"


def test_the_guitar_includes_page_124(omap: dict):
    """The defect that proved part 1's ranges were provisional.

    Page 124 (step 123) still shows the guitar mid-build — red body, yellow
    neck — so a range ending at 123 cut a model in half.
    """
    guitar = next(m for m in omap["models"] if m["id"] == "instrument_guitar")
    assert guitar["pages"] == [114, 125]
    assert guitar["pages"][0] <= 124 <= guitar["pages"][1]


def test_the_mic_and_keyboard_absorb_part_1s_unresolved_spans(omap: dict):
    mic = next(m for m in omap["models"] if m["id"] == "mic")
    kbd = next(m for m in omap["models"] if m["id"] == "instrument_keyboard")
    assert mic["pages"] == [66, 88]      # was 66-72 with 73-88 unresolved
    assert kbd["pages"] == [89, 101]     # was 89-95 with 96-101 unresolved


def test_every_model_id_is_a_frozen_canonical_id(omap: dict):
    for m in omap["models"]:
        ids = m.get("instances", [m["id"]])
        for i in ids:
            assert i in S3_BUILDABLE_OBJECTS, f"{i} is not in the frozen §5.3 table"


def test_every_model_carries_identification_evidence(omap: dict):
    for m in omap["models"]:
        assert m["evidence"].strip(), m["id"]
        assert m["confidence"] in {"high", "medium", "low"}, m["id"]


def test_all_sixteen_objects_are_mapped_and_nothing_is_unresolved(omap: dict):
    """The headline result of part 3: no span is left unexplained."""
    identified = set()
    for m in omap["models"]:
        identified.update(m.get("instances", [m["id"]]))
    assert identified == S3_BUILDABLE_OBJECTS
    assert "unresolved" not in omap, "part 3 closed every unresolved span"


# --------------------------------------------------------------------------- #
# ADR-018 — sub-assemblies are not objects
# --------------------------------------------------------------------------- #


def test_subassemblies_never_claim_a_canonical_id(omap: dict):
    for s in omap["subassemblies"]:
        assert s["id"] not in S3_BUILDABLE_OBJECTS, s["id"]
        assert s["evidence"].strip(), s["id"]


def test_every_subassembly_sits_inside_the_model_it_names(omap: dict):
    models = {m["id"]: m["pages"] for m in omap["models"]}
    for s in omap["subassemblies"]:
        lo, hi = s["pages"]
        parent = models[s["inside"]]
        assert parent[0] <= lo and hi <= parent[1], \
            f"{s['id']} {s['pages']} escapes {s['inside']} {parent}"


# --------------------------------------------------------------------------- #
# The honesty guards
# --------------------------------------------------------------------------- #


def test_dimensions_record_the_method_and_its_calibration(omap: dict):
    dims = omap["dimensions"]
    assert dims["rejected_because"].strip()
    assert dims["method_used"].strip()
    assert dims["stud_count_coverage"].strip()
    assert "31 of 31" in dims["shape_transfer_calibration"]


def test_every_base_carries_evidence_and_both_extents(omap: dict):
    """No bare numbers: a base states contact, projection and how it was read."""
    for m in omap["models"]:
        base = m.get("base")
        if base is None:
            continue
        assert len(base["contact_studs"]) == 2, m["id"]
        assert len(base["projection_studs"]) == 2, m["id"]
        assert base["evidence"].strip(), m["id"]
        assert isinstance(base["overhang_height_mm"], float), m["id"]


def test_a_pending_footprint_says_WHY_and_bounds_itself(omap: dict):
    """An unmeasured footprint must name its failure mode, not just be absent."""
    for m in omap["models"]:
        pending = m.get("footprint_pending")
        if pending is None:
            continue
        assert pending["reason"] == "open_frame"
        assert pending["fitted_extent_is_a_bound"] is True
        assert "UPPER BOUND" in pending["bound_note"]
        # the distinction from the note base's failure mode must be explicit
        assert "occlusion" in pending["why_the_self_check_cannot_apply"]


def test_scoring_relevance_partitions_all_sixteen_objects(omap: dict):
    """S1 scores four objects for NOT moving; they need no containment footprint."""
    s = omap["scoring_relevance"]
    both = set(s["needs_containment"]) | set(s["scored_by_not_moving"])
    assert both == S3_BUILDABLE_OBJECTS
    assert not set(s["needs_containment"]) & set(s["scored_by_not_moving"])
    assert set(s["scored_by_not_moving"]) == {"clef", "amp", "speaker_a", "speaker_b"}


def test_congas_pair_separation_is_not_invented(omap: dict):
    pair = omap["congas_pair_extent"]
    assert pair["pair_separation"] == "NOT MEASURED"
    assert pair["per_drum_contact_mm"] == [32.0, 32.0]
    assert "393.809" in pair["blocks_nothing_because"]


# --------------------------------------------------------------------------- #
# The cable orientation constraint
# --------------------------------------------------------------------------- #


def test_cable_orientation_arithmetic_is_self_consistent(omap: dict):
    c = omap["cable_orientation"]
    assert c["cable_length_mm"] == c["cable_length_studs"] * omap["meta"]["stud_pitch_mm"]
    assert c["fits_along_long_axis"] is True
    assert c["fits_across_short_axis"] is False
    assert c["slack_per_end_along_long_axis_mm"] == pytest.approx(
        (c["area_long_axis_mm"] - c["cable_length_mm"]) / 2, abs=0.01)
    assert c["slack_per_side_across_short_axis_mm"] == pytest.approx(
        (c["area_short_axis_mm"] - c["cable_width_mm"]) / 2, abs=0.01)
    assert c["binding_slack_mm"] == pytest.approx(
        min(c["slack_per_end_along_long_axis_mm"],
            c["slack_per_side_across_short_axis_mm"]), abs=0.01)
    assert c["deficit_across_short_axis_mm"] == pytest.approx(
        c["area_short_axis_mm"] - c["cable_length_mm"], abs=0.01)
    assert c["deficit_across_short_axis_mm"] < 0, "the point: it does NOT fit across"


def test_cable_area_figures_come_from_the_POLYGON_not_the_bbox(omap: dict):
    """The correction that ab07e75 needed.

    A rotated rectangle's axis-aligned bounding box is strictly larger than the
    rectangle. Reading ``bbox_mm`` as the area overstated the cable area's short
    axis by 34.77 mm and its slack by 13.09 mm — in the flattering direction.
    """
    import json
    import math
    spec = json.loads(FIELD_SPEC.read_text())
    c = omap["cable_orientation"]
    for area, expected_angle in (("cable_area_upper", c["area_angle_upper_deg"]),
                                 ("cable_area_lower", c["area_angle_lower_deg"])):
        poly = spec["areas"][area]["polygon_visible_mm"]
        edges = [(poly[(i + 1) % len(poly)][0] - poly[i][0],
                  poly[(i + 1) % len(poly)][1] - poly[i][1]) for i in range(len(poly))]
        lengths = sorted(math.hypot(*e) for e in edges)
        assert lengths[0] == pytest.approx(c["area_short_axis_mm"], abs=0.01), area
        assert lengths[-1] == pytest.approx(c["area_long_axis_mm"], abs=0.01), area

        longest = max(edges, key=lambda e: math.hypot(*e))
        angle = math.degrees(math.atan2(longest[1], longest[0])) % 180.0
        assert angle == pytest.approx(expected_angle, abs=0.01), area

        # and the bbox must NOT be mistakable for the area
        b = spec["areas"][area]["bbox_mm"]
        assert (b[2] - b[0]) > c["area_short_axis_mm"] + 30.0, \
            f"{area}: the bbox is much wider than the area — that is the trap"

    assert omap["cable_orientation"]["areas_are_axis_aligned"] is False


def test_the_cable_correction_is_recorded_not_overwritten(omap: dict):
    """The superseded figures stay on the record with their root cause."""
    fix = omap["cable_orientation"]["correction_2026_07_27"]
    assert "ab07e75" in fix["supersedes"]
    assert "114.47" in fix["was"]
    assert "bbox_mm" in fix["root_cause"]
    assert "OVERSTATED" in fix["direction_of_error"]


# --------------------------------------------------------------------------- #
# A7 — unchanged by part 3, and still cross-checked against S5
# --------------------------------------------------------------------------- #


def test_a7_inference_is_kept_but_marked_superseded(omap: dict):
    assert "inference" in omap["a7_inference"]["confidence"].lower()
    a7m = omap["a7_measurement"]
    assert a7m["confidence"] == "MEASURED(S3)"
    assert "a7_inference" in a7m["supersedes"]


def test_a7_measurement_records_BOTH_readings(omap: dict):
    """Contact and silhouette give different slack; both must be present."""
    a7 = omap["a7_measurement"]
    pitch = omap["meta"]["stud_pitch_mm"]
    assert a7["note_contact_footprint_mm"] == [a7["note_contact_footprint_studs"][0]*pitch,
                                              a7["note_contact_footprint_studs"][1]*pitch]
    assert a7["note_max_projection_mm"] == [a7["note_max_projection_studs"][0]*pitch,
                                            a7["note_max_projection_studs"][1]*pitch]
    tgt = a7["note_target_mm"]
    assert a7["slack_per_side_contact_mm"] == pytest.approx(
        (tgt - a7["note_contact_footprint_mm"][1])/2, abs=0.01)
    assert a7["slack_per_side_projection_mm"] == pytest.approx(
        (tgt - a7["note_max_projection_mm"][1])/2, abs=0.01)
    assert a7["slack_per_side_projection_mm"] > 0, "the silhouette must fit too"


def test_a7_arithmetic_is_self_consistent(omap: dict):
    a7 = omap["a7_inference"]
    pitch = omap["meta"]["stud_pitch_mm"]
    assert a7["note_target_studs"] == pytest.approx(a7["note_target_mm"] / pitch, abs=1e-2)
    assert a7["note_start_square_studs"] == pytest.approx(
        a7["note_start_square_mm"] / pitch, abs=1e-2
    )
    expected = (a7["note_target_mm"] - a7["inferred_note_base_studs"] * pitch) / 2
    assert a7["inferred_slack_per_side_mm"] == pytest.approx(expected, abs=1e-2)


def test_a7_numbers_agree_with_field_spec(omap: dict):
    """Cross-source: the mat figures must match S5, not be retyped."""
    import json
    spec = json.loads(FIELD_SPEC.read_text())
    target = spec["areas"]["note_target_yellow"]["bbox_mm"]
    width = target[2] - target[0]
    assert omap["a7_inference"]["note_target_mm"] == pytest.approx(width, abs=1e-2)
    start = spec["note_starts"]["note_start_rand_0"]["size_mm"]
    assert omap["a7_inference"]["note_start_square_mm"] == pytest.approx(start[0], abs=1e-2)
