# Extraction report — S1, S2, S3

Produced by `tools/pdf_extract.py` v1.0.0 (PyMuPDF 1.28.0 / MuPDF 1.29.0, Python 3.13.11).
Everything below is read out of `docs/extracted/*/probe.json`, `manifest.json` and
`vector/*.json`. Nothing here is estimated or recalled.

**Headline: S2 is vector.** Mat geometry is extractable as exact polygon coordinates, so
`data/field_spec.json` can be mm-exact. The measured mat is **2361.999 × 1143.000 mm**,
confirming the working `2362 × 1143` assumption to within 1.1 µm.

`last_reviewed: 2026-07-25`

---

## 1 · Integrity

| | S1 Game Rules | S2 Game Mat | S3 Building Instructions |
|---|---|---|---|
| sha256 | `3ec1bb2b…87877f` | `8d58381f…66c4d9` | `ab7fa33b…66bd7a` |
| bytes | 7,468,185 | 9,426,139 | **15,358,983** |
| format | PDF 1.4 | PDF 1.3 | PDF 1.6 (object streams) |
| pages | 15 | 1 | 177 |
| text layer | **15/15 pages**, 13,596 chars | 0/1 pages, 0 chars | **1/177 pages, 52 chars** |
| embedded fonts | 22 | **0** | 14 |
| image XObjects | 68 (58 drawn, 10 orphan) | 4,220 (all drawn) | 181 (179 drawn, 2 orphan) |
| rasters extracted | 85 | 4,448 | 179 |
| vector paths | 980 | **50,479** | **0** |
| vector path items | 1,664 | 307,603 | 8 |
| distinct fill colours | 8 | **580** | 0 |
| files emitted | 220 | 8,904 | 894 |
| **verdict** | **USABLE** | **USABLE** | **DEGRADED** |

**The BI PDF is real.** 15,358,983 bytes, 177 parseable page objects across 4 object
streams — not the 403-byte stub seen previously.

**Why S3 is DEGRADED, not BROKEN.** Its rasters extract cleanly at native resolution
(179/179, zero failures) and pages render fine. But the booklet is **fully rasterized**:
one image per page, zero vector paths on all 177 pages, and a text layer on the title page
only — 52 characters in the entire document. Consequences:

- Game-object dimensions, mass and grip points **cannot be text-extracted from S3**. They
  must be read visually from the page rasters, or measured from physical parts.
- Roadmap phase 4 (object spec) is therefore manual-reading work, not parsing work. That is
  a schedule fact worth knowing before it is scheduled.

**Zero extraction failures across all three files** after the fixes described in §7.

---

## 2 · S2 geometry verdict — **VECTOR**

Stated plainly: the mat artwork is vector. It is *not* a single embedded raster.

| Evidence | Value |
|---|---|
| Painted vector paths on the single page | **50,479** |
| Path items | 307,603 — `c` 274,555 · `l` 32,058 · `re` 987 · `qu` 3 |
| Content-stream painting operators | 50,491 |
| **paths per painting op** | **0.9998** — MuPDF descended into everything |
| Fill colour operators (`k`, CMYK) | 6,705 |
| Clip operations (`W n`) | 5,267 |
| Embedded fonts | **0** — all mat text is outlined into paths |
| Largest embedded raster | 2,953 × 2,953 px (8.72 MPix), **square** |
| A full-mat raster would need | 9,300 × 4,500 px (42 MPix) at 100 dpi; 27,874 × 13,500 (376 MPix) at 300 dpi |

The decisive negative: **no raster of the required size or aspect exists.** The mat is
2.07:1; the largest embedded image is 1:1 and 8.72 MPix — 43× too few pixels to be a
300 dpi mat backing. The 4,448 raster placements are decorative (audience figures, sponsor
panels, logos, textures).

The decisive positive: the **0.9998 paths-per-painting-op ratio**. Every painting operator
in the content stream produced exactly one reported drawing entry, so no geometry is hiding
inside a Form XObject that MuPDF declined to descend into. That ratio is the cross-check
this toolchain was built around, and on S2 it is as close to 1.0 as it can get.

⇒ **Exact polygon coordinates for every area are extractable. `field_spec.json` can be
mm-exact.**

### Transform validated on the real file, not just in tests

| Check | Result |
|---|---|
| Painted paths inside the page box | 48,487 / 50,479 = **96.1 %** |
| Union bbox overlaps the page box | yes |
| Self-check verdict | **ok** |
| Visual check of the 4 px/mm render | upright, not mirrored, not rotated |
| Independent corroboration | the 4 light-green squares sit on the **upper** edge, matching §5.6's description of the note start positions, so `+Y` up is correct |

The 3.9 % of paths outside the box are a tiled brown texture (`#81583f`, consecutive
sequence numbers, ~4,596 mm² each, regular ~29 mm offsets) that runs past the trim and is
clipped at render time. That is normal PDF artwork, not a broken transform — see §7.

---

## 3 · Measured mat dimensions

**`MEASURED(S2)`** — from TrimBox, which is present:

| Axis | pt | mm | Assumption | Δ |
|---|---:|---:|---:|---:|
| Width | 6695.43 | **2361.999** | 2362 | −0.001 mm |
| Height | 3240.00 | **1143.000** | 1143 | 0.000 mm |

**The `2362 × 1143` working assumption is confirmed.** The 1.1 µm width difference is
rounding in the PDF's own number, not a discrepancy.

### The bleed finding — read this before freezing coordinates

```
TrimBox  = CropBox = BleedBox = MediaBox = [0 0 6695.43 3240.0] pt
delta(used − MediaBox)                    = [0, 0, 0, 0]
```

All four boxes are **identical**. The file carries **zero bleed and no crop marks**, which
is unusual for a print-ready file and has one important consequence: there is no printed
margin outside the artwork, so the artwork edge *is* the mat edge as far as this PDF is
concerned. Page rotation is 0 and the page transformation matrix is the identity, so there
is no ambiguity about which corner is the origin.

Other facts: authored in **Adobe InDesign** (`/PieceInfo /InDesign`, LastModified
`D:20251212150752Z`), **PDF/X-3:2002**, output condition **CGATS TR 001**, DeviceCMYK with
ICC profiles of 1 and 4 components.

---

## 4 · Fill-colour inventory (raw — **no area IDs assigned**)

580 distinct fill colours. Per §6 of the session brief, mapping these to canonical area IDs
is a judgement call deferred to the next session. This is the raw inventory only.

Top 20 by total area, from `vector/fills_by_colour.json`:

| # | fill | paths | total area mm² | largest path mm² | bbox x0,y0 → x1,y1 (mm) |
|--:|---|--:|--:|--:|---|
| 1 | `#8d8f91` | 4 | 2,274,403 | 642,893 | 389, 0 → 2362, 1143 |
| 2 | `#468744` | 68 | 569,601 | 397,933 | 1147, −32 → 2410, 1161 |
| 3 | `#ffffff` | 115 | 556,798 | 141,600 | 66, 0 → 2312, 1143 |
| 4 | `#85604b` | 1 | 389,479 | 389,479 | −13, 324 → 535, 1182 |
| 5 | `#81583f` | 253 | 288,668 | 4,844 | −322, 74 → 2676, 1413 |
| 6 | `#0a151e` | 31 | 130,815 | 28,320 | 37, 150 → 2312, 1004 |
| 7 | `#cf8fbb` | 1 | 129,452 | 129,452 | 0, 0 → 400, 324 |
| 8 | `#356233` | 12 | 98,384 | 27,660 | 1150, −4 → 2372, 1153 |
| 9 | `#585a5c` | 31,852 | 87,095 | 68 | 386, −13 → 2375, 1157 |
| 10 | `#8d5f47` | 2 | 82,667 | 79,089 | 1967, 919 → 2372, 1159 |
| 11 | `#24408f` | 1 | 74,529 | 74,529 | 2039, 435 → 2312, 708 |
| 12 | `#afbbdf` | 2 | 71,637 | 35,819 | 1055, 23 → 1703, 135 |
| 13 | `#4d7489` | 2 | 56,140 | 28,070 | 1064, 30 → 1694, 123 |
| 14 | `#4e5252` | 6 | 38,112 | 6,352 | 1025, 453 → 1898, 795 |
| 15 | `#3d4d24` | 2 | 35,011 | 22,568 | 1143, −36 → 2414, 1165 |
| 16 | `#000d1c` | 70 | 34,145 | 5,990 | 7, 8 → 1860, 386 |
| 17 | `#157a55` | 1 | 33,587 | 33,587 | 123, 85 → 358, 228 |
| 18 | `#b5b5b6` | 2 | 33,028 | 16,514 | 20, 441 → 134, 1045 |
| 19 | `#000001` | 97 | 27,347 | 1,718 | 388, 0 → 2362, 1143 |
| 20 | `#03390c` | 2,882 | 24,525 | 70 | 312, 70 → 2338, 1164 |

### Four caveats that will bite whoever maps these to area IDs

0. **Superseded 2026-07-25 — a scoring area is not always its own fill.** `backstage`'s fill
   `#cf8fbb` **includes** a 6.3 mm grey border (`#d6d0cc`) that S1 explicitly excludes, so the
   scoring polygon is the *inset*, 124,923.697 mm², not the fill's 129,452.075. A border
   signature sweep over all 255 points found this is the **only** such case. Never assume the
   selected fill is the scoring polygon.
1. **`total_area_mm2` is not printed area.** Areas are unclipped and overlapping fills are
   double-counted. The 580 fills sum to **5,673,520 mm²** against a mat of
   **2,699,765 mm²** — a 2.1× overcount. Use it to rank candidates, never to measure.
   (`AS-4`)
2. **Two populations are mixed in here.** 89 fills have a largest path ≥ 1000 mm² — those
   are the structural candidates. Entries like `#585a5c` (31,852 paths, largest 68 mm²) and
   `#03390c` (2,882 paths, largest 70 mm²) are cobblestone and foliage *texture*, not areas.
   Sort by **largest path**, not by path count.
3. **Every RGB value here is approximate** (`AS-1`). The source is CMYK with a PDF/X output
   intent; MuPDF converts without the profile. Measured drift between the vector-fill value
   and the same pixel in a render: `#8d8f91` vs `#8c8f90`, `#4e5252` vs `#4e5152` — about
   ±1 per channel. Small, but enough to make exact hex matching between the two paths fail.
4. **One `Separation(DeviceCMYK, All)` spot colourspace exists**, used by 112 images
   (`AS-2`). Spot colour does not round-trip through RGB, so if any of it is artwork rather
   than printer's marks, it is absent from this inventory entirely.

---

## 5 · Rendering recommendation

Measured on this machine (47 GB RAM, 64 cores), whole mat, RGB:

| px/mm | dpi | pixels | MPix | PNG | wall time |
|--:|--:|---|--:|--:|--:|
| 1.0 | 25.4 | 2362 × 1143 | 2.70 | 0.95 MB | 3.0 s |
| **2.0** | 50.8 | 4724 × 2286 | 10.80 | 2.34 MB | 3.9 s |
| 4.0 | 101.6 | **9448 × 4572** | **43.20** | 5.63 MB | 7.3 s |
| 8.0 | 203.2 | 18896 × 9144 | 172.78 | 16.29 MB | 16.1 s |

The brief's estimate is confirmed exactly: 4 px/mm gives **9448 px wide, 43.20 MPix**.
Cost is a non-issue at this scale — even 8 px/mm renders in 16 s and 16 MB.

**(a) Whole-mat overview → 2 px/mm.** 10.8 MPix resolves every area boundary and all mat
lettering, for a quarter of the pixels of 4 px/mm. Use 4 px/mm only when reading fine print.

**(b) Per-area crops for colour sampling → 8–12 px/mm, but resolution is the wrong lever.**

Measured on a 125 × 120 mm crop at 12 px/mm (`--bbox 1000,495,1125,615`):

| region | median RGB | median CMYK | distinct colours in window | pixels >30 from median |
|---|---|---|---|--:|
| note-square interior | `#faef3a` | C3 M0 Y87 K0 | **1** | 0.0 % |
| its dark border | `#4e5152` | C65 M56 Y56 K33 | **1** | 0.0 % |
| speckled plaza background | `#8c8f90` | C47 M38 Y38 K2 | **406** | **17.2 %** |

Flat areas are exactly one colour at any resolution — sampling them needs no pixels at all.
The grey plaza, however, is deliberately speckled with darker dots: **17.2 % of its pixels
sit more than 30 RGB units from the median**, so a single-pixel sample there is wrong
roughly one time in six, and raising px/mm does not help — it samples the same dots more
finely.

**Recommended sampling method:** take the **median over an interior window eroded well away
from the area boundary**, on a **`--colorspace cmyk` render** (`ADR-007`), never a single
pixel and never a mean. Anti-aliased boundary pixels and texture dots both fail a
single-pixel or mean-based sample.

---

## 6 · Open questions

### `NEEDS-VERIFY(S4)` — blocked on the missing General Rules 2026

| # | Question | Why extraction raised it |
|---|---|---|
| 1 | Does the competition-supplied mat carry a **border beyond the artwork trim edge**, and is it laid flush to the table walls? | S2 has **zero bleed** — TrimBox == MediaBox. If the physical mat has an unprinted margin, every MAT-frame coordinate is offset by a constant that no amount of internal consistency would reveal. This is `AS-5`, the highest-consequence open item. |
| 2 | Max motors/sensors, start-size envelope, EV3+SPIKE mixing | `AMBIGUITY(A6)` — hard-blocks robot design |
| 3 | Does a robot overlapping a target area at time-out break "completely in"? | `AMBIGUITY(A3)` |
| 4 | Must the robot return to start to stop the clock? Where does time sit in tie-break? | `AMBIGUITY(A4)` |
| 5 | Do objects still held by the mechanism at time-out score? | `AMBIGUITY(A5)` |

### `NEEDS-VERIFY(S1/S2)` — answerable without S4

| # | Question | Status |
|---|---|---|
| 6 | Is the `Separation(DeviceCMYK, All)` content printer's marks or artwork? | 112 images use it. The `All` separant conventionally means printer's marks, but that is convention, not proof (`AS-2`). Check by diffing an RGB render against a CMYK render at the same scale. |
| 7 | `AMBIGUITY(A1)` — "moved" is AND or OR? | **S1 text now extracted verbatim, and it confirms the conflict.** Page 13 defines: *"The game object is considered as moved if it no longer touches its initial position **and** is no longer upright"* — while the same page's caption grid awards *"0 points (not upright anymore)"*. The register's OR default stands. |
| 8 | Which fills correspond to which canonical areas? | **ANSWERED 2026-07-25.** All 10 scoring areas identified and cross-checked against S1's labelled field diagram (p3): `backstage` `#cf8fbb` **inset to `[0,0,393.809,317.219]`** (S1 excludes the grey border `#d6d0cc`) · `mic_target` `#c3d82d` · `cable_area_upper/lower` `#b5b5b6` · six `note_target_*` `#4e5252` 79.699–79.700 mm outer squares · `start_area` = a 250.0 × 250.0 mm **raster** placement rect. See `data/field_spec.json` and ADR-012/013/015. |
| 9 | Do S3's object dimensions exist anywhere machine-readable? | No — S3 is rasterized (§1). Phase 4 is visual-reading work. |

### Not an open question

**`2362 × 1143` is confirmed**, not assumed. **S2 is vector**, not raster. **All three files
are intact.** None of these need re-checking.

---

## 7 · Extraction defects found and fixed during this run

Recorded because each one produced *plausible-looking wrong output* before it was caught.

| # | Symptom | Root cause | Fix |
|---|---|---|---|
| 1 | 10/15 S1 pages reported "vector extraction may be incomplete" | The operator census counted operator-shaped bytes **inside text strings** — a page containing " l " or " c " in its prose inflated the count | `strip_literals()` blanks `( … )` and `< … >` before counting |
| 2 | `<</MCID 0>>` swallowed by the stripper | `<<` was consumed one byte at a time, so the second `<` opened a bogus hex string | consume `<<` as a unit |
| 3 | Shortfall still reported on clipped pages | Clip-path construction ops are in the content stream but excluded from non-extended `get_drawings()` | compare against the **extended** entry list |
| 4 | Shortfall *still* reported | MuPDF collapses `m l l l h` quads into a single `re` item, so item counts legitimately sit far below construction-op counts | switched the trigger to **painting ops vs entries** (1:1 expected); item ratio kept as informational only |
| 5 | **112 S2 images silently failed to decode** | `Separation(DeviceCMYK, All)` has no PNG representation and `tobytes("png")` raises | `_encode_image()` escalates pixmap→PNG, forced RGB→PNG, then native encoding. All 112 now recovered at the RGB step; **0 failures** (`ADR-011`) |
| 6 | Self-check flagged S2's transform as broken | The union bbox alone is not a valid test — artwork legitimately extends past the trim and is clipped | trigger on **no overlap** or **majority of paths outside**, and report the inside-share (96.1 % on S2) |

Defects 1–4 and 6 were all **false alarms produced by the cross-check itself**. They are
listed because a cross-check that cries wolf is worse than none: it trains the reader to
ignore it. It now reads `ok` on every page of all three documents, which means a future
`shortfall` is worth acting on.

---

## 8 · Reproducibility

`manifest.json` splits `run` (timestamp, argv, params) from `outputs` (path → sha256 +
bytes), so the timestamp cannot mask a real difference.

| Source | Runs compared | `text/` + `vector/` identical | All outputs identical |
|---|---|---|---|
| S1 Game Rules | 2 (distinct timestamps) | ✅ 18/18 files | ✅ **220/220** files |
| S2 Game Mat | 2 (distinct timestamps) | ✅ 4/4 files | ✅ **8,904/8,904** files |

Byte-identity extends **beyond the stated guarantee**: every output matched, including all
4,448 extracted PNGs and the 129,426,683-byte `vector/drawings.json`, not just the text and
vector JSON. Zero differing files across 9,124 compared outputs.

### Artifact sizes and what is committed

| Artifact | Size | In git? |
|---|--:|---|
| `vector/drawings.json` (S2) | 129,426,683 B | ❌ gitignored — `ADR-010` |
| `vector/fills_by_colour.json` (S2) | 340,140 B | ✅ committed — this is the raw inventory §4 presents |
| `img/` (S2, 4,448 rasters) | 38 MB | ❌ gitignored — `ADR-001` |
| `render/full_4pxmm.png` | 5.6 MB | ❌ gitignored |
| `probe.json`, `manifest.json`, `citations.json` | 2.5 MB | ✅ committed |
| `text/` (verbatim rulebook text) | — | ❌ gitignored since the publish commit — **corrected 2026-07-25**; rule citations live in `docs/citations.json` instead |

Ignored artifacts still carry a sha256 and byte length in `manifest.json`, so their
integrity is auditable from git even though the bytes are not stored. Regeneration is one
command and, as measured above, byte-identical.

---

## 9 · What is deliberately absent

Per §6 and §8 of the session brief:

- **`data/field_spec.json` was not created.** Extraction quality must be human-reviewed first.
- **No fill colour was mapped to a canonical area ID.**
- **`CLAUDE.md` §5.3 remains a `NEEDS-VERIFY(S1)` stub** — the canonical ID table is frozen
  in the same session that produces `field_spec.json`.
- No robot design, strategy, or simulator work.
- No statement anywhere in this repo is sourced from memory of prior-season WRO rules.

**Next step is human review** (`docs/plans/ROADMAP.md` phase 1), and in parallel and
independently, **acquiring S4** (phase 5) — which is blocked by nothing and blocks the most.
