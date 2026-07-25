# Field test plan — two drive platforms as measuring instruments

`last_reviewed: 2026-07-25`

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
runs on the simulator and on hardware. **That is currently an untested claim.** Two platforms
is the strongest test it will ever get.

Write `RobotIO` and one trivial mission — **drive 500 mm, turn 90°, read a colour** — and run
it on both hubs. That single result determines whether `RobotIO` needs one implementation or
two, and it is far cheaper to learn now than after twelve mission programs exist.

### Toolchain — verified, and the answer is two

`NEEDS-VERIFY` discharged against current documentation on 2026-07-25:

| Toolchain | EV3 | SPIKE Prime |
|---|---|---|
| Pybricks v3/v4 — the hub index lists MoveHub, CityHub, TechnicHub, InventorHub, **PrimeHub**, EssentialHub | **absent** | ✓ |
| EV3 MicroPython v2.0.0 — ev3dev-based SD image, **May 2020** | ✓ | ✗ |

⇒ **No single current toolchain targets both.** `RobotIO` must be **one contract with two
implementations**, designed that way from the start rather than retrofitted.

`NEEDS-VERIFY(toolchain-alt)`: verified for Pybricks specifically. `ev3dev` /
`python-ev3dev2` and LEGO's own SPIKE app were **not** exhaustively surveyed; if a single
toolchain does exist via one of those, the two-implementation decision should be revisited
before `RobotIO` hardens.

Sources: `docs.pybricks.com/en/latest/hubs/` · `pybricks.com/ev3-micropython/`

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
time. The start area is **exactly 250.0 × 250.0 mm** with zero slack, so this number sets the
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

### P5 · Upright, as a contact test — **BLOCKED on physical game objects**

The S6 answer of 2026-06-30 defines *not upright* as **not fully touching the floor**. With a
physical game object, measure the tilt angle at which the base **first lifts**.

→ replaces: AS-6 / `upright_tolerance_deg = 15°`

**Blocked** until game objects exist — i.e. on Phase 4, or on acquiring WRO Brick Set 45811 /
Expansion 45819. Listed here so it is visibly blocked rather than looking runnable.

### P6 · Motor characterisation

Acceleration limit, slip threshold, and minimum controllable speed — **per platform**.

→ feeds: `dynamics.py`

---

## Phase 4 interaction

Whether the team holds **WRO Brick Set 45811** and **Expansion Set 45819** is not yet certain,
so both routes stay documented:

| | Phase 4 method | P5 |
|---|---|---|
| **Sets held** | measure physical parts with calipers — closes A7 (note base vs the 79.699 mm target), grip points, and P5 in one afternoon. Stud-counting becomes the **cross-check**, not the source. | runnable |
| **Not held** | count studs in the S3 page rasters × 8.00 mm (S4 §7.4: elements are LEGO System/Technic, so stud pitch is a known constant) | waits |

Phase 4 is the sole remaining item on the critical path to Phase 6, so resolving the
procurement question is the highest-leverage action available.
