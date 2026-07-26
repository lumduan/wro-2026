# Ambiguity register

Seeded from `CLAUDE.md` §5.4. Every ambiguity here has a **conservative default** that code
may implement *today*, plus the condition under which that default gets replaced.

Rule: an ambiguity is never resolved by picking whichever reading is convenient. It is
resolved by a source (S1, S2, S4 or S6) or it stays open with its default in force.
**All remaining open items route to S6**, which answers questions that were *asked* —
so submitting them is an action, not a wait.

`last_reviewed: 2026-07-25` · S4 and S6 acquired; four of six ambiguities resolved.

| ID | Status | Ambiguity | Conservative default |
|---|---|---|---|
| A1 | **OPEN** — route: S6 | "moved" is defined as *no longer touching initial position* AND *no longer upright*, but the rulebook photos award 0 to a clef that fell over while still in place | implement as **OR**; expose flag `moved_semantics: "or" \| "and"` |
| A2 | **RESOLVED** S6 2026-06-30 | "upright" has no angular definition | `ASSUME:` tilt ≤ 15° from start pose; parameter `upright_tolerance_deg` |
| A3 | **RESOLVED BY IMPLICATION** S6 2026-06-30 | Does the robot overlapping a target area at time-out break "completely in"? | default **retained**: the robot is not "an area on the mat" |
| A4 | **RESOLVED** S4 10.7 / 10.13 | Must the robot return to start to stop the clock? Where does time sit in tie-break? | score first, then time; **no return-to-start requirement** |
| A5 | **RESOLVED** S6 2026-06-30 | Do objects still held by the mechanism at time-out score? | old default **no** was WRONG — they score at the **partial tier** |
| A6 | **RESOLVED** (international) S4 5.x | Max motors/sensors, start-size envelope, EV3+SPIKE mixing | S4 §5.1 250³ · §5.2.8 **4 motors** · §5.2.7 **cameras prohibited** · §5.2 brand mixing allowed. `NEEDS-VERIFY(NO-TH)` at national scope |
| A7 | **OPEN** — route: S6 | "completely in" says *no other area on the mat*, but "area" is undefined and the mat carries 580 distinct fills | Full containment in the target polygon. This is a **FORCED** reading, not a conservative choice — see below |
| A9 | **OPEN** — route: S6 | S4 §7.8 defines the start area as "the white area within a coloured border", but 29.56 % of this mat's start-area interior is **not white** (logo, band, text, QR). The *boundary* is measured; the *interpretation* is not. | the measured 250.02 × 250.02 mm placement rect |
| A8 | **OPEN** — route: S6 | Bonus-only run (40 pts, no mission solved): actual elapsed time, or forced 120 s under S4 §10.12? | forced 120 s |

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

### A2 — "upright" — **RESOLVED 2026-06-30 (S6)**

> *"A microphone that is not fully touching the floor should not be considered upright."*

The operative test is **contact**, not angle: the base must be fully in contact with the mat.
`upright_tolerance_deg` survives as a *parameter* but is demoted — the contact predicate is
what has official backing. Any result that depends on the angle is reported as a sweep
(AS-6), never as a single number.

### A3 — robot overlapping a target area at time-out

`completely in` = object touches the target area **and no other area on the mat** (§5.6).
If the robot's own footprint counts as "an area", a robot parked over a scoring zone would
break its own delivery.

**RESOLVED BY IMPLICATION 2026-06-30 (S6).** In the microphone answer the judge treats the
object as *"completely inside the microphone target area"* **while the robot's gripper is
still in contact with it**; the deduction was for uprightness alone. The robot's presence did
not break "completely in".

- **Default retained:** the robot is **not** "an area on the mat".
- **Evidence class:** an implication, not an explicit statement. Recorded as such so nobody
  later cites it as a direct ruling.
- **Consequence if wrong:** end-of-run positioning changes, not mission ordering.

### A4 — clock stop and tie-break — **RESOLVED (S4)**

- **§10.7** lists every way an attempt ends; **no return-to-start requirement appears.**
- **§10.13** ranks by score, ties broken by time. **§10.1** sets the attempt at 2 minutes.
- **§10.12** forces 120 s on a run with no positive-scoring (partial) task — see A8.
- **§10.4** forces 0 points *and* 120 s if the robot loses a controller, motor or sensor.
  Other shed parts are free and stay on the field.

Consequence for the objective function: `t ≤ 120 s` stands, but **time is a pure tie-break**,
so it ranks below `E[score]` and below `Var[score]`.

### A5 — objects held by the mechanism at time-out — **RESOLVED 2026-06-30 (S6)**

The old default was **wrong**, and wrong in the costly direction.

> A microphone completely inside the target area but held off the floor by the gripper
> *"is not upright, so the correct score is 10 points."*

| | old default | resolved |
|---|---|---|
| held object at time-out | scores **0** | scores at the **partial tier** |

Two consequences: the scorer must not zero held objects; and the abort policy **inverts** —
when the clock runs out mid-placement, **leave the object in the target area rather than
retreating with it.** Half credit beats nothing.

### A6 — robot configuration limits

Max motors/sensors, start-size envelope, whether EV3 and SPIKE parts may be mixed.

**RESOLVED at international scope (S4).** Quoted in `docs/citations.json`:

| item | value | rule |
|---|---|---|
| envelope before start | 250 × 250 × 250 mm, cables included; unrestricted after start | 5.1 |
| weight | ≤ 1.5 kg | 5.2.1 |
| battery | ≤ 6,000 mAh | 5.2.2 |
| voltage | ~~≤ 14 V~~ → **≤ 14.8 V nominal** | 5.2.3, superseded by S6 2026-05-14 |
| current | ~~≤ 4 A~~ → **limit removed** | 5.2.4, deleted by S6 2026-05-14 |
| **motors** | **4** (Junior 5, Senior 6); motors inside other components count | 5.2.8 |
| **cameras** | **prohibited** — Junior/Senior only | 5.2.7 |
| other sensors | no limit on type or number | 5.2.7 |
| controllers | no limit; **no wireless between components** | 5.2.5 |
| brand mixing (EV3 + SPIKE) | allowed at international level | 5.2 intro |

Motor-budget exemptions that change the arithmetic: pneumatics ≤ 3 bar with tanks ≤ 150 ml
count **only the compressor** (5.2.16) · uncontrolled pullback motors do not count, but the
robot must wind them itself (5.2.8) · hold-only electromagnets do not count (5.2.10).

**`NEEDS-VERIFY(NO-TH)`** — S4 §4.3 and §5.2 let National Organizers change these. A6 is
closed *internationally*, not locally; it stays open at national scope.


---

## A7 — "no other area on the mat" (added 2026-07-25)

S1 p9: *"Completely means that the game object is touching the corresponding area and no
other area on the mat."* **"Area on the mat" is undefined.** The mat carries 580 distinct
fills; `field_spec.json` will carry roughly a dozen polygons.

Every scoring target except `backstage` is drawn on top of a larger fill — `mic_target` sits
on `stage`, the six note targets and `start_area` sit on `plaza`. Read literally, an object
touching a note target also touches the plaza beneath it, so **nothing could ever score**.

- **Default:** the object's footprint must lie entirely inside the target polygon, and the
  "no other area" test ranges only over areas flagged `scoring: true`.
- **This is a FORCED reading, not a conservative choice.** Recording it as "conservative"
  would invite a later session to reconsider it as if a freer reading existed. None does.
- **Route:** `NEEDS-VERIFY(S6)`. See `docs/DECISIONS.md` ADR-013.
- **Consequence if wrong:** the containment margin changes.

**MEASURED(S3), 2026-07-26** — superseding the previous cross-source inference,
which is kept in `docs/object_map.toml` `[a7_inference]` for the record.

Eight models (the six notes, `mic`, `instrument_guitar`) share one base pattern, read off the
consecutive S3 pages 17 / 18 / 19:

```
step n     2x (2x4 brick)  ->  a 4x4 core          <- THIS touches the mat
step n+1   1x (4x8 plate)  ->  ON TOP of the core   <- overhangs at +9.6 mm
step n+2   2x (2x4 brick)  ->  stacked on the plate
```

| reading of "touching" | note extent | slack per side vs the 79.699 mm target |
|---|---|---|
| **contact patch** (4×4) | 32.0 × 32.0 mm | **23.85 mm** |
| **silhouette** (4×8 plate) | 32.0 × 64.0 mm | **7.85 mm** |

**A7's default holds under either reading** — both are positive, so nothing is blocked.
Which one the scorer uses is a scoring *interpretation* question, not an arithmetic one, and
`data/object_spec.json` records both as `contact_footprint_mm` and `max_projection_mm`.

**Cross-source check:** S2's note start square measures **31.9 mm** and the contact patch
derives to **32.0 mm** from the stud count — two independent sources agreeing to 0.1 mm. The
start square is sized to the note's *contact patch*, not its silhouette.

**A correction worth recording.** Part 1 inferred a 4×4 base from the mat and reported
23.85 mm. Mid-analysis I read the 4×8 plate as the base and "corrected" this to 7.85 mm. That
was the error — caught by following the build sequence through pages 17–19 before it was
committed. The inference was right; the plate is an overhang.

## A8 — bonus-only run timing (added 2026-07-25)

S4 §10.12 forces 120 s when a team finishes *"without having solved a (partial) task that
yields positive points"*. Bonus points **are** positive and are on the season-challenge
sheet, but passively not damaging an object is arguably not "solving a task".

- **Default:** time forced to 120 s.
- **Route:** `NEEDS-VERIFY(S6)` — submitted 2026-07-25.
- **Consequence if wrong:** affects tie-break among bonus-floor runs only. Low stakes, but it
  is the kind of thing that decides a placement.


## A9 — the §7.8 start-area interpretation (added 2026-07-25)

**The geometry is resolved. The interpretation is not.** Separating the two matters here.

`MEASURED(S2)`: the start area is the **250.02 × 250.02 mm** raster placement rect
`[2050.49, 446.49, 2300.51, 696.51]`, inside an 11.5 mm `#24408f` border. Evidence: the outer
20 px ring of that raster is 100.000 % one colour (`#fefefd`, 234,640 px, zero non-white); the
continuous all-white margin is 8.21–29.12 mm per side, so it is not a self-framing raster; and
S1's own labelled field diagram (p3) points its "Start Area" arrow directly at that panel.

**But S4 §7.8 says "the white area", and 29.56 % of that interior is not white** — it carries
the WRO logo, a yellow band, text and a QR code. Whether §7.8's description is meant to
describe this mat literally, or whether the whole bordered panel is the start area regardless
of what is printed on it, is unanswered.

- **Default:** the whole 250.02 × 250.02 mm panel is the start area. Any narrower reading would
  make the start area smaller than the §5.1 robot envelope, which cannot be intended.
- **Route:** `NEEDS-VERIFY(S6-startarea)` — submitted 2026-07-25 with A1 and A8.
- **Consequence if wrong:** the usable start footprint shrinks below 250 mm and every chassis
  width derived from `PHASE7_CONSTRAINTS.md` §2 moves with it.
- **Status:** operator action remains **blocking-advisory, not closed**, even though the
  boundary itself is measured.
