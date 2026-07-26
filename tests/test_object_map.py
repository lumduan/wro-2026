"""Invariants on docs/object_map.toml (Phase 4, part 1).

Phase 4 is deliberately split: this file records **which S3 pages build which
object**, verified; per-object dimensions are pending a second pass. The tests
below guard that split honestly — in particular that no dimension appears before
it has a source, and that unresolved models stay unresolved rather than drifting
into a canonical ID.
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


def test_step_numbering_is_recorded_as_continuous(omap: dict):
    """The planned boundary signal does not exist; the record must say so."""
    s = omap["structure"]
    assert s["step_numbering"] == "continuous"
    assert s["resets"] is False


def test_every_model_page_range_is_inside_the_build_pages(omap: dict):
    for m in omap["models"]:
        lo, hi = m["pages"]
        assert 2 <= lo <= hi <= 177, m["id"]
        assert m["steps"] == [lo - 1, hi - 1], f"{m['id']}: steps must be page-1"


def test_model_and_unresolved_ranges_do_not_overlap(omap: dict):
    spans = [tuple(m["pages"]) for m in omap["models"]]
    spans += [tuple(u["pages"]) for u in omap["unresolved"]]
    spans.sort()
    for (a_lo, a_hi), (b_lo, b_hi) in zip(spans, spans[1:]):
        assert a_hi < b_lo, f"page ranges overlap: {(a_lo,a_hi)} and {(b_lo,b_hi)}"


def test_every_model_id_is_a_frozen_canonical_id(omap: dict):
    for m in omap["models"]:
        ids = m.get("instances", [m["id"]])
        for i in ids:
            assert i in S3_BUILDABLE_OBJECTS, f"{i} is not in the frozen §5.3 table"


def test_every_model_carries_identification_evidence(omap: dict):
    for m in omap["models"]:
        assert m["evidence"].strip(), m["id"]
        assert m["confidence"] in {"high", "medium", "low"}, m["id"]


def test_all_six_notes_and_the_clef_are_identified(omap: dict):
    """The notes carry 120 of 255 points; the clef is a bonus object."""
    ids = {m["id"] for m in omap["models"]}
    for colour in ("red", "blue", "green", "yellow", "white", "black"):
        assert f"note_{colour}" in ids
    assert "clef" in ids


def test_unresolved_models_are_not_assigned_a_canonical_id(omap: dict):
    """Same discipline as unassigned_marker_{1..4}: an empty slot beats a wrong one."""
    for u in omap["unresolved"]:
        assert "id" not in u, f"unresolved span {u['pages']} must not claim an ID"
        assert u["candidates"] and u["note"].strip()


def test_objects_not_yet_identified_are_accounted_for(omap: dict):
    """Whatever is missing must be listed as a candidate somewhere, not forgotten."""
    identified = set()
    for m in omap["models"]:
        identified.update(m.get("instances", [m["id"]]))
    missing = S3_BUILDABLE_OBJECTS - identified
    candidates = {c for u in omap["unresolved"] for c in u["candidates"]}
    assert missing <= candidates, f"unaccounted objects: {sorted(missing - candidates)}"


# --------------------------------------------------------------------------- #
# The honesty guards
# --------------------------------------------------------------------------- #


def test_no_dimensions_are_recorded_yet(omap: dict):
    """Guards against a plausible-looking footprint appearing without a source.

    The planned method (counting studs on the assembly render) was tested and
    rejected because the base is occluded by the object's own body. Until the
    parts-callout pass runs, this file must carry no dimension.
    """
    assert omap["dimensions"]["status"] == "pending"
    assert omap["dimensions"]["rejected_because"].strip()
    assert omap["dimensions"]["replacement_method"].strip()
    for m in omap["models"]:
        for key in m:
            assert "footprint" not in key and "height" not in key, (
                f"{m['id']} carries a dimension before the dimension pass has run"
            )


def test_a7_is_labelled_an_inference_not_a_measurement(omap: dict):
    """It is derived from S2's mat geometry, not measured from S3's objects."""
    a7 = omap["a7_inference"]
    assert "inference" in a7["confidence"].lower()
    assert "NOT a measurement" in a7["confidence"]


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
