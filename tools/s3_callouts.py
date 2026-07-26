#!/usr/bin/env python3
"""Read the per-step parts callouts out of S3's rasterised building instructions.

S3 has no text layer and every page is a single 1684x1192 raster, so everything
here is image analysis. The one thing that makes it tractable: each step draws
its part **in isolation** in a light-blue callout box with a quantity label, and
the same part always renders the same way.

Why the callouts rather than the assembly renders — this was tested, not assumed.
Counting studs on a model's base in the assembly view fails because the base is
occluded by the object's own body: on ``note_blue``'s final step only 10 of the
plate's stud centres are visible, in two disjoint groups either side of the
column. The callout draws the same plate unoccluded, and all 32 studs resolve.

Measured constants, not chosen ones:

* the callout background is exactly ``(215, 238, 254)``
* two renders of the **same** part differ by a mean absolute channel delta of
  **0.18** (antialiasing from the box sitting at a different x when the step
  numeral is wider). Different parts differ by orders of magnitude more, so
  :data:`CALLOUT_MATCH_TOL` = 2.0 separates them with room to spare.
* 152 of the 176 build pages carry a callout; the other 24 place a previously
  built sub-assembly rather than a new part.
"""

from __future__ import annotations

import re
from collections import deque
from pathlib import Path
from typing import Any, Final, Iterable, Sequence

import numpy as np
from PIL import Image

#: Exact RGB of the parts-callout box background in S3.
CALLOUT_BG: Final = np.array([215, 238, 254])

#: Tolerance on the exact-background match, to absorb JPEG/antialias fringing.
CALLOUT_BG_TOL: Final = 20

#: Mean absolute channel delta below which two callout renders are the same part.
#: Same-part pairs measure 0.18; this leaves an order of magnitude of headroom.
CALLOUT_MATCH_TOL: Final = 2.0

#: A callout box smaller than this is noise, not a box.
MIN_CALLOUT_PX: Final = 800

#: LEGO System geometry — constants per S4 7.4, never measured from the raster.
STUD_MM: Final = 8.0
PLATE_MM: Final = 3.2
BRICK_MM: Final = 9.6


def _largest_component(mask: np.ndarray) -> np.ndarray | None:
    """Pixel list of the largest 4-connected component, or None."""
    height, width = mask.shape
    seen = np.zeros_like(mask)
    best: list[tuple[int, int]] | None = None
    ys, xs = np.where(mask)
    for y0, x0 in zip(ys, xs):
        if seen[y0, x0]:
            continue
        queue = deque([(y0, x0)])
        seen[y0, x0] = True
        pixels: list[tuple[int, int]] = []
        while queue:
            y, x = queue.popleft()
            pixels.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    queue.append((ny, nx))
        if best is None or len(pixels) > len(best):
            best = pixels
    return np.array(best) if best else None


def page_image(img_dir: Path, page: int) -> np.ndarray:
    path = img_dir / f"p{page:03d}_0001.png"
    return np.asarray(Image.open(path).convert("RGB")).astype(int)


def callout(image: np.ndarray) -> tuple[np.ndarray, tuple[int, int, int, int]] | None:
    """Crop the parts-callout box, or None when the step has no callout."""
    mask = np.abs(image - CALLOUT_BG).sum(axis=2) < CALLOUT_BG_TOL
    if mask.sum() < MIN_CALLOUT_PX:
        return None
    pixels = _largest_component(mask)
    if pixels is None or len(pixels) < MIN_CALLOUT_PX:
        return None
    y0, y1 = int(pixels[:, 0].min()), int(pixels[:, 0].max())
    x0, x1 = int(pixels[:, 1].min()), int(pixels[:, 1].max())
    return image[y0:y1 + 1, x0:x1 + 1], (x0, y0, x1 - x0 + 1, y1 - y0 + 1)


def blobs(region: np.ndarray, *, min_px: int, w_range: tuple[int, int],
          h_range: tuple[int, int], lum_below: int = 110) -> list[tuple[float, float]]:
    """Centres of dark blobs matching a size window — the drawn stud ellipses."""
    lum = 0.299 * region[..., 0] + 0.587 * region[..., 1] + 0.114 * region[..., 2]
    dark = lum < lum_below
    height, width = dark.shape
    seen = np.zeros_like(dark)
    out: list[tuple[float, float]] = []
    ys, xs = np.where(dark)
    for y0, x0 in zip(ys, xs):
        if seen[y0, x0]:
            continue
        queue = deque([(y0, x0)])
        seen[y0, x0] = True
        pixels: list[tuple[int, int]] = []
        while queue:
            y, x = queue.popleft()
            pixels.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < height and 0 <= nx < width and dark[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    queue.append((ny, nx))
        pts = np.array(pixels)
        w = int(pts[:, 1].max() - pts[:, 1].min() + 1)
        h = int(pts[:, 0].max() - pts[:, 0].min() + 1)
        if len(pixels) >= min_px and w_range[0] <= w <= w_range[1] and h_range[0] <= h <= h_range[1]:
            out.append((float(pts[:, 1].mean()), float(pts[:, 0].mean())))
    return out


def lattice_extent(centres: Sequence[tuple[float, float]]) -> tuple[int, int] | None:
    """Fit the isometric stud lattice and return (rows, cols).

    The renders are isometric, so the two in-plane axes appear as one offset
    going down-right and one going down-left. Averaging only **nearest-neighbour**
    offsets matters: including longer pairs mixes in diagonals and skews the basis
    (an early attempt produced |u| = 48.9 against |v| = 42.5, which cannot both be
    a unit step of the same square grid).

    Returns None when the fit is degenerate. The caller must cross-check
    ``rows * cols`` against the stud count — a fit that disagrees is rejected
    rather than rounded into agreement.
    """
    if len(centres) < 2:
        return None
    pts = np.array(centres)
    offsets: list[np.ndarray] = []
    for i in range(len(pts)):
        deltas = pts - pts[i]
        radii = np.hypot(deltas[:, 0], deltas[:, 1])
        for k in np.argsort(radii)[1:4]:
            if 0 < radii[k] < 60:
                offsets.append(deltas[k])
    if not offsets:
        return None
    offs = np.array(offsets)
    angles = np.degrees(np.arctan2(offs[:, 1], offs[:, 0]))
    down_right = offs[(angles > 5) & (angles < 75)]
    down_left = offs[(angles > 105) & (angles < 175)]
    if len(down_right) == 0 or len(down_left) == 0:
        return None
    u, v = down_right.mean(axis=0), down_left.mean(axis=0)
    basis = np.array([[u[0], v[0]], [u[1], v[1]]])
    if abs(np.linalg.det(basis)) < 1e-6:
        return None
    coords = np.round(np.linalg.solve(basis, (pts - pts[0]).T).T).astype(int)
    rows = int(coords[:, 0].max() - coords[:, 0].min() + 1)
    cols = int(coords[:, 1].max() - coords[:, 1].min() + 1)
    return rows, cols


def count_studs(box: np.ndarray) -> tuple[int, tuple[int, int] | None]:
    """(stud count, (rows, cols)) for an isolated callout part."""
    centres = blobs(box, min_px=60, w_range=(14, 60), h_range=(6, 40))
    return len(centres), lattice_extent(centres)


def digit_glyphs(image: np.ndarray, x0: int, x1: int, y0: int, y1: int,
                 max_glyph_w: int = 100) -> list[np.ndarray]:
    """Tight bitmaps of the numeral glyphs in a region, left to right.

    Used for both the step number (top-left of the page) and the callout
    quantity. Glyphs are large, black, on white and identical across the whole
    document, so exact bitmap comparison identifies them without OCR.
    """
    region = np.asarray(image[y0:y1, x0:x1]).astype(int)
    lum = 0.299 * region[..., 0] + 0.587 * region[..., 1] + 0.114 * region[..., 2]
    dark = lum < 128
    columns = dark.sum(axis=0)
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for i, value in enumerate(columns):
        if value > 0 and start is None:
            start = i
        if value == 0 and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(columns) - 1))
    out: list[np.ndarray] = []
    for a, b in runs:
        if b - a + 1 > max_glyph_w:
            break  # the callout box / artwork begins; the numeral ended
        sub = dark[:, a:b + 1]
        rows = np.where(sub.any(axis=1))[0]
        if len(rows):
            out.append(sub[rows.min():rows.max() + 1, :])
    return out


def build_pages(img_dir: Path, first: int = 2) -> list[int]:
    pages = []
    for path in img_dir.glob("p*_0001.png"):
        match = re.search(r"p(\d{3})_", path.name)
        if match and int(match.group(1)) >= first:
            pages.append(int(match.group(1)))
    return sorted(pages)


def cluster_callouts(img_dir: Path, pages: Iterable[int]) -> tuple[list[dict[str, Any]], list[int]]:
    """Group pages by which part their callout shows.

    Returns (clusters, pages_without_a_callout). Each cluster carries its
    representative crop so the caller can render a contact sheet for the
    one-off human identification pass.
    """
    clusters: list[dict[str, Any]] = []
    missing: list[int] = []
    for page in pages:
        found = callout(page_image(img_dir, page))
        if found is None:
            missing.append(page)
            continue
        box, bbox = found
        for cluster in clusters:
            ref = cluster["image"]
            if ref.shape == box.shape and float(np.abs(ref - box).mean()) < CALLOUT_MATCH_TOL:
                cluster["pages"].append(page)
                break
        else:
            clusters.append({"image": box, "pages": [page], "bbox": bbox})
    clusters.sort(key=lambda c: (-len(c["pages"]), c["pages"][0]))
    for index, cluster in enumerate(clusters):
        studs, extent = count_studs(cluster["image"])
        cluster["cluster_id"] = index
        cluster["studs"] = studs
        cluster["lattice"] = list(extent) if extent else None
        cluster["consistent"] = bool(extent and extent[0] * extent[1] == studs)
        cluster["size_px"] = [int(cluster["image"].shape[1]), int(cluster["image"].shape[0])]
    return clusters, missing
