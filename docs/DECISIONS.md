# Decision record

ADR format: **context → options → decision → consequence.**

`last_reviewed: 2026-07-25`

| ADR | Decision | Status |
|---|---|---|
| [ADR-001](#adr-001) | `docs/extracted/**/img/` is gitignored | accepted |
| [ADR-002](#adr-002) | Image filenames use a 4-digit index, not 2 | accepted |
| [ADR-003](#adr-003) | Page-box precedence is TrimBox → CropBox → MediaBox | accepted |
| [ADR-004](#adr-004) | Béziers flattened at a fixed 16 segments for area | accepted |
| [ADR-005](#adr-005) | stdlib `argparse`, no CLI framework | accepted |
| [ADR-006](#adr-006) | Dependency set: pymupdf, pdfplumber, pillow, numpy | accepted |
| [ADR-007](#adr-007) | `render --colorspace {rgb,cmyk,gray}` added to the spec | accepted |
| [ADR-008](#adr-008) | Float precision defaults to 3 decimals (1 µm) | accepted |
| [ADR-009](#adr-009) | Clip paths are retained in the vector dump | accepted |

---

## ADR-001

### `docs/extracted/**/img/` is gitignored

**Context.** S2 alone carries ~3.4k image XObjects; ~3.39k of them are under 10k pixels and
are almost certainly InDesign transparency-flattening tiles. Extracting each produces a PNG
plus a sidecar JSON, i.e. roughly 7k files for one source document. The original scaffold
spec gitignored only `render/`.

**Options.**

| Option | Effect |
|---|---|
| Commit everything | repo is self-contained; ~7k derived files enter git for S2 alone |
| Extract all, ignore `img/` | nothing lost on disk; repo stays reviewable; regeneration is deterministic |
| Extract page-referenced rasters only | smaller, but no longer "every embedded raster" |

**Decision.** Extract **all** rasters to disk; gitignore `docs/extracted/**/img/`.
`manifest.json` records path → sha256 + bytes for every one of them, so the integrity record
survives in git even though the bytes do not.

**Consequence.** A fresh clone has no `img/` until `pdf_extract.py` is re-run. That is
acceptable because the run is deterministic and the manifest hashes make tampering
detectable. Reviewers who need a specific image regenerate it or use `render --bbox`.

---

## ADR-002

### Image filenames use a 4-digit index

**Context.** The spec named images `p{page:03d}_{n:02d}.png`. S2 is a single page carrying
~10³ drawn rasters.

**Decision.** `p{page:03d}_{n:04d}.png`.

**Consequence.** Deviates from the written spec. Without it the index overflows two digits at
image 100 and lexical sort order no longer matches draw order, which would silently scramble
any later attempt to correlate an image with its placement rect.

---

## ADR-003

### Page-box precedence: TrimBox → CropBox → MediaBox

**Context.** The spec said "TrimBox as the mat boundary if present, MediaBox only as
fallback", and did not mention CropBox. A CropBox, when it differs from MediaBox, is a
closer approximation of the intended visible page than MediaBox is.

**Decision.** Precedence TrimBox → CropBox → MediaBox. `NEEDS-VERIFY(S2)` is emitted
whenever TrimBox is absent, naming which tier was actually used.

**Consequence.** Strictly better than the two-tier rule when a CropBox exists, and identical
when it does not. The required `NEEDS-VERIFY` still fires, so the safety property the spec
was protecting is preserved.

*(For S2 as delivered this is moot: TrimBox == CropBox == BleedBox == MediaBox.)*

---

## ADR-004

### Béziers flattened at a fixed 16 segments for area computation

**Context.** `area_mm2` needs a polygon. Path items include cubic Béziers (`c`) and quads
(`qu`). Adaptive flattening tolerances make output non-deterministic across library versions.

**Options.** Anchor points only (understates curved areas) · adaptive tolerance
(non-deterministic) · fixed subdivision (deterministic, slight error on tight curves).

**Decision.** Fixed 16 linear segments per cubic, shoelace over the result.

**Consequence.** Exact for the rectangular and polygonal mat zones that actually matter.
Curved decorative shapes carry a small area error, which is acceptable because area is used
for *ranking and inventory*, not for geometry freeze. `bbox_area_mm2` is emitted alongside so
a large discrepancy is visible.

---

## ADR-005

### stdlib `argparse`, no CLI framework

**Context.** `typer` / `click` would be marginally nicer. Every added dependency must be
justified.

**Decision.** `argparse`.

**Consequence.** Slightly more verbose parser code; zero additional dependency surface for a
tool whose entire value is reproducibility.

---

## ADR-006

### Dependency set

| Package | Justification |
|---|---|
| `pymupdf` | Primary engine. The only one of these with content-stream vector access (`get_drawings`), explicit-scale rasterisation, and image XObject placement rects. Everything structural depends on it. |
| `pdfplumber` | Text/table **fallback only**. Used when `page.find_tables()` returns nothing on a page that clearly has tabular text. The manifest records which engine produced each page. |
| `pillow` | Raster post-processing where PyMuPDF's Pixmap path is awkward — CMYK JPEG round-trips and SMask compositing. |
| `numpy` | Vectorised shoelace area over flattened paths, and pixel sampling on rendered pixmaps. |

**Decision.** These four, nothing more. `argparse`, `hashlib`, `json`, `zlib` come from stdlib.

**Consequence.** `pillow` and `numpy` are the weakest justifications of the four; if they end
up unused after Phase 1 they should be dropped rather than left as decoration.

---

## ADR-007

### `render --colorspace {rgb,cmyk,gray}` added to the spec

**Context.** S2 is `DeviceCMYK` with a PDF/X-3:2002 output intent and a 4-component ICC
profile. PyMuPDF hands back RGB after a conversion that ignores that profile. Mat colour
identification is a primary downstream use of this data, so a naive RGB value is not good
enough to be the *only* colour record.

**Decision.** Add a `--colorspace` flag to `render`. RGB stays the default; `cmyk` renders
through PyMuPDF's CMYK colourspace so true 4-channel values can be sampled.

**Consequence.** Extends the specified CLI surface. Every RGB value the toolchain emits is
tagged `ASSUME:` and the CMYK render is the cross-check. Without this there would be no way
to distinguish two mat colours that collide after a naive CMYK→RGB conversion.

---

## ADR-008

### Float precision defaults to 3 decimals

**Context.** `--precision` controls rounding in all emitted JSON. S2's vector dump is large;
precision directly drives file size.

**Decision.** Default 3 decimal places = 1 µm in mm.

**Consequence.** 1 µm is three orders of magnitude finer than anything a printed vinyl mat
can hold, so no real information is lost, and `drawings.json` stays substantially smaller
than at 4–6 decimals. `-0.0` is normalised to `0.0` so sign noise cannot break byte-identity
between runs.

---

## ADR-009

### Clip paths are retained in the vector dump

**Context.** S2's content stream contains ~1000 `W n` clip operations. `get_drawings()`
reports path geometry *before* clipping, so a clipped path's reported area can be far larger
than the area actually visible on the mat. Dropping clip entries would produce a fill
inventory that looks clean and is wrong.

**Decision.** Use `get_drawings(extended=True)` and emit clip entries as `type: "clip"` with
their nesting `level`, alongside normal fill/stroke paths.

**Consequence.** `drawings.json` is larger and consumers must be clip-aware. In exchange, the
next session can reconstruct the clip stack and compute *visible* area rather than trusting a
number that silently overstates coverage.
