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

S3 draws **two** kinds of box, and part 1 of this phase only knew about one:

======================  ====================  =========================================
box                     background            meaning
======================  ====================  =========================================
parts callout           ``(215, 238, 254)``   the part(s) added by **this step**
run preview             ``(255, 245, 218)``   a picture of **what this run produces**
======================  ====================  =========================================

The run preview is the model-boundary signal. Part 1 used the light-blue
callout instead and recorded a caveat that the signal degrades after page 124;
that caveat described a limitation of the wrong signal, not of the source. The
cream box lands on 20 pages, always anchored at y = 98, and its contents are
the identification evidence — unoccluded, isolated and complete.

Measured constants, not chosen ones:

* the two box backgrounds above are exact; a flat-colour census over every
  build page finds no third box colour
* two renders of the **same** part differ by a mean absolute channel delta of
  **0.18** (antialiasing from the box sitting at a different x when the step
  numeral is wider). Different parts differ by orders of magnitude more, so
  :data:`CALLOUT_MATCH_TOL` = 2.0 separates them with room to spare.
* 152 of the 174 build pages carry a callout; the others place a previously
  built sub-assembly rather than a new part.
* pages 176-177 are the **parts inventory**, not build steps: they carry no
  step numeral. See :func:`is_build_step`.
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

#: Exact RGB of the RUN-PREVIEW box background — the second box colour.
#:
#: A flat-colour census over all build pages returns exactly TWO box
#: backgrounds; every other flat colour is brick paint ((0,6,18) black,
#: (1,80,198) blue, (210,14,0) red, (26,121,53) green, (255,214,48) yellow).
#: There is no third box type.
PREVIEW_BG: Final = np.array([255, 245, 218])

#: Tolerance on the exact-background match, to absorb JPEG/antialias fringing.
CALLOUT_BG_TOL: Final = 20

#: Mean absolute channel delta below which two callout renders are the same part.
#: Same-part pairs measure 0.18; this leaves an order of magnitude of headroom.
CALLOUT_MATCH_TOL: Final = 2.0

#: A callout box smaller than this is noise, not a box.
MIN_CALLOUT_PX: Final = 800

#: A silhouette component smaller than this is a quantity glyph, not a part.
MIN_PART_PX: Final = 1500

#: Silhouette-match window for deciding two renders show the same part SHAPE.
#: Calibrated, not chosen: over all 58 part renders, every pair that falls
#: inside this window AND self-checks its own lattice agrees on both the stud
#: count and the lattice (31 of 31 pairs, zero conflicts). Genuinely different
#: shapes score 0.66-0.74, far below the 0.9552 worst same-part case.
SHAPE_SLACK_PX: Final = 8
SHAPE_AGREE: Final = 0.95

#: Minimum glyph height of a real step numeral. Pages 176-177 carry the parts
#: inventory, whose "24x"/"3003" labels are ~30 px; step numerals are 87-127 px.
STEP_NUMERAL_MIN_H: Final = 60

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


def flat_box(image: np.ndarray, bg: np.ndarray
             ) -> tuple[np.ndarray, tuple[int, int, int, int]] | None:
    """Crop the largest flat-``bg``-coloured box on the page, or None.

    Shared by both box kinds — the only difference between a parts callout and
    a run preview is the background colour.
    """
    mask = np.abs(image - bg).sum(axis=2) < CALLOUT_BG_TOL
    if mask.sum() < MIN_CALLOUT_PX:
        return None
    pixels = _largest_component(mask)
    if pixels is None or len(pixels) < MIN_CALLOUT_PX:
        return None
    y0, y1 = int(pixels[:, 0].min()), int(pixels[:, 0].max())
    x0, x1 = int(pixels[:, 1].min()), int(pixels[:, 1].max())
    return image[y0:y1 + 1, x0:x1 + 1], (x0, y0, x1 - x0 + 1, y1 - y0 + 1)


def callout(image: np.ndarray) -> tuple[np.ndarray, tuple[int, int, int, int]] | None:
    """Crop the parts-callout box, or None when the step has no callout."""
    return flat_box(image, CALLOUT_BG)


def run_preview(image: np.ndarray) -> tuple[np.ndarray, tuple[int, int, int, int]] | None:
    """Crop the cream run-preview box, or None when the page starts no run."""
    return flat_box(image, PREVIEW_BG)


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
    """Every page from ``first`` on — including the trailing inventory pages."""
    pages = []
    for path in img_dir.glob("p*_0001.png"):
        match = re.search(r"p(\d{3})_", path.name)
        if match and int(match.group(1)) >= first:
            pages.append(int(match.group(1)))
    return sorted(pages)


def is_build_step(image: np.ndarray) -> bool:
    """True when the page carries a real step numeral.

    Part 1 recorded "step numbering is continuous 1..176, one step per page,
    pages 2..177". That over-counted by two: pages 176-177 are the parts
    inventory and carry no numeral at all. The digit census that produced the
    claim counted their ``24x`` / ``3003`` labels as three-digit step numbers,
    which is exactly why its three-digit bucket read 77 instead of 75.
    """
    glyphs = digit_glyphs(image, 80, 400, 60, 220)
    return max((g.shape[0] for g in glyphs), default=0) >= STEP_NUMERAL_MIN_H


def step_pages(img_dir: Path) -> list[int]:
    """The pages that are genuinely build steps, inventory pages excluded."""
    return [p for p in build_pages(img_dir) if is_build_step(page_image(img_dir, p))]


def run_boundaries(img_dir: Path, pages: Sequence[int]) -> list[dict[str, Any]]:
    """Partition ``pages`` at every run-preview box.

    Each entry is ``{"start", "end", "preview", "bbox"}``. A preview marks the
    start of a run, but a run is **not** always a model: some previews mark a
    sub-assembly built inside a larger model (page 73 sits inside the
    microphone, pages 130/132/138/140 inside the amplifier). Deciding which is
    which is a judgement call and lives in ``docs/object_map.toml``, not here.
    """
    starts: list[dict[str, Any]] = []
    for page in pages:
        found = run_preview(page_image(img_dir, page))
        if found is not None:
            box, bbox = found
            starts.append({"start": page, "preview": box, "bbox": bbox})
    for index, entry in enumerate(starts):
        nxt = starts[index + 1]["start"] if index + 1 < len(starts) else None
        entry["end"] = (nxt - 1) if nxt else pages[-1]
    return starts


# --------------------------------------------------------------------------- #
# Part-level analysis: segment a callout into individual parts, then transfer
# a stud count between renders of the same shape in different paint.
# --------------------------------------------------------------------------- #


def _components(mask: np.ndarray, min_px: int) -> list[np.ndarray]:
    """All 8-connected components of ``mask`` with at least ``min_px`` pixels."""
    height, width = mask.shape
    seen = np.zeros_like(mask)
    out: list[np.ndarray] = []
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
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if (0 <= ny < height and 0 <= nx < width
                            and mask[ny, nx] and not seen[ny, nx]):
                        seen[ny, nx] = True
                        queue.append((ny, nx))
        if len(pixels) >= min_px:
            out.append(np.array(pixels))
    return out


def part_components(box: np.ndarray) -> list[np.ndarray]:
    """Split a callout into its individual parts, left to right.

    A callout may hold two or three different parts side by side. Fitting one
    lattice across all of them cannot self-check — page 89's callout returns
    14 stud centres and a 5x9 extent, which is 45 cells for 14 studs. Splitting
    first turns that into a 2x4 brick (8 studs) plus a 1x6 brick.
    """
    fg = np.abs(box - CALLOUT_BG).sum(axis=2) >= CALLOUT_BG_TOL
    parts = []
    for pixels in _components(fg, MIN_PART_PX):
        y0, y1 = int(pixels[:, 0].min()), int(pixels[:, 0].max())
        x0, x1 = int(pixels[:, 1].min()), int(pixels[:, 1].max())
        parts.append((x0, box[y0:y1 + 1, x0:x1 + 1]))
    return [p for _x, p in sorted(parts, key=lambda t: t[0])]


def silhouette(part: np.ndarray) -> np.ndarray:
    return np.abs(part - CALLOUT_BG).sum(axis=2) >= CALLOUT_BG_TOL


def _erode(mask: np.ndarray, rounds: int = 2) -> np.ndarray:
    """Shrink by ``rounds`` pixels, discarding the antialias fringe.

    A dark part's fringe against the light-blue background crosses the
    threshold where a white part's does not, so raw silhouettes of the same
    part in different paint differ by 1-2 px all the way round. Eroding both
    removes that systematic difference.
    """
    for _ in range(rounds):
        p = np.pad(mask, 1)
        mask = (p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:] & p[1:-1, 1:-1]
                & p[:-2, :-2] & p[:-2, 2:] & p[2:, :-2] & p[2:, 2:])
    return mask


def _centred(mask: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    out = np.zeros(shape, bool)
    h, w = mask.shape
    dy, dx = (shape[0] - h) // 2, (shape[1] - w) // 2
    out[dy:dy + h, dx:dx + w] = mask
    return out


def same_shape(a: np.ndarray, b: np.ndarray) -> bool:
    """True when two silhouettes are the same part shape in different paint."""
    if (abs(a.shape[0] - b.shape[0]) > SHAPE_SLACK_PX
            or abs(a.shape[1] - b.shape[1]) > SHAPE_SLACK_PX):
        return False
    shape = (max(a.shape[0], b.shape[0]) + 4, max(a.shape[1], b.shape[1]) + 4)
    return float((_centred(_erode(a), shape) == _centred(_erode(b), shape)).mean()) >= SHAPE_AGREE


def stud_fit(part: np.ndarray) -> dict[str, Any]:
    """Count studs on one isolated part and self-check the lattice."""
    centres = blobs(part, min_px=60, w_range=(14, 60), h_range=(6, 40))
    extent = lattice_extent(centres)
    consistent = bool(extent and extent[0] * extent[1] == len(centres) and centres)
    return {"studs": len(centres), "lattice": list(extent) if extent else None,
            "consistent": consistent}


def shape_groups(clusters: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group every part render by shape and transfer counts within a group.

    Stud ellipses are only separable from the body on **light** parts, so a
    direct count self-checks on a minority of renders. The silhouette does not
    depend on paint at all, so a dark part inherits the count of a light part
    with the same shape — and only ever from a render that self-checked. A
    group with no self-checking member stays unresolved; it never guesses.
    """
    renders: list[dict[str, Any]] = []
    for cluster in clusters:
        for index, part in enumerate(part_components(cluster["image"])):
            fit = stud_fit(part)
            renders.append({"cluster_id": cluster["cluster_id"], "part_index": index,
                            "pages": list(cluster["pages"]),
                            "size_px": [int(part.shape[1]), int(part.shape[0])],
                            "sil": silhouette(part), **fit})

    groups: list[list[dict[str, Any]]] = []
    for render in renders:
        for group in groups:
            if same_shape(group[0]["sil"], render["sil"]):
                group.append(render)
                break
        else:
            groups.append([render])

    out: list[dict[str, Any]] = []
    for index, group in enumerate(groups):
        checked = [r for r in group if r["consistent"]]
        counts = {(r["studs"], tuple(r["lattice"])) for r in checked}
        if len(counts) > 1:  # pragma: no cover - never happens on S3, but never guess
            raise ValueError(
                f"shape group {index} disagrees with itself: {sorted(counts)}")
        studs, lattice = (counts.pop() if counts else (None, None))
        out.append({
            "shape_id": index,
            "size_px": group[0]["size_px"],
            "studs": studs,
            "lattice": list(lattice) if lattice else None,
            "source": "self_check" if checked else None,
            "self_checked_from": sorted({r["cluster_id"] for r in checked}),
            "members": sorted({(r["cluster_id"], r["part_index"]) for r in group}),
            "pages": sorted({p for r in group for p in r["pages"]}),
        })
    out.sort(key=lambda g: (-len(g["members"]), g["shape_id"]))
    return out


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
