# Ambiguity register

Seeded from `CLAUDE.md` §5.4. Every ambiguity here has a **conservative default** that code
may implement *today*, plus the condition under which that default gets replaced.

Rule: an ambiguity is never resolved by picking whichever reading is convenient. It is
resolved by a source (S1–S4) or it stays open with its default in force.

`last_reviewed: 2026-07-25`

| ID | Status | Ambiguity | Conservative default |
|---|---|---|---|
| A1 | OPEN | "moved" is defined as *no longer touching initial position* AND *no longer upright*, but the rulebook photos award 0 to a clef that fell over while still in place | implement as **OR**; expose flag `moved_semantics: "or" \| "and"` |
| A2 | OPEN | "upright" has no angular definition | `ASSUME:` tilt ≤ 15° from start pose; parameter `upright_tolerance_deg` |
| A3 | OPEN | Does the robot overlapping a target area at time-out break "completely in"? | `NEEDS-VERIFY(S4)`; default: robot is not "an area on the mat" |
| A4 | OPEN | Must the robot return to start to stop the clock? Where does time sit in tie-break? | `NEEDS-VERIFY(S4)`; default: score first, then time |
| A5 | OPEN | Do objects still held by the mechanism at time-out score? | `NEEDS-VERIFY(S4)`; default: **no** |
| A6 | OPEN | Max motors/sensors, start-size envelope, EV3+SPIKE mixing | `NEEDS-VERIFY(S4)`; **no final robot design before this is answered** |

---

## Detail

### A1 — "moved" semantics: AND vs OR

The written definition and the rulebook photography disagree. A clef that topples in place
satisfies *not upright* but not *no longer touching initial position*; the photos score it 0,
which only follows if the two conditions are **OR**-ed.

- **Default:** OR (the stricter reading — easier to lose points, so plans built on it do not
  over-promise).
- **Exposed as:** `moved_semantics: "or" | "and"` on the scorer.
- **Resolved by:** S1 re-read against the photo captions, or a WRO clarification/FAQ.
- **Consequence if wrong:** if the true semantics are AND, the OR default *understates*
  achievable score — safe direction. The reverse would overstate it.

### A2 — "upright" has no angular definition

- **Default:** `ASSUME:` tilt ≤ 15° from the start pose counts as upright.
- **Exposed as:** `upright_tolerance_deg` (default 15.0).
- **Resolved by:** S1 or S4 text, or an empirical test against a physical object at a venue.
- **Consequence if wrong:** a too-generous tolerance makes the simulator score runs the
  referee would not; a too-strict one hides viable strategies. Sensitivity must be reported
  as a sweep over this parameter, not a single number.

### A3 — robot overlapping a target area at time-out

`completely in` = object touches the target area **and no other area on the mat** (§5.6).
If the robot's own footprint counts as "an area", a robot parked over a scoring zone would
break its own delivery.

- **Default:** the robot is **not** "an area on the mat" — robot overlap does not break
  `completely in`.
- **Resolved by:** `NEEDS-VERIFY(S4)`.
- **Consequence if wrong:** every strategy that ends with the robot resting near a delivery
  zone loses those points. This changes end-of-run positioning, not mission ordering.

### A4 — clock stop and tie-break ordering

- **Default:** score first, then time. Robot need not return to start to stop the clock.
- **Resolved by:** `NEEDS-VERIFY(S4)`.
- **Consequence if wrong:** if a return-to-start is required, every route needs a return leg
  budgeted into the time model — a material change to route planning, not a tweak.

### A5 — objects still held by the mechanism at time-out

- **Default:** **no**, held objects do not score.
- **Resolved by:** `NEEDS-VERIFY(S4)`.
- **Consequence if wrong:** the default is the pessimistic one; being wrong means unclaimed
  upside, not an overstated plan.

### A6 — robot configuration limits

Max motors/sensors, start-size envelope, whether EV3 and SPIKE parts may be mixed.

- **Default:** none possible — this is a hard block.
- **Resolved by:** `NEEDS-VERIFY(S4)` only.
- **Consequence if wrong:** a robot built against guessed limits can be disqualified at
  inspection. **No final robot design before this is answered** (`docs/plans/ROADMAP.md`
  phase 7 is blocked on phase 5 for exactly this reason).
