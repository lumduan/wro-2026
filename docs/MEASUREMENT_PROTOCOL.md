# Measurement protocol — Block MEAS

`last_reviewed: 2026-07-27`

**You get one shot at physical access. This exists so you do not measure twice.**

`docs/HARDWARE_SESSION.md` says *what to measure and in what order*. This says *how*, to what
resolution, how many times, and **exactly where each number goes** — so nothing is written on
paper and transcribed later.

Every destination below is **live and inert**: the fields exist in `docs/object_map.toml`, the
builder reads them if present, and a test asserts every one is still `null` until you type a
number. Type numbers, re-run `uv run python tools/build_object_spec.py`, done.

---

## Session budget — about four hours, not an afternoon

Run the blocks **in this order**. It is ordered by *what closes soonest*, so a session that runs
short stops cleanly instead of dying mid-block.

| order | block | count | estimate | done by |
|---:|---|---:|---:|---:|
| 1 | **MEAS-1** parts inventory | 3 sets | 15 min | 0:15 |
| 2 | **MEAS-2** mass | 48 weighings | 20 min | 0:35 |
| 3 | **MEAS-3** grip + pick-and-place timing | 12 objects | 50 min | **1:25** |
| 4 | **MEAS-4** calipers | 120 readings | 50 min | 2:15 |
| 5 | **MEAS-5a** tilt angle | 55–71 trials | 45–60 min | 3:00–3:15 |
| — | **MEAS-5b** CoG height | derived from 5a | — | — |

Add ~20 min setup. **Call it four hours.**

**The one milestone that matters is 1:25.** At that point MEAS-1/2/3 are done and **ADR-022's
manipulator decision closes** — the design decision gated since Phase 7. Everything after is
verification (MEAS-4 independently checks Phase 4's entire stud-counting chain) and refinement
(MEAS-5a replaces an assumption that S6 already demoted to a parameter).

**If you have 90 minutes, do 1–3 and stop.** That is the whole gate.

**MEAS-5a is last on purpose**, despite being the longest: A2 in the ambiguity register records
that S6 2026-06-30 made "upright" a *contact* test, which demoted `upright_tolerance_deg` from a
threshold to a parameter. It is the softest consumer on this page.

---

## Before you start

| Instrument | Required resolution | Why that and not less |
|---|---|---|
| **Scale** | **0.1 g**, ±0.3 g accuracy | Mass feeds ADR-022's motor-torque arithmetic, not a containment predicate. The lightest object is a single note; at ~20 g, 0.1 g is 0.5 %. A 1 g kitchen scale is **not** enough — it is 5 % on the object that matters most. |
| **Calipers** | digital **0.01 mm**, or vernier 0.05 mm | The builder flags agreement with the stud-derived value at **±0.5 mm**. Anything coarser than 0.1 mm cannot distinguish "agrees" from "instrument noise". |
| **Angle** | **±0.5°** — digital angle gauge, or a phone inclinometer against a rigid flat reference | Error into CoG is amplified by `2/sin 2θ`, **never below 2×** and 3.11× at 20°. At ±1° that is 5.4 %, at ±2° 10.9 %. A protractor read by eye does not qualify. |
| **Anti-slip cleat** | a **LEGO tile**, 3.2 mm, flat top | Mandatory for MEAS-5a — every object slides without it. A tile is dimensionally standard; a shim is not. Its height enters the answer 1 : 1, so measure it in situ. |
| **Part-type set** | one of each of the **14 distinct parts** | The MEAS-2 cross-check predicts every object's mass from its BOM. Without the part masses there is nothing to check a reading against. |
| **Flat reference surface** | — | Everything in MEAS-4 and MEAS-5 assumes the object sits on a true plane. A warped table silently biases every tilt reading in the same direction. |

**Tag every value** `MEASURED(<instrument>, <date>)` per CLAUDE.md §5.5, and record the raw
readings, not just the mean — the readings are the evidence.

---

## How many repeats, and why they differ

A single reading gives no spread at all, and repeats are not free. The relative standard error of
a **sample standard deviation** is approximately `1 / √(2(n−1))`:

| n | 2 | 3 | 5 | 6 | **11** | 13 | 21 |
|---|---:|---:|---:|---:|---:|---:|---:|
| error on the σ you compute | 71 % | 50 % | 35 % | 32 % | **22 %** | 20 % | 16 % |

So the repeat count depends on **whether the spread is the quantity you want**:

| field | n | what the repeats are for |
|---|---:|---|
| **mass** | **3** | The scale's own resolution dominates; three readings detect a gross error (wrong object, finger on the pan), they do **not** produce a useful σ and are not meant to. |
| **footprint**, per axis | **5** | Catches a mis-seated caliper or a jaw on a stud rather than a face. **This is not enough for a σ** — 35 % error — and no downstream artefact treats it as one. |
| **grip span** | **3** | Same as footprint; the answer is mostly pass/fail, the number is secondary. |
| **tilt angle** | **3, then 11** | **Here the spread *is* the quantity.** It replaces `AS-6`, and an assumption is only worth replacing with something better than a guess. 11 readings give 22 %; below 6 you are not improving on the assumption you are retiring. But see the screen below — 11 on *every* object is 143 trials to feed a single swept scalar. |

### Screen, then characterise — do not assign tiers in advance

An earlier draft grouped the thirteen objects into six "shape classes" and measured one of each
at n = 11. **Two things were wrong with that**, and both are settled by the repo's own data.

**The six notes are not one shape class.** Their BOMs differ — 5, 6, 6, 8, 7 and 5 bricks — so
although they share a footprint (32 × 32), a projection (32 × 64) and an overhang (9.6 mm), they
differ in **CoG height** and therefore in tipping angle, plausibly by several degrees. The pairs
*are* genuinely identical, and that is verified, not assumed:

| group | BOMs identical? | |
|---|---|---|
| `cable_upper` / `cable_lower` | **yes** | one class ✓ |
| `speaker_a` / `speaker_b` | **yes** | one class ✓ |
| the six notes | **no** | six builds ✗ |

**And the consumer is a single scalar.** `sim/scoring.py` carries
`upright_tolerance_deg: float = 15.0` — one value for every object, which S6 2026-06-30 demoted
to a *swept parameter* when it made the operative test contact rather than angle. Characterising
thirteen objects to ±0.5° to feed one swept scalar is over-specified by construction. What that
scalar needs is its **range**: the least stable object and the most stable one.

| step | objects | n | trials |
|---|---|---:|---:|
| **screen** | all 13 | **3** | 39 |
| **promote** | the least-stable and the most-stable, **plus anything within 3° of either** | **11** | +8 each |
| | | | **≈ 55–71** |

**The 3° threshold** is six times the ±0.5° measurement resolution — wide enough that two objects
inside it are not distinguishable by this rig, narrow enough to exclude anything clearly
separated. Expect 2–4 promotions.

**Nothing is below a line in advance.** The screen decides. If a cable turns out least stable it
gets n = 11 on its merits — which matters, because the two cables carry a 10-point upright delta
each. Assigning tiers by shape guessed at the answer; screening measures it, and costs less.

**Never average across objects.** Thirteen objects, thirteen rows. The pairs may be *compared*
once both are screened, but they are recorded separately.

---

## MEAS-1 · Parts inventory

Not per object — per set. Fill `docs/FIELD_TEST_PLAN.md` Step 0's table.

Count **motors, colour sensors, distance/force sensors, hubs** in EV3 45544, SPIKE Prime 45678
and SPIKE Expansion 45681. **Watch the coincidence** flagged in the work order: S4 §5.2.8 caps
Elementary at 4 motors, and if the SPIKE count is also 4 there is no spare.

→ **Destination:** `docs/FIELD_TEST_PLAN.md` Step 0 table, tagged `MEASURED(inventory, <date>)`.

---

## MEAS-2 · Mass — all 16 objects

Weigh **all sixteen**, not just the twelve placement objects. The four bonus objects (`clef`,
`amp`, `speaker_a`, `speaker_b`) are never lifted, but they are the objects a collision topples,
and mass is the cheapest thing to record while they are already on the bench.

**n = 3.** Record all three readings.

```toml
[[models]]
id = "note_blue"
mass_g = 23.4
mass_source = "MEASURED(scale 0.1 g, 2026-08-02) n=3 readings [23.4, 23.4, 23.5]"
```

### Precondition — weigh the 14 part types, then every object mass is *predicted*

A single weighing has nothing to check it against, and the most likely error — **a dropped brick
during handling** — produces a perfectly plausible number. So before weighing the objects, weigh
**one of each of the 14 distinct part types** the sixteen objects are built from:

`brick_1x2_with_side_pin` · `brick_1x6` · `brick_2x2` · `brick_2x2_with_pins` · `brick_2x4` ·
`flexible_hose` · `plate_2x2` · `plate_4x8` · `shape_10` · `shape_11` · `technic_brick_1x16` ·
`technic_brick_1x2` · `tile_1x2` · `tile_2x4`

That is ~5 minutes. Every object then has a **predicted** mass from its own `bom_steps` in
`data/object_spec.json`:

```
predicted = Σ (count × part mass)      # e.g. note_blue = 6 × brick_2x4 + 1 × plate_4x8
```

**Check every measured mass against its prediction.** Tolerance is the accumulated part-mass
resolution — roughly **±1 g** for a ten-part object at 0.1 g. A discrepancy that equals **one
part's mass** is a dropped brick, and it is the only cheap way to catch one.

This uses no external data — the BOMs are the repo's own, from S3 — and it covers all sixteen
objects rather than just the notes. **It is also the only cross-check available**: the six notes
cannot be checked against each other, because their BOMs differ (5, 6, 6, 8, 7, 5 bricks), so
they are *supposed* to weigh different amounts.

→ **Destination:** `docs/object_map.toml`, per `[[models]]` entry. Already wired (ADR-026).
Part masses go in `docs/object_parts.toml` alongside the part identification.

---

## MEAS-3 · Grip face — the 12 placement objects

For each, find where a mechanism can hold it without the object rotating, tipping or shedding a
part. Record the **opposed pair of faces** a gripper would close on:

| field | meaning |
|---|---|
| `axis` | `"x"` or `"y"` in the object's own frame — which way the jaws close |
| `span_mm` | distance between the two faces, **n = 3** |
| `height_mm` | height above the base at which the faces are parallel and rigid |
| `opposed` | `true` if two parallel faces exist; `false` if the object can only be scooped |

**The two cases that decide the mechanism**, per the work order — answer these explicitly:

- **the cable**, 16 × 128 mm: can it be lifted from **one** grip point, or does it need two?
  This is what separates a parallel gripper from a fork.
- **the congas**: does it grip on the 2×6 Technic bridge, or on a drum?

**Also time a realistic pick-and-place** while the object is in hand — ten repetitions with a
stopwatch. ADR-030 shows the run becomes impossible at 12 s per object *at any driving speed*,
and ADR-032 shows handling time is what decides whether σ or speed is the binding unknown. This
is the single most informative number of the whole session that is not a dimension.

```toml
grip_face = { axis = "x", span_mm = 32.1, height_mm = 12.0, opposed = true }
grip_face_evidence = "MEASURED(calipers, 2026-08-02) n=3 [32.1, 32.0, 32.1]; jaws on the two 4-stud side faces, clears the 9.6 mm overhang"
```

→ **Destination:** `docs/object_map.toml` `[[models]]`. **Newly wired by this unit.**
Pick-and-place seconds go in `docs/FIELD_TEST_PLAN.md` alongside P7.

---

## MEAS-4 · Calipers on every footprint — the independent check

Phase 4 derived **every** dimension in this project by counting studs in a rasterised PDF and
multiplying by 8.00 mm. Nothing has tested that chain by a second method.

Measure the **contact footprint** (the part that touches the mat) on both axes, **n = 5 per
axis**. Compare against `data/object_spec.json`:

| Object | Repo says | Why |
|---|---|---|
| any note, `mic`, `instrument_guitar` | contact **32.0 × 32.0** | both A7 readings rest on these |
| `cable_upper` / `cable_lower` | **16.0 × 128.0** | 128.0 is what makes the placement orientation *forced* |
| `clef` | **32.0 × 48.0** | |
| `instrument_keyboard` | **≤ 56 × 56 — a BOUND** | upgrade to a measurement |
| `instrument_congas` | **≤ 112 mm long — a BOUND** | upgrade to a measurement |

### Precondition — every reading must land on the LEGO lattice

LEGO geometry is a lattice, so a caliper reading is not a free number. It has to land on it:

| axis | predicate | why |
|---|---|---|
| **horizontal** | **`8n − 0.2 mm`** for `n` studs | 8.0 mm stud pitch, 0.2 mm clearance. 4 studs = **31.8**, 8 = **63.8**, 16 = **127.8**. Assemblies follow the *total* stud count — two 2×4 bricks side by side span 8 studs = 63.8, not 2 × 31.8. |
| **vertical** | **`3.2 mm × plates`** (a brick is 9.6 = 3 plates) | stacking is flush, so there is **no** −0.2 here |

**More than ±0.3 mm off the lattice is a mis-measurement. Fail the field, do not record it** —
unless the object was declared in advance as Technic or non-orthogonal. The declared exceptions
are the cable's `flexible_hose` (ADR-017 gives it no footprint at all) and the two unidentified
parts `shape_10` and `shape_11`.

> **This makes MEAS-4 a test of a prediction, not a transcription — and there is a prediction to
> test.** The repo derives footprints as `studs × 8.00`, so it reports **32.0 mm** where the
> physical part is **31.8**. Every derived dimension is **systematically +0.2 mm** by
> construction. It has never surfaced because the agreement tolerance is ±0.5 mm, which absorbs
> it.
>
> **So calipers should read 0.2 mm *below* the repo value, consistently, on every orthogonal
> object.** If they do, the stud-counting chain is confirmed *and* its bias is quantified. If
> they read exactly 32.0, suspect the calipers spanned stud centres rather than part edges.
>
> **Do not change `studs_to_mm` on the strength of this.** Correcting a derived value on theory,
> ahead of the measurement that would confirm it, is the wrong order — and it would destroy the
> prediction this block exists to test.

```toml
base = { contact_studs = [4, 4], projection_studs = [4, 8], overhang_height_mm = 9.6,
         measured_contact_mm = [31.8, 31.8],
         measured_contact_evidence = "MEASURED(calipers 0.01 mm, 2026-08-02) n=5 x:[31.79,31.80,31.81,31.80,31.79] y:[31.80,31.78,31.81,31.80,31.80]; on lattice (8x4-0.2=31.8)" }
```

The builder **keeps the derived figure** as `derived_contact_footprint_mm` and sets
`contact_footprint_agrees_with_derived` at **±0.5 mm**, so a disagreement between two independent
methods is a visible finding, never a silent overwrite.

> **Calipers do not close A7.** A7 asks *which* extent `completely_in` consumes. Both numbers are
> already known; the ambiguity is in a sentence. See `docs/QUESTIONS.md` §1.

→ **Destination:** `docs/object_map.toml` `base` table. Already wired (ADR-026).

---

## MEAS-5a · Tilt angle — **13 objects, not 16**

S6 2026-06-30 defines *not upright* as **not fully touching the floor**. Tilt each object until
its base **first lifts**, and record the angle. This retires `AS-6`
(`upright_tolerance_deg = 15°`, an assumption with no measurement behind it).

**The three instruments are excluded.** `data/scoring_model.json`,
`m2_prepare_show_instruments`: `full_condition: "completely_in(instrument, backstage)"`, note
*"No uprightness requirement and no partial credit."* No predicate anywhere consumes their tilt
angle. Cables, microphone and notes carry `AND upright` / `OR not upright`; the four bonus
objects reach it through `NOT moved`. **13 objects: 6 notes, 2 cables, mic, clef, 2 speakers, amp.**

### ⚠ Without an anti-slip cleat this measures friction, not tipping

An object on an incline **tips** at `tan θ = w/h` and **slides** at `tan θ = μ_s`. Whichever
angle is lower happens first — so tipping only occurs when `w/h < μ_s`. Against μ_s ≈ 0.35 for
ABS on a smooth surface:

| object | w (mm) | h est | w/h | θ_tip | θ_slide | |
|---|---:|---:|---:|---:|---:|---|
| note | 16 | 27 | 0.59 | 30.7° | 19.3° | **slides** |
| cable | 8 | 10 | 0.80 | 38.7° | 19.3° | **slides** |
| mic | 16 | 45 | 0.36 | 19.6° | 19.3° | **slides** |
| amp | 30 | 35 | 0.86 | 40.6° | 19.3° | **slides** |
| speaker | 20 | 30 | 0.67 | 33.7° | 19.3° | **slides** |
| clef | 16 | 40 | 0.40 | 21.8° | 19.3° | **slides** |

**Every shape slides.** And it fails silently: the object still stops moving at a definite angle,
you still read a number, and the formula still returns a CoG height. That number is `w/μ_s`.
Every object would report ≈19.3°, which looks like excellent repeatability.

**So the cleat is mandatory, not an option.**

- **Use a LEGO tile — 3.2 mm, flat top, no studs.** A tile is dimensionally standard and
  repeatable; a fabricated shim is neither. Bound: **`c` ≤ 3.5 mm**, which a tile satisfies.
- It lifts the effective pivot by `c`, so the tipping condition becomes `tan θ = w/(h − c)` and
  the recovery formula becomes **`h = w/tan θ + c`**.
- Worked check: w = 16, true h = 27, c = 2 → tips at **32.62°**. With the correction you recover
  **27.00 mm**; without it, **25.00 mm — 7.4 % low**.
- Keep the cleat **low**. A tall cleat is not wrong, but `c` becomes a large fraction of `h` and
  its own measurement error dominates.

#### `c` enters `h` at 1 : 1 — measure it, never assume it

A 0.2 mm error in `c` is a **0.2 mm error in `h`**, undamped. So:

- **Measure `c` in situ, with calipers, including any tape or adhesive under the tile.** A tile
  is 3.2 mm; a tile on a strip of double-sided tape is not, and the difference is entirely real.
- **Log it once per session**, with the rig. If the cleat is re-seated, re-measure.
- Do **not** take 3.2 mm as nominal. The one number in this method with no measurement behind it
  is the one that propagates straight into the answer.

#### The pivot is at `(0, c)` only for a flat, perpendicular face

The derivation assumes the object's downhill face is flat and square to its base. **Several are
not** — the notes have shaped bodies, and the cable's ends carry sloped feet. Where the face is
shaped, contact happens somewhere else, and that perturbs **both** `w` and the effective `c`.

**Per object, identify and record where the object actually touches the cleat:**

| field | what it is |
|---|---|
| `cleat_contact_height_mm` | the height at which contact occurs — **use this as `c`**, not the tile's height |
| `cleat_contact_note` | flat-and-square, or where and why it differs |

If contact is **not** on a vertical face — a slope, a curve, a single protruding foot — then `w`
is no longer the base half-width either. Measure `w` to the **actual contact**, or mark the
object CoG-underivable and leave `cog_height_mm` null. A null is recoverable; a CoG computed
from the wrong lever arm is not distinguishable from a right one.

### Validation — if this fires, fail the block and record nothing

1. **Watch for translation.** Mark the object's downhill edge on the ramp before each trial. If
   the object *moves down the ramp before it rotates*, it slid. Discard the trial.
2. **Check the numbers for the friction signature.** `arctan(0.35) ≈ 19.3°`, and friction does
   not care about shape. **If objects whose base widths differ by more than 1.5× report angles
   within ±2° of each other — and especially if that cluster sits at 19–20° — you measured μ_s.**
   Do not record it. Fix the cleat and re-run the block.

A genuine tipping measurement produces angles that **differ across shapes**, because `w/h`
differs across shapes. Agreement between a note and an amp is the failure signal, not success.

### Angular resolution — ±0.5°

Error propagates as `|dh/h| = 2·dθ / sin 2θ`, which is an **amplification, never a reduction**:

| θ | amplification | at ±0.5° | at ±1° | at ±2° | |
|---:|---:|---:|---:|---:|---|
| **20°** | **3.11×** | 2.7 % | 5.4 % | 10.9 % | ⚠ **not your operating point — this is the friction angle.** See below. |
| **30–35°** | 2.31 – 2.13× | **1.8 – 2.0 %** | 3.7 – 4.0 % | 7.4 – 8.1 % | ← **where a cleated object actually reads** |
| 45° (best case) | **2.00×** | 1.7 % | 3.5 % | 7.0 % | |

**Even at the optimum the error doubles.** Use a **digital angle gauge or a phone inclinometer
against a rigid flat reference — target ±0.5°.** A protractor read by eye is ±2° and gives
7–11 % on CoG; at that point do not derive CoG at all (see MEAS-5b).

> **Evaluate sensitivity at the TIPPING angle, not at 20°.** With a cleat these objects tip at
> **≈ 30–35°** — a note with `w = 16`, `h = 27`, `c = 2` tips at **32.6°** — so the expected
> error at ±0.5° is **≈ 1.8 %**, not the 2.7 % the 20° row shows.
>
> The 20° row is kept as **contrast, not as a target**: `arctan(0.35) ≈ 19.3°` is the *friction*
> angle, which is what you read **if the cleat fails**. Computing your error budget there is
> planning against a measurement you are trying to avoid — and it is pessimistic by roughly 2.6×
> (`dh/dθ` is −146.5 mm/rad at 19.3° against −55.1 at 32.6°).
>
> **This is the same fact as the validation rule, seen from the other side.** A reading near 20°
> is the friction signature. If your angles land there, the answer is not "the error is 2.7 %" —
> it is "the cleat is not working, fail the block."

```toml
tilt_angle_deg = 32.6
tilt_evidence = "MEASURED(digital angle gauge ±0.5°, 2026-08-02) n=11; no translation observed; readings [32.4, 32.7, ...]"
cleat_contact_height_mm = 3.25
cleat_contact_note = "LEGO tile 3.2 mm + 0.05 tape, measured in situ; contact on the flat 4-stud downhill face, square to the base"
```

→ **Destination:** `docs/object_map.toml` `[[models]]`. Record the superseded `AS-6` value rather
than deleting it.

---

## MEAS-5b · CoG height — derived, and optional

**No separate measurement.** `cog_height_mm = w/tan θ + c` from MEAS-5a, with `cog_source`
recording that it is derived and naming `c`.

**Skip it if the angle rig cannot hold ±0.5°.** Its only consumer is ADR-022's manipulator
decision — will a gripper tip the object while lifting — and a value carrying 11 % error informs
that no better than the geometry already does.

**If CoG is wanted at better precision, do not use the incline at all.** The **reaction-board**
method never requires the object to tip, so friction is irrelevant and the cleat is unnecessary:

> Board pivoted at **A**, resting on the scale at **B**, distance **L** apart. Clamp the object
> to the board and tare the board. Read the scale level (**R₀**), then with the board tilted by
> **θ** about A (**R₁**). With total object weight **W**:
>
> **`h = L (R₀ − R₁) / (W · tan θ)`** — CoG height above the board surface.

At L = 200 mm, W = 25 g, θ = 30°, a 0.1 g scale resolves `h` to about **5 %** — comparable to the
±0.5° tilt method, with no failure mode that returns a plausible wrong answer. It costs a board,
a pivot and a clamp, and about 3 minutes per object.

---

## Proxies, stated in advance

Decided **now**, so that a field which turns out to be unmeasurable on the day does not become an
improvised judgement call at the bench.

| field | if it cannot be measured directly | acceptable proxy |
|---|---|---|
| **CoG height** | no reaction board | **Derive it from MEAS-5a — with the cleat correction.** `h = w/tan θ + c`, never the uncorrected `w/tan θ`, and never without the cleat: an object that slides returns `w/μ_s` and looks fine. Record `cog_source` as derived, name `c`, and skip the field entirely if the angle rig is worse than ±0.5°. |
| **grip face** on an object with no parallel faces | e.g. a drum shell | the **widest parallel pair on the rigid carrier**, with `opposed = false` and the reason in `grip_face_evidence`. A scoop is a valid answer and changes the mechanism decision. |
| **cable footprint** | the flexible hose has no defined extent | **the rigid carrier only** — ADR-017 already gives the hose no footprint. Measure the 2× Technic Brick 1×16 and the protruding red feet separately. |
| **keyboard / congas** | too irregular for a clean two-axis reading | record the **bounding rectangle of the contact patches** and say so; it upgrades a bound to a measured bound, which is still progress. |
| **tilt** on a near-spherical or rocking base | no clean tipping edge | record the angle at which it *begins to roll* and say so in `tilt_evidence`. Do not derive a CoG from it — the pivot is not where the formula assumes. |
| **tilt** when the cleat cannot stop the slide | very low friction, or a base that rides over the cleat | **do not raise the cleat until it works** — a tall cleat makes `c` dominate. Switch to the reaction board, or leave `tilt_angle_deg` null and record why. A null is recoverable; `w/μ_s` recorded as a tipping angle is not. |

**If a field is genuinely unmeasurable and has no proxy, leave it `null`.** That is the ADR-014
discipline: an obvious gap beats a plausible placeholder, because every downstream module reads
`data/object_spec.json` without question.

---

## When you are done

```bash
uv run python tools/build_object_spec.py     # numbers flow into data/object_spec.json
uv run python tools/build_all.py             # rebuild whatever those numbers changed
uv run pytest                                # the inert-value guards will now fail — expected
```

**The inert guards failing is the success signal**, not a problem: `tests/test_object_spec.py`
asserts every measured field is still `null`, precisely so that the moment real numbers arrive
the repo notices. Update those tests to assert the *new* invariants — ranges, agreement flags,
`cog_source` present wherever `cog_height_mm` is — in the same unit of work as the measurement.
