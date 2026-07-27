# B1 procedure — one implementation or two?

`last_reviewed: 2026-07-27`

**B1 answers exactly one question**, and it is not about accuracy:

> Does `robot/robot_io.py` need **one** implementation or **two**?

`tools/check_portability.py` already proves the *linguistic* half — that one file parses inside
the MicroPython subset on both platforms. B1 is the half only hardware can test: whether the same
call means the same thing on an EV3 hub and a SPIKE hub.

Everything else you might want from a first robot — speed, accuracy, a gripper — is **not B1**.
Measuring those needs a design that ADR-022 cannot make until MEAS-2/3 land.

---

## Platforms in scope — both, necessarily

**B1 run on one hub cannot answer B1's question.** "One implementation or two" is a comparison;
a single platform produces no comparison. Both are in scope and both are held:

| platform | set | hub | drive motors | colour sensor | toolchain |
|---|---|---|---|---|---|
| **EV3** | 45544 Core Set | EV3 Brick | 2 × Large | 1 × Colour | Pybricks **v2.x** (EV3 MicroPython) |
| **SPIKE Prime** | 45678 + Expansion 45681 | SPIKE Prime Hub | 2 × Large | 1 × Colour | Pybricks **v3/v4** |

**Build two chassis, one per platform. Do not build one and rebuild it.**

- Both sets are held, so the parts exist for two simultaneous builds.
- Rebuilding costs 30–45 minutes and **confounds the comparison**: a difference between runs
  could then be the platform or the rebuild, and B1 exists precisely to attribute differences.
- With both alive you can re-run a single call side by side the moment a discrepancy appears —
  which is exactly when you need to, and exactly what a rebuilt chassis cannot do.

The two chassis need not match each other. B1 does not compare them; it compares what the *same
source file* does on each.

### ⚠ Dated prerequisite — archive the EV3 toolchain first

`NEEDS-VERIFY(ev3-download-window)` in `docs/FIELD_TEST_PLAN.md`: several third-party summaries
state the **EV3 app download ends 31 July 2026**. LEGO's own retired-products and EV3 software
pages carry **no such date**, so it is recorded as unconfirmed rather than repeated as fact —
but the asymmetry is stark. If it is true and the window is missed, the EV3 half of B1 becomes
impossible and `robot/robot_io_ev3.py` can never be verified.

**Archive both toolchains locally before doing anything else in this procedure.** It costs
minutes, it is useful either way, and it is the only item here with a deadline.

**A first pass ran on 2026-07-27** (`tools/archive_toolchains.sh`, logged in
[`TOOLCHAIN_ARCHIVE.md`](TOOLCHAIN_ARCHIVE.md)). It pinned the two GitHub toolchains and left
**five LEGO-hosted artifacts unobtained** — every one needs a manual download. Note that the
pinned `pybricks-micropython v4.0.1` targets SPIKE and newer hubs; **EV3 needs Pybricks v2.x**,
the separate *EV3 MicroPython* image, which is still on the manual list. **The EV3 side is not
yet archived.**

### What this procedure assumes you have

Stated rather than inherited, because ADR-025 exists precisely because an operator answer was
once hardened into a fact and never re-asked.

| platform | B1 needs | provided by | Expansion 45681? |
|---|---|---|---|
| **EV3** | hub + 2 motors + 1 colour sensor | **45544** Core Set | — |
| **SPIKE Prime** | hub + 2 motors + 1 colour sensor | **45678** base set | **not needed** |

B1 uses only `wait_for_start`, `drive_straight`, `turn`, `read_reflection`, `stop` — so the base
sets suffice and the Expansion is not required.

**Where the claim comes from:** your own statement, recorded in **ADR-025** and confirmed
**2026-07-27** in `docs/HARDWARE_SESSION.md`.

**Worth re-verifying physically before building.** LEGO Education direct sales of the SPIKE
portfolio **ended 30 June 2026** — already past. If either platform turns out not to be on the
shelf, that is no longer a purchase away, and B1 loses the comparison that is its entire purpose.
Open both boxes and count before cutting a single beam. That is also **MEAS-1**, so it costs
nothing extra.

---

## Minimum viable chassis

`robot/missions/trivial.py` exercises exactly four calls: `wait_for_start`, `drive_straight`,
`turn`, `read_reflection`, then `stop`. Build the least that runs them.

| Part | Count | Why |
|---|---:|---|
| Hub | 1 | — |
| Drive motor | **2** | differential drive; `drive_straight` and `turn` need no more |
| Colour / reflected-light sensor | **1** | `read_reflection` |
| Battery, wheels, castor or third contact | as needed | — |

**Per platform** — so twice over, once from each set.

**Build no manipulator.** ADR-022's mechanism decision is gated on MEAS-2/3 and anything built
before those numbers exist is discarded. `pick_up`, `place` and `carrying` are **out of scope for
B1** and stay unimplemented.

**Stay at 2 motors and 1 sensor.** A6 is resolved at *international* scope only — S4 §5.2.8 caps
Elementary at 4 motors, but §4.3 and §5.2 let the National Organizer vary it and nobody has asked
(`docs/QUESTIONS.md` §3). Two motors is inside any plausible national limit, so B1's result
survives whatever that answer turns out to be.

### What is throwaway, explicitly

| Throwaway | Why |
|---|---|
| wheelbase, wheel diameter, track width | all move once `PHASE7_CONSTRAINTS.md` §2 closes on the A9 start-area answer |
| sensor mounting height and angle | P1/P4 will re-decide it against real mat reflectance |
| chassis geometry generally | the 250 mm envelope is a *start* constraint (S4 §5.1); the final shape is a manipulator decision |
| the castor / third contact point | a placeholder until the drive geometry is chosen |

### What you keep — this is the deliverable

`robot/robot_io_ev3.py` and `robot/robot_io_spike.py`, filled in and with
`VERIFIED_ON_HARDWARE = True` set — **only** once the calls have actually run. Those two files
are the output of B1. The chassis is scaffolding.

---

## Procedure

Run the **same** `trivial.py` on both hubs. Do not edit it between runs — if it needs editing,
that is itself the answer to B1.

| Step | Action | Pass | Fail |
|---|---|---|---|
| **1** | Power on, load the backend, call `wait_for_start()` | robot does nothing until the start signal, then proceeds | proceeds immediately, or never proceeds |
| **2** | `drive_straight(500)` | robot drives **forward** and stops without further input | drives backward, does not stop, or requires a second call |
| **3** | `turn(90)` | robot rotates **counter-clockwise seen from above** | rotates clockwise → **the sign bug**, see below |
| **4** | `read_reflection()` | returns a number in **0–100** | returns a colour name, `None`, or raises |
| **5** | `stop()` | motors hold or coast, no error | raises, or motors continue |

**Judge only what the table says.** Whether the robot drove 500 mm or 480 mm is **recorded, not
graded** — B1 asks whether the *contract* holds, not whether the robot is accurate. Accuracy is
B5 (σ) and B6 (P6), and both need a design B1 deliberately does not have.

### The one criterion that is not about the contract

**`turn(90)` must rotate counter-clockwise viewed from above, on both hubs.**

Pybricks `turn()` is **clockwise-positive**; the MAT frame and this contract are
**counter-clockwise-positive** (`CLAUDE.md` §5.2). **Both backends must negate.** Get it wrong
and every future mission is mirrored — and it will look like a working robot right up until it
drives off the far side of the mat. Check it with your eyes, not with a heading reading, because
a sign error in `heading()` would hide a sign error in `turn()`.

---

## Log schema

Write `docs/b1_results.json` by hand — one object per hub, both in the same file so the
comparison is a diff rather than a memory:

```json
{
  "schema_version": 1,
  "date": "2026-08-02",
  "chassis": {
    "drive_motors": 2, "sensors": 1,
    "wheel_diameter_mm": 56, "wheelbase_mm": 120,
    "note": "throwaway - see B1_PROCEDURE.md"
  },
  "hubs": [
    {
      "platform": "ev3",
      "firmware": "pybricks 2.x",
      "calls": {
        "wait_for_start": {"pass": true,  "note": ""},
        "drive_straight": {"pass": true,  "commanded_mm": 500, "measured_mm": 487, "note": ""},
        "turn":           {"pass": true,  "commanded_deg": 90, "measured_deg": 88,
                           "direction_ccw_from_above": true, "negated_in_backend": true},
        "read_reflection":{"pass": true,  "value": 42, "note": "white mat area"},
        "stop":           {"pass": true,  "note": ""}
      },
      "semantic_differences": []
    }
  ],
  "verdict": {
    "implementations_needed": 1,
    "reason": ""
  }
}
```

`semantic_differences` is the field that decides the verdict. Record anything where the **meaning**
of a call differed — not where the API spelling differed.

---

## The decision rule

**Two implementations are needed only if a call requires different *semantics*, not merely a
different API name.**

| Observation | Verdict |
|---|---|
| EV3 uses `Motor(Port.A)`, SPIKE uses `Motor(Port.A)` with different import paths | **one** — spelling, already absorbed by the two backend files |
| Both need `turn()` negated by the same rule | **one** — a shared convention, not a divergence |
| `read_reflection()` returns 0–100 on one hub and 0–1023 on the other | **one**, if a scale factor in the backend fixes it |
| One hub cannot express a call at all without changing `trivial.py` | **two** — the contract does not hold |
| A call needs a *different sequence* of mission-level steps on one platform | **two** |

Record the verdict in `docs/b1_results.json` and write it up as an ADR — **ADR-023 claims the
contract works and B1 is the evidence.** If the answer is *two*, that is not a failure; it is the
finding the test exists to produce, and it is far cheaper to have now than after twelve mission
programs exist.

→ closes: the hardware half of **ADR-023**. Unblocks the twelve mission programs, which are
deliberately unwritten until this returns.
