#!/usr/bin/env python3
"""Polygon primitives for the scorer.

Everything the scoring predicates need and nothing else: build an object's
footprint as an oriented rectangle, ask whether it lies wholly inside a target
area, and ask whether it touches an area it must not.

**Exactness matters more than generality here.** All ten ``scoring: true`` areas
are convex rectangles and every object footprint is a rectangle, so the
separating-axis test below is *exact* rather than approximate. Convexity is a
property of today's field spec, not a law, so :func:`require_convex` asserts it:
a concave scoring area would silently break containment, and must raise instead.

**They are rectangles, but not all axis-aligned.** The two cable areas are
79.700 × 207.201 mm tilted to 80° and 100°; the other eight happen to sit square
to the mat. Nothing here may substitute ``bbox_mm`` for an area — that reads the
cable areas 35 mm too wide across their short axis. Use :func:`min_area_rect`,
which recovers a rectangle's own axes exactly.

Units are millimetres in the MAT frame throughout (``CLAUDE.md`` §5.2): origin
bottom-left, ``+X`` right, ``+Y`` up, heading ``0° = +X``, CCW positive.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Sequence

import numpy as np

#: Distances below this are treated as zero. The field spec carries 3 decimals
#: (1 µm, ADR-008), so this sits two orders of magnitude below the data's own
#: resolution and cannot mask a real geometric difference.
EPS: Final = 1e-9

Point = tuple[float, float]
Polygon = Sequence[Point]


def oriented_rect(cx: float, cy: float, width: float, height: float,
                  theta_deg: float = 0.0) -> list[Point]:
    """A ``width × height`` rectangle centred on ``(cx, cy)``, rotated CCW.

    ``width`` runs along the object's local X and ``height`` along its local Y,
    so a footprint recorded as ``[16.0, 128.0]`` at ``theta_deg = 0`` is 16 mm
    across X and 128 mm along Y.
    """
    hw, hh = width / 2.0, height / 2.0
    corners = ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))
    rad = math.radians(theta_deg)
    cos, sin = math.cos(rad), math.sin(rad)
    return [(cx + x * cos - y * sin, cy + x * sin + y * cos) for x, y in corners]


def signed_area(polygon: Polygon) -> float:
    """Shoelace area; positive when the winding is counter-clockwise."""
    pts = np.asarray(polygon, dtype=float)
    if len(pts) < 3:
        return 0.0
    x, y = pts[:, 0], pts[:, 1]
    return float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2.0


def is_convex(polygon: Polygon) -> bool:
    """True when every cross product along the boundary shares one sign."""
    pts = np.asarray(polygon, dtype=float)
    n = len(pts)
    if n < 3:
        return False
    edges = np.roll(pts, -1, axis=0) - pts
    nxt = np.roll(edges, -1, axis=0)
    cross = edges[:, 0] * nxt[:, 1] - edges[:, 1] * nxt[:, 0]
    nonzero = cross[np.abs(cross) > EPS]
    return bool(len(nonzero) == 0 or np.all(nonzero > 0) or np.all(nonzero < 0))


def require_convex(polygon: Polygon, name: str) -> None:
    """Raise unless ``polygon`` is convex.

    The scorer's containment and overlap tests are exact only for convex
    shapes. Rather than degrade quietly on a shape they cannot handle, they
    refuse to run — the same discipline as the builders' hard-fails.
    """
    if not is_convex(polygon):
        raise ValueError(
            f"{name} is not convex; the separating-axis containment test in "
            f"sim.geometry is exact only for convex polygons. Either the field "
            f"spec changed shape or this area needs a decomposition step."
        )


def point_in_polygon(point: Point, polygon: Polygon) -> bool:
    """Ray-casting containment, boundary counted as inside."""
    x, y = point
    pts = list(polygon)
    inside = False
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        # on-edge check first: the boundary is inside, and a vertex hit would
        # otherwise flip the parity twice
        cross = (x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)
        if abs(cross) <= EPS * max(1.0, abs(x1 - x0) + abs(y1 - y0)):
            if min(x0, x1) - EPS <= x <= max(x0, x1) + EPS and \
               min(y0, y1) - EPS <= y <= max(y0, y1) + EPS:
                return True
        if (y0 > y) != (y1 > y):
            x_hit = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < x_hit:
                inside = not inside
    return inside


def _axes(polygon: Polygon) -> list[tuple[float, float]]:
    """Outward edge normals, the candidate separating axes."""
    pts = list(polygon)
    out = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        if length > EPS:
            out.append((-dy / length, dx / length))
    return out


def _project(polygon: Polygon, axis: tuple[float, float]) -> tuple[float, float]:
    dots = [px * axis[0] + py * axis[1] for px, py in polygon]
    return min(dots), max(dots)


def polygons_intersect(a: Polygon, b: Polygon, *, touching_counts: bool = True) -> bool:
    """Separating-axis overlap test for two convex polygons.

    ``touching_counts`` decides whether a shared boundary is an intersection.
    It is ``True`` for the scorer because S1's wording is *"touching"*: an
    object resting exactly on the line between two areas touches both.
    """
    for polygon in (a, b):
        for axis in _axes(polygon):
            a_lo, a_hi = _project(a, axis)
            b_lo, b_hi = _project(b, axis)
            if touching_counts:
                if a_hi < b_lo - EPS or b_hi < a_lo - EPS:
                    return False
            else:
                if a_hi <= b_lo + EPS or b_hi <= a_lo + EPS:
                    return False
    return True


def polygon_contains(outer: Polygon, inner: Polygon) -> bool:
    """True when every vertex of ``inner`` lies inside convex ``outer``.

    For convex ``outer`` this is sufficient: a convex region containing all the
    vertices of any polygon contains its whole hull, and ``inner`` is inside its
    own hull. No edge-crossing pass is needed, and adding one would be wrong —
    it would reject a rectangle sitting flush against the target's edge, which
    S1 counts as inside.
    """
    return all(point_in_polygon(p, outer) for p in inner)


@dataclass(frozen=True)
class OrientedRect:
    """A polygon's own rectangle: centre, extents and heading.

    Needed because **the two cable areas are not axis-aligned** — they are
    79.700 × 207.201 mm rectangles tilted to 80° and 100°, mirrored about the
    horizontal. Their axis-aligned bounding box is 114.47 × 217.89 mm and
    encloses 24,942 mm² against the area's true 16,514 mm², so anything that
    reads ``bbox_mm`` as though it were the area over-states the short axis by
    35 mm. Every other scoring area happens to be axis-aligned, which is exactly
    what makes the mistake easy to miss.
    """

    cx: float
    cy: float
    width_mm: float      # the SHORT extent
    height_mm: float     # the LONG extent
    angle_deg: float     # heading of the long axis, 0..180
    aspect: float


def min_area_rect(polygon: Polygon) -> OrientedRect:
    """Minimum-area enclosing rectangle of a convex polygon.

    Exact by the rotating-calipers property: the minimum-area rectangle shares
    an edge with the hull, so testing every edge direction suffices. For a
    polygon that already *is* a rectangle this recovers it exactly.
    """
    pts = np.asarray(polygon, dtype=float)
    edges = np.roll(pts, -1, axis=0) - pts
    best: tuple[float, OrientedRect] | None = None
    for dx, dy in edges:
        length = math.hypot(dx, dy)
        if length <= EPS:
            continue
        ux, uy = dx / length, dy / length
        along = pts[:, 0] * ux + pts[:, 1] * uy
        across = pts[:, 0] * -uy + pts[:, 1] * ux
        w, h = float(along.ptp() if hasattr(along, "ptp") else np.ptp(along)), \
               float(np.ptp(across))
        area = w * h
        mid_a, mid_c = (along.min() + along.max()) / 2, (across.min() + across.max()) / 2
        cx = mid_a * ux + mid_c * -uy
        cy = mid_a * uy + mid_c * ux
        short, long = (w, h) if w <= h else (h, w)
        # heading of the LONG axis
        angle = math.degrees(math.atan2(uy, ux)) if w >= h else \
            math.degrees(math.atan2(ux, -uy))
        rect = OrientedRect(cx, cy, short, long, angle % 180.0,
                            long / short if short > EPS else float("inf"))
        if best is None or area < best[0] - EPS:
            best = (area, rect)
    assert best is not None, "degenerate polygon has no edge direction"
    return best[1]


def bbox(polygon: Polygon) -> tuple[float, float, float, float]:
    pts = np.asarray(polygon, dtype=float)
    return (float(pts[:, 0].min()), float(pts[:, 1].min()),
            float(pts[:, 0].max()), float(pts[:, 1].max()))


def centroid(polygon: Polygon) -> Point:
    """Area centroid; falls back to the vertex mean for degenerate input."""
    pts = np.asarray(polygon, dtype=float)
    area = signed_area(polygon)
    if abs(area) < EPS:
        return (float(pts[:, 0].mean()), float(pts[:, 1].mean()))
    x, y = pts[:, 0], pts[:, 1]
    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    cross = x * y1 - x1 * y
    return (float(np.dot(x + x1, cross) / (6.0 * area)),
            float(np.dot(y + y1, cross) / (6.0 * area)))
