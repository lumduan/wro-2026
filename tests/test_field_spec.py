"""Invariants on data/field_spec.json (S5).

S5 is the single source of truth every future module reads, so these are not
smoke tests — each one guards a specific way the spec could be wrong while still
looking entirely plausible.

Two deliberate design points:

* Shoelace is **recomputed here**, independently. Calling the builder's own
  function would compare the builder against itself and prove nothing.
* Invariants name **which polygon** they run on. ``polygon_constructed_mm`` is
  pre-clip and comparable to the dump; ``polygon_visible_mm`` is what is actually
  painted. ``stage`` legitimately overruns the mat box, so containment is asserted
  only for scoring areas (ADR-013, and EXTRACTION_REPORT §2 for why).
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "data" / "field_spec.json"
AREA_MAP = ROOT / "docs" / "area_map.toml"

MAT_W = 2361.999
MAT_H = 1143.0

#: CLAUDE.md §5.3, frozen by ADR-012.
OBJECT_IDS = {
    "cable_upper", "cable_lower", "mic",
    "instrument_guitar", "instrument_keyboard", "instrument_congas",
    "note_red", "note_blue", "note_green", "note_yellow", "note_white", "note_black",
    "clef", "amp", "speaker_a", "speaker_b", "robot",
}
AREA_IDS = {
    "start_area", "cable_area_upper", "cable_area_lower", "mic_target", "backstage",
    *(f"note_target_{c}" for c in ("red", "blue", "green", "yellow", "white", "black")),
    *(f"unassigned_marker_{i}" for i in (1, 2, 3, 4)),
    "stage", "plaza",
}
NOTE_START_IDS = {
    *(f"note_start_rand_{i}" for i in range(4)),
    "note_start_fixed_red", "note_start_fixed_green",
}


def shoelace(points) -> float:
    """Independent reimplementation — never import the builder's version."""
    total = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


@pytest.fixture(scope="module")
def spec() -> dict:
    return json.loads(SPEC.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def areas(spec: dict) -> dict:
    return spec["areas"]


# --------------------------------------------------------------------------- #
# Coverage of the frozen ID tables (ADR-012)
# --------------------------------------------------------------------------- #


def test_every_frozen_area_id_resolves(areas: dict, spec: dict):
    """ADR-012 froze the AREA table too; only the object side was guarded before."""
    resolved = set(areas) | set(spec["start_groups"])
    missing = AREA_IDS - resolved
    assert not missing, f"§5.3 area IDs absent from the spec: {sorted(missing)}"


def test_every_frozen_object_id_resolves(spec: dict):
    """ADR-014: a measured start square, a randomized slot set, or nominal+tolerance."""
    poses = spec["object_start_poses"]
    missing = OBJECT_IDS - set(poses)
    assert not missing, f"§5.3 object IDs absent from object_start_poses: {sorted(missing)}"
    for name, pose in poses.items():
        assert pose["kind"] in {"measured", "randomized", "nominal_pending", "start_area"}, name


def test_objects_without_a_marker_are_flagged_not_invented(spec: dict):
    """No coordinate is fabricated for an object the mat does not mark."""
    for name, pose in spec["object_start_poses"].items():
        if pose["kind"] == "nominal_pending":
            assert pose["nominal_start_pose_mm"] is None
            assert pose["needs_measurement"] is True


def test_unassigned_markers_present_and_non_scoring(areas: dict):
    for i in (1, 2, 3, 4):
        marker = areas[f"unassigned_marker_{i}"]
        assert marker["scoring"] is False


def test_truck_is_a_start_group_with_no_polygon_and_no_poses(spec: dict):
    """ADR-015 sub-decision; ADR-014 keeps poses in exactly one place."""
    truck = spec["start_groups"]["truck"]
    assert truck["kind"] == "start_group"
    assert "polygon_constructed_mm" not in truck and "polygon_visible_mm" not in truck
    assert set(truck["members"]) == {
        "mic", "instrument_guitar", "instrument_keyboard", "instrument_congas"
    }
    # membership only - never poses
    assert not any("pose" in k or "_mm" in k for k in truck)


# --------------------------------------------------------------------------- #
# Schema shape (ADR-013)
# --------------------------------------------------------------------------- #


def test_scoring_is_explicit_on_every_area(areas: dict):
    for name, area in areas.items():
        assert isinstance(area.get("scoring"), bool), f"{name}: scoring not explicit"


def test_polygon_mm_never_appears(spec: dict):
    """A conditional field breaks every invariant that names it."""
    blob = json.dumps(spec)
    assert '"polygon_mm"' not in blob


def test_both_polygon_fields_always_present(areas: dict):
    for name, area in areas.items():
        has_single = "polygon_constructed_mm" in area
        has_multi = "polygons_constructed_mm" in area
        assert has_single or has_multi, f"{name}: no constructed polygon"
        if has_single:
            assert "polygon_visible_mm" in area, f"{name}: missing visible polygon"
        else:
            assert "polygons_visible_mm" in area, f"{name}: missing visible polygons"
        assert isinstance(area["clip_divergent"], bool)


def test_exactly_ten_scoring_areas_six_of_them_note_targets(areas: dict):
    scoring = [n for n, a in areas.items() if a["scoring"]]
    assert len(scoring) == 10, sorted(scoring)
    assert sum(1 for n in scoring if n.startswith("note_target_")) == 6


def test_stage_and_plaza_are_not_scoring(areas: dict):
    """If they were, ADR-013's predicate would make nothing scoreable anywhere."""
    assert areas["stage"]["scoring"] is False
    assert areas["plaza"]["scoring"] is False


def test_start_area_is_explicitly_non_scoring(areas: dict):
    assert areas["start_area"]["scoring"] is False


# --------------------------------------------------------------------------- #
# Geometry — each invariant names its polygon
# --------------------------------------------------------------------------- #


def test_visible_scoring_polygons_are_inside_the_mat(areas: dict):
    for name, area in areas.items():
        if not area["scoring"]:
            continue
        for x, y in area["polygon_visible_mm"]:
            assert -1e-6 <= x <= MAT_W + 1e-6, f"{name}: x={x}"
            assert -1e-6 <= y <= MAT_H + 1e-6, f"{name}: y={y}"


def test_non_scoring_areas_only_have_to_OVERLAP_the_mat(areas: dict):
    """Containment is NOT asserted: `stage` runs to x0=-13.169, y1=1182.364.

    PDF artwork legitimately extends past the trim and is clipped at render time
    (EXTRACTION_REPORT §2). A containment test would go red on a correct spec, and
    the cheapest fix would be deleting `stage` - which would undo ADR-013.
    """
    for name, area in areas.items():
        if area["scoring"]:
            continue
        x0, y0, x1, y1 = area["bbox_mm"]
        assert x1 > 0 and y1 > 0 and x0 < MAT_W and y0 < MAT_H, f"{name} does not overlap"


def test_stage_really_does_overrun_the_trim(areas: dict):
    """Pins the reason the previous test is written the way it is."""
    x0, _y0, _x1, y1 = areas["stage"]["bbox_mm"]
    assert x0 < 0 and y1 > MAT_H


def test_no_two_scoring_areas_overlap(areas: dict):
    scoring = [(n, a["bbox_mm"]) for n, a in areas.items() if a["scoring"]]
    for i, (na, a) in enumerate(scoring):
        for nb, b in scoring[i + 1:]:
            disjoint = a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]
            assert disjoint, f"{na} overlaps {nb}"


def test_area_equals_independently_recomputed_shoelace(areas: dict):
    """Recomputed HERE, not by calling the builder's own function."""
    for name, area in areas.items():
        if "polygon_constructed_mm" not in area:
            continue
        got = shoelace([tuple(p) for p in area["polygon_constructed_mm"]])
        assert got == pytest.approx(area["area_mm2"], abs=5e-4), name


def test_dump_cross_check_is_within_its_derived_bound(areas: dict):
    """The ONLY check comparing S5 against the extraction toolchain.

    The bound is derived from --precision (ADR-008), never chosen: each emitted
    coordinate carries at most 0.5e-precision of error, so the shoelace residue is
    bounded by that times the perimeter.
    """
    checked = 0
    for name, area in areas.items():
        if "dump_area_mm2" not in area:
            continue
        checked += 1
        assert area["dump_area_delta_mm2"] <= area["dump_area_bound_mm2"], (
            f"{name}: |spec - dump| = {area['dump_area_delta_mm2']} exceeds "
            f"bound {area['dump_area_bound_mm2']}"
        )
    assert checked >= 8, "cross-check ran on too few areas to be meaningful"


def test_rectangles_have_area_exactly_width_times_height(areas: dict):
    """Exact only because both sides derive from the same ROUNDED coordinates."""
    for name, area in areas.items():
        poly = area.get("polygon_constructed_mm")
        if not poly or len(poly) != 4:
            continue
        xs = {p[0] for p in poly}
        ys = {p[1] for p in poly}
        if len(xs) != 2 or len(ys) != 2:
            continue  # not axis-aligned; the cable quads land here
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        assert round(w * h, 3) == pytest.approx(area["area_mm2"], abs=1e-9), name


# --------------------------------------------------------------------------- #
# The specific findings this session made
# --------------------------------------------------------------------------- #


def test_backstage_is_the_inset_not_the_pink_fill(areas: dict):
    """S1 p11 excludes the grey border; the pink fill INCLUDES it.

    Guards 45 points: an instrument on the 6.3 mm band would otherwise score 15.
    """
    backstage = areas["backstage"]
    assert backstage["bbox_mm"] == pytest.approx([0.0, 0.0, 393.809, 317.219], abs=1e-3)
    assert backstage["area_mm2"] == pytest.approx(124923.697, abs=1e-2)
    # and emphatically NOT the fill's own extent
    assert backstage["bbox_mm"][2] < 400.135
    assert backstage["selector"]["inset_by"] == "#d6d0cc"


def test_start_area_matches_the_robot_envelope(areas: dict):
    """MEASURED 250.02 x 250.02 - an EQUALITY, because the slack is ~zero.

    `>= 250` would test nothing and would pass silently if the selector grabbed
    something larger.
    """
    x0, y0, x1, y1 = areas["start_area"]["bbox_mm"]
    assert (x1 - x0) == pytest.approx(250.02, abs=0.01)
    assert (y1 - y0) == pytest.approx(250.02, abs=0.01)
    assert areas["start_area"]["needs_verify"] == "S6-startarea"


def test_note_targets_include_the_grey_border(areas: dict):
    """S1 p11: the target area INCLUDES the border, so it is the 79.7 mm square."""
    for colour in ("red", "blue", "green", "yellow", "white", "black"):
        area = areas[f"note_target_{colour}"]
        x0, y0, x1, y1 = area["bbox_mm"]
        assert (x1 - x0) == pytest.approx(79.7, abs=0.01)
        assert (y1 - y0) == pytest.approx(79.7, abs=0.01)
        assert area["selector"]["includes_grey_border"] is True


def test_cable_areas_are_quadrilaterals_not_rectangles(areas: dict):
    """A bbox would overstate each cable target by ~34 %."""
    for name in ("cable_area_upper", "cable_area_lower"):
        area = areas[name]
        x0, y0, x1, y1 = area["bbox_mm"]
        assert area["area_mm2"] < 0.75 * (x1 - x0) * (y1 - y0)


def test_only_backstage_has_a_detected_border(areas: dict):
    """The border signature, run over every scoring area (Gate 3 generalized)."""
    with_border = [n for n, a in areas.items() if a.get("border_detected")]
    assert with_border == ["backstage"], with_border
    assert areas["backstage"]["border_detected"]["handled_by_inset"] is True


# --------------------------------------------------------------------------- #
# Randomization
# --------------------------------------------------------------------------- #


def test_six_note_starts_four_randomizable_twentyfour_permutations(spec: dict):
    starts = spec["note_starts"]
    assert set(starts) == NOTE_START_IDS
    assert sum(1 for s in starts.values() if s["randomizable"]) == 4
    assert spec["randomization"]["permutations"] == 24


def test_fixed_start_colour_matches_its_target_colour(spec: dict):
    """A cross-source consistency check: S2 fills must agree with S1's semantics."""
    pairs = {"note_start_fixed_red": "#c92027", "note_start_fixed_green": "#1f7941"}
    for start_id, fill in pairs.items():
        assert spec["note_starts"][start_id]["fill_hex"] == fill
    inner = {n: a["selector"].get("inner_fill") for n, a in spec["areas"].items()}
    assert inner["note_target_red"] == pairs["note_start_fixed_red"]
    assert inner["note_target_green"] == pairs["note_start_fixed_green"]


# --------------------------------------------------------------------------- #
# Provenance
# --------------------------------------------------------------------------- #


def test_provenance_pins_the_whole_chain(spec: dict):
    prov = spec["provenance"]
    for key in (
        "s2_sha256",
        "drawings_json_sha256",
        "start_area_sidecar_sha256",  # start_area comes from a gitignored sidecar
        "extraction_argv",
        "extraction_precision",
        "output_precision",
    ):
        assert prov.get(key), f"provenance missing {key}"
    assert len(prov["s2_sha256"]) == 64
    assert len(prov["start_area_sidecar_sha256"]) == 64


def test_table_block_records_the_registration_datum(spec: dict):
    table = spec["table"]
    assert table["tolerance_mm"] == 5.0
    assert table["wall_height_mm"] == 50.0
    assert table["registration"] == {"x": "right_wall", "y": "centred"}


def test_mat_dimensions_match_the_measured_trimbox(spec: dict):
    assert spec["mat"]["width_mm"] == pytest.approx(MAT_W, abs=1e-3)
    assert spec["mat"]["height_mm"] == pytest.approx(MAT_H, abs=1e-3)
    assert spec["mat"]["box_source"] == "TrimBox"


# --------------------------------------------------------------------------- #
# The area map itself
# --------------------------------------------------------------------------- #


def test_area_map_declares_scoring_on_every_area():
    amap = tomllib.loads(AREA_MAP.read_text(encoding="utf-8"))
    for name, entry in amap["areas"].items():
        assert "scoring" in entry, f"{name}: area_map does not declare scoring"


def test_union_selectors_declare_expect_paths():
    """A bare union silently absorbs any path added later (ADR-015)."""
    amap = tomllib.loads(AREA_MAP.read_text(encoding="utf-8"))
    for name, entry in amap["areas"].items():
        if entry.get("match") == "union":
            assert "expect_paths" in entry, f"{name}: union without expect_paths"


def test_start_pose_ingestion_is_wired_but_carries_nothing_yet():
    """Work order B0 lands measured poses in area_map.toml.

    Ten objects are `nominal_pending` and measurable. The four randomized notes
    are NOT a gap: S1 p7 assigns them at randomization, so they have no fixed
    start pose to measure and never will.
    """
    import json
    spec = json.loads((ROOT / "data" / "field_spec.json").read_text())
    poses = spec["object_start_poses"]
    kinds: dict[str, list[str]] = {}
    for object_id, entry in poses.items():
        kinds.setdefault(entry["kind"], []).append(object_id)

    assert len(kinds["nominal_pending"]) == 10
    assert sorted(kinds["randomized"]) == [
        "note_black", "note_blue", "note_white", "note_yellow"]
    assert sorted(kinds["measured"]) == ["note_green", "note_red"]

    for object_id in kinds["nominal_pending"]:
        entry = poses[object_id]
        assert entry["nominal_start_pose_mm"] is None, object_id
        assert entry["needs_measurement"] is True, object_id
        assert "B0" in entry["note"], "the note must point at the work-order item"
