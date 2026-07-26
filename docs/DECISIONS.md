# Decision record

ADR format: **context → options → decision → consequence.**

`last_reviewed: 2026-07-27` · ADR-013/014/015 signed off 2026-07-25; ADR-017/018/019 added 2026-07-26; ADR-020/021 added 2026-07-27 (Phase 6); ADR-022 added 2026-07-27 (Phase 7 part 1); ADR-023 added 2026-07-27 (Phase 7 part 2); ADR-024, ADR-025 and ADR-026 added 2026-07-27.

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
| [ADR-010](#adr-010) | `vector/drawings.json` is gitignored; the fill inventory is not | accepted |
| [ADR-011](#adr-011) | Images escalate through fallbacks rather than being dropped | accepted |
| [ADR-012](#adr-012) | Canonical ID table frozen (first freeze, not a rename) | accepted |
| [ADR-013](#adr-013) | `completely_in` domain via `scoring`; both polygon fields always emitted | accepted 2026-07-25 |
| [ADR-014](#adr-014) | Initial object pose is run-time state, not a spec constant | accepted 2026-07-25 |
| [ADR-015](#adr-015) | Selector: full predicate, per-entry cardinality, `inset_by` | accepted 2026-07-25 |
| [ADR-016](#adr-016) | `manifest.json` describes the last run, not a merged history | accepted 2026-07-25 |
| [ADR-017](#adr-017) | A flexible object gets the rigid carrier's footprint, and says so | accepted 2026-07-26 |
| [ADR-018](#adr-018) | Non-scoring runs live in `[[subassemblies]]`, never in `objects` | accepted 2026-07-26 |
| [ADR-019](#adr-019) | The cream run-preview box replaces the callout as the boundary signal | accepted 2026-07-26 |
| [ADR-020](#adr-020) | `sim/` is a package; every open interpretation is a named parameter | accepted 2026-07-27 |
| [ADR-021](#adr-021) | Area geometry comes from the polygon, never from `bbox_mm` | accepted 2026-07-27 |
| [ADR-022](#adr-022) | Motor budget: 2 drive + 0 yaw + 2 manipulator; mechanism gated on mass | accepted 2026-07-27 |
| [ADR-023](#adr-023) | `RobotIO` is intent-level, and portability is linted, not assumed | accepted 2026-07-27 |
| [ADR-024](#adr-024) | S6 is parsed structurally; the EV risk term is a worst case, not a constant | accepted 2026-07-27 |
| [ADR-025](#adr-025) | An operator-dependent blocker carries the date it was last confirmed | accepted 2026-07-27 |
| [ADR-026](#adr-026) | Expected value carries the partial tier; measurement paths ship inert | accepted 2026-07-27 |

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

---

## ADR-010

### `vector/drawings.json` is gitignored; `fills_by_colour.json` is committed

**Context.** S2's mat artwork is vector, and richly so: 55,746 drawing entries carrying
~307k path items, of which ~275k are cubic Béziers. Serialised at 3-decimal precision that
is roughly 120 MB of JSON for a single page. Git stores each revision whole, so every re-run
that changes one coordinate adds another ~120 MB blob to history forever.

**Options.**

| Option | Effect |
|---|---|
| Commit `drawings.json` | repo is self-contained; history grows ~120 MB per regeneration |
| Reduce precision further | 2 decimals saves maybe 15 %; still ~100 MB, and loses resolution for no real gain |
| Filter to "significant" paths | invents a threshold, i.e. a judgement call this session is explicitly not allowed to make (§6) |
| Gitignore it, commit the inventory | repo stays reviewable; full dump regenerates byte-identically |

**Decision.** Gitignore `docs/extracted/**/vector/drawings.json`. Commit
`vector/fills_by_colour.json` (small, and it *is* the raw inventory the extraction report
is asked to present). `manifest.json` records the sha256 and byte length of the ignored
dump, so its integrity is still auditable from git.

**Consequence.** A fresh clone must run `pdf_extract.py vector <pdf>` before it has path
geometry. That is one command and it is deterministic, which is the same trade already
accepted in ADR-001 for rasters. The alternative — a multi-hundred-megabyte git history
built out of regenerable derived data — is worse, and filtering the dump would have
required exactly the kind of judgement call this session must not make.

---

## ADR-011

### Images escalate through fallbacks rather than being dropped

**Context.** The first full run of S2 reported *112 embedded images could not be decoded*:
`pixmap must be grayscale or rgb to write as png`. They are all
`Separation(DeviceCMYK, All)` — a 1-channel spot colourspace with no PNG representation.
The naive `pixmap.tobytes("png")` path silently loses every one of them.

**Decision.** `_encode_image()` escalates: pixmap → PNG, then forced RGB → PNG, then the
embedded stream in its **native** encoding (typically JPEG) via `doc.extract_image()`. The
method used is recorded per image in the sidecar (`encode_method`) and aggregated in
`manifest.json`, and any non-default method raises an `ASSUME:` note.

**Outcome on the real file.** All 112 recovered at step 2 (forced RGB), so `img/` stayed
all-PNG and step 3 was not exercised on S2. It is kept regardless: it is the only step that
cannot fail, and a future source with a DeviceN or stencil colourspace will need it.

**Consequence.** No image is ever dropped, and the sidecar states plainly when pixel values
are not sRGB. The cost is a potentially mixed-format `img/` directory, which is why the
sidecar carries `format` explicitly rather than the filename extension being assumed
`.png`.

**This also sharpens [AS-2](ASSUMPTIONS.md#as-2):** the spot colourspace is
`Separation(DeviceCMYK, All)` — the `All` separant, conventionally used for printer's marks
that must appear on every plate. That is evidence for, but not proof of, "technical layer,
not artwork".


---

## ADR-012

### Canonical ID table frozen

**Context.** `CLAUDE.md` §5.3 had been a `NEEDS-VERIFY(S1)` stub since session 1: the
original brief's ID table arrived empty and no table existed anywhere in the repo. Both
`field_spec.json` (keys) and `scoring_model.json` (references) need it, so it blocked both.

**Options.** Derive names from S1 vocabulary · adopt an operator-supplied table verbatim ·
keep deferring.

**Decision.** Freeze the operator-supplied table **verbatim**, in `CLAUDE.md` §5.3. This is a
**first freeze, not a rename** — nothing was renamed because nothing existed. An earlier
in-session proposal (`grey_area_*`, `microphone_target_area`, `backstage_area`,
`note_start_slot_{1..4}`) is **discarded**; the supplied table wins in every case, including
zero-indexed `note_start_rand_{0..3}` and the short forms `mic` / `amp`.

**Two additions resolved here.**

1. **`unassigned_marker_{1..4}`** for the four `#979797` 31.9 mm squares at (90.9, 101.8),
   (988.9, 715.2), (1779.3, 133.8), (2004.9, 1051.6). An earlier hypothesis mapped them to
   clef / amp / speakers / mic. **Repo data excludes three of those four**: none of the
   markers lies on the stage `#85604b` `[-13, 324, 535, 1182]`, yet S1 puts the amplifier and
   both speakers *on the stage* and the microphone *in the truck*. S1 p2 warns of markings
   unused at local/national events, and S4 §8.4 describes the Extra Day Challenge relocating
   objects on the same mat (S1 dates it 8 Oct 2026). `NEEDS-VERIFY(S1-extra-mission)`.
2. **`stage` and `plaza` enter the spec at `scoring: false`.** The sensor/navigation model
   needs the large mat colour regions, and ADR-013's predicate ranges only over
   `scoring: true`, so their presence is safe **by construction rather than by convention**.

**Consequence.** Instance-distinguishing IDs are mandatory where scoring needs them: bonus
awards 10 per speaker to a max of 20, so a singular `speaker` could not express which one
toppled. Recording the marker IDs as *unassigned* rather than guessing keeps a wrong semantic
out of S5 — every downstream module reads S5 without question, whereas an empty slot is
visibly empty.

---

## ADR-013

### `completely_in` gets a declared domain — accepted

**Context.** S1 p9 defines *completely in* as touching the corresponding area **and no other
area on the mat**. "Area on the mat" is undefined. The mat carries **580 distinct fills**;
`field_spec.json` will carry roughly a dozen polygons. Every scoring target except
`backstage` is drawn on top of a larger fill:

| target | enclosing fill |
|---|---|
| `mic_target` `#c3d82d` `[220.2, 695.2, 299.9, 790.8]` | `stage` `#85604b` `[-13, 324, 535, 1182]` |
| `note_target_*` ×6, `start_area` | `plaza` `#8d8f91` `[389, 0, 2362, 1143]` |
| `backstage` `#cf8fbb` `[0, 0, 400.1, 323.5]` | none — runs to the mat corner |

If `stage` or `plaza` enter the spec unflagged and the predicate iterates every area, **no
object can score anywhere.** That failure is silent at build time and surfaces only when the
scorer runs, in Phase 6.

**Options.**

| option | verdict |
|---|---|
| scoring areas only | works, but leaves the flag implicit and fragile |
| **all spec areas behind an explicit `scoring` flag** | **proposed** |
| all 580 mat fills | **rejected** — not implementable from a dozen polygons, and it is the reading that makes the game unscoreable |

**Decision (proposed).**

```
areas: { id, polygon_mm, scoring: bool, includes_grey_border: bool, ... }

completely_in(obj, target) :=
    contains(target.polygon, obj.footprint)
    AND ∀ a ∈ areas where a.scoring ∧ a.id ≠ target.id :
        ¬intersects(a.polygon, obj.footprint)
```

`scoring` is declared **explicitly on every area** — no default, no inference — and that is
asserted by test.

**Consequence.** A7's default is recorded as a **forced** reading, not a conservative choice:
any literal reading of "no other area on the mat" makes the game unscoreable, so full
containment is the only implementable one. A register that presents a forced reading as a
chosen one invites a later session to "reconsider" it.

---

## ADR-014

### Initial object pose is run-time state, not a spec constant — accepted

**Context.** The schema needs `object_start_poses` for all 16 objects. Precise coordinates
exist for **six**:

| object | precise start pose? |
|---|---|
| `note_*` ×6 | ✅ the six 31.9 mm squares at y = 1059.5 |
| `clef`, `amp`, `speaker_a`, `speaker_b` | ❌ no marker (see ADR-012) |
| `cable_upper`, `cable_lower` | ❌ S1 says only "close to the stage, upper and lower end" |
| `mic`, `instrument_*` ×3 | ❌ "in the truck" — the truck is artwork, not a marker |

Bonus scoring needs exactly the four in the first ❌ row.

**Decision (proposed).** Change the semantics rather than hunt for coordinates. `moved` is
judged against where the object stood at the start of **that run**, not against a constant in
a spec file — S4 §10.8 scores the end-of-attempt field state and §9.6 has judges re-set the
tables between rounds.

```
field_spec.json      nominal_start_pose_mm + placement_tolerance_mm   (ASSUME:)
simulator, per seed  initial_pose = nominal + setup noise
scorer, moved()      compares against THAT RUN's initial_pose, never the spec value
```

**Consequence.** Unblocks all ten objects, keeps the spec honest about measured versus
assumed, and pulls setup variance into the Monte-Carlo where S4 §7.10 says it belongs.

**Why low absolute precision on `nominal_start_pose_mm` is acceptable** — recorded so a later
session does not chase accuracy nothing consumes:

- **Bonus scoring does not use it.** `moved` compares against that run's initial pose and the
  object's own footprint — a relative quantity; the footprint comes from Phase 4's stud count,
  not from the mat.
- **Route planning does use it**, but tolerates roughly ±20 mm, because S4 §9.6 and §10.2
  force the robot to sense its way in regardless.

---

## ADR-015

### Selector: full predicate, per-entry cardinality, and `inset_by` — accepted

**Context.** A global "exactly one path" rule makes the builder's hard-fail valuable, but it
is wrong for at least three entries measured in the repo:

| area | paths | measured | required |
|---|---:|---|---|
| `truck` `#afbbdf` / `#4d7489` | 2 + 2 | **two separate vehicles**, x 1055–1376 and 1381–1703 | `union`, `expect_paths = 2` |
| `plaza` `#8d8f91` | **4** | largest is 642,893 of 2,274,403 mm² = **28 %** | `union`, `expect_paths = 4` |
| `stage` `#85604b` | 1 | 389,479 mm², single `re` | `exact` |

`largest` on `plaza` would silently take about a quarter of it and the builder would report
success.

**Decision (proposed).**

```toml
[areas.truck]
match        = "union"    # "exact" (default) | "union" | "largest"
expect_paths = 2          # MANDATORY when match = "union"
```

`expect_paths` is **not optional**: a bare `union` silently absorbs any path added later and
destroys the one property that makes hard-fail worth having.

**Two sub-decisions to settle at sign-off.**

1. **Does `truck` need a polygon at all?** Under ADR-014 it may be only a label on a
   start-pose group. Decide deliberately; do not let the builder discover it.
2. **`start_area` — now RESOLVED, see below.** Its cardinality is not a vector-path question.

**`start_area` resolution (2026-07-25).** The earlier candidate — a `#ffffff` path inside the
`#24408f` border — does not exist. Three checks settled it:

| check | result |
|---|---|
| near-white vector fills in that bbox | **zero** |
| `#24408f` shape | solid `re`, `area == bbox_area == 74,529` — not a frame |
| raster placements overlapping it | `p001_3832`, 2953 × 2953 px, placed at **[2050.49, 446.49, 2300.51, 696.51] = 250.02 × 250.02 mm** |

S1's own labelled field diagram (p3, image `p003_0003`) points its **"Start Area"** arrow
directly at that panel. So under S4 §7.8 (*"the white area within a coloured border"*) the
blue `#24408f` 273 mm rect **is** the coloured border (11.5 mm wide) and the **white area is a
raster, not a vector path** — which is exactly why no `#ffffff` path exists.

The white area measures **250.02 × 250.02 mm** — the §5.1 robot envelope plus 0.01 mm per
side. A full-size robot therefore has **effectively zero placement slack**; any real design
needs to be smaller than 250 mm to have any. `start_area`'s selector is a **raster placement
rect**, not a fill selector — the builder needs that path, and it is a schema question, not a
cardinality one.


---

## ADR-013 addendum — the polygon field schema

**Context.** Emitting `polygon_visible_mm` *only* where clipping diverges makes the field set
conditional. Every invariant that names `polygon_mm` then reads a field whose meaning changes
with the data. The sharp case: `area_mm2` from the dump is **pre-clip always** (AS-4), so if
the spec's area bound to *visible* on a genuinely clipped area, the cross-check would compare
a clipped area against a pre-clip one and miss its 0.724 mm² bound by thousands — and the
cheapest fix would be widening the bound, destroying the invariant.

**Decision.**

```
polygon_constructed_mm   always present
polygon_visible_mm       always present; EQUAL to constructed when there is no divergence
clip_divergent: bool     explicit
area_mm2                 binds to CONSTRUCTED
visible_area_mm2         a separate named field if/when wanted
```

**`polygon_mm` does not exist.** No invariant can read a field that may be absent.

**Measured, not assumed.** Reconstructing the clip stack with correct `q`/`Q` scoping — a clip
leaves scope as soon as an entry at level ≤ its own appears — every scoring path in S2 sits at
**level 0**, so no clip is ever in scope:

| areas | paths | active clips | `clip_divergent` |
|---|---:|---:|---|
| backstage · mic_target · cable ×2 · note_target ×6 · plaza ×4 · stage | 15 | **0** | **false, all** |

So the two polygons are equal throughout the current mat and the cross-check bound is safe.
The builder still implements the reconstruction, so the guarantee survives a mat revision that
does clip something.

**Consequence.** Slight redundancy in the file; no conditional schema; every invariant names
its field exactly.

---

## ADR-015 addendum — full predicate, `inset_by`, and the publication boundary

**The predicate is fill AND size AND position.** `match` governs how many paths the **full**
predicate may resolve to — *not* how many share a fill. Fill alone is ambiguous almost
everywhere, and the ambiguity carries points:

| fill | paths | discriminator | at stake |
|---|---:|---|---:|
| `#4e5252` | 6 | **position** — all six are note targets, same fill *and* same 79.7 mm size | 120 pts |
| `#b5b5b6` | 2 | **position only** — both cable areas are 16,514 mm², 114.5 × 217.9, identical | 30 pts |
| `#a0d187` | 4 | position — the four randomized start squares | — |
| `#c92027` / `#1f7941` | 2 each | size or position — target inner 47.8 mm vs fixed start 31.9 mm | — |

Position takes a **point + tolerance** under `match = "exact"` and a **region** under
`match = "union"`. `union` additionally requires `expect_paths`, and asserts `union_bbox_mm`
as an **equality** — a containment test against the paths' own union bbox is true by
construction and guards nothing.

**`inset_by` — a new selector verb.** `backstage` is S1's pink area *excluding* its grey
border, and that polygon is not any path in the dump. `inset_by` consumes a **measured vertex**
of the named band, never an area subtraction:

```toml
[areas.backstage]
select   = "#cf8fbb"
inset_by = "#d6d0cc"    # the L-band's INNER VERTEX
# -> [0, 0, 393.809, 317.219]   all four values from measured paths
```

Deriving it by subtracting areas gives 124,920.48 instead of the correct **124,923.697**,
because the band runs 0.013 mm past the pink and the L-corner is not a clean rectangle
difference. **Never derive a polygon area by subtracting another path's area.** `backstage`
is `inset_by`'s only user today.

**Border detection is a process, not an accident.** `backstage`'s border was found by tripping
over a dropped to-do. The reusable form is a **border signature**: a different-hex fill whose
bbox matches the area's on all four edges within `BORDER_MATCH_TOL_MM = 0.5`, with
`area/bbox < 0.5`. The tolerance is justified by a sweep, not fitted: the positive fires from
0.02 mm (the real edge delta is 0.013) and holds to 10 mm, while all other scoring areas stay
negative at **every** tolerance from 0.001 to 10 mm. Run over all 255 points, only `backstage`
has a border.

**Publication boundary.** This repository is **public**. `docs/citations.json`'s caps —
≤ 15 words per quote, one entry per `(source, rule)` — are therefore the *publication
boundary*, not internal tidiness, and the same reasoning gitignores `docs/extracted/**/text/`
and the S6 HTML snapshots. The uniqueness cap matters as much as the word cap: without it a
long rule could be reassembled from several individually-compliant fragments.


---

## ADR-016

### `manifest.json` describes the last run, not a merged history

**Context.** `build_field_spec.py` pins its provenance to hashes recorded in
`manifest.json` — `vector/drawings.json` and the `img/p001_3832.json` sidecar that
`start_area` derives from. Running `pdf_extract.py probe docs/*.pdf` afterwards **rewrote the
manifest with a single output**, and the builder failed with a bare `KeyError`. This was hit
for real: the Definition-of-Done check in an earlier session re-ran `probe`, silently
truncating the record of the preceding `all` run.

**Options.**

| Option | Effect |
|---|---|
| Merge outputs into any existing manifest | the file becomes dependent on **run order**, so two clones with the same input can hold different manifests — this destroys the byte-identity guarantee that ADR-008/010 rest on |
| Keep last-run semantics, fail clearly downstream | the manifest stays a faithful, reproducible record of exactly one command |
| Write a separate always-append log | a second provenance source, i.e. one fact with two homes |

**Decision.** Keep last-run semantics. `manifest.json` describes **exactly one command**, so
it stays reproducible. `build_field_spec.py` validates up front that the manifest contains
every output it intends to pin, and fails with the command needed to fix it:

```
docs/extracted/.../manifest.json describes command 'probe' and is missing
['vector/drawings.json', 'img/p001_3832.json'].
field_spec.json pins the whole extraction chain, so it needs a manifest from a full run:
    uv run python tools/pdf_extract.py all docs/WRO-2026-GameMat-Elementary-Printing-File.pdf
```

**The footgun, and its guard.** `probe docs/*.pdf` is a Definition-of-Done command, and
running it truncates all four manifests — this bit twice during the session that introduced
the builder, the second time inside the verification sweep itself. So `pdf_extract.py` gained
**`--no-manifest`** for read-only inspection:

```bash
uv run python tools/pdf_extract.py --no-manifest probe docs/*.pdf   # inspect, clobber nothing
```

Documenting the hazard was not enough; a flag that removes it is.

**Consequence.** `field_spec.json` can only be built from a manifest produced by `all` (or by
a run covering both `vector` and `images`). That is a real constraint on the workflow, and it
is stated in the error rather than left to be rediscovered. The alternative — a merged
manifest — would have traded a loud, one-line-fix failure for a silent loss of reproducibility.

---

## ADR-017

**A flexible object gets the rigid carrier's footprint, and says so.**
`2026-07-26 · Phase 4 part 3 · accepted`

**Context.** The two cables are not rigid bodies. Each is a red Technic Brick 1×16 carrier
(part 3703, ×2 side by side) plus a **flexible hose** (part 78c18) — S3 page 173 draws the hose
alone, and page 174 shows the finished cable with the hose arched over the carrier. A flexible
element has no fixed contact patch: its footprint depends on how it is laid. But the cables are
worth **30 points** under "completely in the grey area and upright" (S1 §3.1), so the scorer
needs a number.

**Options.**

| Option | Effect |
|---|---|
| Bounding box of carrier + hose exactly as S3 draws it | encodes **one arbitrary pose** of a bendable part as if it were a property of the object — the same class of error as reading the 4×8 plate as the note base (see ADR-014's discipline) |
| No footprint at all; defer to calipers | nothing unverified enters the repo, but Phase 6's scorer gets no cable geometry, and the cable is the one object whose geometry actually decides a scoring outcome |
| **Rigid carrier only, with the gap flagged** | a real measurement for the part that determines placement, and an explicit statement of what is not covered |

**Decision.** `contact_footprint_studs` is the **rigid carrier**: 2 × 16 studs = 16.0 × 128.0 mm.
Alongside it, `flexible_element: true`, `hose_footprint_studs: null` and
`footprint_covers: "the rigid carrier only"`.

**Consequence.** The scorer can evaluate cable containment, and it can tell that the hose is not
in the number. The measurement immediately produced a hard constraint that would have been
invisible under the "defer" option: 128.0 mm of cable does not fit across a 114.47 mm area, so
the cable's placement **orientation is forced** (see `docs/PHASE7_CONSTRAINTS.md` §7).

---

## ADR-018

**Non-scoring runs live in a separate table, never in `objects`.**
`2026-07-26 · Phase 4 part 3 · accepted`

**Context.** The cream run-preview box (ADR-019) partitions S3 into 20 runs, but a run is not
always a model. Six of them build a **sub-assembly** inside a larger model: page 73 sits inside
the microphone, page 96 inside the keyboard, and pages 130/132/138/140 inside the amplifier.
None of these is an object in the frozen CLAUDE.md §5.3 / ADR-012 id table, and part 1 had
already been misled by two of them into recording "unresolved spans".

**Options.**

| Option | Effect |
|---|---|
| Extend the frozen id table with non-scoring ids | amends a table deliberately frozen in an earlier session, and weakens `test_every_model_id_is_a_frozen_canonical_id` to the point where it no longer catches anything |
| Leave them in `unresolved` | permanently marks as unknown something the preview does in fact explain, and leaves Phase 4 unable to close |
| **A separate `[[subassemblies]]` table** | the frozen table is untouched and the canonical-id test keeps its full force |

**Decision.** `docs/object_map.toml` gains `[[subassemblies]]` with free-form ids
(`sub_073_mic_arm`, `sub_140_amp_stack`, …), each naming the model it sits `inside`. The builder
emits them under a sibling `"subassemblies"` key in `object_spec.json` and **hard-fails** if any
id collides with an object id, if a sub-assembly escapes its parent's page range, or if a run
preview exists that neither a model nor a sub-assembly claims.

**Consequence.** Every one of the 20 preview boundaries is now accounted for by exactly one
entry, and `objects` contains exactly the 16 frozen ids — no more, no fewer.

---

## ADR-019

**The cream run-preview box replaces the parts callout as the model-boundary signal.**
`2026-07-26 · Phase 4 part 3 · accepted`

**Context.** Parts 1 and 2 derived model boundaries from the light-blue parts callout
`(215, 238, 254)` and recorded a caveat that the signal degrades after page 124 — "callouts also
mark sub-assemblies, producing 1–2 step 'models' that are not models". That caveat was written as
if it described a limitation of the source. It described a limitation of the **wrong signal**.

S3 draws a **second** box colour, cream `(255, 245, 218)`, which parts 1 and 2 never looked for.
A flat-colour census over all 174 build pages confirms there are exactly two box backgrounds and
no third; every other flat colour is brick paint.

| Box | Background | Pages | Meaning |
|---|---|---|---|
| parts callout | `(215, 238, 254)` | 152 | the part(s) added by **this step** |
| **run preview** | `(255, 245, 218)` | **20** | a picture of **what this run produces** |

Every cream box is anchored at `y = 98`. Its contents are the identification evidence: page 26's
is the finished blue note, page 102's the finished congas, page 153's the finished speaker with a
`2x` multiplier beside it.

**Decision.** Re-derive **every** boundary from the run preview, treating parts 1 and 2's ranges
as provisional rather than patching them. The builder asserts that the models tile the build
steps exactly and that every model start lands on a preview page.

**Consequence — three of part 1's facts were wrong, and are recorded as superseded.**

| Fact | Part 1 | Part 3 | How it was caught |
|---|---|---|---|
| `instrument_guitar` | pages 114–123 | **114–125** | page 124 still shows the guitar mid-build |
| `cable` | pages 167–172 | **167–175** | no preview after 167 |
| `mic` | 66–72, with 73–88 unresolved | **66–88** | p72 shows the column uncapped, p88 capped |
| `instrument_keyboard` | 89–95, with 96–101 unresolved | **89–101** | p101 shows the assembled keyboard |
| build steps | 176, pages 2–177 | **174, pages 2–175** | pages 176–177 are the parts inventory and carry no step numeral |

The step-count error has a precise cause worth recording: part 1 verified its claim with a digit
census that read 9 one-digit, 90 two-digit and 77 three-digit numerals. The three-digit bucket is
**75**; the census counted the inventory pages' `24x` and `3003` labels as step numbers.
9 + 90 + 75 = 174. **A cross-check can agree with a wrong answer if it measures the wrong thing.**

All three of part 1's unresolved spans are closed, and all 16 objects are mapped.

---

## ADR-020

**`sim/` is a package, and every open interpretation is a named parameter.**
`2026-07-27 · Phase 6 · accepted`

**Context.** Phase 6 needs a scorer. Two questions had to be settled before writing one: where
it lives, and what it does about the five interpretations that are still open.

Everything in `tools/` so far is a *build script* — it reads sources and writes a `data/*.json`
artefact. A scorer is not that: it is a library that other code calls, and Phase 8 will call it
thousands of times per strategy comparison.

**Options.**

| Option | Effect |
|---|---|
| Add `scoring.py` to `tools/` | conflates "script that emits an artefact" with "library that is imported"; `tools/` is on `pythonpath` as flat modules, so a multi-file scorer would collide in a flat namespace |
| A `src/wro/` layout with an installable package | conventional, but `pyproject.toml` sets `package = false` deliberately — this repo is scripts plus data, and making it installable would add a build step to every `uv run` |
| **A `sim/` package on `pythonpath`** | the scorer is importable as `sim.scoring`, `tools/` keeps its flat-module contract, and nothing needs installing |

**Decision.** `sim/` — `geometry.py`, `world.py`, `scoring.py`, `sensitivity.py` — added to
`pytest`'s `pythonpath` alongside `tools`.

Every open interpretation becomes a field on a frozen `ScoringParams`, defaulted to its
register entry, never hard-coded:

| Parameter | Ambiguity | Default | Status |
|---|---|---|---|
| `moved_semantics` | A1 | `or` | OPEN → S6 |
| `upright_tolerance_deg` | A2 | 15.0 | demoted; the operative test is contact |
| `held_at_timeout` | A5 | `partial` | RESOLVED S6 2026-06-30 |
| `bonus_only_forces_120s` | A8 | `True` | OPEN → S6 |
| `footprint_reading` | A7 | `contact` | OPEN → S6 |

**Consequence.** No scoring result can be quoted without the parameter set that produced it,
and resolving an ambiguity is a one-line change rather than a hunt through predicates. The
sensitivity sweep exploits this directly: it runs the whole grid under **both** A7 readings
rather than choosing one, which is what surfaced the 2.6× accuracy cost of that open question.

---

## ADR-021

**Area geometry comes from the polygon, never from `bbox_mm`.**
`2026-07-27 · Phase 6 · accepted, and it corrects ADR-019's session`

**Context.** Phase 4 part 3 published a cable constraint built on `field_spec.json`'s
`bbox_mm`: *"the grey cable areas are 114.47 × 217.89 mm, so a 128 mm cable is 13.53 mm too
long to fit across."* The conclusion was right and the numbers were wrong.

The two cable areas are **rotated rectangles** — 79.700 × 207.201 mm at 80° and 100°. For a
rotated shape the axis-aligned bounding box is strictly larger than the shape: 114.47 mm across
where the area is 79.700 mm. Eight of the ten scoring areas happen to be axis-aligned, which is
precisely what makes the substitution invisible in testing and wrong in the one case that
mattered.

**The data already said so, twice.** `field_spec.json` records `area_mm2 = 16513.822` for
`cable_area_upper` against a bounding-box area of 24,941.9 mm² — a 34 % gap that only a rotated
shape produces. And `ROADMAP.md` already recorded the cable area as **2.5 × 6.5 design units**
= 79.75 × 207.35 mm, which agrees with the polygon and contradicts the bbox reading. Two
independent records were correct; the derived figure was wrong because it came from a
convenience field instead of the geometry.

**Decision.** `bbox_mm` is a convenience index for *filtering and pre-checks only*. Any figure
that will be quoted, tested or designed against comes from `polygon_visible_mm`, via
`sim.geometry.min_area_rect`, which recovers a rectangle's own axes exactly.

**Consequence.** The corrected figures, with what they superseded and why, are in
`docs/object_map.toml` `[cable_orientation.correction_2026_07_27]`. The error direction is
recorded too, because it is the dangerous one: slack was **overstated** (44.94 mm against a
true binding 31.85 mm).

The substantive loss was not a number. Aligning to the mat axes hid that the two areas tilt in
**opposite** directions, so the two cables need **different, mirrored headings** — a robot that
places both identically gets one wrong, worth 15 points. Guarded now by
`tests/test_geometry.py::test_the_cable_areas_are_rotated_and_the_others_are_not` and
`tests/test_scoring.py::test_the_two_cables_get_mirrored_nominal_headings`.

---

## ADR-022

**Motor budget: 2 drive + 0 yaw + 2 manipulator. The mechanism stays gated on mass.**
`2026-07-27 · Phase 7 part 1 · accepted`

**Context.** `docs/PHASE7_CONSTRAINTS.md` §1 has carried this instruction since Phase 5:

> Either the manipulator is passive/geometric, or pneumatics buy DOF at the cost of one slot.
> **Record whichever way this goes as an ADR with the arithmetic shown; do not assert a
> topology without it.**

S4 §5.2.8 gives Elementary **4 motors**. A differential drive takes 2, leaving 2 for twelve
placement operations. The open question was whether those 2 suffice, and what else competes
for them.

**The arithmetic, now that it exists.** `data/manipulator_requirements.json` derives three
things from the frozen specs rather than assuming them:

| | |
|---|---|
| **Grip span** | 32 mm for 8 of the 12 objects; 56 mm (bound) for the keyboard; 112 mm (bound) for the congas; 128 mm for the cables |
| **Yaw tolerance** | measured by scanning the containment predicate — **unbounded** for 10 of 12 objects, **±31°** for the two cables |
| **Placement accuracy** | from `data/placement_sensitivity.json`, both A7 readings |

**Decision — the budget.**

```
2 slots   differential drive
0 slots   yaw
2 slots   manipulator, both available
```

**Yaw costs nothing, and this is the load-bearing finding.** A 32 mm object in a 79.7 mm
square target fits at *every* heading — its diagonal is 45.3 mm. Only the cables constrain
heading at all, and their tolerance is ±31°, which a differential drive holds comfortably.
A dedicated yaw actuator would buy nothing and cost half the manipulator budget.

This **corrects** `PHASE7_CONSTRAINTS.md` §7 as published on 2026-07-26, which said of the
cable *"along-axis accuracy is not the problem here. Rotation is."* Measured, translation
dominates: σ for P ≥ 90 % is 13.90 mm with rotation coupled against 17.68 mm without, so
rotation costs 21 % of the tolerance rather than being the binding term.

**What the budget buys — the capability ladder.**

| grip span | objects | run total | left on the table |
|---:|---:|---:|---:|
| 32 mm | 8 | **195 / 255 (76 %)** | 60 |
| 56 mm | 9 | 210 / 255 (82 %) | 45 |
| 112 mm | 10 | 225 / 255 (88 %) | 30 |
| 128 mm | 12 | 255 / 255 (100 %) | 0 |

Run totals include the 40-point bonus floor, because a robot that handles nothing still
scores 40 (S6 2026-06-17). **A mechanism that only ever grips 32 mm reaches three quarters of
the maximum.** That is not a recommendation to build one; it is the price list.

**Not decided — the mechanism.** Parallel gripper, fork, scoop or passive geometry all satisfy
the span and accuracy requirements on paper. What separates them is whether a mechanism can
lift and hold a 128 mm cable without dropping it, and that needs **object mass and grip
points**. `mass_g` is `null` for all 16 objects because no building instruction contains it.

Asserting a topology from footprints alone is precisely the "topology without arithmetic" §1
forbids, so it is refused rather than guessed.

**Consequence.** The chassis is fully designable: the drivetrain allocation is fixed, and the
manipulator's envelope is bounded by a 128 mm span with two free motor slots. The mechanism
decision is reduced to a single measurement — weigh the objects and identify grip points —
which is added to `docs/FIELD_TEST_PLAN.md`. S4 §5.1 leaves post-start size unrestricted, so a
deployable mechanism remains legal whichever way that measurement goes.

---

## ADR-023

**`RobotIO` is intent-level, and portability is linted rather than assumed.**
`2026-07-27 · Phase 7 part 2 · accepted`

**Context.** `docs/FIELD_TEST_PLAN.md` Step 1 states the project's core invariant and then
admits it is unverified:

> mission code imports only `robot_io.RobotIO`, so one file runs on the simulator and on
> hardware. **That is currently an untested claim.**

It also assumes the test needs two hubs — which are the project's bottleneck. Two decisions
were needed: what the contract exposes, and how much of the claim can be tested without
hardware.

**Decision 1 — the manipulator surface is intent, not actuators.**

ADR-022 fixed the motor budget at 2 drive + 0 yaw + 2 manipulator but deliberately left the
*mechanism* open, gated on object mass and grip points.

| Option | Effect |
|---|---|
| `actuator_a(position)` / `actuator_b(position)` | mirrors the two free slots honestly, and bakes one mechanism into all twelve mission files — changing from a gripper to a fork would rewrite every one |
| Both layers | mission code can bypass the abstraction, so the portability guarantee is only as good as the layer people happen to use |
| **`pick_up()` / `place()` / `carrying()`** | a fork, scoop, gripper or passive geometry each implement it differently and **no mission file changes** |

Intent survives an open mechanism decision; actuators do not. That is the whole reason ADR-022
was able to refuse the mechanism without blocking anything.

The same reasoning excludes a convenience method. Pybricks offers `ColorSensor.color()`, which
classifies to seven fixed colours — and conveniently covers all six note colours. The contract
does **not** expose it: S4 §7.10 has mat brightness varying table to table and lighting hour to
hour, §9.3 puts calibration in practice time and requires it to survive quarantine, and §5.2.7
prohibits cameras so there is no fallback. Sensing must be ratiometric, so the contract exposes
the scalar `read_reflection()` and nothing that invites an absolute threshold.

**Decision 2 — lint the portability claim.**

The risk in "one file runs on both" is not electrical, it is **linguistic**: the simulator is
CPython 3.13 and both hubs are MicroPython, EV3's from **May 2020**. A construct CPython accepts
and MicroPython rejects is a syntax error discovered on the competition table.

`tools/check_portability.py` walks the AST of every hub-bound file and rejects what those ports
cannot run. **Every rule cites its evidence**, because a lint rule without a source is a style
opinion:

| Rule | Evidence |
|---|---|
| no f-strings | MicroPython added them in **1.17, September 2021**; EV3 MicroPython v2.0 is **18 May 2020** |
| no `typing` / `dataclasses` / `abc` / `enum` / `__future__` | absent from MicroPython — which is also why the contract is a plain class and not an `abc.ABC` |
| no `async` / `await` | not on these ports |
| no relative imports | hub files are copied flat |
| imports restricted to an allowlist | a hub resolves only its own frozen modules |

**Consequence.** The claim is now tested on every commit, without hardware. Eleven parametrised
cases assert the lint *rejects* each construct — a lint that has never rejected anything is not
evidence. Hardware is left to test only what hardware can: that the Pybricks calls behave as
documented.

The `sim/robot_io_sim.py` backend closes the loop. A mission runs against it, the resulting
world goes to `sim.scoring.Scorer`, and the score is asserted — so **mission logic is verifiable
today**. It is explicitly not a performance model: no friction, slip, drift or motor response,
because every one of those is an unmeasured `ASSUME:` until P1–P6. Same line Phase 6 drew.

**A finding from building it.** `SimRobotIO.pick_up()` originally took the nearest object.
Because 15 of 17 start poses are `nominal_pending` with null coordinates (ADR-014), unplaced
objects all sit at the origin — and dict order silently handed the robot the **amplifier**,
which it carried to a note target, losing 10 bonus points and 20 note points while the test
reported a pass. `pick_up()` now **raises on ambiguity**. Reaching for the nearest thing is
what a real robot does; a *test* that does it is not testing what it claims.

---

## ADR-024

**S6 is parsed structurally, and the EV risk term is a worst case rather than a constant.**
`2026-07-27 · S6 re-verification + Phase 8 part 1 · accepted`

Two decisions, taken together because the S6 re-read is what prompted looking at both.

### Part 1 — the S6 indexer parses markup, not shape

**Context.** `CLAUDE.md` §5.1 requires S6 to be re-read *"before any scoring or robot-limit
claim, and at least weekly."* Phases 6 and 7 made many such claims against a 2026-07-25 snapshot
and never re-read it. Discharging that obligation surfaced a defect.

`tools/s6_index.py`'s docstring is emphatic:

> Do NOT diff on the page's `Last-Modified` header: on a WordPress site that is a render/cache
> timestamp and moves on plugin, theme and footer edits.

But its entry regex matched a generic `>text< … >name< … >timestamp<` shape **anywhere on the
page**, including the page's own JSON-LD `schema.org` block. That produced a tenth phantom
entry — `admin · "Questions & Answers" · 2026-06-30T18:45:33+02:00` — whose timestamp **is** the
page's modified time. A theme edit would move the phantom and `--check` would report a content
change that had not happened: exactly the false positive the docstring was written to prevent,
reintroduced through the back door.

**Decision.** Parse within the FAQ panel markup —
`<div class="… fusion-faq-post fusion-faq-post-NNNN AGEGROUP">` plus its `entry-title` /
`vcard fn` / `updated` spans. Structural, so page furniture cannot masquerade as an answer.

**Consequence, and an upgrade.** `entry_count` drops **10 → 9**, which is a fix and not a lost
answer; the test that pins it says so, because a bare decrement would otherwise read as an
alarm. The panel class also carries the **age group**, which the docstring's stated diff tuple
`(section, question, author, timestamp)` had always promised and the code never delivered. So
the index now knows that **only 4 of the 9 answers bind this project** — 3 RoboMission
(all age groups) and 1 RoboMission Elementary. Junior, RoboSports and Future Innovators do not.
A weekly check that cries wolf over a RoboSports answer stops being run; one that says *"a new
Elementary answer appeared"* does not.

An unrecognised section is treated as **binding**. If WRO adds a category, the conservative
answer is "look at it".

**The fix is in the parser, proven separately.** Running the repaired parser over the *old*
2026-07-25 snapshot also yields 9, not 10 — so the drop is not a difference between the two
snapshots. That check cannot live in CI: `.gitignore` excludes
`docs/s6-qa-snapshot-*.html` as third-party content, and only the index is committed. It is a
manual step alongside `--check`, and it is recorded here because it is the evidence.

**S6 itself is unchanged.** The 2026-07-27 fetch is byte-identical to the 2026-07-25 snapshot
(sha256 `d6667dfb…`, 156,091 bytes), and all nine answers match. Phases 6 and 7 rest on current
rules. The schema bump is handled: `--check` against an older index compares on the common
fields and says so, rather than screaming once per upgrade for ever.

### Part 2 — the EV risk term decomposes

**Context.** `CLAUDE.md` §5.6 and `data/scoring_model.json` both state

    E[Δscore] = P(success) × points − P(collision) × 40

**The 40 is not one object.** It is clef 10, speakers 2 × 10, amp 10 — and S1 places them
apart: the amplifier and both speakers *"on the stage at the left end of the game field"*, the
clef *"in the middle on the left end of the staff lines"*. So a route exposes the cluster it
passes, not all four.

**Decision.** Sweep three risk tiers — 10, 30, 40 — in `data/strategy_frame.json`, and **retain
40 as the conservative default**. §5.6's intent, that EV is never written as a gross point gain,
is correct and unchanged; only the magnitude is refined, and only with the exposed cluster named.

**Consequence.** Which tier applies decides whether a mission can ever be not-worth-attempting:

| zone | missions | points | distance from start | bonus exposed | break-even P(collision) at P(success)=1 |
|---|---|---:|---:|---:|---:|
| left stage end | 2 cables, mic, 3 instruments | 95 | 1923–2130 mm | **30** | 0.38–0.67 |
| right staff end | 6 notes | 120 | 367–1110 mm | **10** | **2.0 — always worth attempting** |

A note is worth 20 against a 10-point clef, so no collision probability makes one not worth
attempting. Under the flat ×40 it would appear to break even at 0.5. The left-hand missions are
genuinely conditional, and they are also eight times less dense in points per metre travelled
(3.5 for a cable against 27.3 for the nearest note).

**This orders nothing.** Mission ordering is Phase 8 proper and needs σ from field tests P2/P3
plus the pickup locations, 15 of which are `nominal_pending` with null coordinates (ADR-014).
`CLAUDE.md` §5.7 anti-pattern #3 forbids claiming one strategy beats another without simulator
evidence; this supplies the cost and risk inputs to that claim, not the claim.

---

## ADR-025

**An operator-dependent blocker carries the date it was last confirmed.**
`2026-07-27 · accepted`

**Context.** From Phase 4 until today this repo recorded itself as blocked on procurement. Four
documents said so — the ROADMAP carried an `S · WRO sets` node in red, `FIELD_TEST_PLAN` marked
P5 "BLOCKED on physical game objects", `PHASE7_CONSTRAINTS` §8 said "the reason is now
procurement, not analysis", and ADR-022 gated the manipulator mechanism on sets "the team does
not yet hold". Four consecutive commit messages closed with some version of *"the sets are the
one action that unblocks everything."*

**It was never true.** The operator holds all of it: EV3 Core Set 45544, SPIKE Prime 45678 +
Expansion 45681, WRO Brick Set 45811 + Expansion 45819, the printed mat, and a competition-spec
table.

**Root cause.** An operator answer of *"partially / not sure yet"*, given once, was written down
as *blocked*. Nothing after that re-asked. Every later phase inherited the framing from the
document before it, and each inheritance made it look better established — by the fourth
repetition it read as a settled fact with four independent sources, when it had one ambiguous
source and no date.

The failure is not the original answer, which was honest. It is that **an expression of
uncertainty was flattened into a state, and the state had no expiry.**

**Options.**

| Option | Effect |
|---|---|
| Re-ask everything each session | thorough, and unworkable — most facts do not change |
| Treat operator answers as durable | what happened; a "not sure yet" silently becomes permanent |
| **Date every operator-dependent claim** | the claim carries its own staleness, and a reader can see when to re-ask |

**Decision.** Any blocker that depends on operator state — hardware held, procurement, a
national-organizer decision, a Q&A submission — is recorded with **the date it was last
confirmed**. An undated one is treated as unverified, not as true. Ambiguous answers are
recorded as *ambiguous* rather than resolved to whichever reading is more conservative: "not
sure yet" is not a synonym for "no".

This is the operator-state analogue of what `docs/ASSUMPTIONS.md` already does for `ASSUME:` —
every one of those carries a consequence-if-wrong, and the point is the same. An assumption
without a consequence is a guess; a blocker without a date is a rumour.

**Consequence.** `docs/HARDWARE_SESSION.md` is the work order that should have existed six
phases ago. The remaining operator-dependent items now carry dates:

| Claim | State | Last confirmed |
|---|---|---|
| All hardware held | **yes** | 2026-07-27 |
| `NEEDS-VERIFY(NO-TH)` — Thai National Organizer | unconfirmed | never asked |
| A7 / A1 / A8 submitted to the official Q&A | not submitted | 2026-07-27 |

**Scope.** This is about *recording* state, not about deciding anything. It does not license
assuming an operator answer — the opposite: it forces the question to be re-asked rather than
inherited.

---

## ADR-026

**Expected value carries the partial tier, and measurement paths ship inert.**
`2026-07-27 · accepted`

### Part 1 — a correct number with a wrong usage instruction

**Context.** `data/strategy_frame.json` publishes `breakeven_p_collision_at_p_success_1` and,
beside it, the rule `P(collision)* = P(success) × points / risk` with `linear_in_p_success:
true`.

**The values are correct.** They are the σ → 0 limit, where `p_full = 1` and `p_partial = 0`, so
`E = points` exactly.

**The rule attached to them is not.** A missed placement usually does not score zero — it scores
the **partial** tier, and `data/placement_sensitivity.json` has carried the per-tier
probabilities since Phase 6. Applying the linear rule at any σ > 0 understates EV:

| σ | p_full | p_partial | **p_none** | by that rule | true |
|---:|---:|---:|---:|---:|---:|
| 15 mm | 0.749 | 0.251 | 0.000 | 14.98 | **17.49** |
| 20 mm | 0.522 | 0.469 | **0.008** | 10.44 | **15.13** |
| 30 mm | 0.278 | 0.625 | 0.097 | 5.56 | **11.81** |

Up to **45 %**. And the shape matters more than the size: **`p_none` stays near zero**. A note
almost never scores nothing — it scores 20 or 10. Attempting one is far safer than the linear
rule implied.

**Decision.** `tools/build_expected_score.py` → `data/expected_score.json` computes

```
E[score](σ, P_collision) = 40  +  Σ p_full·full  +  Σ p_partial·partial  −  P_collision·risk
```

and `strategy_frame.json` records the superseded rule rather than deleting it.

**It is not a blanket factor.** Cable 5/15, microphone 10/20, note 10/20 — and the three
**instruments have no partial tier at all**, so for them the old rule was exactly right. A
uniform correction would have been a second error.

**Consequence.** The full-attempt run degrades gracefully rather than falling off a cliff: even
at σ = 20 mm the expected total is **216/255** on the contact reading. On the silhouette reading
it is 192 — A7 again, and again worth more than any measurement in the work order.

**The pattern is worth naming.** This is the second EV correction in three units — ADR-024
corrected a flat ×40 risk term that should have been 30 or 10 — and **both were pessimistic, and
both were in artefacts I built**. Neither was caught by a test, because both were errors in what
the number *meant* rather than in what it computed. The tests added here assert the *relationship
between* published numbers, which is the class of thing that would have caught either.

### Part 2 — measurement paths ship inert

**Context.** The work order needs three measurements to land: mass (A2), calipered footprints
(A4), start poses (B0). None had anywhere to go — `mass_g` was hard-coded `None`,
`object_map.toml` carried only derived stud counts, and `nominal_pending` was hard-coded for ten
objects. The work order itself said *"one-line change needed first"* and warned: not before,
"so the field cannot quietly carry a placeholder".

**Decision.** Wire all three now, each **read-if-present**, and test that every one is inert:
all 16 masses `null`, all 10 start poses `nominal_pending`, every footprint still stud-derived.

A calipered footprint **supersedes** the derived one and keeps it as
`derived_contact_footprint_mm` with an agreement flag — because Phase 4 derived every dimension
in this project by counting studs in a raster, and a disagreement between two independent
methods is a finding, not a value to overwrite.

**Consequence.** The session is spent measuring rather than editing builders: type numbers into
TOML, re-run, get an updated spec. Verified end to end by putting a mass and a pose through both
paths and reverting.
