# Phase 7 constraint set — robot design

Everything the robot design must satisfy, recorded **before** anyone picks a chassis rather
than after. Every entry cites its rule; quotes are in `docs/citations.json`.

`last_reviewed: 2026-07-27`

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

### The motor budget — SETTLED by ADR-022 (2026-07-27)

4 motors. A differential drive consumes **2**, leaving **2 for 12 placement operations**
(cable ×2, mic, instruments ×3, notes ×6). Three exemptions change that arithmetic:

| Mechanism | Counts against the 4? | Rule |
|---|---|---|
| Pneumatics ≤ 3 bar, tanks ≤ 150 ml | **only the compressor** — one slot can drive many actuators | 5.2.16 |
| Pullback motor without electronic control | **no** — but the robot must wind it itself | 5.2.8 |
| Electromagnet used only to hold | **no** (counts if used as a linear motor) | 5.2.10 |
| Solenoid ≤ 20 N / ≤ 20 mm | **yes** | 5.2.10 |

The instruction this section carried — *"record whichever way this goes as an ADR with the
arithmetic shown"* — is discharged. The arithmetic is
`data/manipulator_requirements.json`; the decision is **ADR-022**:

```
2 slots   differential drive
0 slots   yaw          <- measured tolerance +/-31 deg; chassis heading suffices
2 slots   manipulator, both available
```

**Yaw was the open cost and it is zero.** A 32 mm object in a 79.7 mm square target fits at
every heading (its diagonal is 45.3 mm); only the cables constrain heading, and ±31° is well
inside what a differential drive holds. A dedicated yaw actuator would have consumed half the
manipulator budget for nothing.

§5.1's post-start size freedom makes deployable mechanisms legal, so both remaining slots are
genuinely available. **The mechanism itself — parallel gripper, fork, scoop or passive — stays
open**, gated on object mass and grip points, which no document contains.

---

## 2 · Start heading is coupled to footprint

S4 §7.8 requires the robot's **projection** to be completely within the start area, and the
start area measures **250.02 × 250.02 mm** — `MEASURED(S2)`, i.e. the §5.1 envelope plus
**0.02 mm total, 0.01 mm per side.** The constraint binds at every heading and the slack at
maximum legal size is, for practical purposes, **zero**.

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

## 7 · Placement tolerance — what the gripper actually has to hit

`MEASURED(S3)`, 2026-07-26. The six notes, `mic` and `instrument_guitar` share one base:

| | extent | slack per side in the 79.699 mm note target |
|---|---|---|
| contact patch (4×4 studs) | 32.0 × 32.0 mm | 23.85 mm |
| silhouette incl. the 4×8 plate at +9.6 mm | 32.0 × 64.0 mm | **7.85 mm** |

**Design against the 7.85 mm figure, not the 23.85 mm one.** Even if scoring only counts the
contact patch, a placement that leaves the silhouette hanging over the target edge looks wrong
to a judge and leaves no margin for the table tolerance (§7.2, ±5 mm) already accumulating
toward −X. The `clef` differs: a 4×6 contact patch with no overhang.

Combined with the start-area result in §2 — zero placement slack there — the robot must be
accurate to a few millimetres at both ends of every note run. That is a **gripper and odometry
requirement**, and field tests P2 and P3 are what will say whether it is met.

### The cable's orientation is forced, and the two cables differ

`MEASURED(S3) × MEASURED(S2)`, corrected 2026-07-27. The single hardest placement constraint on
the field, and it is not about tolerance — it is about whether the object fits at all.

> **Corrected.** The figures first published here on 2026-07-26 read `bbox_mm` as if it were the
> area. The two cable areas are **rotated**, so their bounding box is much larger than the area
> itself; the slack was overstated by 13.09 mm and the mirrored headings were missed entirely.
> Superseded values and root cause are in `docs/object_map.toml`
> `[cable_orientation.correction_2026_07_27]`.

| | value | source |
|---|---|---|
| cable length | **128.0 mm** (2 × Technic Brick 1×16, part 3703) | S3 p167 callout + p177 inventory |
| cable width | 16.0 mm | same |
| cable area rectangle | **79.700 × 207.201 mm** | `polygon_visible_mm`, S5 |
| `cable_area_upper` long axis | **80°** | same |
| `cable_area_lower` long axis | **100°** | same |

```
   cable_area_upper, tilted 80 deg          cable_area_lower, tilted 100 deg
        ╱‾‾‾‾‾‾‾‾‾‾╲                             ╱‾‾‾‾‾‾‾‾‾‾╲
       ╱  ║ cable ║ ╲                           ╱ ║ cable ║  ╲
      ╱   ║ 128mm ║  ╲   207.201 mm            ╱  ║ 128mm ║   ╲
     ╱    ║       ║   ╲  long axis            ╱   ║       ║    ╲
    ╲     ║       ║    ╱                     ╲    ║       ║     ╱
     ╲    ║       ║   ╱                       ╲   ║       ║    ╱
      ╲___╚═══════╝__╱                         ╲__╚═══════╝___╱
       ◄── 79.700 ──►                           ◄── 79.700 ──►
        short axis                               short axis
   object heading -10 deg                   object heading +10 deg
```

**The cable cannot lie across its area's short axis.** 128.0 mm into 79.700 mm is short by
**48.300 mm** — not a low probability, an impossibility. Worth **30 points** (15 per cable,
"completely in the grey area **and upright**", S1 §3.1).

| axis | extent | cable | slack |
|---|---|---|---|
| along the long axis | 207.201 mm | 128.0 mm | 39.600 mm per end |
| across the short axis | 79.700 mm | 16.0 mm | **31.850 mm per side** ← binding |

Consequences for the design, not just the strategy:

1. The manipulator must be able to **set the cable's yaw**. A gripper that cannot control
   rotation makes 30 points a coin flip.
2. **It must set it to two different values.** The areas tilt in *opposite* directions — 80° and
   100°, mirrored about the vertical. A robot that places both cables identically gets one
   wrong. This is the consequence that the bounding-box reading hid completely.
3. Both areas are the same size and sit at the mat's left edge, so one *mechanism* serves both —
   but not one *heading*.
4. Binding slack is 31.850 mm, generous next to the note target's 7.85 mm.

> **Corrected 2026-07-27.** Point 4 previously read *"Along-axis accuracy is not the problem
> here. **Rotation is.**"* That is backwards. Measured: σ for P ≥ 90 % is **13.90 mm** with
> rotation coupled against **17.68 mm** with translation alone, so rotation costs 21 % of the
> tolerance rather than being the binding term. And the cable's pure yaw tolerance is **±31°**
> — full at 31°, partial at 32°.
>
> The design consequence inverts with it. ±31° is loose enough to come from chassis heading, so
> **yaw needs no dedicated actuator and costs zero motor slots** (ADR-022). The earlier wording
> implied the opposite and would have spent half the manipulator budget on a mechanism the
> geometry does not ask for.

Asserted in `tests/test_object_spec.py` (`test_the_cable_cannot_lie_across_its_target_area`,
`test_the_two_cable_areas_need_mirrored_headings`) and in `tests/test_scoring.py`, all measured
from the polygon rather than the bounding box.

---

## 7b · Required placement accuracy — `data/placement_sensitivity.json`

`MEASURED(sim)`, 2026-07-27. Slack says whether a placement *can* succeed; this says how
accurately it must be made. σ is the standard deviation of placement error in x and y.

| placement | binding slack | σ for P ≥ 90 % | σ for P ≥ 99 % |
|---|---:|---:|---:|
| notes — **contact** reading | 23.85 mm | 11.2–11.4 mm | 7.8–7.9 mm |
| notes — **silhouette** reading | 7.85 mm | **4.3–4.4 mm** | **2.7–3.0 mm** |
| microphone — contact | 23.85 mm | 12.5 mm | 8.6 mm |
| microphone — silhouette | 15.80 mm | 8.5 mm | 5.4 mm |
| cable, correctly oriented | 31.85 mm | 14.1–14.5 mm | 9.3–9.8 mm |
| cable, across the area | −24.15 mm | **never** | **never** |
| instruments (backstage) | 82.45 mm | > 45 mm | ~32 mm |

4,000 samples per cell, seed 20260726, both A7 readings swept. Each row is
cross-checked against the closed-form slack computed in the target area's own frame.

**A7 is not academic — it costs a factor of 2.6 in required accuracy.** The register records
that A7 "holds under either reading, so nothing is blocked". True for *feasibility*, and
misleading for *design*: the notes carry 120 of 255 points, and resolving A7 to the silhouette
reading tightens their requirement from ~11 mm to ~4.4 mm. That is the difference between a
forgiving gripper and a precise one. **This raises the value of submitting A7 to the official
Q&A above every other open question.**

The instruments are the opposite case: backstage is so large that placement accuracy is
irrelevant to them. Any effort spent making instrument placement precise is wasted.

`ASSUME:` σ itself is not measured anywhere — field tests **P2** and **P3** measure it. What is
fixed here is the *requirement*, which does not depend on the robot.

---

## 7c · What the manipulator must handle — `data/manipulator_requirements.json`

`MEASURED(sim)`, 2026-07-27. Derived from the object footprints, the target geometry and the
accuracy sweep; nothing here is hand-assigned. Classes are clustered on grip span with a
one-stud separation, so a new object cannot land in the wrong one.

| class | objects | grip span | yaw tolerance | σ for P ≥ 90 % (contact / silhouette) | points |
|---|---|---:|---:|---:|---:|
| **A** | 6 notes, `mic`, `instrument_guitar` | 32 mm | free | 11.2 / 4.2 mm | **155** |
| **B** | `instrument_keyboard` | ≤ 56 mm* | free | > 45 mm | 15 |
| **C** | `instrument_congas` | ≤ 112 mm* | free | > 45 mm | 15 |
| **D** | `cable_upper`, `cable_lower` | 128 mm | **±31°** | 14.1 mm | 30 |

\* upper bound, not a measurement — the keyboard's base is an open frame and the congas' drum
separation is not derivable from an isometric render. Both bounds are safe in the conservative
direction.

**Eight of the twelve objects are the same 32 mm block.** That uniformity is the single most
useful fact for the mechanism: most of the game is one repeated operation.

### The capability ladder — what a grip span buys

| grip span | objects reachable | run total | left on the table |
|---:|---:|---:|---:|
| 32 mm | 8 | **195 / 255 (76 %)** | 60 |
| 56 mm | 9 | 210 / 255 (82 %) | 45 |
| 112 mm | 10 | 225 / 255 (88 %) | 30 |
| 128 mm | 12 | 255 / 255 (100 %) | 0 |

Run totals include the 40-point bonus floor: a robot that handles nothing still scores 40
(S6 2026-06-17), so every rung is an increment on 40, not on 0.

**This is a price list, not a recommendation.** Deciding to stop at 32 mm is a legitimate
choice that leaves 60 points; it becomes a strategy question in Phase 8, where the ×40
collision term also enters. What this table fixes is the *cost of each option*, which does not
depend on the strategy.

### Handling notes that are not obvious from the table

- **The congas is one rigid object**, not two drums: S3 page 104 bridges them with a 2×6
  Technic assembly. So there are 12 pick-ups for 12 objects. It has **two contact patches** on
  one body, like the cable.
- **The two cables need different headings** — 80° and 100°, mirrored. One mechanism serves
  both; one heading does not.
- **Yaw is free for 10 of 12 objects.** A 32 mm square in a 79.7 mm square target has a 45.3 mm
  diagonal, so it fits at any heading whatsoever.

---

## 8 · What is NOT yet designable

**Phase 4 has now run**, and the object set it produced is complete: all 16 objects mapped, with
contact footprints for every object on a scoring-containment path except the keyboard, which is
bounded at ≤ 56 × 56 mm rather than measured (`data/object_spec.json`, `footprint_pending`).

| Object | Contact footprint | Note |
|---|---|---|
| 6 notes, `mic`, `instrument_guitar` | 32.0 × 32.0 mm | 4×8 plate overhangs at +9.6 mm |
| `clef` | 32.0 × 48.0 mm | no overhang; scored for **not** being moved |
| `instrument_congas` | 32.0 × 32.0 mm **per drum**, ×2 | pair separation not measured — see below |
| `cable_upper` / `cable_lower` | 16.0 × 128.0 mm | rigid carrier only; the hose has no fixed patch (ADR-017) |
| `instrument_keyboard` | **≤ 56 × 56 mm (bound)** | open frame — the lattice self-check cannot apply |
| `amp`, `speaker_a`, `speaker_b` | not measured | scored for **not** being moved; off the containment path |

**What still blocks a final manipulator: mass and grip points.** Neither can come from a
building instruction. `mass_g` is `null` for all 16 objects and needs the objects on a scale.

**That is now an afternoon's work, not a purchase.** The sets are held — see ADR-025 and
`docs/HARDWARE_SESSION.md` items **A2** and **A3**, which close ADR-022's gated half. A final
**chassis** is permitted (A6 is closed at international scope). A final **manipulator** is not
yet, but the only thing between here and it is a scale, a pair of calipers, and writing down
what they say.
