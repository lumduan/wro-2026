# Assumptions

Every `ASSUME:` emitted anywhere in this repo appears here with a
**consequence-if-wrong** line. An assumption without a stated consequence is not an
assumption, it is a guess.

Emitted assumptions also appear verbatim in the `notes` array of the relevant
`docs/extracted/<pdf-stem>/manifest.json`, so the machine-readable record and this
document cannot drift apart silently.

`last_reviewed: 2026-07-27`

| ID | Assumption | Source | Consequence if wrong |
|---|---|---|---|
| [AS-1](#as-1) | RGB values from S2 are profile-less CMYK conversions | `probe`, `vector` | mat colours may be misidentified; two distinct printed colours can collide |
| [AS-2](#as-2) | The single `/Separation` spot colourspace is not artwork | `probe` | one printed feature is missing from the fill inventory |
| [AS-3](#as-3) | `area_mm2` uses fixed 16-segment Bézier flattening | `vector` (ADR-004) | curved-shape areas carry a small error; rectangles are exact |
| [AS-4](#as-4) | `area_mm2` is computed **before** clipping | `vector` (ADR-009) | a clipped path's area overstates what is visible on the mat |
| [AS-5](#as-5) | ~~The printed mat equals the TrimBox exactly~~ | **RESOLVED** S4 §7.2 | — (kept for the record; see below) |
| [AS-6](#as-6) | "upright" means tilt ≤ 15° from the start pose | `AMBIGUITY(A2)` | simulator scores runs the referee would not, or hides viable strategies |
| [AS-7](#as-7) | The MAT frame equals the S2 page-trim frame | `MatFrame` | every coordinate downstream is offset by the same constant error |
| [AS-8](#as-8) | Placement error is Gaussian and isotropic in x and y | `sim.sensitivity` | the required-accuracy figures shift; the ORDERING of missions by difficulty does not |
| [AS-9](#as-9) | Heading error is 0.5° per mm of placement σ | `sim.sensitivity` | cable and note requirements tighten or loosen together; the cable is most exposed |

---

## AS-1

### RGB values from S2 are profile-less CMYK conversions

**What was measured.** S2 declares a PDF/X output intent (`GTS_PDFX`), output condition
`CGATS TR 001`, embedded ICC profiles with 1 and 4 components, and 3381 `/DeviceCMYK`
references. The native colour space of the mat artwork is **CMYK**, not RGB.

**The assumption.** PyMuPDF converts CMYK to RGB without applying the embedded ICC
profile. Every `fill_rgb`, `fill_hex`, `stroke_rgb` and `stroke_hex` this toolchain emits
is therefore an approximation of the printed colour, not a measurement of it.

**Consequence if wrong.** Two distinct printed mat colours that happen to converge under a
naive conversion would appear as one entry in `fills_by_colour.json`, and a later session
mapping fills to canonical area IDs would merge two areas into one. This is the single most
likely way the colour inventory misleads.

**Mitigation available now.**
`pdf_extract.py render --colorspace cmyk` writes a 4-channel TIFF so true CMYK can be
sampled per area. Sample a **median over an interior window**, eroded away from the area
boundary — a single pixel lands on an anti-aliased edge.

---

## AS-2

### The single `/Separation` spot colourspace is not artwork

**What was measured.** Exactly one `/Separation` colourspace in S2 — specifically
`Separation(DeviceCMYK, All)` — used by **112 embedded images**. Those images are long thin
strips (10×86, 889×147, 150×1437, 1500×153, 153×903, 774×234 px …), and PyMuPDF refuses to
write that colourspace as PNG, which is how they were found (see `ADR-011`).

**The assumption.** The `All` separant conventionally means "paint on every plate", which is
what printer's marks, die-lines and registration targets use. A lone spot colour in a
print-ready file is usually a technical layer rather than a printed mat feature.

**Strength of evidence.** Suggestive, not conclusive. `All` is a strong convention and the
strip geometry fits registration/edge marks, but 112 objects is a substantial presence and
nothing here rules out artwork.

**Consequence if wrong.** If that separation *is* artwork, one printed feature is absent
from the RGB fill inventory, because spot colours do not round-trip through RGB. An area
could be missing from `field_spec.json` entirely — worse than a wrong colour, because
nothing flags its absence.

**How to check.** Compare a CMYK render against the RGB render at the same `px_per_mm`; a
region that differs between them is spot-coloured.

---

## AS-3

### `area_mm2` uses fixed 16-segment Bézier flattening

See ADR-004. Fixed subdivision is chosen over an adaptive tolerance because adaptive
flattening would vary by library version and break the byte-identity guarantee.

**Consequence if wrong.** Tight curves carry a small area error. Straight-edged zones —
which is what mat areas actually are — are exact. `bbox_area_mm2` is emitted alongside
`area_mm2`, so a large divergence between the two is visible rather than hidden.

---

## AS-4

### `area_mm2` is computed before clipping

See ADR-009. `get_drawings()` reports path geometry as constructed, not as painted. S2
contains thousands of clip operations.

**Consequence if wrong.** `total_area_mm2` in `fills_by_colour.json` **overstates** visible
coverage for any clipped path. Do not treat it as printed area. It is a ranking signal for
"which fills are big enough to be mat zones", not a measurement.

Clip entries are retained in `drawings.json` (`type: "clip"`, with `level` and
`scissor_mm`) precisely so a later session can reconstruct the clip stack and compute true
visible area.

---

## AS-5

### The printed mat equals the TrimBox exactly

**What was measured.** In S2, `TrimBox == CropBox == BleedBox == MediaBox ==
[0 0 6695.43 3240.0]` pt. The file carries **zero bleed** and no crop marks.

**The assumption.** The physical competition mat is exactly the TrimBox — 2361.999 ×
1143.000 mm — with no border beyond the artwork.

**Consequence if wrong.** If the supplied mat has an unprinted margin, or is trimmed
inside the artwork, then **every** MAT-frame coordinate is offset by a constant. The error
would be invisible in the data (all areas stay self-consistent) and would only surface as a
systematic miss on the physical table. This is the highest-consequence assumption in this
document.

### RESOLVED 2026-07-25 — S4 §7.2

> *"dimensions of a WRO mat are 2362 mm x 1143 mm"* — game tables are the same size or
> max ±5 mm in each dimension; the official border height is 50 mm.

The printed mat **is** the TrimBox: 2362 × 1143 mm, matching the measured 2361.999 × 1143.000
to within 1.1 µm. The "borders" are the **50 mm table walls**, not a print margin. The entry
is kept rather than deleted so the reasoning stays auditable.

**What replaces it** is not zero uncertainty but a *different* one: S4 §7.2 allows the table
to exceed the mat by up to 5 mm, and S1 p3 says to lay the mat against the short wall nearest
the start area (the right) and centre it in the other axis. So the registration datum is
X = right wall, Y = centred — up to 5 mm of slack accumulates toward −X, and the stage-side
missions (cables, mic, backstage, all at x < 535) sit at the far end of that error chain.
That is now `table.tolerance_mm` data in `field_spec.json`, not an assumption.

---

## AS-6

### "upright" means tilt ≤ 15° from the start pose

See `AMBIGUITY(A2)` in `docs/AMBIGUITIES.md`. Exposed as `upright_tolerance_deg`.

**Consequence if wrong.** A too-generous tolerance makes the simulator award points a
referee would not; a too-strict one hides viable strategies. Any result that depends on it
must be reported as a sweep over the parameter, never as a single number.

---

## AS-7

### The MAT frame equals the S2 page-trim frame

**The assumption.** `CLAUDE.md` §5.2 defines the MAT frame as origin bottom-left of the
mat. This toolchain equates that with the bottom-left of S2's TrimBox.

**Why it is well-founded.** S2's TrimBox has zero offset from its MediaBox, `/Rotate 0` and
an identity page transformation matrix, so there is no ambiguity about which corner is
which — and the measured size, 2361.999 × 1143.000 mm, matches the independently expected
2362 × 1143 mm to within 1.1 µm.

**Consequence if wrong.** Every coordinate in the project shares one constant offset or a
mirrored axis. `vector/drawings.json` carries a `self_check` block per page asserting that
the union of all path bounding boxes falls inside the declared page box; a flipped or
offset frame pushes the union outside it and the run says so.

**Caveat for S1 and S3.** Those are A4 documents, not mats. Their frames are page-trim
frames (`frame.semantic: "page_trim_frame"`) and carry no MAT-frame meaning. Do not read a
coordinate out of S1 or S3 as if it were a mat coordinate.

---

## AS-8

### Placement error is Gaussian and isotropic in x and y

**The assumption.** `data/placement_sensitivity.json` perturbs each placement by
`N(0, σ)` independently in x and y. Real placement error is neither perfectly Gaussian
nor perfectly isotropic — a differential-drive robot approaching along a heading
typically has larger along-track than cross-track error, and both distributions have
tails a normal understates.

**Why it is used anyway.** The artefact's purpose is the *requirement*, not a
prediction. Every mission is evaluated under the same error model, so the comparison
between missions — which is what Phase 7 and Phase 8 consume — is unaffected by the
model's shape.

**Consequence if wrong.** The absolute σ figures move. The **ordering** does not: the
notes need roughly 2–3× tighter placement than the cables under any symmetric error
model, because that ordering follows from the slack (7.85 mm against 31.85 mm), which
is measured rather than modelled.

**Replaced by.** Field tests **P2** (start-area repeatability, 20 placements) and **P3**
(odometry drift per metre and per 90°). Those give the real distribution, at which point
the sweep should be re-run against it rather than against a normal.

---

## AS-9

### Heading error is 0.5° per mm of placement σ

**The assumption.** `sim.sensitivity.DEG_PER_MM = 0.5` couples rotational error to
translational error. There is no measurement behind the coefficient; it is a plausible
shape chosen so that rotation is present in the model rather than silently zero.

**Why the coupling exists at all.** Setting it to zero would be the more dangerous
choice: it would model a robot that translates imperfectly but rotates perfectly, and
would flatter exactly the mission most exposed to rotation — the cable, whose 128 mm
length makes it far more sensitive to heading than any 32 mm note.

**Consequence if wrong.** The cable's required accuracy is the figure that moves most.
The notes are nearly square in the contact reading, so their result is dominated by
translation and barely depends on this coefficient. It also drives the small non-zero
`p_full` on the impossible across-the-area cable row at extreme σ, which is a modelling
artefact of the coupling and is documented as such in `tests/test_sensitivity.py`.

**Replaced by.** Field test **P3**, which reports drift per 90° of turn directly.
