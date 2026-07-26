"""Invariants on sim/geometry.py.

The containment and overlap primitives decide every scoring outcome, so they are
tested against hand-computable cases rather than against themselves.

The load-bearing one is :func:`min_area_rect`. Phase 4 published a cable
constraint derived from ``bbox_mm``, which is the axis-aligned bounding box, not
the area — and the two cable areas are rotated, so the bounding box overstated
the short axis by 34.77 mm. These tests pin the distinction.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from sim.geometry import (
    bbox,
    centroid,
    is_convex,
    min_area_rect,
    oriented_rect,
    point_in_polygon,
    polygon_contains,
    polygons_intersect,
    require_convex,
    signed_area,
)

ROOT = Path(__file__).resolve().parents[1]
FIELD_SPEC = ROOT / "data" / "field_spec.json"

UNIT = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]


# --------------------------------------------------------------------------- #
# Rectangles
# --------------------------------------------------------------------------- #


def test_oriented_rect_at_zero_is_axis_aligned():
    rect = oriented_rect(0.0, 0.0, 4.0, 10.0, 0.0)
    x0, y0, x1, y1 = bbox(rect)
    assert (x1 - x0, y1 - y0) == pytest.approx((4.0, 10.0))


def test_oriented_rect_at_90_swaps_the_extents():
    rect = oriented_rect(0.0, 0.0, 4.0, 10.0, 90.0)
    x0, y0, x1, y1 = bbox(rect)
    assert (x1 - x0, y1 - y0) == pytest.approx((10.0, 4.0))


def test_a_rotated_rectangle_keeps_its_area():
    for theta in (0.0, 17.0, 45.0, 80.0, 133.0):
        rect = oriented_rect(3.0, -2.0, 4.0, 10.0, theta)
        assert abs(signed_area(rect)) == pytest.approx(40.0, abs=1e-9)


def test_centroid_of_a_rectangle_is_its_centre():
    assert centroid(oriented_rect(5.0, 7.0, 3.0, 9.0, 31.0)) == pytest.approx((5.0, 7.0))


# --------------------------------------------------------------------------- #
# Containment
# --------------------------------------------------------------------------- #


def test_boundary_points_count_as_inside():
    """S1 says 'touching'; an object flush to the target edge is inside."""
    for point in ((0.0, 0.0), (10.0, 10.0), (5.0, 0.0), (0.0, 5.0)):
        assert point_in_polygon(point, UNIT), point


def test_points_outside_are_outside():
    for point in ((-0.1, 5.0), (10.1, 5.0), (5.0, -0.1), (5.0, 10.1)):
        assert not point_in_polygon(point, UNIT), point


def test_a_flush_rectangle_is_contained():
    """Exactly filling the target must count as inside, not as a near miss."""
    assert polygon_contains(UNIT, oriented_rect(5.0, 5.0, 10.0, 10.0, 0.0))


def test_one_micron_of_overhang_is_not_contained():
    assert not polygon_contains(UNIT, oriented_rect(5.0, 5.0, 10.002, 10.0, 0.0))


def test_containment_implies_intersection():
    inner = oriented_rect(5.0, 5.0, 2.0, 2.0, 0.0)
    assert polygon_contains(UNIT, inner)
    assert polygons_intersect(UNIT, inner)


def test_touching_along_an_edge_counts_as_intersecting():
    """Two areas sharing a boundary: an object on the line touches both."""
    neighbour = [(10.0, 0.0), (20.0, 0.0), (20.0, 10.0), (10.0, 10.0)]
    assert polygons_intersect(UNIT, neighbour)
    assert not polygons_intersect(UNIT, neighbour, touching_counts=False)


def test_separated_rectangles_do_not_intersect():
    far = [(11.0, 0.0), (20.0, 0.0), (20.0, 10.0), (11.0, 10.0)]
    assert not polygons_intersect(UNIT, far)


def test_a_rotated_rectangle_can_intersect_where_its_bbox_does_not_touch():
    """A diagonal probe: SAT must beat a bounding-box approximation."""
    diamond = oriented_rect(11.5, 5.0, 2.0, 2.0, 45.0)
    assert not polygons_intersect(UNIT, diamond)
    near = oriented_rect(10.5, 5.0, 2.0, 2.0, 45.0)
    assert polygons_intersect(UNIT, near)


# --------------------------------------------------------------------------- #
# Convexity guard
# --------------------------------------------------------------------------- #


def test_convexity_guard_accepts_rectangles_and_rejects_an_L():
    assert is_convex(UNIT)
    require_convex(UNIT, "unit square")
    ell = [(0.0, 0.0), (10.0, 0.0), (10.0, 4.0), (4.0, 4.0), (4.0, 10.0), (0.0, 10.0)]
    assert not is_convex(ell)
    with pytest.raises(ValueError, match="not convex"):
        require_convex(ell, "L shape")


# --------------------------------------------------------------------------- #
# min_area_rect — the bounding-box trap
# --------------------------------------------------------------------------- #


def test_min_area_rect_recovers_a_rotated_rectangle_exactly():
    for theta in (0.0, 10.0, 37.0, 80.0, 100.0, 179.0):
        rect = min_area_rect(oriented_rect(100.0, 200.0, 30.0, 90.0, theta))
        assert (rect.cx, rect.cy) == pytest.approx((100.0, 200.0), abs=1e-6)
        assert rect.width_mm == pytest.approx(30.0, abs=1e-6)
        assert rect.height_mm == pytest.approx(90.0, abs=1e-6)
        assert rect.aspect == pytest.approx(3.0, abs=1e-6)
        assert rect.angle_deg == pytest.approx((theta + 90.0) % 180.0, abs=1e-6)


def test_min_area_rect_is_smaller_than_the_bbox_when_rotated():
    """The whole reason this function exists."""
    poly = oriented_rect(0.0, 0.0, 30.0, 90.0, 45.0)
    x0, y0, x1, y1 = bbox(poly)
    rect = min_area_rect(poly)
    assert rect.width_mm * rect.height_mm == pytest.approx(2700.0, abs=1e-6)
    assert (x1 - x0) * (y1 - y0) > 2700.0 * 1.5


@pytest.fixture(scope="module")
def field() -> dict:
    return json.loads(FIELD_SPEC.read_text(encoding="utf-8"))


def test_the_cable_areas_are_rotated_and_the_others_are_not(field: dict):
    """The fact Phase 4 missed, asserted so it cannot be missed again."""
    rotated, aligned = [], []
    for area_id, area in field["areas"].items():
        if not area.get("scoring"):
            continue
        rect = min_area_rect(area["polygon_visible_mm"])
        square = min(abs(rect.angle_deg), abs(rect.angle_deg - 90.0),
                     abs(rect.angle_deg - 180.0)) < 1e-6
        (aligned if square else rotated).append(area_id)
    assert sorted(rotated) == ["cable_area_lower", "cable_area_upper"]
    assert len(aligned) == 8


def test_the_cable_area_bbox_overstates_its_short_axis(field: dict):
    """34.77 mm of phantom width — the exact size of the Phase 4 error."""
    for area_id in ("cable_area_upper", "cable_area_lower"):
        area = field["areas"][area_id]
        rect = min_area_rect(area["polygon_visible_mm"])
        x0, y0, x1, y1 = bbox(area["polygon_visible_mm"])
        assert rect.width_mm == pytest.approx(79.700, abs=0.01)
        assert rect.height_mm == pytest.approx(207.201, abs=0.01)
        assert (x1 - x0) == pytest.approx(114.47, abs=0.01)
        assert (x1 - x0) - rect.width_mm == pytest.approx(34.77, abs=0.02)


def test_min_area_rect_agrees_with_the_recorded_area(field: dict):
    """Cross-check: width × height must reproduce field_spec's own area_mm2."""
    for area_id, area in field["areas"].items():
        if not area.get("scoring"):
            continue
        rect = min_area_rect(area["polygon_visible_mm"])
        assert rect.width_mm * rect.height_mm == pytest.approx(
            area["area_mm2"], rel=1e-4), area_id
