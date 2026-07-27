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
| [ADR-027](#adr-027) | The objective is `E[max of N rounds]`, not `E[score]` of one attempt | accepted 2026-07-26 |
| [ADR-028](#adr-028) | A rounded probability is not a probability distribution | accepted 2026-07-26 |
| [ADR-029](#adr-029) | Travel is a budget; capacity buys it; `strategy_frame` never costed a mission | accepted 2026-07-26 |
| [ADR-030](#adr-030) | A bounded start beats a pending one — the truck, and the pick-and-place cliff | accepted 2026-07-26 |
| [ADR-031](#adr-031) | The feasibility frontier; speed saturates; the instruments are σ-proof | accepted 2026-07-26 |
| [ADR-032](#adr-032) | The first end-to-end score, and which unknown to measure first | accepted 2026-07-27 |
| [ADR-033](#adr-033) | `A1`–`A5` renamed to `MEAS-`; S6's scope stated; the seven questions drafted | accepted 2026-07-27 |
| [ADR-034](#adr-034) | The tilt proxy measured friction, not centre of gravity | accepted 2026-07-27 |

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

**A third addition, 2026-07-26 (ADR-030).** `truck_vehicle_left` and `truck_vehicle_right`,
`scoring = false`, for the two `#afbbdf` bodies that S1 p4 starts four objects in. Directly
analogous to sub-decision 2 above — measured mat geometry the model needs, kept out of the
`completely_in` predicate by construction — and pre-authorised in writing by
`docs/area_map.toml`, which described the mechanism and deferred it.

**What "frozen" means, stated because it was tested.** Frozen forbids **renaming and
substitution**: no downstream file may invent a synonym or quietly swap one id for another.
It does not forbid *adding* measured geometry under a new id. An addition costs an ADR, which
is exactly the friction intended — three in this project so far, all recorded here.

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
| `NEEDS-VERIFY(NO-TH)` — robot limits (S4 §4.3, §5.2) | unconfirmed | never asked |
| `NEEDS-VERIFY(NO-TH)` — **tournament format** (S4 §9.1.2, §10.13, §10.14): round count, aggregation rule, mulligan offered?, practice interleaved? | unconfirmed | never asked — added 2026-07-26, ADR-027 |
| A7 / A1 / A8 / A10 submitted to the official Q&A | not submitted | 2026-07-27 |

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

---

## ADR-027

**The objective is `E[max of N rounds]`, not `E[score]` of one attempt.**
`2026-07-26 · accepted`

**Context.** Phase 8 optimises the expected score of a **single attempt**. Everything downstream
of it — `data/expected_score.json`, the break-even `P(collision)` table in
`data/strategy_frame.json`, ADR-024, ADR-026 — inherits that objective. Nothing in the repo ever
stated it, and S4 does not support it.

Three rules, quoted rather than paraphrased:

| Rule | Text | What it settles |
|---|---|---|
| §9.1.2 (p12) | "A number of robot rounds." | the count is **unspecified** |
| §10.13 (p14) | "The ranking of teams depends on the overall tournament format. **For example**, the best attempt out of three rounds could be used and if competing teams have the same points, the ranking is decided by the record of time." | the aggregation rule is **organizer-set**; best-of-three is an *example*, not the rule |
| §10.14 (p14) | "Mulligan (optional element)… If a team decides to redo the run the new score will be used for the ranking **no matter what**." | a **replacement**, not a maximum — never recorded here before |

**Why it changes anything.** Under a best-of-N ranking the objective is `E[max(X₁…X_N)]`, which
**rewards variance**. Two strategies with equal means and different spreads stop being
equivalent, and ranking them by `E[X]` gives the wrong order.

That is exact, not a heuristic. For two rounds,

```
E[max(X₁, X₂)]  =  E[X]  +  E|X₁ − X₂| / 2
```

— the premium *is* half the Gini mean difference, a pure dispersion measure, and nothing else.
The identity is asserted in `tests/test_rounds.py` by double summation over the pmf, which shares
no code path with the powered-cdf method the module uses. For N > 2 the premium is still a
dispersion functional, increasing in the convex order, so the direction holds for any N.

Measured — exact convolution over the integer points axis, no sampling (`sim/rounds.py`):

| σ (mm) | `E[X]` | sd | `E[max2]` | `E[max3]` | **premium @ N=3** |
|---:|---:|---:|---:|---:|---:|
| 10 | 251.7 | 5.6 | 254.2 | 254.8 | **+3.0** |
| 15 | 235.5 | 12.3 | 242.2 | 245.3 | **+9.8** |
| 20 | 216.3 | 15.1 | 224.7 | 228.8 | **+12.5** |
| 30 | 184.7 | 17.2 | 194.3 | 199.0 | **+14.4** |
| 45 | 150.7 | 18.8 | 161.2 | 166.5 | **+15.9** |

**The premium grows with σ.** At σ = 20 mm it is worth more than a whole cable mission (15
points). That inverts the naive reading of Phase 8: extra rounds reward the *less* precise, more
ambitious strategy, because a bad round is discarded while a good one is kept. It also moves the
decision that ADR-024 framed — `cable_upper` at σ = 20 mm tolerates `P(collision)` of **0.398**
across one attempt but **0.603** across three.

**Decision.** `sim/rounds.py` supplies the distribution and the objective;
`tools/build_round_strategy.py` → `data/round_strategy.json` tabulates both, **parametric in N**.
`data/expected_score.json` is not superseded — it is the `N = 1` case, and the two agree to
within 0.05 points across the whole grid.

**What this does not do.** It does not rank mission subsets. That still needs the 120 s budget
and a route, and a route needs the start poses (work order **B0**) — the same refusal
`expected_score.json` already makes, for the same reason (CLAUDE.md §5.7 anti-pattern #3).

**Consequence.** `NEEDS-VERIFY(NO-TH)` now covers **two** things, not one. The robot limits were
already open; the tournament format joins them — round count, aggregation rule, whether a
mulligan is offered, and whether practice time is interleaved between rounds (§9.3 permits code
changes only during practice, which is what would make a round-level portfolio possible at all).
Until the Thai National Organizer answers, every figure here is published against N, not for it.

---

## ADR-028

**A rounded probability is not a probability distribution.**
`2026-07-26 · accepted`

**Context.** ADR-008 rounds every emitted float to 3 decimals so that runs are byte-identical.
`data/expected_score.json` therefore publishes `p_full`, `p_partial` and `p_none` at 3 decimals,
and **they need not sum to 1**: the worst single mission carries **1.001**, and across the twelve
missions of a run the excess compounds multiplicatively to **1.002001**.

As inputs to a **mean** this is harmless — a linear sum absorbs it, which is why it survived
Phase 8 unnoticed and why `expected_score.json` is not wrong.

As inputs to a **distribution** it is not. `E[max of N]` comes from `cdf ** N`, which amplifies
the excess: `1.002001³ = 1.006`. The first version of `sim/rounds.py` fed the published cells
straight into a convolution and reported

    E[max of 3] = 256.30      against a maximum of 255

and, from the same excess mass, a **`nan`** standard deviation at σ = 10 mm where
`E[X²] − E[X]²` went negative. Neither looks wrong in a table.

**Decision.** `sim.rounds.tier_terms` renormalises every mission before use, and
`sim.rounds.run_score_pmf` **raises** rather than returning a defective pmf. The error budget
justifies it outright: 3-dp rounding is ±0.05 pp against the underlying sweep's ±0.8 pp sampling
noise at 4000 samples per cell, so the rounding was never the dominant uncertainty.

The defect is emitted into `data/round_strategy.json` as `rounding_defect`, with the measured
masses, so a reader holding only the JSON can check the claim.

**Consequence.** Three tests, all of which fail if the renormalisation is removed: the pmf must
have mass 1 and support within `[40, 255]`; `E[max of N]` must never exceed 255; and the
historical un-renormalised path is reproduced explicitly and asserted to produce 256.30, so the
guard is a tested fact rather than a claim about history.

**The pattern, now three times.** ADR-024 corrected a flat ×40 risk term; ADR-026 corrected a
scaling rule attached to correct values; this corrects a usage that correct values do not
support. Every one was an error in what a number *meant*, not in what it computed, and none was
caught by a test of the producing code — because the producing code was right. The guard that
works is the one that asserts a **relationship the number must satisfy**: sums to one, never
exceeds the maximum, agrees with the artefact it was derived from.

---

## ADR-029

**Travel is a budget, manipulator capacity is what buys it, and `strategy_frame` never costed a mission.**
`2026-07-26 · accepted`

### Part 1 — the 120 seconds nobody had costed

**Context.** Eight phases went into **accuracy**. Nothing asked whether a run fits the two
minutes S4 §10.1 allows. `attempt_seconds: 120` sat in `data/scoring_model.json` and was quoted
in three documents; no artefact ever turned geometry into distance, and no document named a speed
the robot must reach. CLAUDE.md §5.7 anti-pattern #5 forbids optimising for 255/255 without
reporting `P(success)` — a strategy that places perfectly and runs out of clock fails the same
way, and was invisible.

**Decision.** `sim/travel.py` computes the exact minimum tour to fetch and deliver the notes, by
DP over `(notes remaining, current position)` with batches of at most `capacity`.
`tools/build_travel_budget.py` → `data/travel_budget.json` publishes it, plus the **required mean
speed** — the time analogue of the required placement accuracy already in
`placement_sensitivity.json`. A number for field test **P6** to test against.

**Scope.** The six notes only — 120 of 255 points, and the only objects whose start geometry is
known. The other six are `nominal_pending` until work order **B0**.

> **Superseded in part by ADR-030 (2026-07-26).** *"The only objects whose start geometry is
> known"* was true of `field_spec.json` as it then stood and false of the sources: the truck is
> two `#afbbdf` bodies on the printed mat, and `docs/area_map.toml` had already written down how
> to admit them. Four more objects are now **bounded**, and the covered set is ten of twelve
> missions, 185 of the 215 placement points. The two cables remain genuinely pending. Everything
> else in this ADR stands unchanged.

### Part 2 — capacity deletes the randomization, and it is a phase change

S1 p7 assigns four notes to four slots at randomization; S4 §9.6 does it **after** quarantine, so
the draw is fresh every round. Exact over all 24 permutations:

| capacity | min | median | **max** | **spread** | required mm/s at 120 s |
|---:|---:|---:|---:|---:|---:|
| 1 | 6592 | 7038 | **7592** | **999.6** | 63.3 |
| 2 | 4721 | 5283 | **5379** | 657.8 | 44.8 |
| 3 | 3952 | 4315 | **4378** | 425.8 | 36.5 |
| 4 | 3683 | 4173 | **4236** | **552.3** | 35.3 |
| 5 | 3413 | 3601 | **3839** | 425.4 | 32.0 |
| 6 | 2986 | 2986 | **2986** | **0.0** | 24.9 |

**Capacity 1 → 2 takes 2213 mm off the worst case — 29 %, the largest single step in the
project so far.** And at capacity 6 the spread is **exactly zero**, structurally: a robot that
collects every note before delivering any visits the same set of points whatever the permutation,
so the tour length cannot depend on which colour is in which slot.

**It is a phase change, not the end of a slope.** Distance falls monotonically with capacity — a
tour feasible at *k* is feasible at *k+1* — but the **spread does not**: it *rises* from 426 at
capacity 3 to 552 at capacity 4. A mechanism that carries *most* of the notes buys distance
without buying predictability. All six capacities are published for exactly this reason; the
1/2/3/6 subset would have implied a smooth trend to zero that does not exist.

**Capacity also makes sensing free.** §10.2 forbids entering the permutation before the run, so
it must be read at runtime (`PHASE7_CONSTRAINTS.md` §5). At high capacity the robot passes every
slot anyway; at capacity 1 it must spend a scanning pass or commit blind.

**This does not choose a capacity.** That needs note mass and grip geometry — work order
**MEAS-2/3** — and **ADR-022** left the mechanism open deliberately. This says what each choice buys.

### Part 3 — `strategy_frame.json` was not costing a mission

`tools/build_strategy_frame.py` computes `distance = _distance(start, centroid(target))`: **start
area to target**. The object's own starting position never enters, so the leg that *fetches* it is
missing. The values are what they compute; the claim attached to them — `scope.answers`, *"what
each mission costs in travel"* — was not supported.

The error runs **both ways**, so it is not a bound in either direction:

| note | `2 × d(start, target)` | true fetch-and-deliver | |
|---|---:|---:|---|
| `note_yellow` | 2221 | 1502 – 1598 | **overstates** ~650 |
| `note_white` | 733 | 871 – 1760 | **understates** up to 1027 |

**So `points_per_metre_round_trip` does not preserve the ranking it appears to give — and how
badly is itself randomized.** Against the true fetch-and-deliver cost, Spearman ρ is:

- **+1.000 at the luckiest permutation** — the metric is *exactly right*
- **−0.486 at the unluckiest** — the metric is *anti-correlated*

All six notes change rank between the two, `note_white` moving from 1st to 6th. The mechanism is
simple: ranking by distance to *target* flatters any target near the start area regardless of
where its object begins, and `note_white`'s target is the closest to start while its note can
begin 1760 mm away. Which draw you get is decided after quarantine.

**Decision.** Fix the claim, not the number — the ADR-026 precedent. `scope.answers` now says
what it measures; `round_trip_excludes_fetch_leg` and
`points_per_metre_is_not_a_mission_ranking` are explicit flags; a real `fetch_leg_mm` is emitted
for the six notes and `null` with a B0 pointer for the rest; the console summary leads with the
fetch leg instead of the misleading points-per-metre.

**Fourth instance of the same failure class** — ADR-024 (a flat ×40 that should have been 30 or
10), ADR-026 (a scaling rule attached to correct values), ADR-028 (rounded probabilities used as
a distribution), and now a distance used as a mission cost. Every one was an error in what a
number *meant*, none was caught by testing the producing code, because the producing code was
right. The guards that work assert a **relationship the number must satisfy** — and the one added
here is the sharpest yet: the published metric is checked against an independently computed
ranking, at both ends of the randomization.

---

## ADR-030

**A bounded start beats a pending one — the truck, and the pick-and-place cliff.**
`2026-07-26 · accepted`

### Part 1 — four objects had no geometry, and did not need to be measured to get some

**Context.** ADR-029 costed the six notes and stopped, because the other six placement missions
are `nominal_pending`. That refusal was one step too strong. `field_spec.json` carries
`start_groups.truck` — the microphone and all three instruments, *"S1 p4: lower end, in the
truck"* — with **no polygon**, leaving **65 of 255 points** with no geometry at all, so no route
through them could be costed at any capacity.

`docs/area_map.toml` had already written down the fix and deferred it:

> `truck` gets no polygon: the two vehicles are disjoint … **If the sensor model later wants the
> vehicle bodies they enter as two separate `scoring = false` areas under their OWN ids — never
> as `truck`.**

**Decision.** Take it up. Two `#afbbdf` bodies at the mat's lower edge, measured from S2 and
identical to 4 µm, enter as `truck_vehicle_left` and `truck_vehicle_right`:

| | `size_mm` | `at_mm` | built area |
|---|---|---|---:|
| left | `[321.162, 111.692]` | `[1215.550, 79.162]` | 35 818.401 |
| right | `[321.166, 111.692]` | `[1542.259, 79.587]` | 35 818.828 |

**A bound is not a pose.** `nominal_start_pose_mm` stays `null` for all four members and
**ADR-014 is untouched** — the areas say *where the objects are somewhere within*, never where
any one of them is. `scoring = false`, emphatically: this is a start region, never a target.

**ADR-012 is amended, not broken.** The canonical ID list is frozen against *renaming and
substitution*; adding measured geometry under a new id is a different act, and this one was
pre-authorised in writing by the file it lives in. `CLAUDE.md` §5.3 now says so, and gains both
ids. An addition is an ADR, never a convenience.

### Part 2 — the run, and what the pending measurement is worth

Ten of twelve missions — **185 of the 215 placement points** — enumerated exactly over a
**24 × 16 grid**: note permutations against vehicle choices, 384 joint start states. (The notes
are a bijection onto four slots; the truck is a *free product*, because S1 says only "in the
truck" and nothing forbids two objects sharing a vehicle.)

| capacity | min | median | max | spread | required mm/s at 120 s |
|---:|---:|---:|---:|---:|---:|
| 1 | 14 789 | 16 286 | 18 090 | 3 301 | **151** |
| 2 | 9 550 | 10 526 | 11 154 | 1 603 | **93** |

Keeping the grid rather than a flat list is what makes the uncertainty **decomposable**, and the
decomposition is the finding:

| source of spread | capacity 1 | capacity 2 | removable? |
|---|---:|---:|---|
| note permutation | 999 | 627 | **never** — S1 p7, randomized after quarantine (S4 §9.6) |
| vehicle choice | **2 327** | **1 088** | **yes — work order B0** |

**B0 is worth more than twice what the irreducible randomization costs.** That prices a
measurement that had no price before, and it inverts the intuition that the randomization is the
dominant unknown here — it is not; not knowing where our own objects start is.

The residual after the vehicle choice — *where on that body* — is **152–172 mm** per object,
measured over every corner of both bodies rather than bounded by the diagonal. Small because the
targets are more than a metre away, which is why the vehicle **choice** is enumerated and the
position on it is not.

**Capacities above 2 are not computed for the full run**, and both reasons are stated: the batch
enumeration is `s! × s!`, so ten missions cost ~27 s at capacity 1, ~150 s at 2 and ~22 minutes
at 3; and an instrument is not a 31.9 mm note, so carrying three of them plus the microphone is
not a design point anyone reaches. The six-note curve still runs to capacity 6, where it is both
cheap and meaningful.

### Part 3 — the cliff, which no motor can buy back

There are ten objects, so **every second of pick-and-place costs ten seconds of the attempt**:

| s per object | 0 | 2 | 4 | 6 | 8 | 10 | **12** |
|---|---:|---:|---:|---:|---:|---:|---:|
| driving seconds left | 120 | 100 | 80 | 60 | 40 | 20 | **0** |
| required mm/s, capacity 2 | 93 | 112 | 139 | 186 | 279 | 558 | **impossible** |

**At 12 s per object the attempt is entirely consumed and the run cannot be completed at any
driving speed.** The threshold is `attempt_seconds / objects = 120 / 10` exactly, so it is
**independent of distance, capacity and the randomization** — shortening the tour buys driving
speed, never pick-and-place time.

**Consequence for the work order.** This makes **A3** (grip points) a feasibility question, not
only a mechanism-selection one, and it gives the session a threshold to measure against rather
than a preference. It also means the emphasis on **P6** (motor speed) was misplaced: 93 mm/s is
undemanding for either platform, while 12 s to pick and place is not obviously safe.

**What this does not claim.** Not that the run is or is not feasible — speed is unmeasured until
P6 and pick-and-place time until a mechanism exists. Not which missions to attempt: that needs
σ (**B5**) and CLAUDE.md §5.7 anti-pattern #3 still applies. The two cables remain genuinely
`nominal_pending`; *"close to the stage (left end)"* is not a measured region, and inventing one
would be exactly the error ADR-014 exists to prevent.

---

## ADR-031

**The feasibility frontier — and the ban on mission ordering lifts, for ten missions.**
`2026-07-26 · accepted`

### Part 1 — why this is allowed now

**Context.** Three units built the pieces and nothing joined them. `data/travel_budget.json` was
a leaf, consumed by nothing. So the repo could say how far every mission is, what each tier of
accuracy pays, and how a best-of-N ranking changes the objective — and still not answer the
question a team asks: *given a robot that drives at v and picks-and-places in t, which missions
fit in 120 seconds?*

That was refused for eight phases, and the refusal was correct and specific.
`strategy_frame.json` says it verbatim: *"Mission ordering needs σ from field tests P2/P3 and the
object pickup locations, 15 of which are `nominal_pending`."* CLAUDE.md §5.7 anti-pattern #3
forbids claiming one strategy beats another without simulator evidence.

**Both conditions are now met.** ADR-029 and ADR-030 supply exact tours for ten of the twelve
placement missions. And **feasibility does not need σ** — σ decides whether a placement *scores*,
not whether it *fits*. So the ban lifts for the covered set and stays for the two cables, which
are still `nominal_pending`. Every subset here is missing them, so the frontier is a **lower
bound**: 185 of the 215 placement points, never 215.

**The subset tours are free.** `tour_points` already memoises `best_from(remaining, position)`,
and `best_from(S, start)` *is* the optimal tour for subset `S`. Querying all 1024 subsets against
one shared memo costs 0.10 s at capacity 1 and 0.58 s at capacity 2 — the work the full tour
already did.

### Part 2 — speed saturates, pick-and-place does not

Worst case over all **384 joint start states** — guaranteed whatever the randomization draws.
Capacity 2, of 185 placement points:

| v \ t | 0 s | 2 s | 4 s | 6 s | 8 s |
|---|---:|---:|---:|---:|---:|
| **75 mm/s** | 155 | 140 | 120 | 120 | 120 |
| **100** | 185 | 155 | 155 | 135 | 120 |
| **125** | 185 | 185 | 165 | 155 | 140 |
| **150** | 185 | 185 | 185 | 155 | 155 |
| **200** | 185 | 185 | 185 | 185 | 155 |
| **300** | 185 | 185 | 185 | 185 | 185 |

The **exact** speed that reaches the ceiling — by formula, not search, since a subset fits iff
`travel / v + count × t ≤ 120`:

| t (s per object) | 0 | 2 | 4 | 6 | 8 | 10 |
|---|---:|---:|---:|---:|---:|---:|
| **needs (mm/s)** | **92.9** | 111.5 | 139.4 | 185.9 | 278.8 | 557.7 |

**Above that line more speed buys literally nothing**, and in the sensitive region each extra
second of handling costs about **15 points — one instrument**. Both platforms clear 93 mm/s
without effort. **You do not need a fast robot; you need a fast gripper.** That is the same
conclusion ADR-030 reached from the 12 s cliff, arrived at independently.

**The drop order is not the obvious one.** At 120 mm/s the optimal subset sheds the three
instruments first — 15 points each and two metres away — and the notes survive longest, as
ADR-030's 5.2× points-per-metre gap predicted. But at 7 s per object **`mic` is dropped ahead of
a cheaper instrument**, despite being worth 20 against 15, because it costs more travel than the
instrument it displaces. A points-per-metre table gets that call wrong. It is why the frontier is
computed rather than reasoned about.

### Part 3 — the instruments are σ-proof, and they overtake the notes

Pricing accuracy in changes **which** missions to attempt in 44 of 270 cells at capacity 2, and
74 of 270 at capacity 1. The direction is the opposite of the raw ranking — at capacity 2,
`instrument_keyboard` is *added* in **26** of those cells, `instrument_guitar` in **17** and
`instrument_congas` in **13**, while notes are dropped.

The cause is geometry, not scoring. The instruments deliver to **`backstage`, 124 924 mm²** —
**20× a note target's 6 352 mm²** — so their `p_full` is still **1.000 at σ = 30 mm**:

| σ (mm) | note (20 full) | instrument (15 full) |
|---:|---:|---:|
| 10 | 19.57 | 15.00 |
| 15 | 17.49 | 15.00 |
| 20 | 15.13 | 15.00 |
| **30** | **11.81** | **15.00** |
| 45 | 7.62 | 14.91 |

**They cross at σ = 20.4 mm.** Below it a note is worth more; above it an instrument is, despite
being worth five fewer points at full credit — and despite having **no partial tier at all**
(ADR-026), which it does not need.

**This qualifies CLAUDE.md §5.6.** *"Notes are 120/255 = 47 % of total"* is a statement about the
**maximum** score. At realistic placement error it overstates their share of the **expected**
score, and the three instruments are the robust play. Which side of 20.4 mm the robot lands on is
work order **B5**.

**What this does not claim.** Not that the team should build for any point on the frontier. `v`
is unmeasured until **P6**, `t` until a mechanism exists (**A3**), and σ until **B5**. The
frontier reports what is *reachable* at a given operating point; choosing one is a decision the
measurements inform and this does not pre-empt.

---

## ADR-032

**The first end-to-end score — and which unknown to measure first.**
`2026-07-27 · accepted`

### Part 1 — six unknowns, five artefacts, no ranking

**Context.** Every artefact declares its own free parameter and stops:

| parameter | declared in | closed by |
|---|---|---|
| σ, placement error | `expected_score`, `placement_sensitivity`, `round_strategy` | **B5** |
| `v`, driving speed | `travel_budget`, `feasibility_frontier` | **P6** |
| `t`, pick-and-place | `feasibility_frontier` | **A3** |
| `N`, rounds | `round_strategy` | **NEEDS-VERIFY(NO-TH)** |
| `P(collision)` | `expected_score`, `strategy_frame` | **nothing measures it** |
| carry capacity | `travel_budget` | **MEAS-2/3** |

Nowhere did the repo say which one matters. The operator is about to spend an afternoon
measuring, and that is the one question a work order should already answer.

**Decision.** Compose the chain — `sim/model.py`:

```
choose the highest-EXPECTED-value subset that fits   (sim.frontier, ADR-031)
  → convolve its tier probabilities into a distribution  (sim.rounds, ADR-028)
    → subtract the exposed bonus cluster once            (ADR-024)
      → take E[max] over N rounds                        (ADR-027)
```

**There is no new arithmetic.** Every step already existed; eleven artefacts and nothing had
composed them. The anchors verify exactly: σ = 0 with unlimited speed, instant handling, one
round and no collision returns **225.000**, and a run that fits nothing returns **40.000**.

**The ceiling is 225, not 255.** The two cables are still `nominal_pending`, so 40 (bonus floor)
+ 185 (costable placement points) is everything on the table. Quoting /255 would overstate by the
30 points nobody can cost until **B0**.

### Part 2 — the ranking is not stable, and that is the finding

Swing in expected score across each parameter's plausible range, one at a time:

| rank | comfortable (v 200, t 4) | | marginal (v 150, t 6) | | tight (v 100, t 8) | |
|---|---|---:|---|---:|---|---:|
| 1 | **σ** | **57.3** | **σ** | **54.0** | **`v`** | **62.3** |
| 2 | `v` | 30.0 | `v` | 45.0 | `t` | 47.3 |
| 3 | `t` | 15.0 | `t` | 30.0 | σ | 45.2 |
| 4 | `N` | 11.1 | **capacity** | **30.0** | `N` | 10.4 |
| 5 | `P(coll)` | 7.5 | `N` | 11.1 | `P(coll)` | 7.5 |
| 6 | capacity | 0.0 | `P(coll)` | 7.5 | capacity | 1.1 |

Nominal scores: **204.9**, **189.9**, **142.6** of 225. Across all 64 corners the envelope is
**107.5 – 225.0** — the answer is still anywhere, which is the honest measure of what remains
unknown.

**Three contexts disagree — but three points are not a shape.** Read alone, the table above says
*"σ for a fast robot, speed for a slow one"*, and that is what this ADR first concluded. A grid
sweep of seven speeds × five handling times says otherwise:

|  | 2 s | 4 s | 6 s | **8 s** | 10 s |
|---|:---:|:---:|:---:|:---:|:---:|
| 100 – 300 mm/s | σ | σ | σ | **`v`** | σ (one cell `v`) |

**σ leads in 27 of 35 cells.** Driving speed takes the top rank at **`t` = 8 s per object and at
every speed swept, from 100 to 300 mm/s** — and essentially nowhere else. That is the clinching
detail: if *slow driving* caused the flip, speed would lead in the slow rows and not the fast
ones. It leads across the whole column instead, so **handling time causes it, not speed**.

The mechanism is ADR-030's cliff seen from the other side: at 8 s per object, ten objects consume
80 of the 120 seconds and only 40 remain for driving, so how far the robot can travel decides how
many missions fit at all. Below that speed is not binding; above it, so little fits that speed
stops changing the count.

**So the measurement order is simply σ (B5) first, with one named exception** — not *"find out
which regime you are in"*. That is a simpler instruction than the one this ADR started with, and
it took a grid rather than two chosen points to earn it.

### Part 3 — two of this project's own emphases, qualified

**Carry capacity and the randomization are boundary effects.** Neither is well described by *"it
matters"* or *"it doesn't"*:

| | comfortable | marginal | tight |
|---|---:|---:|---:|
| capacity swing | **0.0** | **30.0** | 1.1 |
| randomization band over 384 states | **0.0** | **15.0** | **0.0** |

Both cost nothing when the budget is comfortable, nothing when it is tight, and a great deal at
the margin where one more mission is borderline. **Subset selection absorbs them everywhere
else** — an unlucky draw or a smaller gripper costs a mission only when a mission was borderline
anyway.

**ADR-029 stands unchanged.** Its travel findings are travel findings: 2213 mm off the
worst-case note tour at the first extra slot, and the randomization deleted entirely at capacity
6. What this adds is *where that travel converts into score* — only at the boundary. That is a
narrower claim than either the earlier emphasis or the flat "capacity barely matters" this
analysis first suggested, and it took a third operating context to see.

**The method's own limit, stated.** Each swing varies one parameter with the others at the
context nominal, so interactions are invisible *within* a context. The interaction between σ,
speed and handling time is precisely the finding, so it is exposed by publishing three contexts
rather than by pretending one suffices.

**What this does not claim.** Not a score. Every figure is an evaluation at an assumed operating
point, and all six parameters are unmeasured. This ranks what to *measure*; what to build stays
gated on MEAS-2/3, and what to attempt on B5.

---

## ADR-033

**Two identifier collisions, and the seven questions nobody had written down.**
`2026-07-27 · accepted`

### Part 1 — `A1`–`A5` meant two different things

**Context.** `docs/HARDWARE_SESSION.md` numbered its bench-work items **A1–A5**;
`docs/AMBIGUITIES.md` numbers its rule ambiguities **A1–A10**. The same five strings identified
both. Worse than a clash of namespaces: **A4 and A5 are *resolved* ambiguities** — return-to-start
(S4 §10.7/§10.13) and held objects scoring the partial tier (S6 2026-06-30) — so an unqualified
"A5" read as **settled fact** in one document and an **unstarted task** in another.

**Decision.** The measurement block becomes **MEAS-1 … MEAS-5**. The ambiguity register keeps
`A1`–`A10`, which is the older and more widely cited family.

**The rename could not be mechanical.** 171 occurrences of `A1`–`A5` exist across 35 files with
the two senses interleaved — `ROADMAP.md` line 54 reads *"A2/A3/A4/A5/A6 resolved"* (ambiguity
sense, **kept**) thirteen lines from *"Block A — items A1 to A3"* (measurement sense, renamed).
Every occurrence was read. A `sed` would have corrupted more than a hundred correct citations.

**Consequence.** Five builders emit the identifier into their artefacts, so
`manipulator_requirements`, `travel_budget`, `feasibility_frontier` and `parameter_sensitivity`
changed content — a string change to existing artefacts, not a new one.
`tests/test_hardware_session.py` gains a guard that no `### A<n> ·` heading returns.

### Part 2 — S6's row stated its precedence but never its scope

**Context.** The brief reported S6 as missing from the source table. It is not: `CLAUDE.md` §5.1
has it as **row 1**. But the premise pointed at something real. Every other row says what its
source is authoritative *for* — S1 *"missions, scoring, definitions, randomization"*, S4
*"robot limits, run procedure, table setup, tie-break"* — while S6's cell said only
*"overrides everything below it"*. It declared that S6 **wins** without saying what it wins
**about**.

**Decision.** S6's cell now states its scope: *any question a lower source leaves ambiguous —
scoring predicates, rule wording, and the meaning of a term S1/S4 use without defining.* And,
explicitly, that it **does not originate** geometry or robot limits; it reinterprets them. That
distinction is what makes `docs/QUESTIONS.md` §1 answerable and §3 not: A7 is a reading of a
sentence and belongs to S6; the national robot limits are a *fact* and belong to the organizer.

**A second defect, found beside it.** The rule line under the table read *"must trace to S1–S4 or
S6"* and **silently omitted S5** — the derived spec the same table lists as a source, and which
every module actually reads. Now stated, with the qualification that S5 is not an independent
authority: it may only restate what S1–S4 and S6 already say, and carries a provenance sha for
every input it read.

### Part 3 — the questions, and the two protocols

**Context.** Eight consecutive analysis units left the repo with eleven derived artefacts, 503
tests and **zero measured values**. Every remaining path runs through numbers only the operator
can produce, or through **seven questions that had never been written down** — five open
ambiguities routed to the official Q&A since 2026-07-25, and two `NEEDS-VERIFY(NO-TH)` items
never asked at all.

**Decision.** Three documents, no new derived artefact:

| document | what it settles |
|---|---|
| `docs/QUESTIONS.md` | the seven, **ordered by magnitude**, each with a verbatim quote and page, *all* plausible readings (A7 and A9 have three, not two), the artefact or ADR that changes, the magnitude as a number, and a fallback with its consequence-if-wrong |
| `docs/MEASUREMENT_PROTOCOL.md` | instrument resolutions justified against what consumes the number, repeat counts derived from `1/√(2(n−1))`, the destination field for every value, and proxies decided in advance |
| `docs/B1_PROCEDURE.md` | the minimum viable chassis, which parts are throwaway, pass/fail judged without interpretation, and the decision rule for one implementation or two |

**Two magnitudes worth recording here**, because they set the order everything else follows:
**A7 is worth 24 points** of expected score at σ = 20 mm (216 against 192 of 255) and a **2.64×**
swing in required note accuracy; the **tournament format** is worth **+12.5** at N = 3 and,
unlike everything else on the list, *inverts* strategy rather than scaling it — under best-of-N
variance becomes an asset.

**The schema gained two fields it was missing.** `grip_face` and `cog_height_mm` had **no
destination at all**, so MEAS-3 and MEAS-5 would have produced numbers with nowhere to go.
Added to `docs/object_map.toml` and `build_object_spec.py` read-if-present, with `tilt_angle_deg`
and `cog_source` beside them so a derived CoG is never mistaken for a measured one. All five ship
`null` across all 16 objects, guarded — the ADR-026 precedent exactly.

**What this deliberately does not do.** It sends nothing: the questions are drafted for review,
and transmission is the operator's. And it produces no twelfth derived artefact — the four that
changed did so only because a renamed string flows through them.

---

## ADR-034

**The tilt proxy measured friction, not centre of gravity.**
`2026-07-27 · accepted`

### The error

ADR-033 shipped a measurement protocol whose MEAS-5 derived centre-of-gravity height from a
tilt-table reading: *"An object tips when its centre of gravity passes over the pivot edge, so
`tan θ = w/h` … therefore `h = w/tan θ`."*

The formula is correct. **Its precondition was never checked.** An object on an incline **tips**
at `tan θ = w/h` and **slides** at `tan θ = μ_s`, and whichever angle is lower happens first. So
`h = w/tan θ` is valid only when `w/h < μ_s`. Evaluated against μ_s ≈ 0.35 for ABS on a smooth
surface, using the repo's own footprints:

| object | w (mm) | h est | w/h | θ_tip | θ_slide | |
|---|---:|---:|---:|---:|---:|---|
| note | 16 | 27 | 0.59 | 30.7° | 19.3° | slides |
| cable | 8 | 10 | 0.80 | 38.7° | 19.3° | slides |
| microphone | 16 | 45 | 0.36 | 19.6° | 19.3° | slides |
| amplifier | 30 | 35 | 0.86 | 40.6° | 19.3° | slides |
| speaker | 20 | 30 | 0.67 | 33.7° | 19.3° | slides |
| clef | 16 | 40 | 0.40 | 21.8° | 19.3° | slides |

**Every shape slides. All six.** The protocol would have produced 176 trials of `arctan μ_s`.

### Why nothing in the repo would have caught it

This is the failure mode the project has now hit four times, and this is the worst instance.

A sliding object **still stops at a definite angle**. The operator still reads a number, the
formula still returns a plausible CoG height, and the field lands in `object_spec.json` tagged
`MEASURED(...)`. Nothing is null, nothing is out of range, no test fires.

Worse: because friction does not depend on shape, **every object would have reported ≈19.3°**.
Thirteen objects agreeing to a fraction of a degree reads as *excellent repeatability*. The
strongest available signal that the measurement was sound would in fact have been proof that it
was worthless.

The value recovered would have been `w/μ_s` — a **friction measurement wearing a geometry
label**, and one that would then have informed ADR-022's manipulator decision.

### Decision

Three changes, all mandatory, none of them optional refinements:

1. **An anti-slip cleat, ≤ 3 mm, flush against the downhill face**, with its height `c` measured.
   It lifts the effective pivot, so the recovery formula becomes **`h = w/tan θ + c`**. Verified:
   w = 16, true h = 27, c = 2 → tips at 32.62°; the correction recovers **27.00 mm**, omitting it
   gives **25.00 mm, 7.4 % low**.
2. **A validation rule that fails the block.** Watch for translation before rotation; and at the
   data level, `arctan(0.35) ≈ 19.3°` regardless of shape, so **angles that agree across objects
   whose base widths differ by more than 1.5× are the friction angle, not tipping**. Do not
   record them. *Disagreement between shapes is the success signal.*
3. **±0.5° angular resolution.** Error propagates as `|dh/h| = 2·dθ/sin 2θ` — an amplification
   that never drops below **2×**, and is **3.11×** at θ = 20°. At ±1° that is 5.4 %; at ±2°,
   10.9 %. Below ±0.5°, do not derive CoG at all.

**And an alternative that cannot fail this way.** The reaction-board method never requires the
object to tip, so friction is irrelevant: `h = L(R₀ − R₁)/(W tan θ)` from two scale readings,
level and tilted. At L = 200 mm, W = 25 g, θ = 30° a 0.1 g scale resolves h to ≈ 5 % — as good as
the ±0.5° tilt method, with no mode that returns a confident wrong answer.

### And a cut, found while fixing it

`data/scoring_model.json`, `m2_prepare_show_instruments`:
`full_condition: "completely_in(instrument, backstage)"`, note *"No uprightness requirement and
no partial credit."* **No predicate consumes the instruments' tilt angle.** Cables, microphone
and notes carry `AND upright` / `OR not upright`; the four bonus objects reach it through
`NOT moved`. Tilt therefore covers **13 objects, not 16** — 33 trials removed with no loss.

With a tiered design as well — full characterisation at n = 11 on one object per *shape class*,
n = 3 on duplicates as an identity check — tilt drops from **176 trials to 87**, and the
statistics improve: measuring six notes eleven times each was re-characterising the same build.

### Consequence

The session is budgeted honestly for the first time: **≈ 4 hours**, block by block, ordered so
that **ADR-022's manipulator decision closes at 1 h 25 m** and a session that runs short stops
cleanly. MEAS-5a goes last despite being longest, because A2 records that S6 demoted
`upright_tolerance_deg` from a threshold to a parameter — the softest consumer on the page.

**The pattern, fifth instance.** ADR-024, ADR-026, ADR-028, ADR-029 and now this: every one an
error in what a number *meant*, none caught by testing the code that produced it. The difference
here is that the previous four were caught by a downstream inconsistency. **This one had no
downstream inconsistency to find** — it would have been caught only on the day, or never. The
guard that works is the one that checks a **precondition of the method**, not a property of the
output.
