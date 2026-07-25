#!/usr/bin/env python3
"""Deterministic PDF extraction for the WRO 2026 RoboMission Elementary repo.

Turns the read-only source PDFs (S1 game rules, S2 game mat, S3 building
instructions) into machine-readable artifacts under ``docs/extracted/``.

Design rules that are not negotiable:

* **One coordinate authority.** :class:`MatFrame` owns the pt -> mm conversion and
  the flip into the MAT frame. No command re-derives it.
* **Deterministic output.** Same input sha256 + same params => byte-identical
  ``text/`` and ``vector/`` JSON. Timestamps live only in ``manifest.json``'s
  ``run`` block, never in the data files.
* **Sources are read-only.** Documents are opened, never saved. Writes are
  refused outside the extraction root.

Coordinate spaces in play (empirically pinned against PyMuPDF 1.28, see
``tests/test_pdf_extract.py``):

===========================  ==================================  ==========
space                        produced/consumed by                rotation
===========================  ==================================  ==========
PDF user space               raw /MediaBox /TrimBox arrays       n/a
unrotated page space         ``page.transformation_matrix``,     excluded
                             ``page.get_drawings()``
rotated page space           ``page.rect``, ``page.get_pixmap``  included
MAT frame (mm)               everything this tool emits          excluded
===========================  ==================================  ==========

``get_drawings()`` reports *unrotated* page space, so ``transformation_matrix``
alone bridges PDF space to it. Rendering needs the extra ``rotation_matrix`` hop.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, Iterable, Literal, Sequence

import fitz
import numpy as np

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

TOOL_NAME: Final = "pdf_extract"
TOOL_VERSION: Final = "1.0.0"
SCHEMA_VERSION: Final = 1

MM_PER_PT: Final = 25.4 / 72.0
PT_PER_MM: Final = 72.0 / 25.4

BEZIER_SEGMENTS: Final = 16          # ADR-004: fixed subdivision, never adaptive
#: Slack when testing whether a path lies inside the page box, in mm. Artwork
#: routinely touches or marginally overruns the trim edge.
_BOX_TOLERANCE_MM: Final = 1.0
DEFAULT_PRECISION: Final = 3         # ADR-008: 1 um
DEFAULT_PX_PER_MM: Final = 4.0
DEFAULT_MAX_MPIX: Final = 200.0
DEFAULT_OUT_DIR: Final = "docs/extracted"

BoxSource = Literal["TrimBox", "CropBox", "MediaBox"]

#: /MediaBox and /CropBox are inheritable (PDF 32000-1 sec. 7.7.3.4). TrimBox,
#: BleedBox and ArtBox are not - they default to CropBox, which is exactly the
#: precedence chain in ADR-003.
_INHERITABLE: Final = frozenset({"MediaBox", "CropBox"})

_BOX_KEYS: Final = ("MediaBox", "CropBox", "TrimBox", "BleedBox", "ArtBox")

# --------------------------------------------------------------------------- #
# Deterministic number + JSON emission
# --------------------------------------------------------------------------- #

_PRECISION: int = DEFAULT_PRECISION


def set_precision(precision: int) -> None:
    """Set the global rounding precision for every emitted float."""
    global _PRECISION
    _PRECISION = precision


def R(value: float) -> float:
    """Round to the configured precision, normalising ``-0.0`` to ``0.0``.

    The sign normalisation matters: without it two runs can differ by a single
    ``-`` character and break the byte-identity guarantee.
    """
    rounded = round(float(value), _PRECISION)
    return 0.0 if rounded == 0.0 else rounded


def RS(values: Iterable[float]) -> list[float]:
    """Round a sequence of floats."""
    return [R(v) for v in values]


def json_bytes(obj: Any) -> bytes:
    """Serialise deterministically: sorted keys, fixed indent, LF, trailing NL."""
    text = json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False)
    return (text + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --------------------------------------------------------------------------- #
# Run context: output rooting, write guard, manifest accumulation
# --------------------------------------------------------------------------- #


class RunContext:
    """Owns the output directory, the write guard and the manifest accumulator."""

    def __init__(self, pdf_path: Path, out_root: Path, argv: Sequence[str]) -> None:
        self.pdf_path = pdf_path.resolve()
        self.out_root = out_root.resolve()
        self.out_dir = (self.out_root / self.pdf_path.stem).resolve()
        self.argv = list(argv)
        self.outputs: dict[str, dict[str, Any]] = {}
        self.params: dict[str, Any] = {}
        self.notes: list[str] = []
        self.source_sha256 = sha256_file(self.pdf_path)
        self.source_bytes = self.pdf_path.stat().st_size

    # -- writing -------------------------------------------------------- #

    def write(self, relpath: str, data: bytes) -> Path:
        """Write bytes under the extraction root and record them in the manifest.

        Refuses any path that escapes the extraction root. Source PDFs live
        outside it, so they cannot be clobbered even by a malformed relpath.
        """
        target = (self.out_dir / relpath).resolve()
        root = str(self.out_root)
        if not (str(target) == root or str(target).startswith(root + os.sep)):
            raise SystemExit(
                f"refusing to write outside the extraction root: {target}"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        self.outputs[relpath] = {"sha256": sha256_bytes(data), "bytes": len(data)}
        return target

    def write_json(self, relpath: str, obj: Any) -> Path:
        return self.write(relpath, json_bytes(obj))

    def write_text(self, relpath: str, text: str) -> Path:
        return self.write(relpath, text.encode("utf-8"))

    def note(self, message: str) -> None:
        """Record a NEEDS-VERIFY / ASSUME note once."""
        if message not in self.notes:
            self.notes.append(message)

    # -- manifest ------------------------------------------------------- #

    def write_manifest(self, command: str) -> None:
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "tool": tool_block(),
            "source": {
                "name": self.pdf_path.name,
                "sha256": self.source_sha256,
                "bytes": self.source_bytes,
            },
            "run": {
                "command": command,
                "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "argv": self.argv,
                "params": self.params,
                "precision": _PRECISION,
            },
            "notes": self.notes,
            # `outputs` is the reproducibility surface: two runs with the same
            # input and params must produce an identical map here (for text/ and
            # vector/ at minimum). `run` deliberately sits outside it.
            "outputs": dict(sorted(self.outputs.items())),
        }
        path = (self.out_dir / "manifest.json").resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(json_bytes(manifest))


def tool_block() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "version": TOOL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "pymupdf": fitz.pymupdf_version,
        "mupdf": fitz.mupdf_version,
        "python": ".".join(str(v) for v in sys.version_info[:3]),
    }


# --------------------------------------------------------------------------- #
# Coordinate authority
# --------------------------------------------------------------------------- #


def raw_box(doc: fitz.Document, xref: int, key: str) -> tuple[float, ...] | None:
    """Read a page box array in **PDF user space**, honouring inheritance.

    Returns ``None`` when the key is absent. Only /MediaBox and /CropBox walk the
    /Parent chain; the others are not inheritable per the PDF spec.
    """
    seen: set[int] = set()
    current = xref
    while current and current not in seen:
        seen.add(current)
        kind, value = doc.xref_get_key(current, key)
        if kind == "array":
            numbers = [float(tok) for tok in value.strip("[] \t\r\n").split()]
            if len(numbers) == 4:
                return tuple(numbers)
        if key not in _INHERITABLE:
            return None
        kind, value = doc.xref_get_key(current, "Parent")
        current = int(value.split()[0]) if kind == "xref" else 0
    return None


def _pdf_box_to_page_rect(box: Sequence[float], page: fitz.Page) -> fitz.Rect:
    """PDF user space box -> unrotated page space (the ``get_drawings()`` space)."""
    matrix = page.transformation_matrix
    corner_a = fitz.Point(box[0], box[1]) * matrix
    corner_b = fitz.Point(box[2], box[3]) * matrix
    rect = fitz.Rect(corner_a, corner_b)
    rect.normalize()
    return rect


@dataclass(frozen=True)
class MatFrame:
    """The single conversion from page geometry into the MAT frame.

    MAT frame: origin at the bottom-left corner of the chosen page box, ``+X``
    right, ``+Y`` up, millimetres. Every command in this module funnels through
    :meth:`pt_to_mm`; there is deliberately no second copy of this transform.
    """

    box_source: BoxSource
    box_pdf: tuple[float, float, float, float]
    box_page: tuple[float, float, float, float]
    rotation: int
    boxes_pdf: dict[str, tuple[float, float, float, float] | None]
    notes: tuple[str, ...]

    # -- construction ---------------------------------------------------- #

    @classmethod
    def from_page(cls, page: fitz.Page) -> MatFrame:
        doc = page.parent
        boxes = {key: raw_box(doc, page.xref, key) for key in _BOX_KEYS}
        notes: list[str] = []

        # ADR-003: TrimBox -> CropBox -> MediaBox.
        if boxes["TrimBox"] is not None:
            source: BoxSource = "TrimBox"
        elif boxes["CropBox"] is not None:
            source = "CropBox"
            notes.append(
                "NEEDS-VERIFY(S2): TrimBox missing, mat boundary derived from CropBox"
            )
        elif boxes["MediaBox"] is not None:
            source = "MediaBox"
            notes.append(
                "NEEDS-VERIFY(S2): TrimBox missing, mat boundary derived from MediaBox"
            )
        else:  # pragma: no cover - a PDF without any MediaBox is malformed
            source = "MediaBox"
            rect = page.rect
            boxes["MediaBox"] = (rect.x0, rect.y0, rect.x1, rect.y1)
            notes.append(
                "NEEDS-VERIFY(S2): no page box found at all, fell back to page.rect"
            )

        box_pdf = boxes[source]
        assert box_pdf is not None
        page_rect = _pdf_box_to_page_rect(box_pdf, page)
        return cls(
            box_source=source,
            box_pdf=(box_pdf[0], box_pdf[1], box_pdf[2], box_pdf[3]),
            box_page=(page_rect.x0, page_rect.y0, page_rect.x1, page_rect.y1),
            rotation=int(page.rotation),
            boxes_pdf=boxes,
            notes=tuple(notes),
        )

    # -- the transform ---------------------------------------------------- #

    def pt_to_mm(self, x: float, y: float) -> tuple[float, float]:
        """Unrotated page-space point (pt) -> MAT frame (mm).

        ``+Y`` flips: page space grows downward, the MAT frame grows upward.
        """
        x0, _y0, _x1, y1 = self.box_page
        return ((x - x0) * MM_PER_PT, (y1 - y) * MM_PER_PT)

    def mm_to_pt(self, x_mm: float, y_mm: float) -> tuple[float, float]:
        """MAT frame (mm) -> unrotated page space (pt). Inverse of :meth:`pt_to_mm`."""
        x0, _y0, _x1, y1 = self.box_page
        return (x_mm * PT_PER_MM + x0, y1 - y_mm * PT_PER_MM)

    def point_mm(self, point: Any) -> list[float]:
        return RS(self.pt_to_mm(point.x, point.y))

    def rect_to_mm(self, rect: Any) -> list[float]:
        """Page-space rect -> ``[x0, y0, x1, y1]`` mm, normalised so ``y0 < y1``."""
        ax, ay = self.pt_to_mm(rect.x0, rect.y0)
        bx, by = self.pt_to_mm(rect.x1, rect.y1)
        return RS((min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)))

    def mm_rect_to_page_rect(self, bbox_mm: Sequence[float]) -> fitz.Rect:
        """MAT-frame mm bbox -> unrotated page-space rect."""
        ax, ay = self.mm_to_pt(bbox_mm[0], bbox_mm[1])
        bx, by = self.mm_to_pt(bbox_mm[2], bbox_mm[3])
        rect = fitz.Rect(min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))
        return rect

    # -- reporting -------------------------------------------------------- #

    @property
    def width_mm(self) -> float:
        return (self.box_page[2] - self.box_page[0]) * MM_PER_PT

    @property
    def height_mm(self) -> float:
        return (self.box_page[3] - self.box_page[1]) * MM_PER_PT

    def to_dict(self) -> dict[str, Any]:
        boxes: dict[str, Any] = {}
        for key, value in self.boxes_pdf.items():
            if value is None:
                boxes[key] = None
                continue
            boxes[key] = {
                "pt": RS(value),
                "size_pt": RS((value[2] - value[0], value[3] - value[1])),
                "size_mm": RS(
                    (
                        (value[2] - value[0]) * MM_PER_PT,
                        (value[3] - value[1]) * MM_PER_PT,
                    )
                ),
            }
        media = self.boxes_pdf.get("MediaBox")
        used = self.box_pdf
        delta: list[float] | None = None
        if media is not None:
            delta = RS(
                (
                    used[0] - media[0],
                    used[1] - media[1],
                    used[2] - media[2],
                    used[3] - media[3],
                )
            )
        return {
            "semantic": "page_trim_frame",
            "note": (
                "origin = bottom-left of the box named by box_source; +X right, "
                "+Y up; units mm. For the game-mat PDF this frame IS the MAT frame."
            ),
            "box_source": self.box_source,
            "box_used_pt": RS(used),
            "box_used_mm_size": RS((self.width_mm, self.height_mm)),
            "rotation": self.rotation,
            "boxes_pdf_space": boxes,
            "used_minus_mediabox_pt": delta,
            "has_bleed": bool(delta is not None and any(abs(d) > 1e-6 for d in delta)),
            "notes": list(self.notes),
        }


# --------------------------------------------------------------------------- #
# Geometry helpers
# --------------------------------------------------------------------------- #


def flatten_cubic(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    segments: int = BEZIER_SEGMENTS,
) -> list[tuple[float, float]]:
    """Flatten a cubic Bezier into ``segments`` line segments (ADR-004).

    Fixed subdivision, never adaptive: an adaptive tolerance would make output
    depend on library version and break byte-identity between runs.
    """
    out: list[tuple[float, float]] = []
    for index in range(1, segments + 1):
        t = index / segments
        u = 1.0 - t
        a, b, c, d = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
        out.append(
            (
                a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1],
            )
        )
    return out


def polygon_area(points: Sequence[tuple[float, float]]) -> float:
    """Absolute shoelace area of a polygon."""
    if len(points) < 3:
        return 0.0
    array = np.asarray(points, dtype=float)
    x, y = array[:, 0], array[:, 1]
    return float(
        abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))) / 2.0
    )


def rgb_from_float(colour: Sequence[float] | None) -> tuple[list[float], str] | None:
    """PyMuPDF float RGB -> (rounded triple, ``#rrggbb``).

    ASSUME: the source may be CMYK with an ICC output intent; PyMuPDF converts
    without the profile, so these values are approximate. Recorded as such.
    """
    if colour is None:
        return None
    triple = [max(0.0, min(1.0, float(c))) for c in colour[:3]]
    while len(triple) < 3:
        triple.append(triple[-1] if triple else 0.0)
    hex_code = "#" + "".join(f"{int(round(c * 255)):02x}" for c in triple)
    return ([round(c, 6) for c in triple], hex_code)


# --------------------------------------------------------------------------- #
# probe
# --------------------------------------------------------------------------- #

_INLINE_IMAGE_RE = re.compile(rb"\bBI\b.*?\bID\b.*?\bEI\b", re.S)
_OPERATOR_RE = re.compile(
    rb"(?:(?<=[\s\]>)])|^)"
    rb"(re|m|l|c|v|y|h|f\*|f|F|B\*|B|b\*|b|S|s|n|W\*|W|Do|sh|cs|CS|scn|SCN|sc|SC"
    rb"|g|rg|k|G|RG|K|gs|cm|q|Q|BT|ET|Tj|TJ)"
    rb"(?=[\s\[/(<]|$)"
)


def strip_literals(data: bytes) -> bytes:
    """Blank out ``( ... )`` and ``< ... >`` literals in a content stream.

    Without this the census counts operator-shaped bytes *inside text strings* —
    a page whose prose contains " l " or " c " inflates the construction-op count
    and fakes a shortfall. Text-heavy documents (S1) are hit hardest.
    """
    out = bytearray()
    index, length, depth = 0, len(data), 0
    while index < length:
        char = data[index]
        if depth == 0:
            if char == 0x28:  # '(' opens a literal string
                depth = 1
                out.append(0x20)
            elif char == 0x3C:
                # '<<' is a dictionary delimiter; consume BOTH bytes, otherwise the
                # second '<' is mistaken for a hex string and swallows the dict.
                if index + 1 < length and data[index + 1] == 0x3C:
                    out.extend(b"<<")
                    index += 2
                    continue
                close = data.find(b">", index)  # a lone '<' opens a hex string
                if close < 0:
                    break
                out.append(0x20)
                index = close + 1
                continue
            else:
                out.append(char)
        else:
            if char == 0x5C:  # backslash escape consumes the next byte
                index += 2
                continue
            if char == 0x28:
                depth += 1
            elif char == 0x29:
                depth -= 1
                if depth == 0:
                    out.append(0x20)
        index += 1
    return bytes(out)


def content_op_census(page: fitz.Page) -> dict[str, int]:
    """Heuristic operator census straight from the decompressed content stream.

    This exists to cross-check ``get_drawings()``: if MuPDF silently declines to
    descend into a Form XObject, the census stays high while the drawings count
    collapses, and the mismatch is reported instead of passing unnoticed.
    """
    try:
        data = page.read_contents()
    except Exception:  # pragma: no cover - defensive
        return {}
    data = _INLINE_IMAGE_RE.sub(b" ", data)
    data = strip_literals(data)
    census: dict[str, int] = {}
    for match in _OPERATOR_RE.finditer(data):
        token = match.group(1).decode("latin-1")
        census[token] = census.get(token, 0) + 1
    return dict(sorted(census.items()))


def _document_colour_facts(doc: fitz.Document) -> dict[str, Any]:
    """Output intent, ICC channel count and spot colourspaces.

    Read from the raw file because PyMuPDF exposes no direct accessor, and the
    PDF/X output intent is exactly what makes RGB values an ``ASSUME:``.
    """
    facts: dict[str, Any] = {
        "output_intent_subtypes": [],
        "output_condition_identifiers": [],
        "icc_component_counts": [],
        "has_separation_colorspace": False,
        "separation_count": 0,
        "devicecmyk_refs": 0,
        "devicergb_refs": 0,
    }
    try:
        raw = Path(doc.name).read_bytes() if doc.name else b""
    except Exception:  # pragma: no cover - defensive
        return facts
    facts["output_intent_subtypes"] = sorted(
        {m.decode("latin-1") for m in re.findall(rb"/(GTS_PDFX|GTS_PDFA1|ISO_PDFE1)", raw)}
    )
    facts["output_condition_identifiers"] = sorted(
        {
            m.decode("latin-1", "replace")[:80]
            for m in re.findall(rb"/OutputConditionIdentifier\s*\(([^)]{0,80})\)", raw)
        }
    )
    facts["icc_component_counts"] = sorted(
        {int(m) for m in re.findall(rb"/N\s+(\d)\b", raw)}
    )
    facts["separation_count"] = len(re.findall(rb"/Separation\b", raw))
    facts["has_separation_colorspace"] = facts["separation_count"] > 0
    facts["devicecmyk_refs"] = len(re.findall(rb"/DeviceCMYK\b", raw))
    facts["devicergb_refs"] = len(re.findall(rb"/DeviceRGB\b", raw))
    return facts


def _count_image_xobjects(doc: fitz.Document) -> int:
    """Total image XObjects in the file, including ones no page draws."""
    total = 0
    for xref in range(1, doc.xref_length()):
        try:
            if doc.xref_get_key(xref, "Subtype")[1] == "/Image":
                total += 1
        except Exception:  # pragma: no cover - defensive
            continue
    return total


def cmd_probe(ctx: RunContext, doc: fitz.Document, args: argparse.Namespace) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    referenced_images: set[int] = set()
    # Collapse per-page findings into one note each: a 177-page document would
    # otherwise emit 177 identical lines and bury the signal.
    frame_notes: dict[str, list[int]] = {}
    shortfall_pages: list[int] = []

    for number, page in enumerate(doc, start=1):
        frame = MatFrame.from_page(page)
        for note in frame.notes:
            frame_notes.setdefault(note, []).append(number)

        text = page.get_text("text")
        fonts = sorted(
            {
                f"{item[3]} ({'embedded' if item[1] else 'not-embedded'})"
                for item in page.get_fonts(full=True)
            }
        )
        images = []
        for item in page.get_images(full=True):
            xref = int(item[0])
            referenced_images.add(xref)
            images.append(
                {
                    "xref": xref,
                    "width_px": int(item[2]),
                    "height_px": int(item[3]),
                    "bpc": int(item[4]),
                    "colorspace": str(item[5]),
                    "filter": str(item[8]),
                    "smask_xref": int(item[1]),
                }
            )
        images.sort(key=lambda entry: entry["xref"])

        drawings = page.get_drawings()
        extended = page.get_drawings(extended=True)
        paint_items = sum(len(entry.get("items", ())) for entry in drawings)
        # Clip paths contribute construction ops to the content stream but are
        # absent from non-extended get_drawings(), so the census must be compared
        # against the EXTENDED item count or every clipped page fakes a shortfall.
        item_total = sum(len(entry.get("items", ())) for entry in extended)
        census = content_op_census(page)
        construction_ops = sum(census.get(op, 0) for op in ("re", "l", "c", "v", "y"))
        paint_ops = sum(
            census.get(op, 0)
            for op in ("f", "f*", "F", "B", "B*", "b", "b*", "S", "s")
        )
        # PRIMARY signal. Every painting operator should surface as exactly one
        # get_drawings() entry. If MuPDF fails to descend into a Form XObject the
        # painting ops stay in the census while the entries vanish, and the ratio
        # collapses. This is the failure this cross-check exists to catch.
        paint_ratio = (len(drawings) / paint_ops) if paint_ops else None
        # SECONDARY, informational only: MuPDF collapses `m l l l h` quads into a
        # single `re`/`qu` item, so this ratio sits well below 1.0 on rectangle-
        # heavy pages without anything being wrong. Never trigger on it.
        item_ratio = (item_total / construction_ops) if construction_ops else None
        cross_check = {
            "get_drawings_paths": len(drawings),
            "get_drawings_extended_entries": len(extended),
            "get_drawings_paint_items": paint_items,
            "get_drawings_items": item_total,
            "content_stream_construction_ops": construction_ops,
            "content_stream_paint_ops": paint_ops,
            "paths_per_paint_op": R(paint_ratio) if paint_ratio is not None else None,
            "items_per_construction_op": R(item_ratio) if item_ratio is not None else None,
            "items_per_construction_op_note": (
                "informational only - MuPDF collapses m/l/l/l/h quads into one "
                "`re` item, so values well below 1.0 are normal"
            ),
            "verdict": "ok",
        }
        if paint_ops >= 20 and (paint_ratio is None or paint_ratio < 0.9):
            cross_check["verdict"] = "shortfall"
            shortfall_pages.append(number)

        pages.append(
            {
                "page": number,
                "frame": frame.to_dict(),
                "rotation": int(page.rotation),
                "page_rect_pt": RS(
                    (page.rect.x0, page.rect.y0, page.rect.x1, page.rect.y1)
                ),
                "text": {
                    "chars": len(text),
                    "stripped_chars": len(text.strip()),
                    "has_text_layer": bool(text.strip()),
                    "blocks": len(page.get_text("blocks")),
                },
                "fonts": fonts,
                "font_count": len(fonts),
                "images": {"count": len(images), "native": images},
                "drawings": {
                    "paths": len(drawings),
                    "items": item_total,
                    "content_stream_ops": census,
                    "cross_check": cross_check,
                },
            }
        )

    def _page_span(numbers: Sequence[int]) -> str:
        head = ", ".join(str(n) for n in numbers[:6])
        return head + (f", ... (+{len(numbers) - 6} more)" if len(numbers) > 6 else "")

    for note, numbers in sorted(frame_notes.items()):
        ctx.note(
            f"{note} [{len(numbers)}/{doc.page_count} page(s): {_page_span(numbers)}]"
        )
    if shortfall_pages:
        ctx.note(
            f"NEEDS-VERIFY: get_drawings() returned fewer than 0.9 entries per "
            f"content-stream painting operator on {len(shortfall_pages)}/"
            f"{doc.page_count} page(s) [{_page_span(shortfall_pages)}] - vector "
            "extraction may be incomplete on those pages"
        )

    total_image_xobjects = _count_image_xobjects(doc)
    report = {
        "schema_version": SCHEMA_VERSION,
        "tool": tool_block(),
        "source": {
            "name": ctx.pdf_path.name,
            "sha256": ctx.source_sha256,
            "bytes": ctx.source_bytes,
        },
        "document": {
            "page_count": doc.page_count,
            "pdf_version": doc.metadata.get("format") if doc.metadata else None,
            "is_encrypted": bool(doc.is_encrypted),
            "is_repaired": bool(getattr(doc, "is_repaired", False)),
            "xref_length": doc.xref_length(),
            "metadata": {
                key: value
                for key, value in sorted((doc.metadata or {}).items())
                if value
            },
            "image_xobjects_total": total_image_xobjects,
            "image_xobjects_page_referenced": len(referenced_images),
            "image_xobjects_orphaned": max(
                0, total_image_xobjects - len(referenced_images)
            ),
            "colour": _document_colour_facts(doc),
        },
        "pages": pages,
    }

    colour = report["document"]["colour"]
    if colour["devicecmyk_refs"] > 0 or 4 in colour["icc_component_counts"]:
        ctx.note(
            "ASSUME: source is CMYK with an ICC/output-intent profile; every RGB "
            "value emitted by this tool is a profile-less conversion and is "
            "approximate. Use `render --colorspace cmyk` to sample true CMYK."
        )
    if colour["has_separation_colorspace"]:
        ctx.note(
            f"ASSUME: {colour['separation_count']} /Separation (spot) colourspace "
            "reference(s) present; spot colours do not round-trip through RGB and "
            "may be a technical layer rather than artwork."
        )

    ctx.write_json("probe.json", report)
    ctx.params["probe"] = {}
    return report


# --------------------------------------------------------------------------- #
# text
# --------------------------------------------------------------------------- #


def _gfm_table(rows: Sequence[Sequence[str | None]]) -> str:
    cleaned = [
        [
            ("" if cell is None else str(cell))
            .replace("\n", " ")
            .replace("|", r"\|")
            .strip()
            for cell in row
        ]
        for row in rows
    ]
    cleaned = [row for row in cleaned if any(cell for cell in row)]
    if not cleaned:
        return ""
    width = max(len(row) for row in cleaned)
    cleaned = [row + [""] * (width - len(row)) for row in cleaned]
    header, body = cleaned[0], cleaned[1:]
    lines = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join(["---"] * width) + "|",
    ]
    lines += ["| " + " | ".join(row) + " |" for row in body]
    return "\n".join(lines)


def _page_markdown(
    page: fitz.Page, number: int, use_pdfplumber_tables: bool
) -> tuple[str, str, int]:
    """Return (markdown, table_engine, table_count) for one page."""
    table_rects: list[fitz.Rect] = []
    renderables: list[tuple[float, float, str]] = []
    engine = "none"

    try:
        finder = page.find_tables()
        tables = list(finder.tables)
    except Exception:
        tables = []
    if tables:
        engine = "pymupdf"
        for table in tables:
            rect = fitz.Rect(table.bbox)
            table_rects.append(rect)
            markdown = _gfm_table(table.extract())
            if markdown:
                renderables.append((rect.y0, rect.x0, markdown))
    elif use_pdfplumber_tables:
        extracted = _pdfplumber_tables(page)
        if extracted:
            engine = "pdfplumber"
            for rect_tuple, rows in extracted:
                rect = fitz.Rect(rect_tuple)
                table_rects.append(rect)
                markdown = _gfm_table(rows)
                if markdown:
                    renderables.append((rect.y0, rect.x0, markdown))

    for block in page.get_text("blocks", sort=True):
        x0, y0, x1, y1, content = block[0], block[1], block[2], block[3], block[4]
        if not isinstance(content, str) or not content.strip():
            continue
        centre = fitz.Point((x0 + x1) / 2, (y0 + y1) / 2)
        if any(rect.contains(centre) for rect in table_rects):
            continue  # already emitted as part of a table
        renderables.append((y0, x0, content.strip()))

    renderables.sort(key=lambda item: (round(item[0], 2), round(item[1], 2)))
    body = "\n\n".join(item[2] for item in renderables)
    header = f"# Page {number}\n"
    return (f"{header}\n{body}\n" if body else f"{header}\n_(no text layer)_\n"), engine, len(table_rects)


def _pdfplumber_tables(page: fitz.Page) -> list[tuple[tuple[float, ...], list[list[str | None]]]]:
    """Fallback table extraction (ADR-006). Returns [(bbox, rows)]."""
    try:
        import pdfplumber
    except Exception:  # pragma: no cover - dependency guaranteed by pyproject
        return []
    try:
        with pdfplumber.open(page.parent.name) as plumb:
            plumb_page = plumb.pages[page.number]
            found = plumb_page.find_tables()
            return [(tuple(t.bbox), t.extract()) for t in found]
    except Exception:
        return []


def cmd_text(ctx: RunContext, doc: fitz.Document, args: argparse.Namespace) -> dict[str, Any]:
    spans_pages: list[dict[str, Any]] = []
    engines: dict[str, str] = {}
    table_counts: dict[str, int] = {}

    for number, page in enumerate(doc, start=1):
        frame = MatFrame.from_page(page)

        # Pass A - spans with geometry preserved, in the MAT frame.
        raw = page.get_text("dict")
        blocks: list[dict[str, Any]] = []
        for block in raw.get("blocks", []):
            if block.get("type") != 0:
                continue
            lines: list[dict[str, Any]] = []
            for line in block.get("lines", []):
                spans: list[dict[str, Any]] = []
                for span in line.get("spans", []):
                    colour_int = int(span.get("color", 0))
                    spans.append(
                        {
                            "text": span.get("text", ""),
                            "font": span.get("font", ""),
                            "size_pt": R(span.get("size", 0.0)),
                            "flags": int(span.get("flags", 0)),
                            "color_hex": f"#{colour_int & 0xFFFFFF:06x}",
                            "bbox_mm": frame.rect_to_mm(fitz.Rect(span["bbox"])),
                            "origin_mm": RS(
                                frame.pt_to_mm(*span.get("origin", (0.0, 0.0)))
                            ),
                        }
                    )
                if spans:
                    lines.append(
                        {
                            "bbox_mm": frame.rect_to_mm(fitz.Rect(line["bbox"])),
                            "dir": RS(line.get("dir", (1.0, 0.0))),
                            "spans": spans,
                        }
                    )
            if lines:
                blocks.append(
                    {
                        "bbox_mm": frame.rect_to_mm(fitz.Rect(block["bbox"])),
                        "lines": lines,
                    }
                )
        spans_pages.append({"page": number, "blocks": blocks})

        # Pass B - flattened reading-order markdown, tables as GFM.
        markdown, engine, table_count = _page_markdown(
            page, number, use_pdfplumber_tables=args.fallback
        )
        ctx.write_text(f"text/page_{number:03d}.md", markdown)
        engines[str(number)] = engine
        table_counts[str(number)] = table_count

    ctx.write_json(
        "text/spans.json",
        {
            "schema_version": SCHEMA_VERSION,
            "source_sha256": ctx.source_sha256,
            "frame_note": "all bboxes are MAT-frame mm; see probe.json for the frame",
            "pages": spans_pages,
        },
    )
    ctx.params["text"] = {
        "fallback_pdfplumber": bool(args.fallback),
        "table_engine_by_page": engines,
        "tables_by_page": table_counts,
    }
    return {"engines": engines, "tables": table_counts}


# --------------------------------------------------------------------------- #
# images
# --------------------------------------------------------------------------- #


def _derotate(page: fitz.Page, rect: fitz.Rect) -> fitz.Rect:
    """Rotated page space -> unrotated page space (the MatFrame input space)."""
    if not page.rotation:
        return rect
    out = fitz.Rect(rect) * page.derotation_matrix
    out.normalize()
    return out


def _encode_image(doc: fitz.Document, xref: int) -> tuple[bytes, str, str]:
    """Encode one image XObject, never dropping it.

    PNG carries only gray/RGB. S2 uses ``Separation(DeviceCMYK, All)`` images —
    a 1-channel spot colourspace PyMuPDF refuses to write as PNG — so a plain
    ``tobytes("png")`` silently loses them. Escalate instead:

    1. pixmap -> PNG (the common case, and CMYK converts cleanly)
    2. force the pixmap through RGB, then PNG
    3. fall back to the embedded stream in its native encoding, losing nothing

    Returns ``(payload, suffix, method)``.
    """
    pixmap = fitz.Pixmap(doc, xref)
    if pixmap.colorspace is None or pixmap.n - pixmap.alpha > 3:
        pixmap = fitz.Pixmap(fitz.csRGB, pixmap)
    try:
        return (pixmap.tobytes("png"), "png", "pixmap_png")
    except Exception:
        pass
    try:
        return (fitz.Pixmap(fitz.csRGB, pixmap).tobytes("png"), "png", "rgb_png")
    except Exception:
        pass
    info = doc.extract_image(xref)
    return (info["image"], str(info["ext"]), "native_" + str(info["ext"]))


def cmd_images(ctx: RunContext, doc: fitz.Document, args: argparse.Namespace) -> dict[str, Any]:
    saved = 0
    skipped = 0
    failed: list[dict[str, Any]] = []
    fallback_used: dict[str, int] = {}

    for number, page in enumerate(doc, start=1):
        frame = MatFrame.from_page(page)
        entries = sorted(page.get_images(full=True), key=lambda item: int(item[0]))
        for index, item in enumerate(entries, start=1):
            xref = int(item[0])
            width_px, height_px = int(item[2]), int(item[3])
            if width_px * height_px < args.min_pixels:
                skipped += 1
                continue

            stem = f"img/p{number:03d}_{index:04d}"  # ADR-002: 4-digit index
            try:
                payload, suffix, method = _encode_image(doc, xref)
            except Exception as exc:
                failed.append({"page": number, "xref": xref, "error": str(exc)})
                continue

            ctx.write(f"{stem}.{suffix}", payload)
            saved += 1
            if method != "pixmap_png":
                fallback_used[method] = fallback_used.get(method, 0) + 1

            placements = []
            try:
                for rect in page.get_image_rects(xref):
                    placements.append(frame.rect_to_mm(_derotate(page, fitz.Rect(rect))))
            except Exception:
                placements = []

            native_ppmm = None
            if placements:
                box = placements[0]
                width_mm = max(box[2] - box[0], 1e-9)
                height_mm = max(box[3] - box[1], 1e-9)
                native_ppmm = {
                    "x": R(width_px / width_mm),
                    "y": R(height_px / height_mm),
                }

            ctx.write_json(
                f"{stem}.json",
                {
                    "schema_version": SCHEMA_VERSION,
                    "page": number,
                    "index": index,
                    "xref": xref,
                    "smask_xref": int(item[1]),
                    "width_px": width_px,
                    "height_px": height_px,
                    "bpc": int(item[4]),
                    "colorspace": str(item[5]),
                    "filter": str(item[8]),
                    "placement_mm": placements,
                    "placement_count": len(placements),
                    "native_px_per_mm": native_ppmm,
                    "format": suffix,
                    "encode_method": method,
                    "image_sha256": sha256_bytes(payload),
                },
            )

    if failed:
        ctx.note(
            f"NEEDS-VERIFY: {len(failed)} embedded image(s) could not be decoded; "
            "see params.images.failed in manifest.json"
        )
    for method, count in sorted(fallback_used.items()):
        ctx.note(
            f"ASSUME: {count} image(s) were written via the '{method}' fallback "
            "because their colourspace (e.g. Separation/DeviceN spot) has no PNG "
            "representation; pixel values are NOT sRGB and must not be colour-sampled "
            "without checking the source colourspace in the sidecar JSON."
        )
    ctx.params["images"] = {
        "min_pixels": args.min_pixels,
        "saved": saved,
        "skipped_below_min_pixels": skipped,
        "encode_methods": dict(sorted(fallback_used.items())),
        "failed": failed,
    }
    return {"saved": saved, "skipped": skipped, "failed": len(failed)}


# --------------------------------------------------------------------------- #
# render
# --------------------------------------------------------------------------- #

_COLORSPACES = {"rgb": fitz.csRGB, "gray": fitz.csGRAY, "cmyk": fitz.csCMYK}


def _parse_bbox(value: str | None) -> list[float] | None:
    if not value:
        return None
    parts = [float(token) for token in value.replace(" ", "").split(",")]
    if len(parts) != 4:
        raise SystemExit("--bbox needs exactly four comma-separated mm values")
    return [min(parts[0], parts[2]), min(parts[1], parts[3]),
            max(parts[0], parts[2]), max(parts[1], parts[3])]


def cmd_render(ctx: RunContext, doc: fitz.Document, args: argparse.Namespace) -> dict[str, Any]:
    bbox_mm = _parse_bbox(args.bbox)
    px_per_mm = float(args.px_per_mm)
    zoom = px_per_mm * MM_PER_PT  # pixels per point
    colorspace = _COLORSPACES[args.colorspace]
    pages = args.pages_list if args.pages_list else list(range(1, doc.page_count + 1))
    rendered: list[dict[str, Any]] = []

    for number in pages:
        page = doc[number - 1]
        frame = MatFrame.from_page(page)

        clip_page = (
            frame.mm_rect_to_page_rect(bbox_mm)
            if bbox_mm
            else fitz.Rect(*frame.box_page)
        )
        # get_pixmap clips in ROTATED page space; MatFrame works unrotated.
        clip = fitz.Rect(clip_page)
        if page.rotation:
            clip = clip * page.rotation_matrix
            clip.normalize()

        megapixels = (clip.width * zoom) * (clip.height * zoom) / 1e6
        if megapixels > args.max_mpix and not args.force:
            raise SystemExit(
                f"refusing to render {megapixels:.1f} MPix (limit {args.max_mpix} "
                f"MPix). Lower --px-per-mm, pass --bbox, or use --force."
            )

        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(zoom, zoom), clip=clip, colorspace=colorspace, alpha=False
        )

        tag = args.name or (
            "full" if bbox_mm is None else
            f"bbox_{int(bbox_mm[0])}_{int(bbox_mm[1])}_{int(bbox_mm[2])}_{int(bbox_mm[3])}"
        )
        scale = f"{px_per_mm:g}".replace(".", "p")
        base = f"render/{tag}_{scale}pxmm"
        if doc.page_count > 1:
            base = f"render/p{number:03d}_{tag}_{scale}pxmm"

        if args.colorspace == "cmyk":
            # PNG cannot carry 4 channels; TIFF can. Pillow earns its place here.
            from io import BytesIO

            from PIL import Image

            image = Image.frombytes(
                "CMYK", (pixmap.width, pixmap.height), pixmap.samples
            )
            buffer = BytesIO()
            image.save(buffer, format="TIFF")
            payload, suffix = buffer.getvalue(), "tif"
        else:
            payload, suffix = pixmap.tobytes("png"), "png"

        ctx.write(f"{base}.{suffix}", payload)

        origin_mm = frame.rect_to_mm(clip_page)
        sidecar = {
            "schema_version": SCHEMA_VERSION,
            "page": number,
            "px_per_mm": R(px_per_mm),
            "dpi_equivalent": R(px_per_mm * 25.4),
            "origin_mm": [origin_mm[0], origin_mm[3]],
            "origin_mm_note": "MAT-frame mm coordinate of the TOP-LEFT pixel",
            "bbox_mm": origin_mm,
            "trimbox_mm": RS((0.0, 0.0, frame.width_mm, frame.height_mm)),
            "box_source": frame.box_source,
            "colorspace": args.colorspace.upper(),
            "channels": pixmap.n,
            "width_px": pixmap.width,
            "height_px": pixmap.height,
            "megapixels": R(pixmap.width * pixmap.height / 1e6),
            "format": suffix,
            "image_sha256": sha256_bytes(payload),
        }
        if args.colorspace != "rgb":
            sidecar["colour_note"] = (
                "ASSUME: CMYK values here are MuPDF's conversion, not an ICC "
                "transform through the document's output intent."
            )
        ctx.write_json(f"{base}.json", sidecar)
        rendered.append(sidecar)

    ctx.params["render"] = {
        "px_per_mm": R(px_per_mm),
        "bbox_mm": bbox_mm,
        "colorspace": args.colorspace,
        "max_mpix": args.max_mpix,
        "pages": pages if args.pages_list else "all",
        "outputs": len(rendered),
    }
    return {"rendered": len(rendered)}


# --------------------------------------------------------------------------- #
# vector
# --------------------------------------------------------------------------- #


def _path_points_and_items(
    entry: dict[str, Any], frame: MatFrame
) -> tuple[list[dict[str, Any]], list[tuple[float, float]]]:
    """Convert one get_drawings entry into mm items plus a flattened polygon."""
    items: list[dict[str, Any]] = []
    polygon: list[tuple[float, float]] = []
    cursor: tuple[float, float] | None = None

    for item in entry.get("items", ()):
        op = item[0]
        if op == "re":
            rect = item[1]
            corners = [
                frame.pt_to_mm(rect.x0, rect.y0),
                frame.pt_to_mm(rect.x1, rect.y0),
                frame.pt_to_mm(rect.x1, rect.y1),
                frame.pt_to_mm(rect.x0, rect.y1),
            ]
            items.append(
                {
                    "op": "re",
                    "rect_mm": frame.rect_to_mm(rect),
                    "orientation": int(item[2]) if len(item) > 2 else 1,
                }
            )
            polygon.extend(corners)
            cursor = corners[-1]
        elif op == "l":
            p1 = frame.pt_to_mm(item[1].x, item[1].y)
            p2 = frame.pt_to_mm(item[2].x, item[2].y)
            items.append({"op": "l", "p1_mm": RS(p1), "p2_mm": RS(p2)})
            if cursor is None:
                polygon.append(p1)
            polygon.append(p2)
            cursor = p2
        elif op == "c":
            pts = [frame.pt_to_mm(p.x, p.y) for p in item[1:5]]
            items.append(
                {
                    "op": "c",
                    "p1_mm": RS(pts[0]),
                    "p2_mm": RS(pts[1]),
                    "p3_mm": RS(pts[2]),
                    "p4_mm": RS(pts[3]),
                }
            )
            if cursor is None:
                polygon.append(pts[0])
            polygon.extend(flatten_cubic(pts[0], pts[1], pts[2], pts[3]))
            cursor = pts[3]
        elif op == "qu":
            quad = item[1]
            corners = [
                frame.pt_to_mm(quad.ul.x, quad.ul.y),
                frame.pt_to_mm(quad.ur.x, quad.ur.y),
                frame.pt_to_mm(quad.lr.x, quad.lr.y),
                frame.pt_to_mm(quad.ll.x, quad.ll.y),
            ]
            items.append({"op": "qu", "quad_mm": [RS(c) for c in corners]})
            polygon.extend(corners)
            cursor = corners[-1]
        else:  # pragma: no cover - PyMuPDF emits only the four ops above
            items.append({"op": str(op)})

    return items, polygon


def cmd_vector(ctx: RunContext, doc: fitz.Document, args: argparse.Namespace) -> dict[str, Any]:
    all_paths: list[dict[str, Any]] = []
    pages_meta: list[dict[str, Any]] = []
    fills: dict[str, dict[str, Any]] = {}

    for number, page in enumerate(doc, start=1):
        frame = MatFrame.from_page(page)
        entries = page.get_drawings(extended=True)  # ADR-009: keep clips

        union: list[float] | None = None
        page_paths = 0
        painted = 0
        inside_box = 0

        for entry in entries:
            items, polygon = _path_points_and_items(entry, frame)
            rect = entry.get("rect")
            bbox = frame.rect_to_mm(rect) if rect is not None else None
            fill = rgb_from_float(entry.get("fill"))
            stroke = rgb_from_float(entry.get("color"))
            area = R(polygon_area(polygon))
            width_pt = entry.get("width")

            record: dict[str, Any] = {
                "page": number,
                "seqno": int(entry.get("seqno", -1)),
                "level": int(entry.get("level", 0)),
                "type": str(entry.get("type", "")),
                "bbox_mm": bbox,
                "area_mm2": area,
                "bbox_area_mm2": (
                    R((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) if bbox else 0.0
                ),
                "fill_rgb": fill[0] if fill else None,
                "fill_hex": fill[1] if fill else None,
                "stroke_rgb": stroke[0] if stroke else None,
                "stroke_hex": stroke[1] if stroke else None,
                "width_mm": R(float(width_pt) * MM_PER_PT) if width_pt else None,
                "even_odd": bool(entry.get("even_odd", False)),
                "close_path": bool(entry.get("closePath", False)),
                "item_count": len(items),
                "items": items,
            }
            if entry.get("type") == "clip":
                scissor = entry.get("scissor")
                record["scissor_mm"] = (
                    frame.rect_to_mm(scissor) if scissor is not None else None
                )

            all_paths.append(record)
            page_paths += 1

            if bbox is not None and entry.get("type") != "clip":
                union = (
                    list(bbox)
                    if union is None
                    else [
                        min(union[0], bbox[0]),
                        min(union[1], bbox[1]),
                        max(union[2], bbox[2]),
                        max(union[3], bbox[3]),
                    ]
                )
                painted += 1
                if (
                    bbox[0] >= -_BOX_TOLERANCE_MM
                    and bbox[1] >= -_BOX_TOLERANCE_MM
                    and bbox[2] <= frame.width_mm + _BOX_TOLERANCE_MM
                    and bbox[3] <= frame.height_mm + _BOX_TOLERANCE_MM
                ):
                    inside_box += 1

            if fill is not None and entry.get("type") in ("f", "fs"):
                bucket = fills.setdefault(
                    fill[1],
                    {
                        "fill_hex": fill[1],
                        "fill_rgb": fill[0],
                        "path_count": 0,
                        "total_area_mm2": 0.0,
                        "bbox_mm": None,
                        "largest": None,
                        "pages": set(),
                    },
                )
                bucket["path_count"] += 1
                bucket["total_area_mm2"] += area
                bucket["pages"].add(number)
                if bbox is not None:
                    current = bucket["bbox_mm"]
                    bucket["bbox_mm"] = (
                        list(bbox)
                        if current is None
                        else [
                            min(current[0], bbox[0]),
                            min(current[1], bbox[1]),
                            max(current[2], bbox[2]),
                            max(current[3], bbox[3]),
                        ]
                    )
                if bucket["largest"] is None or area > bucket["largest"]["area_mm2"]:
                    bucket["largest"] = {
                        "seqno": record["seqno"],
                        "area_mm2": area,
                        "bbox_mm": bbox,
                        "page": number,
                    }

        # Self-check on the MAT-frame transform. A wrong transform yields
        # coordinates that look entirely plausible in isolation, so this is the
        # only cheap way to catch it on a real file.
        #
        # The union bbox alone is NOT a usable test: PDF artwork legitimately
        # extends past the trim and is clipped at render time, so a few off-page
        # decorative paths push the union outside the box while the transform is
        # perfectly correct. Two signals that do discriminate:
        #   * no overlap at all  -> the transform is certainly wrong
        #   * most paths outside -> the transform is probably wrong
        mat = [0.0, 0.0, R(frame.width_mm), R(frame.height_mm)]
        share_inside = (inside_box / painted) if painted else None
        overlaps = union is None or (
            union[2] > 0
            and union[3] > 0
            and union[0] < frame.width_mm
            and union[1] < frame.height_mm
        )
        suspect = (not overlaps) or (
            share_inside is not None and painted >= 20 and share_inside < 0.6
        )
        if suspect:
            ctx.note(
                f"NEEDS-VERIFY: page {number} MAT-frame self-check failed - "
                f"{inside_box}/{painted} painted paths fall inside the {mat} mm page "
                f"box (union {union}). Verify the transform before trusting these "
                "coordinates."
            )
        pages_meta.append(
            {
                "page": number,
                "frame": frame.to_dict(),
                "path_count": page_paths,
                "self_check": {
                    "union_bbox_mm": union,
                    "page_box_mm": mat,
                    "painted_paths": painted,
                    "painted_paths_inside_box": inside_box,
                    "share_inside_box": R(share_inside) if share_inside is not None else None,
                    "union_overlaps_page_box": bool(overlaps),
                    "verdict": "suspect" if suspect else "ok",
                    "tolerance_mm": _BOX_TOLERANCE_MM,
                    "note": (
                        "Paths outside the page box are normal: PDF artwork may "
                        "extend past the trim and is clipped at render time. Only a "
                        "non-overlapping union, or a majority of paths outside, "
                        "indicates a broken transform."
                    ),
                },
            }
        )

    ctx.write_json(
        "vector/drawings.json",
        {
            "schema_version": SCHEMA_VERSION,
            "source_sha256": ctx.source_sha256,
            "bezier_segments": BEZIER_SEGMENTS,
            "colour_note": (
                "ASSUME: fill_rgb/stroke_rgb are MuPDF conversions. If the source "
                "is CMYK with an output intent they are approximate."
            ),
            "clip_note": (
                "type='clip' entries are retained (ADR-009). Path geometry is "
                "reported BEFORE clipping, so a clipped path's area_mm2 can exceed "
                "the area actually visible."
            ),
            "pages": pages_meta,
            "paths": all_paths,
        },
    )

    inventory = []
    for bucket in fills.values():
        largest = bucket["largest"]
        inventory.append(
            {
                "fill_hex": bucket["fill_hex"],
                "fill_rgb": bucket["fill_rgb"],
                "path_count": bucket["path_count"],
                "total_area_mm2": R(bucket["total_area_mm2"]),
                "bbox_mm": bucket["bbox_mm"],
                "bbox_size_mm": (
                    RS(
                        (
                            bucket["bbox_mm"][2] - bucket["bbox_mm"][0],
                            bucket["bbox_mm"][3] - bucket["bbox_mm"][1],
                        )
                    )
                    if bucket["bbox_mm"]
                    else None
                ),
                "largest_path": largest,
                "pages": sorted(bucket["pages"]),
            }
        )
    inventory.sort(key=lambda row: (-row["total_area_mm2"], row["fill_hex"]))

    ctx.write_json(
        "vector/fills_by_colour.json",
        {
            "schema_version": SCHEMA_VERSION,
            "source_sha256": ctx.source_sha256,
            "colour_note": (
                "ASSUME: RGB from a profile-less CMYK conversion. Do NOT map these "
                "to canonical area IDs without a CMYK render cross-check."
            ),
            "area_note": (
                "total_area_mm2 sums UNCLIPPED path areas; a clipped path "
                "contributes more than it visibly covers."
            ),
            "distinct_fills": len(inventory),
            "fills": inventory,
        },
    )

    ctx.params["vector"] = {
        "paths": len(all_paths),
        "distinct_fills": len(inventory),
        "bezier_segments": BEZIER_SEGMENTS,
    }
    return {"paths": len(all_paths), "fills": len(inventory)}


# --------------------------------------------------------------------------- #
# consolidated markdown
# --------------------------------------------------------------------------- #


def write_consolidated(ctx: RunContext, doc: fitz.Document) -> None:
    """One page-anchored markdown file: text plus inline references to images."""
    images_by_page: dict[int, list[str]] = {}
    for relpath in ctx.outputs:
        if relpath.startswith("img/") and relpath.endswith(".png"):
            page = int(relpath[len("img/p"):][:3])
            images_by_page.setdefault(page, []).append(relpath)

    lines = [
        f"# {ctx.pdf_path.name}",
        "",
        f"Generated by `{TOOL_NAME}` v{TOOL_VERSION}. Do not hand-edit — re-run the tool.",
        "",
        f"- source sha256: `{ctx.source_sha256}`",
        f"- pages: {doc.page_count}",
        "",
        "---",
        "",
    ]
    for number in range(1, doc.page_count + 1):
        relpath = f"text/page_{number:03d}.md"
        body = ""
        target = ctx.out_dir / relpath
        if target.exists():
            body = target.read_text(encoding="utf-8")
            body = "\n".join(body.splitlines()[1:]).strip()
        lines.append(f'<a id="page-{number:03d}"></a>')
        lines.append("")
        lines.append(f"## Page {number}")
        lines.append("")
        lines.append(body if body else "_(no text layer)_")
        lines.append("")
        page_images = sorted(images_by_page.get(number, []))
        if page_images:
            lines.append(f"<details><summary>{len(page_images)} embedded image(s)</summary>")
            lines.append("")
            for relpath in page_images:
                lines.append(f"- `{relpath}` (sidecar: `{relpath[:-4]}.json`)")
            lines.append("")
            lines.append("</details>")
            lines.append("")
        lines.append("---")
        lines.append("")

    ctx.write_text(f"{ctx.pdf_path.stem}.md", "\n".join(lines))


# --------------------------------------------------------------------------- #
# Human-readable probe table
# --------------------------------------------------------------------------- #


def print_probe_table(report: dict[str, Any]) -> None:
    doc = report["document"]
    source = report["source"]
    print(f"\n=== {source['name']} ===")
    print(f"  sha256      {source['sha256']}")
    print(f"  bytes       {source['bytes']:,}")
    print(f"  format      {doc['pdf_version']}  pages={doc['page_count']}")
    colour = doc["colour"]
    print(
        f"  colour      output_intent={colour['output_intent_subtypes'] or '-'} "
        f"icc_N={colour['icc_component_counts'] or '-'} "
        f"cmyk_refs={colour['devicecmyk_refs']} separations={colour['separation_count']}"
    )
    print(
        f"  images      {doc['image_xobjects_total']} xobjects "
        f"({doc['image_xobjects_page_referenced']} page-referenced, "
        f"{doc['image_xobjects_orphaned']} orphaned)"
    )
    header = (
        f"  {'page':>4} {'box':>9} {'size mm':>19} {'rot':>4} "
        f"{'text':>6} {'fonts':>6} {'imgs':>6} {'paths':>7} {'items':>7} {'xcheck':>9}"
    )
    print(header)
    print("  " + "-" * (len(header) - 2))
    for page in report["pages"][:12]:
        frame = page["frame"]
        size = frame["box_used_mm_size"]
        print(
            f"  {page['page']:>4} {frame['box_source']:>9} "
            f"{size[0]:>9.3f} x {size[1]:<7.3f} {page['rotation']:>4} "
            f"{'yes' if page['text']['has_text_layer'] else 'NO':>6} "
            f"{page['font_count']:>6} {page['images']['count']:>6} "
            f"{page['drawings']['paths']:>7} {page['drawings']['items']:>7} "
            f"{page['drawings']['cross_check']['verdict']:>9}"
        )
    if len(report["pages"]) > 12:
        print(f"  ... {len(report['pages']) - 12} more pages (see probe.json)")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _run_one(pdf: Path, args: argparse.Namespace, argv: Sequence[str]) -> None:
    if not pdf.exists():
        raise SystemExit(f"no such file: {pdf}")
    ctx = RunContext(pdf, Path(args.out_dir), argv)
    doc = fitz.open(pdf)  # opened read-only; never saved
    try:
        command = args.command
        commands = (
            ["probe", "text", "images", "render", "vector"]
            if command == "all"
            else [command]
        )
        report: dict[str, Any] | None = None
        for name in commands:
            if name == "probe":
                report = cmd_probe(ctx, doc, args)
            elif name == "text":
                cmd_text(ctx, doc, args)
            elif name == "images":
                cmd_images(ctx, doc, args)
            elif name == "render":
                cmd_render(ctx, doc, args)
            elif name == "vector":
                cmd_vector(ctx, doc, args)
        if command == "all":
            write_consolidated(ctx, doc)
        if not args.no_manifest:
            ctx.write_manifest(command)
        if report is not None and not args.quiet:
            print_probe_table(report)
        if not args.quiet:
            print(f"  -> {ctx.out_dir} ({len(ctx.outputs)} files)")
            for note in ctx.notes:
                print(f"     {note}")
    finally:
        doc.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf_extract",
        description="Deterministic PDF extraction for WRO 2026 (see CLAUDE.md).",
    )
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR,
                        help=f"extraction root (default: {DEFAULT_OUT_DIR})")
    parser.add_argument("--precision", type=int, default=DEFAULT_PRECISION,
                        help=f"decimal places in emitted floats (default: {DEFAULT_PRECISION})")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--no-manifest",
        action="store_true",
        help="do not write manifest.json. manifest.json records the LAST command "
             "only (ADR-016), so a casual `probe docs/*.pdf` otherwise truncates the "
             "record that build_field_spec.py pins its provenance to. Use this for "
             "read-only inspection.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    def add(name: str, help_text: str) -> argparse.ArgumentParser:
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("pdf", nargs="+", type=Path)
        return sub

    add("probe", "structural report: boxes, rotation, colour, fonts, op counts")

    text_parser = add("text", "per-page text: spans.json + reading-order markdown")
    text_parser.add_argument("--fallback", action="store_true", default=True,
                             help="use pdfplumber for tables when PyMuPDF finds none")
    text_parser.add_argument("--no-fallback", dest="fallback", action="store_false")

    images_parser = add("images", "extract embedded rasters at native resolution")
    images_parser.add_argument("--min-pixels", type=int, default=0,
                               help="skip images below this pixel count (default: 0 = all)")

    render_parser = add("render", "rasterize pages at an explicit px/mm scale")
    render_parser.add_argument("--px-per-mm", type=float, default=DEFAULT_PX_PER_MM)
    render_parser.add_argument("--bbox", default=None,
                               help="X0,Y0,X1,Y1 in mm, MAT frame")
    render_parser.add_argument("--colorspace", choices=sorted(_COLORSPACES),
                               default="rgb", help="ADR-007; cmyk writes TIFF")
    render_parser.add_argument("--max-mpix", type=float, default=DEFAULT_MAX_MPIX)
    render_parser.add_argument("--force", action="store_true",
                               help="render beyond --max-mpix")
    render_parser.add_argument("--name", default=None, help="output basename tag")
    render_parser.add_argument("--pages", dest="pages_list", default=None,
                               type=lambda s: [int(p) for p in s.split(",")],
                               help="comma-separated 1-based page numbers")

    add("vector", "dump page.get_drawings() to mm-space JSON + fill inventory")

    all_parser = add("all", "probe + text + images + render + vector")
    all_parser.add_argument("--px-per-mm", type=float, default=DEFAULT_PX_PER_MM)
    all_parser.add_argument("--min-pixels", type=int, default=0)
    all_parser.add_argument("--colorspace", choices=sorted(_COLORSPACES), default="rgb")
    all_parser.add_argument("--max-mpix", type=float, default=DEFAULT_MAX_MPIX)
    all_parser.add_argument("--force", action="store_true")
    all_parser.add_argument("--fallback", action="store_true", default=True)
    all_parser.add_argument("--no-fallback", dest="fallback", action="store_false")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    set_precision(args.precision)

    # Defaults for options a given subcommand does not declare.
    for name, value in (
        ("bbox", None), ("name", None), ("pages_list", None),
        ("colorspace", "rgb"), ("px_per_mm", DEFAULT_PX_PER_MM),
        ("min_pixels", 0), ("max_mpix", DEFAULT_MAX_MPIX),
        ("force", False), ("fallback", True), ("no_manifest", False),
    ):
        if not hasattr(args, name):
            setattr(args, name, value)

    for pdf in args.pdf:
        _run_one(Path(pdf), args, argv)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
