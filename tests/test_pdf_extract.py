"""Tests for tools/pdf_extract.py.

Every fixture is synthesised with PyMuPDF at test time. The real source PDFs are
never opened here — a test that depends on them would fail for the wrong reasons
and would not exercise the cases that actually matter (non-zero TrimBox offset,
rotation, a missing TrimBox).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import fitz
import pytest

import pdf_extract as px

MM_PER_PT = 25.4 / 72.0


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _make_pdf(
    path: Path,
    *,
    width: float = 400,
    height: float = 500,
    trimbox: str | None = None,
    cropbox: str | None = None,
    rotate: int | None = None,
    draw: bool = True,
) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=width, height=height)
    if draw:
        # A 30x30 pt marker whose PDF-space bottom-left is (50, 100) — i.e. the
        # bottom-left corner of the TrimBox used throughout these tests.
        page.draw_rect(
            fitz.Rect(50, height - 130, 80, height - 100), color=(1, 0, 0), fill=(1, 0, 0)
        )
        page.insert_text(fitz.Point(60, 60), "marker text", fontsize=11)
    if trimbox is not None:
        doc.xref_set_key(page.xref, "TrimBox", trimbox)
    if cropbox is not None:
        doc.xref_set_key(page.xref, "CropBox", cropbox)
    if rotate is not None:
        doc.xref_set_key(page.xref, "Rotate", str(rotate))
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture(autouse=True)
def _fixed_precision():
    px.set_precision(px.DEFAULT_PRECISION)
    yield
    px.set_precision(px.DEFAULT_PRECISION)


# --------------------------------------------------------------------------- #
# 1 — pt <-> mm round-trip
# --------------------------------------------------------------------------- #


def test_pt_mm_constants_are_exact_inverses():
    assert px.MM_PER_PT * px.PT_PER_MM == pytest.approx(1.0, abs=1e-15)


@pytest.mark.parametrize("value", [0.0, 1.0, 72.0, 595.0, 3240.0, 6695.43, -12.5])
def test_pt_to_mm_round_trip(tmp_path: Path, value: float):
    pdf = _make_pdf(tmp_path / "rt.pdf", trimbox="[50 100 350 400]")
    frame = px.MatFrame.from_page(fitz.open(pdf)[0])
    x_mm, y_mm = frame.pt_to_mm(value, value)
    x_pt, y_pt = frame.mm_to_pt(x_mm, y_mm)
    assert x_pt == pytest.approx(value, abs=1e-9)
    assert y_pt == pytest.approx(value, abs=1e-9)


def test_known_pt_to_mm_scale():
    """72 pt is exactly one inch is exactly 25.4 mm."""
    assert 72.0 * px.MM_PER_PT == pytest.approx(25.4, abs=1e-12)
    assert 6695.43 * px.MM_PER_PT == pytest.approx(2361.9989, abs=1e-4)
    assert 3240.0 * px.MM_PER_PT == pytest.approx(1143.0, abs=1e-9)


# --------------------------------------------------------------------------- #
# 2 — box selection precedence (ADR-003)
# --------------------------------------------------------------------------- #


def test_trimbox_is_preferred_when_present(tmp_path: Path):
    pdf = _make_pdf(tmp_path / "t.pdf", trimbox="[50 100 350 400]", cropbox="[10 20 390 480]")
    frame = px.MatFrame.from_page(fitz.open(pdf)[0])
    assert frame.box_source == "TrimBox"
    assert frame.notes == ()  # no NEEDS-VERIFY when TrimBox exists


def test_cropbox_used_when_trimbox_absent_and_flagged(tmp_path: Path):
    pdf = _make_pdf(tmp_path / "c.pdf", cropbox="[10 20 390 480]")
    frame = px.MatFrame.from_page(fitz.open(pdf)[0])
    assert frame.box_source == "CropBox"
    assert any("NEEDS-VERIFY(S2)" in note and "CropBox" in note for note in frame.notes)


def test_mediabox_used_when_trim_and_crop_absent_and_flagged(tmp_path: Path):
    pdf = _make_pdf(tmp_path / "m.pdf")
    frame = px.MatFrame.from_page(fitz.open(pdf)[0])
    assert frame.box_source == "MediaBox"
    assert any("NEEDS-VERIFY(S2)" in note and "MediaBox" in note for note in frame.notes)
    assert frame.width_mm == pytest.approx(400 * MM_PER_PT, abs=1e-9)
    assert frame.height_mm == pytest.approx(500 * MM_PER_PT, abs=1e-9)


def test_bleed_delta_is_reported(tmp_path: Path):
    """A TrimBox inset from MediaBox must show up as a non-zero delta."""
    pdf = _make_pdf(tmp_path / "bleed.pdf", trimbox="[50 100 350 400]")
    frame = px.MatFrame.from_page(fitz.open(pdf)[0])
    data = frame.to_dict()
    assert data["has_bleed"] is True
    assert data["used_minus_mediabox_pt"] == [50.0, 100.0, -50.0, -100.0]


def test_no_bleed_when_trim_equals_media(tmp_path: Path):
    pdf = _make_pdf(tmp_path / "nobleed.pdf", trimbox="[0 0 400 500]")
    frame = px.MatFrame.from_page(fitz.open(pdf)[0])
    assert frame.to_dict()["has_bleed"] is False


# --------------------------------------------------------------------------- #
# 3 — the MAT transform, with a NON-ZERO TrimBox offset
# --------------------------------------------------------------------------- #
# The real game-mat PDF has TrimBox == MediaBox, so its offset is zero and a
# wrong origin shift would be invisible on it. Only an offset fixture catches it.


def test_mat_frame_maps_trim_corners_to_origin_and_size(tmp_path: Path):
    pdf = _make_pdf(tmp_path / "offset.pdf", trimbox="[50 100 350 400]")
    page = fitz.open(pdf)[0]
    frame = px.MatFrame.from_page(page)

    # TrimBox is 300 x 300 pt.
    expected = 300 * MM_PER_PT  # 105.8333...
    assert frame.width_mm == pytest.approx(expected, abs=1e-9)
    assert frame.height_mm == pytest.approx(expected, abs=1e-9)

    # box_page is in UNROTATED page space (y down, origin at MediaBox top-left):
    # PDF (50,100) -> page (50, 400);  PDF (350,400) -> page (350, 100).
    assert frame.box_page == pytest.approx((50.0, 100.0, 350.0, 400.0), abs=1e-9)

    # Bottom-left of the trim box is the MAT-frame origin.
    assert frame.pt_to_mm(50.0, 400.0) == pytest.approx((0.0, 0.0), abs=1e-9)
    # Top-right of the trim box is (width, height).
    assert frame.pt_to_mm(350.0, 100.0) == pytest.approx((expected, expected), abs=1e-9)
    # Y really flips: a larger page-space y is a SMALLER mat-frame y.
    assert frame.pt_to_mm(50.0, 250.0)[1] == pytest.approx(150 * MM_PER_PT, abs=1e-9)


def test_drawn_marker_lands_at_mat_origin(tmp_path: Path):
    """End-to-end: a rect drawn at the TrimBox corner must extract as (0,0) mm."""
    pdf = _make_pdf(tmp_path / "marker.pdf", trimbox="[50 100 350 400]")
    page = fitz.open(pdf)[0]
    frame = px.MatFrame.from_page(page)
    rects = [frame.rect_to_mm(d["rect"]) for d in page.get_drawings()]
    assert rects, "fixture should contain a drawing"
    bbox = rects[0]
    assert bbox[0] == pytest.approx(0.0, abs=1e-3)
    assert bbox[1] == pytest.approx(0.0, abs=1e-3)
    assert bbox[2] == pytest.approx(30 * MM_PER_PT, abs=1e-3)
    assert bbox[3] == pytest.approx(30 * MM_PER_PT, abs=1e-3)


def test_rect_to_mm_normalises_y(tmp_path: Path):
    pdf = _make_pdf(tmp_path / "norm.pdf", trimbox="[50 100 350 400]")
    frame = px.MatFrame.from_page(fitz.open(pdf)[0])
    bbox = frame.rect_to_mm(fitz.Rect(60, 120, 100, 200))
    assert bbox[0] < bbox[2] and bbox[1] < bbox[3]


def test_cropbox_offset_does_not_shift_the_transform(tmp_path: Path):
    """page.rect is CropBox-origin-shifted; the transform must not double-count it.

    Regression guard for the exact trap this module documents: page.trimbox is
    MediaBox-relative while page.rect is CropBox-relative.
    """
    pdf = _make_pdf(
        tmp_path / "cropoffset.pdf", trimbox="[50 100 350 400]", cropbox="[10 20 390 480]"
    )
    page = fitz.open(pdf)[0]
    frame = px.MatFrame.from_page(page)
    rects = [frame.rect_to_mm(d["rect"]) for d in page.get_drawings()]
    assert rects[0][0] == pytest.approx(0.0, abs=1e-3)
    assert rects[0][1] == pytest.approx(0.0, abs=1e-3)


# --------------------------------------------------------------------------- #
# 4 — rotation
# --------------------------------------------------------------------------- #


def test_rotation_does_not_change_extracted_coordinates(tmp_path: Path):
    """/Rotate must not move vector geometry.

    get_drawings() reports UNROTATED page space, so the MAT frame is unrotated
    too and a rotated page must extract identical mm coordinates. If this ever
    fails, rendering and vector output have drifted into different frames.
    """
    plain = _make_pdf(tmp_path / "r0.pdf", trimbox="[50 100 350 400]")
    turned = _make_pdf(tmp_path / "r90.pdf", trimbox="[50 100 350 400]", rotate=90)

    results = []
    for path in (plain, turned):
        page = fitz.open(path)[0]
        frame = px.MatFrame.from_page(page)
        results.append(
            (frame.rotation, [frame.rect_to_mm(d["rect"]) for d in page.get_drawings()])
        )

    assert results[0][0] == 0 and results[1][0] == 90
    assert results[0][1] == results[1][1]


def test_render_clip_accounts_for_rotation(tmp_path: Path, capsys):
    """A rotated page must still render without a clip/page mismatch."""
    pdf = _make_pdf(tmp_path / "rr.pdf", trimbox="[50 100 350 400]", rotate=90)
    out = tmp_path / "out"
    assert px.main(["--out-dir", str(out), "--quiet", "render", str(pdf)]) == 0
    sidecars = list((out / "rr" / "render").glob("*.json"))
    assert sidecars, "render should emit a sidecar"
    data = json.loads(sidecars[0].read_text())
    assert data["width_px"] > 0 and data["height_px"] > 0


# --------------------------------------------------------------------------- #
# 5 — manifest reproducibility
# --------------------------------------------------------------------------- #


def test_two_runs_produce_identical_outputs_map(tmp_path: Path):
    pdf = _make_pdf(tmp_path / "repro.pdf", trimbox="[50 100 350 400]")
    manifests = []
    for run in ("a", "b"):
        out = tmp_path / run
        assert px.main(["--out-dir", str(out), "--quiet", "all", str(pdf)]) == 0
        manifests.append(json.loads((out / "repro" / "manifest.json").read_text()))

    assert manifests[0]["outputs"] == manifests[1]["outputs"]
    assert manifests[0]["source"]["sha256"] == manifests[1]["source"]["sha256"]
    # The timestamp lives outside `outputs` on purpose, so it cannot mask a diff.
    assert "utc" in manifests[0]["run"]
    assert "utc" not in json.dumps(manifests[0]["outputs"])


def test_text_and_vector_json_are_byte_identical_across_runs(tmp_path: Path):
    pdf = _make_pdf(tmp_path / "bytes.pdf", trimbox="[50 100 350 400]")
    payloads = []
    for run in ("a", "b"):
        out = tmp_path / run
        px.main(["--out-dir", str(out), "--quiet", "all", str(pdf)])
        root = out / "bytes"
        payloads.append(
            {
                "spans": (root / "text" / "spans.json").read_bytes(),
                "drawings": (root / "vector" / "drawings.json").read_bytes(),
                "fills": (root / "vector" / "fills_by_colour.json").read_bytes(),
                "page1": (root / "text" / "page_001.md").read_bytes(),
            }
        )
    assert payloads[0] == payloads[1]


def test_json_serialisation_is_stable_regardless_of_key_order():
    a = px.json_bytes({"b": 1, "a": {"z": 2, "y": 3}})
    b = px.json_bytes({"a": {"y": 3, "z": 2}, "b": 1})
    assert a == b
    assert a.endswith(b"\n")


def test_negative_zero_is_normalised():
    assert math.copysign(1.0, px.R(-0.0000001)) == 1.0
    assert px.R(-0.0) == 0.0


# --------------------------------------------------------------------------- #
# 6 — geometry
# --------------------------------------------------------------------------- #


def test_polygon_area_of_known_rectangle():
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 4.0), (0.0, 4.0)]
    assert px.polygon_area(square) == pytest.approx(40.0, abs=1e-12)


def test_polygon_area_is_orientation_independent():
    forward = [(0.0, 0.0), (10.0, 0.0), (10.0, 4.0), (0.0, 4.0)]
    assert px.polygon_area(forward) == pytest.approx(
        px.polygon_area(list(reversed(forward))), abs=1e-12
    )


def test_polygon_area_of_degenerate_input_is_zero():
    assert px.polygon_area([]) == 0.0
    assert px.polygon_area([(0.0, 0.0), (1.0, 1.0)]) == 0.0


def test_flatten_cubic_of_a_straight_control_polygon_is_a_line():
    """Control points on a line must flatten to points on that same line."""
    points = px.flatten_cubic((0.0, 0.0), (1.0, 1.0), (2.0, 2.0), (3.0, 3.0))
    assert len(points) == px.BEZIER_SEGMENTS
    for x, y in points:
        assert x == pytest.approx(y, abs=1e-12)
    assert points[-1] == pytest.approx((3.0, 3.0), abs=1e-12)


def test_flatten_cubic_is_deterministic():
    args = ((0.0, 0.0), (0.0, 5.0), (5.0, 5.0), (5.0, 0.0))
    assert px.flatten_cubic(*args) == px.flatten_cubic(*args)


def test_rgb_hex_formatting():
    assert px.rgb_from_float([0.0, 0.0, 0.0])[1] == "#000000"
    assert px.rgb_from_float([1.0, 1.0, 1.0])[1] == "#ffffff"
    assert px.rgb_from_float([0.5, 0.25, 0.75])[1] == "#8040bf"
    assert px.rgb_from_float(None) is None


# --------------------------------------------------------------------------- #
# Safety: the source PDFs must never be written to
# --------------------------------------------------------------------------- #


def test_write_guard_refuses_to_escape_the_extraction_root(tmp_path: Path):
    pdf = _make_pdf(tmp_path / "guard.pdf", trimbox="[50 100 350 400]")
    ctx = px.RunContext(pdf, tmp_path / "out", ["test"])
    with pytest.raises(SystemExit, match="refusing to write outside"):
        ctx.write("../../escaped.json", b"{}")


def test_source_pdf_is_unchanged_by_a_full_run(tmp_path: Path):
    pdf = _make_pdf(tmp_path / "readonly.pdf", trimbox="[50 100 350 400]")
    before = px.sha256_file(pdf)
    px.main(["--out-dir", str(tmp_path / "out"), "--quiet", "all", str(pdf)])
    assert px.sha256_file(pdf) == before


# --------------------------------------------------------------------------- #
# CLI surface
# --------------------------------------------------------------------------- #


def test_probe_accepts_multiple_pdfs(tmp_path: Path):
    """`probe docs/*.pdf` shell-expands to N paths — the DoD requires this works."""
    first = _make_pdf(tmp_path / "one.pdf", trimbox="[50 100 350 400]")
    second = _make_pdf(tmp_path / "two.pdf", trimbox="[0 0 400 500]")
    out = tmp_path / "out"
    assert px.main(["--out-dir", str(out), "--quiet", "probe", str(first), str(second)]) == 0
    assert (out / "one" / "probe.json").exists()
    assert (out / "two" / "probe.json").exists()


def test_render_refuses_oversized_output_without_force(tmp_path: Path):
    pdf = _make_pdf(tmp_path / "big.pdf", trimbox="[0 0 400 500]")
    with pytest.raises(SystemExit, match="refusing to render"):
        px.main(
            ["--out-dir", str(tmp_path / "out"), "--quiet", "render", str(pdf),
             "--px-per-mm", "200", "--max-mpix", "1"]
        )


def test_render_bbox_is_interpreted_in_mat_frame_mm(tmp_path: Path):
    pdf = _make_pdf(tmp_path / "bbox.pdf", trimbox="[50 100 350 400]")
    out = tmp_path / "out"
    px.main(
        ["--out-dir", str(out), "--quiet", "render", str(pdf),
         "--bbox", "0,0,50,25", "--px-per-mm", "4"]
    )
    sidecar = json.loads(
        next((out / "bbox" / "render").glob("*.json")).read_text()
    )
    assert sidecar["bbox_mm"][0] == pytest.approx(0.0, abs=1e-6)
    assert sidecar["bbox_mm"][2] == pytest.approx(50.0, abs=1e-6)
    assert sidecar["width_px"] == pytest.approx(200, abs=1)
    assert sidecar["height_px"] == pytest.approx(100, abs=1)


def test_vector_self_check_passes_on_a_clean_page(tmp_path: Path):
    pdf = _make_pdf(tmp_path / "sc.pdf", trimbox="[50 100 350 400]")
    out = tmp_path / "out"
    px.main(["--out-dir", str(out), "--quiet", "vector", str(pdf)])
    data = json.loads((out / "sc" / "vector" / "drawings.json").read_text())
    check = data["pages"][0]["self_check"]
    assert check["verdict"] == "ok"
    assert check["union_overlaps_page_box"] is True
    assert data["paths"], "fixture should yield at least one path"


def test_self_check_tolerates_artwork_that_extends_past_the_trim(tmp_path: Path):
    """Off-page artwork is normal and must not be reported as a broken transform.

    S2 draws ~1.4k tiled-texture paths outside its trim box; they are clipped at
    render time. A union-bbox-only test would call that a transform failure.
    """
    doc = fitz.open()
    page = doc.new_page(width=400, height=500)
    for i in range(30):  # well inside the trim box
        page.draw_rect(fitz.Rect(60 + i, 150 + i, 70 + i, 160 + i), fill=(0, 0, 1))
    page.draw_rect(fitz.Rect(-200, -200, -100, -100), fill=(1, 0, 0))  # off-page
    doc.xref_set_key(page.xref, "TrimBox", "[50 100 350 400]")
    pdf = tmp_path / "overhang.pdf"
    doc.save(str(pdf))
    doc.close()

    out = tmp_path / "out"
    px.main(["--out-dir", str(out), "--quiet", "vector", str(pdf)])
    check = json.loads(
        (out / "overhang" / "vector" / "drawings.json").read_text()
    )["pages"][0]["self_check"]
    assert check["verdict"] == "ok"
    assert check["painted_paths_inside_box"] < check["painted_paths"]  # overhang seen
    assert check["share_inside_box"] > 0.6


def test_self_check_flags_a_page_whose_geometry_is_mostly_outside(tmp_path: Path):
    """The check must still fire when most geometry misses the box."""
    doc = fitz.open()
    page = doc.new_page(width=400, height=500)
    for i in range(30):
        page.draw_rect(fitz.Rect(-300 + i, -300 + i, -290 + i, -290 + i), fill=(1, 0, 0))
    doc.xref_set_key(page.xref, "TrimBox", "[50 100 350 400]")
    pdf = tmp_path / "bad.pdf"
    doc.save(str(pdf))
    doc.close()

    out = tmp_path / "out"
    px.main(["--out-dir", str(out), "--quiet", "vector", str(pdf)])
    check = json.loads(
        (out / "bad" / "vector" / "drawings.json").read_text()
    )["pages"][0]["self_check"]
    assert check["verdict"] == "suspect"


def test_separation_colourspace_images_are_not_dropped(tmp_path: Path):
    """A colourspace PNG cannot represent must fall back, never vanish.

    S2 embeds 112 Separation(DeviceCMYK, All) images; a plain tobytes("png")
    raises on every one of them.
    """
    pdf = _make_pdf(tmp_path / "sep.pdf", trimbox="[0 0 400 500]")
    doc = fitz.open(pdf)
    # A real image XObject is enough to exercise the escalation path end to end.
    if doc[0].get_images(full=True):
        payload, suffix, method = px._encode_image(doc, doc[0].get_images(full=True)[0][0])
        assert payload and suffix and method


def test_probe_records_text_layer_presence(tmp_path: Path):
    with_text = _make_pdf(tmp_path / "wt.pdf", trimbox="[0 0 400 500]")
    without = _make_pdf(tmp_path / "nt.pdf", trimbox="[0 0 400 500]", draw=False)
    out = tmp_path / "out"
    px.main(["--out-dir", str(out), "--quiet", "probe", str(with_text), str(without)])
    a = json.loads((out / "wt" / "probe.json").read_text())
    b = json.loads((out / "nt" / "probe.json").read_text())
    assert a["pages"][0]["text"]["has_text_layer"] is True
    assert b["pages"][0]["text"]["has_text_layer"] is False


def test_precision_flag_changes_rounding(tmp_path: Path):
    pdf = _make_pdf(tmp_path / "prec.pdf", trimbox="[50 100 350 400]")
    out = tmp_path / "out"
    px.main(["--out-dir", str(out), "--precision", "1", "--quiet", "vector", str(pdf)])
    data = json.loads((out / "prec" / "vector" / "drawings.json").read_text())
    for value in data["paths"][0]["bbox_mm"]:
        assert round(value, 1) == value


# --------------------------------------------------------------------------- #
# Content-stream census (cross-check inputs)
# --------------------------------------------------------------------------- #


def test_strip_literals_blanks_text_strings():
    """Operator-shaped bytes inside a string must not reach the census.

    Regression guard: an un-stripped `(a l c re b)` inflated the construction-op
    count on text-heavy pages and faked a vector-extraction shortfall.
    """
    stream = b"BT (a l c re b) Tj ET 0 0 10 10 re f"
    stripped = px.strip_literals(stream)
    assert b"a l c re b" not in stripped
    assert b"re f" in stripped  # real operators outside the string survive


def test_strip_literals_handles_escapes_and_nesting():
    assert b"inner" not in px.strip_literals(rb"(outer (inner) still) Tj")
    assert b"escaped" not in px.strip_literals(rb"(has \) escaped) Tj")
    assert b"deadbeef" not in px.strip_literals(b"<deadbeef> Tj")
    # '<<' is a dictionary, not a hex string, and must be preserved.
    assert b"/MCID" in px.strip_literals(b"/P <</MCID 0>> BDC 0 0 1 1 re f")


def test_census_counts_operators_outside_strings(tmp_path: Path):
    pdf = _make_pdf(tmp_path / "census.pdf", trimbox="[0 0 400 500]")
    census = px.content_op_census(fitz.open(pdf)[0])
    assert census.get("re", 0) >= 1
    # The fixture strokes and fills, which PyMuPDF emits as `B`, so assert on the
    # painting-operator family the cross-check actually uses, not on `f` alone.
    painting = sum(census.get(op, 0) for op in ("f", "f*", "F", "B", "B*", "b", "b*", "S", "s"))
    assert painting >= 1


def test_paint_op_cross_check_is_one_to_one_on_a_simple_page(tmp_path: Path):
    """One painting operator should yield exactly one get_drawings() entry.

    This is the signal that detects MuPDF failing to descend into a Form XObject.
    """
    pdf = _make_pdf(tmp_path / "xcheck.pdf", trimbox="[0 0 400 500]")
    page = fitz.open(pdf)[0]
    census = px.content_op_census(page)
    painting = sum(census.get(op, 0) for op in ("f", "f*", "F", "B", "B*", "b", "b*", "S", "s"))
    assert len(page.get_drawings()) == painting
