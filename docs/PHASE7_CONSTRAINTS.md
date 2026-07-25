# Phase 7 constraint set — robot design

Everything the robot design must satisfy, recorded **before** anyone picks a chassis rather
than after. Every entry cites its rule; quotes are in `docs/citations.json`.

`last_reviewed: 2026-07-25`

**Scope note.** These are **international-level** limits. S4 §4.3 and §5.2 let National
Organizers change them — `NEEDS-VERIFY(NO-TH)` stays open until the Thai National Organizer
confirms which clauses they adapt.

---

## 1 · Hard limits (S4 chapter 5, Elementary column)

| Item | Value | Rule |
|---|---|---|
| Envelope **before start** | 250 × 250 × 250 mm, **cables included**; unrestricted after start | 5.1 |
| Weight | ≤ 1.5 kg | 5.2.1 |
| Battery capacity | ≤ 6,000 mAh | 5.2.2 |
| Battery voltage | ~~≤ 14 V~~ → **≤ 14.8 V nominal** | 5.2.3, superseded by S6 2026-05-14 |
| Current | ~~≤ 4 A~~ → **limit removed** | 5.2.4, deleted by S6 2026-05-14 |
| **Motors** | **4** | 5.2.8 |
| **Cameras** | **PROHIBITED** — Junior/Senior only | 5.2.7 |
| LIDAR / 3D scanners | prohibited — Senior only | 5.2.7 |
| Other sensors | no limit on type or number | 5.2.7 |
| Controllers | no limit on number/type; **no wireless between components** | 5.2.5 |
| Start/stop | one button, same for both, on the outer surface, not underneath | 5.2.6 |
| Brand mixing (EV3 + SPIKE) | allowed at international level | 5.2 intro |
| Spares | spare parts and controllers yes; **a full spare chassis, no** | 5.4 |

### The motor budget is the binding constraint

4 motors. A differential drive consumes **2**, leaving **2 DOF for 12 placement operations**
(cable ×2, mic, instruments ×3, notes ×6). Three exemptions change that arithmetic:

| Mechanism | Counts against the 4? | Rule |
|---|---|---|
| Pneumatics ≤ 3 bar, tanks ≤ 150 ml | **only the compressor** — one slot can drive many actuators | 5.2.16 |
| Pullback motor without electronic control | **no** — but the robot must wind it itself | 5.2.8 |
| Electromagnet used only to hold | **no** (counts if used as a linear motor) | 5.2.10 |
| Solenoid ≤ 20 N / ≤ 20 mm | **yes** | 5.2.10 |

Either the manipulator is passive/geometric, or pneumatics buy DOF at the cost of one slot.
§5.1's post-start size freedom makes deployable mechanisms legal. **Record whichever way this
goes as an ADR with the arithmetic shown; do not assert a topology without it.**

---

## 2 · Start heading is coupled to footprint

S4 §7.8 requires the robot's **projection** to be completely within the start area, and the
start area is **exactly 250.0 × 250.0 mm** — `MEASURED(S2)`, the same figure as the §5.1
envelope. So the constraint binds at every heading, and there is **zero** slack at maximum
legal size.

**For a SQUARE footprint only:**

| θ | max square footprint |
|---:|---:|
| 0° | 250.0 mm |
| 15° | 204.1 mm |
| 30° | 183.0 mm |
| 45° | 176.8 mm |

`footprint_max(θ) = 250 / (cos θ + sin θ)`

**A rectangle binds per axis** — do not read "a 30° start requires a 183 mm robot" as general:

```
w·cos θ + h·sin θ ≤ 250   AND   w·sin θ + h·cos θ ≤ 250
```

`ASSUME:` a practical budget of **~235–240 mm at θ = 0** without a start frame.
*Derivation:* hand-placement repeatability against a printed edge is roughly ±5 mm per side,
so ~10 mm of total width is surrendered to avoid a projection violation at inspection.
*Consequence if wrong:* too generous and the robot fails the §7.8 check at the table; too
tight and chassis volume is given away for nothing.
**This figure is reasoned, not measured — field test P2 replaces it.**

**S4 §10.3 permits a start module / start frame.** That is how the margin is bought back,
which promotes the frame from a convenience to a **design element**. P2 measures what it buys.

---

## 3 · The start area is not a uniform surface

Logo, yellow band, text and a QR code sit inside it — **29.56 % of the interior is non-white**
(2,508,040 px of 2913²; 28.76 % of the full 2953² raster).

Combined with **§10.2** (no sensor calibration or data entry at setup) and **§9.3**
(calibration happens in practice time and must survive quarantine):

> **No start sequence may depend on reading the surface beneath the robot at t = 0.**

---

## 4 · Sensing must be ratiometric, and there is no fallback

S4 §7.10 lists the variability every team must expect: field flaws · **mat colour brightness
varying table to table** · **lighting varying hour to hour** · judges' shadows · judges moving
around the field · texture and bumps under the mat · mat waviness · tables not level.

With §9.3 putting calibration in practice time and requiring it to survive quarantine, and
**cameras prohibited for Elementary (§5.2.7)**, colour discrimination must be
**ratiometric/relative, never an absolute threshold**. There is no camera fallback.

Every §7.10 item is a **parameter** in the eventual `sensors.py` / `dynamics.py` — never a
hard-coded constant. Field tests P1 and P4 measure them.

---

## 5 · Randomization can only be solved at runtime

**§9.6** places randomization *after* the robots are in quarantine. **§10.2** prohibits
entering data into a program by adjusting the position or orientation of robot parts, and
**§5.7** forbids team action after randomization.

⇒ The **4! = 24 note permutations** cannot be selected by a pre-run configuration. They must
be sensed during the run. This is the premise of every mission program.

---

## 6 · Failure modes that end the run

| Event | Result | Rule |
|---|---|---|
| **Losing a controller, motor or sensor** | **0 points and 120 s** | 10.4 |
| Losing any other part | free — it stays on the field, run continues | 10.4 |
| Robot completely leaves the game table | attempt ends | 10.7.3 |
| Team touches the robot or any mission object | attempt ends; DQ for the round | 10.7.2, 10.10 |
| Disqualification | worst possible score and 120 s | 10.11 |
| No positive-scoring (partial) task solved | time forced to 120 s | 10.12 |

**`part_detachment` is a design constraint, not a simulator detail.** §5.1's post-start size
freedom actively encourages deployable mechanisms, and §10.4 makes shedding a sensor
catastrophic. Any deployable mechanism must be captive.

---

## 7 · What is NOT yet designable

**The manipulator.** Gripper, lifter or any object-handling mechanism needs object dimensions,
mass and grip points — those come from **Phase 4, which has not run**. A gripper designed
before the note base width is known is a guess that gets rebuilt.

A final **chassis** is permitted (A6 is closed at international scope). A final
**manipulator** is not. That is precisely why the roadmap gates phase 7 on phase 4.
