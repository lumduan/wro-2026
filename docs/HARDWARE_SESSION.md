# Hardware session — the work order

`last_reviewed: 2026-07-27`

Every measurement below is **runnable now**. All of it is held:

| Set | What it is |
|---|---|
| EV3 Core Set **45544** | robot platform 1 |
| SPIKE Prime **45678** + Expansion **45681** | robot platform 2 |
| WRO Brick Set **45811** + Expansion **45819** | the game objects (S4 §7.4) |
| The printed game mat | 2361.999 × 1143.000 mm, `MEASURED(S2)` |
| A competition-spec table | S4 §7.2 |

> **State correction, 2026-07-27.** Until today this repo recorded itself as blocked on
> procurement, and said so in four documents. It never was — an operator answer of *"partially /
> not sure yet"* was hardened into a blocker and inherited by every later phase without being
> re-asked. See **ADR-025**.

`docs/FIELD_TEST_PLAN.md` remains the **why**: what each test measures and which `ASSUME:` it
replaces. This file is the **order of work**, and the two are checked against each other by
`tests/test_hardware_session.py`.

---

## Priority, if the session is cut short

**A1 → A3 outrank everything else on this page.** They close a *design decision* — the
manipulator mechanism, gated since ADR-022 — where every other item refines a parameter that
already has a working default. A2 and A3 together are perhaps an hour, and they are the only
hour that unblocks Phase 7's completion.

After those, **B5** is the single most valuable: it produces σ, which converts
`data/placement_sensitivity.json` from a statement of what accuracy is *required* into a
prediction of what will actually score, and it is what Phase 8's mission ordering waits on.

---

## Block A — bench work. No robot needed.

Everything here needs the game objects, a scale, calipers and a flat surface. It can be done
before a single motor is attached, and it closes more open questions than Block B.

### A1 · Count the parts — before anything else

**No BOM figure enters this repo unmeasured.** Fill in `docs/FIELD_TEST_PLAN.md` Step 0's table
and tag it `MEASURED(inventory, <date>)`.

| Set | Motors | Colour sensors | Distance / force | Hubs |
|---|---|---|---|---|
| EV3 45544 | | | | |
| SPIKE Prime 45678 | | | | |
| SPIKE Expansion 45681 | | | | |

**Watch for one coincidence.** S4 §5.2.8 caps Elementary at **4 motors**. If the SPIKE count is
also 4, inventory and rules bind simultaneously and there is **no spare motor** if all four are
used — while §5.4 permits spare parts but not a spare chassis. Record it either way; it is a
design constraint, not trivia.

→ closes: Step 0. Feeds ADR-022's motor arithmetic with a measured, not assumed, supply.

### A2 · Weigh all 12 placement objects

Grams, on a scale. `mass_g` has been `null` for all 16 objects since Phase 4 because mass cannot
be derived from a building instruction.

Record in `docs/object_map.toml` per model as `mass_g` plus `mass_source`, tagged
`MEASURED(scale, <date>)`, then re-run `tools/build_object_spec.py`. **The path is live** —
values flow through to `data/object_spec.json`, and a test asserts every one is still `null`
until you type a number.

→ closes: **P7** (first half); `mass_g` for every object; half of ADR-022's gate.

### A3 · Grip points — the measurement that closes a decision

For each of the 12 placement objects, find where a mechanism can hold it without the object
rotating, tipping, or shedding a part. Two cases decide the mechanism between them:

- **the cable** — 16 × 128 mm. Can a 128 mm object be lifted from **one** grip point, or does it
  need two? This is precisely what separates a parallel gripper from a fork.
- **the congas** — one rigid object with **two** contact patches on a 2×6 Technic bridge. Does it
  grip on the bridge or on a drum?

→ closes: **P7** (second half) and **ADR-022's gated half**. Write the outcome as a new ADR
with the arithmetic shown, exactly as ADR-022 refused to do without this measurement.

### A4 · Calipers on every footprint — the independent check

Phase 4 derived **every** dimension in this project by counting studs in rasterised building
instructions and multiplying by 8.00 mm. Nothing has ever tested that chain by another method.
Calipers do.

Measure and compare against `data/object_spec.json`:

| Object | Repo says | Why it matters |
|---|---|---|
| any note, `mic`, `instrument_guitar` | contact **32.0 × 32.0**, projection **32.0 × 64.0** mm | the whole of A7 turns on these two numbers |
| `cable_upper` / `cable_lower` | **16.0 × 128.0** mm | 128.0 mm is what makes the placement orientation *forced* |
| `clef` | **32.0 × 48.0** mm | |
| `instrument_keyboard` | **≤ 56 × 56 mm — a BOUND** | upgrade to a measurement |
| `instrument_congas` | **≤ 112 mm long — a BOUND** | upgrade to a measurement |

Record in `docs/object_map.toml` as `base.measured_contact_mm` plus
`base.measured_contact_evidence`. The builder **keeps the stud-derived figure alongside** as
`derived_contact_footprint_mm` and sets `contact_footprint_agrees_with_derived`, so a
disagreement between the two methods is a visible finding rather than a silent overwrite.

> **Calipers do not close A7.** A7 asks *which* extent `completely_in` consumes — the contact
> patch or the silhouette. Both numbers are already known; the ambiguity is a rule
> interpretation, and only the official Q&A settles it. Measuring more precisely cannot pick
> between two readings of a sentence.

→ closes: two bounds; independently verifies Phase 4's entire method.

### A5 · Tilt each object until its base lifts

S6 2026-06-30 defines *not upright* as **not fully touching the floor**. Measure the tilt angle
at which the base first lifts, per object shape.

→ closes: **P5**. Replaces `AS-6` / `upright_tolerance_deg = 15°` in `docs/ASSUMPTIONS.md`,
with the superseded value recorded rather than deleted.

---

## Block B — table work. Mat and table required.

### B0 · Measure the object start poses — do this while the field is set up

Set the field up per S1's diagram and record where each object actually starts. **Ten objects**
are `nominal_pending` with null coordinates, because ADR-014 refused to invent them:

`amp` · `cable_lower` · `cable_upper` · `clef` · `instrument_congas` · `instrument_guitar` ·
`instrument_keyboard` · `mic` · `speaker_a` · `speaker_b`

Record in `docs/area_map.toml` under `[measured_start_poses.<object>]` as `pose_mm`,
`tolerance_mm` and `evidence`, then re-run `tools/build_field_spec.py`.

> **Do not try to measure the four randomized notes.** `note_black`, `note_blue`, `note_white`
> and `note_yellow` are assigned to their start squares at randomization (S1 p7), so they have
> no fixed start pose — that is the rule, not a gap in the data. `note_green` and `note_red` are
> already measured from S2's fixed squares.

→ closes: ADR-014's pending set. **Unblocks route planning**, which is the other half of what
Phase 8 ordering needs besides σ — and it is what turns `P(collision)` from a free parameter
into something estimable at all.

First in this block because everything else here needs the field set up anyway.

### B1 · Run `robot/missions/trivial.py` on **both** hubs

Drive 500 mm, turn 90°, read a colour. The file imports only `robot_io.RobotIO`; the two
backends are written out call by call and cited to their doc pages.

Fill in `robot/robot_io_ev3.py` and `robot/robot_io_spike.py`, then set
`VERIFIED_ON_HARDWARE = True` in each — **only** once the calls have actually run.

**Watch the sign convention.** Pybricks `turn()` is **clockwise-positive**; the MAT frame and
this contract are **counter-clockwise-positive** (`CLAUDE.md` §5.2). Both backends must negate.
Getting it wrong mirrors every mission, and it will look like a working robot.

→ closes: the hardware half of ADR-023's portability claim. The linguistic half is already
covered by `tools/check_portability.py`; this is the half only hardware can test.

### B2 · P1 — colour separation

Sample the six note colours, the four `#a0d187` start squares and the mat background under
venue lighting. Report per-channel values and **pairwise separation between every pair**.

The discriminator to settle: EV3 has 1 colour sensor, SPIKE has 2 (confirm against A1). **Can
one sensor time-share identification and navigation, or not?** Cameras are prohibited (§5.2.7),
so there is no fallback.

→ closes: P1; the ratiometric-sensing `ASSUME:` in `PHASE7_CONSTRAINTS.md` §4.

### B3 · P4 — mat and table reality

Gap between the mat edge and **each** wall; mat waviness and bumps; whether the table is level.
S4 §7.2 permits ±5 mm per dimension and S1 registers the mat against the **right** wall with Y
centred, so slack accumulates toward **−X** — and every stage-side mission (cables, mic,
backstage, all at x < 460) sits at the far end of that error chain.

→ closes: P4; `table.tolerance_mm` as a nominal figure in `field_spec.json`.

### B4 · P2 — start-area placement repeatability

Place the robot in the start area **20 times** against the printed edge and measure the pose
each time. The start area is **250.02 × 250.02 mm** — 0.01 mm per side over the §5.1 envelope,
i.e. effectively zero slack — so this sets the usable chassis width directly.

Run it **with and without a start frame** (§10.3) to quantify what the frame buys.

→ closes: P2; the `±5 mm` / 235–240 mm `ASSUME:` in `PHASE7_CONSTRAINTS.md` §2.

### B5 · P3 — odometry drift → **σ**

Straight-line and turn-in-place across the mat, measured against mat features. Report drift
**per metre** and **per 90°**.

This is the one that changes the most downstream. σ is the single unmeasured input to
`data/placement_sensitivity.json`; with it, that table stops describing what accuracy is
*required* and starts predicting what will *score*. It also supersedes **AS-8** (placement error
is Gaussian and isotropic) and **AS-9** (0.5° of heading error per mm of σ) — measure the real
shape, then re-run `tools/run_sensitivity.py` against it.

→ closes: P3; AS-8; AS-9. Unblocks Phase 8 mission ordering.

### B6 · P6 — motor characterisation

Acceleration limit, slip threshold, minimum controllable speed — **per platform**.

→ feeds: `dynamics.py`, which does not exist yet and is parameterless by design until this runs.

---

## What no measurement here can close

**A7** — whether `completely_in` consumes the contact patch or the silhouette. It swings the
required note placement accuracy by **2.6×** (σ ≈ 11.4 mm against ≈ 4.3 mm) on the mission
carrying 120 of 255 points. Only the official Q&A settles it, and submitting it is the highest
value action available that is not on this page. **A1**, **A8**, **A9** and **A10** likewise.

**`NEEDS-VERIFY(NO-TH)`** — two questions for the Thai National Organizer, neither yet asked:

1. **Robot limits** — S4 §4.3 and §5.2. Every figure in this repo is international-scope until
   they confirm.
2. **Tournament format** — how many rounds (§9.1.2), how they are aggregated (§10.13), whether a
   mulligan is offered (§10.14), and whether practice time is interleaved between rounds (§9.3).

The second **outranks everything on this page**, because it sets the objective function rather
than a parameter in it (ADR-027). If the ranking is best-of-three, the target is
`E[max of 3]`, which rewards variance — at σ = 20 mm that is 229 rather than 216, and the gap
*widens* as σ grows. A measurement session tuned to minimise σ is optimising the right thing
only if N = 1.
