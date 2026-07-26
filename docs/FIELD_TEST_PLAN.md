# Field test plan — two drive platforms as measuring instruments

`last_reviewed: 2026-07-27` · **all hardware is held; nothing here is blocked**

## Why this exists

Every parameter in the eventual `dynamics.py` and `sensors.py` is currently an `ASSUME:` with
no measurement behind it — **including the ±5 mm hand-placement figure in
`docs/PHASE7_CONSTRAINTS.md` §2, which was reasoned, not measured.** Two drive platforms on a
real table close them.

These builds are **instruments, not competition robots.** Each test below names the parameter
it replaces, so a session on the table produces data with a destination rather than
impressions.

**This moves Phase 6 forward, not Phase 7.** Phase 6's parameter acquisition can run **in
parallel with Phase 4**, not strictly after it — only P5 needs Phase 4's objects.

## What may be built now, and what may not

| Buildable today | Not buildable today |
|---|---|
| drivetrain (wheel Ø, track width, gear ratio) · sensor mounting geometry · chassis inside the 250 mm envelope · start frame per S4 §10.3 | **gripper, lifter, any manipulator** |

Object dimensions, mass and grip points come from Phase 4. A gripper designed before the note
base width is known is a guess that gets rebuilt. A final **chassis** is permitted (A6 closed
at international scope); a final **manipulator** is not.

---

## Step 0 — count the parts before anything else

**No BOM figure enters this repo unmeasured.** Physically count and record with the date, as
`MEASURED(inventory, <date>)`:

| Set | Motors | Colour sensors | Distance / force | Hubs |
|---|---|---|---|---|
| EV3 45544 | | | | |
| SPIKE Prime 45678 | | | | |
| SPIKE Expansion 45681 | | | | |

The commonly-quoted values (EV3 3 motors / 1 colour; SPIKE 4 motors / 2 colour) are **exactly
the kind of number this project does not accept on assertion** — there is no traceable source
for a LEGO set BOM here.

**If the SPIKE motor count is 4, it equals the S4 §5.2.8 Elementary cap with zero slack in
either direction** — inventory and rules bind simultaneously, and no spare motor exists if all
four are used. §5.4 permits spare parts but not a spare chassis. Record that coincidence if it
holds; it is a design constraint, not trivia.

---

## Step 1 — `RobotIO` and a trivial mission, before the full field test

The project's core invariant is that mission code imports only `robot_io.RobotIO`, so one file
runs on the simulator and on hardware.

> **Partly discharged 2026-07-27 (ADR-023).** It is no longer an untested claim, and it did not
> need two hubs to test most of it. The risk is **linguistic**, not electrical: the simulator is
> CPython 3.13 and both hubs are MicroPython, EV3's from May 2020. A construct CPython accepts
> and MicroPython rejects is a syntax error found on the competition table.
>
> `tools/check_portability.py` now walks every hub-bound file and rejects what those ports
> cannot run — f-strings above all, since MicroPython added them in **1.17 (Sept 2021)** and EV3
> MicroPython v2.0 is **18 May 2020**. Eleven parametrised tests assert the lint *rejects* each
> construct, because a lint that has never rejected anything is not evidence.
>
> **What hardware still tests, and only hardware can:** that the Pybricks calls behave as their
> documentation says. Both backends are written out call by call, cited to their doc pages, and
> raise `NotImplementedError("UNVERIFIED")` until run. Arrival day is a checklist.

`robot/missions/trivial.py` is written and runs against the simulator: **drive 500 mm, turn 90°,
read a colour**, exactly as specified below. Run it on both hubs to close the remaining half.

### Toolchain — verified, and the answer is two

`NEEDS-VERIFY` discharged against current documentation on 2026-07-25:

| Toolchain | EV3 | SPIKE Prime |
|---|---|---|
| Pybricks v3/v4 — the hub index lists MoveHub, CityHub, TechnicHub, InventorHub, **PrimeHub**, EssentialHub | **absent** | ✓ |
| EV3 MicroPython v2.0.0 — ev3dev-based SD image, **May 2020** | ✓ | ✗ |

⇒ **No single current toolchain targets both.** `RobotIO` is therefore **one contract with two
implementations**, designed that way from the start — `robot/robot_io.py` plus
`robot_io_ev3.py` and `robot_io_spike.py`.

**Narrowed 2026-07-27.** The two are the same family at two generations, not strangers:
Pybricks v2.x on EV3 (community-supported, in the ev3dev image) and Pybricks v3/v4 on the six
modern hubs, EV3 absent. They share `pybricks.robotics.DriveBase` and
`pybricks.parameters.Port`; they differ in the device module — `pybricks.ev3devices` against
`pybricks.pupdevices` — and in the hub class, `EV3Brick` against `PrimeHub`. One real
capability difference: the PrimeHub has an IMU, so its `heading()` need not be pure odometry.

One trap worth stating: **Pybricks `turn()` is clockwise-positive** while the MAT frame and this
contract are counter-clockwise-positive (`CLAUDE.md` §5.2). Both backends must negate; getting
it wrong mirrors every mission. A test asserts both files say so.

~~`NEEDS-VERIFY(toolchain-alt)`~~ — **DISCHARGED 2026-07-27.** The note asked for `ev3dev` /
`python-ev3dev2` and LEGO's own SPIKE app to be surveyed before `RobotIO` hardened. `RobotIO`
hardened in ADR-023, so this ran late. The answer is unchanged:

| Family | EV3 | SPIKE Prime |
|---|---|---|
| Pybricks v2.x (ev3dev image) | ✓ | ✗ |
| Pybricks v3/v4 (six modern hubs) | ✗ | ✓ |
| `ev3dev` / `python-ev3dev2` | ✓ | **✗** — SPIKE runs embedded MicroPython on an M4; ev3dev is a Linux distribution for EV3/BrickPi. `ev3dev-lang-python` issue #614 treats SPIKE support as an aspiration |
| LEGO SPIKE App | **✗** — EV3 Classroom is a separate application | ✓ |

⇒ **No single toolchain targets both**, now checked against three families rather than one.
ADR-023's two-implementation decision stands.

### Platform availability — both are end-of-life

Not a blocker (the hardware is held) but it bears on spares and on how long the toolchains stay
installable. From LEGO Education's own pages, read 2026-07-27:

- **SPIKE Prime end of sale: 30 June 2026** — already past.
- SPIKE App supported to **30 June 2031**; the software stays online after, without updates.
- Spare parts stocked **until 2028** (two years after last sale).
- **EV3 retired 2021**; EV3 Lab and EV3 Classroom are both listed under "retired products".

`NEEDS-VERIFY(ev3-download-window)`: several third-party summaries state the EV3 app download
ends **31 July 2026**. LEGO's own retired-products and EV3 software pages carry **no such date**,
so it is recorded as unconfirmed rather than repeated as fact. Archiving both toolchains locally
is cheap insurance either way.

Sources: `docs.pybricks.com/en/latest/hubs/` · `pybricks.com/ev3-micropython/` ·
`github.com/ev3dev/ev3dev-lang-python` issue 614 · `education.lego.com/en-us/spike-update-2026/` ·
`education.lego.com/en-us/downloads/retiredproducts/`

---

## The tests

Results land as `MEASURED(field-test, <date>, <venue>)` and replace the corresponding
`ASSUME:` entries in `docs/ASSUMPTIONS.md` — **with the superseded value recorded, not
deleted.**

### P1 · Colour discrimination — the EV3-vs-SPIKE discriminator

Sample the six note colours (red, blue, green, yellow, white, black), the four `#a0d187`
start squares, and the mat background, under venue lighting. Report per-channel values and
**pairwise separation** between every colour pair.

EV3 has 1 colour sensor, SPIKE has 2 (**verify against the Step 0 inventory first**). Two
sensors permit direct ratiometric comparison, which S4 §7.10.2, §7.10.3 and §9.3 already
argue for. **Measure whether one sensor can time-share identification and navigation, or
whether it cannot** — cameras are prohibited (§5.2.7), so there is no fallback.

→ replaces: the "ratiometric colour discrimination" `ASSUME:` in `PHASE7_CONSTRAINTS.md` §4

### P2 · Start-area placement repeatability

Place the robot in the start area **20 times** against the printed edge; measure the pose each
time. The start area measures **250.02 × 250.02 mm** — 0.01 mm per side over the envelope,
i.e. effectively zero slack — so this number sets the
usable chassis width directly.

Run it **with and without a start frame (§10.3)** — that quantifies what the frame buys.

→ replaces: `ASSUME:` ±5 mm per side, ~235–240 mm budget (`PHASE7_CONSTRAINTS.md` §2)

### P3 · Odometry drift

Straight-line and turn-in-place across the mat, measured against mat features. Report drift
**per metre** and **per 90°**.

→ feeds: `dynamics.py`, currently parameterless

### P4 · Table and mat reality

Actual gap between the mat edge and **each** wall. S4 §7.2 permits ±5 mm per dimension and
S1 p3 registers the mat against the **right** wall with Y centred, so slack accumulates toward
−X — and the stage-side missions (cables, mic, backstage, all at x < 535) sit at the far end
of that error chain. Also measure mat waviness, bumps, and whether the table is level.

→ replaces: `table.tolerance_mm` as a nominal figure in `field_spec.json`

### P5 · Upright, as a contact test — **RUNNABLE**

The S6 answer of 2026-06-30 defines *not upright* as **not fully touching the floor**. With a
physical game object, measure the tilt angle at which the base **first lifts**.

→ replaces: AS-6 / `upright_tolerance_deg = 15°`

**Unblocked 2026-07-27.** The game objects are held (WRO Brick Set 45811 + Expansion 45819).
This was recorded as blocked from Phase 4 onward on the strength of an operator answer of
"partially / not sure yet" that was never re-asked — see ADR-025. Sequenced as **A5** in
`docs/HARDWARE_SESSION.md`.

### P7 · Object mass and grip points — **the measurement ADR-022 waits on**

Added 2026-07-27. With the physical objects, for each of the 12 placement objects record:

| | |
|---|---|
| **mass** | grams, on a scale. Replaces `mass_g: null` in `data/object_spec.json` for all 16 objects |
| **grip points** | where a mechanism can hold it without the object rotating, tipping or shedding a part |
| **the cable specifically** | can a 128 mm object be lifted from one grip point, or does it need two? That is what separates a parallel gripper from a fork |
| **the congas** | its true drum separation, currently **bounded** at ≤ 112 mm rather than measured |
| **the keyboard** | its true base extent, currently **bounded** at ≤ 56 × 56 mm |

→ closes: **ADR-022's gated half** — the manipulator mechanism. Also closes A7 by calipers, and
upgrades two bounds to measurements.

**This is the highest-value hour of table time available**, because it is the only measurement
here that unblocks a design *decision* rather than refining a parameter.

### P6 · Motor characterisation

Acceleration limit, slip threshold, and minimum controllable speed — **per platform**.

→ feeds: `dynamics.py`

---

## Phase 4 interaction

**Resolved 2026-07-27: the team holds both sets.** The table below is kept because the
stud-counting route was the one actually taken and it worked — Phase 4 closed with all 16
objects mapped. It is now the thing calipers **check** rather than the thing they replace:

| | Phase 4 method | P5 |
|---|---|---|
| **Sets held** | measure physical parts with calipers — closes A7 (note base vs the 79.699 mm target), grip points, and P5 in one afternoon. Stud-counting becomes the **cross-check**, not the source. | runnable |
| **Not held** | count studs in the S3 page rasters × 8.00 mm (S4 §7.4: elements are LEGO System/Technic, so stud pitch is a known constant) | waits |

**Superseded twice, 2026-07-27.** First: phases 4 and 6 are DONE, so "the sole remaining item
on the critical path" no longer described the project. Second, and larger: **the sets are held.**
Nothing on this page is blocked.

What the sets were said to gate — every `mass_g`, the manipulator mechanism (ADR-022), and every
field test here — is now simply *work to be done*, ordered in `docs/HARDWARE_SESSION.md`. The
highest-leverage action is no longer a purchase; it is an afternoon with a scale and calipers.
