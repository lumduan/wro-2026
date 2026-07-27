# The seven unasked questions

`last_reviewed: 2026-07-27`

Five for the **official Q&A** (S6) and two for the **Thai National Organizer** (NO-TH). None has
ever been sent. Together they are the only items on the critical path that cost minutes rather
than an afternoon, and two of them decide *what to optimise* rather than how precisely.

**Ordered by magnitude, descending** — so a partial reply is still useful, and so it is obvious
which to chase if one goes unanswered. Every magnitude is read out of a committed artefact, not
estimated.

| # | ask | to | magnitude | if never answered |
|---|---|---|---:|---|
| [1](#q1) | `completely_in`: contact patch or silhouette? (**A7**) | S6 | **24 pts** | silhouette |
| [2](#q2) | round count, aggregation, mulligan, practice | NO-TH | **12.5 pts + inverts strategy** | N = 1 |
| [3](#q3) | robot limits at national scope | NO-TH | **unbounded — all 255 + the entry** | international |
| [4](#q4) | start area: whole panel or white part only? (**A9**) | S6 | **chassis width** | whole panel |
| [5](#q5) | mulligan: replaces the round or the ranking? (**A10**) | S6 | **inverts retake rule** | ranking-global |
| [6](#q6) | "moved": AND or OR? (**A1**) | S6 | **conservative already** | OR |
| [7](#q7) | bonus-only run: elapsed or 120 s? (**A8**) | S6 | **tie-break only** | 120 s |

> **How to send.** S6 questions go to the Q&A form at
> `wro-association.org/competition/questions-answers/`. NO-TH questions go to the Thai National
> Organizer directly. Send **all five S6 questions together** — they are independent, and the
> Q&A answers in batches. Record the send date in `docs/DECISIONS.md`'s operator-state table,
> which currently reads *"not submitted"*.

---

<a id="q1"></a>
## 1 · A7 — does `completely_in` consume the contact patch or the silhouette?

**Quote.** S1 p9: *"completely in"* — the object touches the target area **and no other area on
the mat**.

**Why it is ambiguous.** "Area" is never defined, and the printed mat carries **580 distinct
fills**. Read literally, almost nothing is ever "completely in" anything, because every object
overlaps some printed feature. So the question is not *whether* to narrow the reading but
**which extent of the object the test applies to**.

**All plausible readings** — three, not two:

| reading | test | effect |
|---|---|---|
| **contact** | the object's footprint *where it touches the mat* must lie inside the target polygon | most permissive; a 32 × 32 mm note in an 80 × 80 mm target |
| **silhouette / projection** | the object's *full outline seen from above*, overhangs included, must lie inside | harshest; a note projects 32 × 64 mm |
| **enclosing volume** | any part of the object in any orientation | not seriously entertained, but nothing in the text excludes it |

**What changes with the answer.** `data/placement_sensitivity.json` computes both readings
already; `docs/PHASE7_CONSTRAINTS.md` §7b, `data/expected_score.json` and every downstream
artefact carry two columns because of this one sentence. An answer collapses them to one and
retires **AMBIGUITY(A7)**.

**Magnitude — the largest on this page.** On the contact reading a note tolerates **σ = 11.37 mm**
at 90 % success; on the silhouette reading **σ = 4.31 mm**. That is a **2.64× swing in required
placement accuracy**, on the missions carrying **120 of 255 points**. In expected score at
σ = 20 mm the full run is **216/255 (contact) against 192/255 (silhouette) — 24 points**.

**Fallback: silhouette**, the harsher reading. **Consequence if wrong:** the robot is built and
tuned to a 4.31 mm budget it never needed, spending design effort and probably run time on
precision that buys nothing. It loses no points; it wastes the wrong resource.

---

<a id="q2"></a>
## 2 · NO-TH (b) — round count, aggregation, mulligan, practice interleaving

**Quotes.** S4 §9.1.2 p12: *"A number of robot rounds. The robot rounds can consist of the Season
Challenge only or can use different elements as listed in chapter 8."* · S4 §10.13 p14: *"The
ranking of teams depends on the overall tournament format. **For example**, the best attempt out
of three rounds could be used and if competing teams have the same points, the ranking is decided
by the record of time."* · S4 §10.14 p14: *"Mulligan (optional element): The organizer of a
competition may allow that teams can retake a round right on the spot after the run… This concept
is optional and has to be announced by the organizer of an event upfront."* · S4 §9.3 p12:
*"Teams need to calibrate their robots during practice time, not directly before an attempt."*

**Why it is ambiguous.** It is not ambiguous — it is **undetermined by design**. §10.13 says the
ranking *depends on the format* and offers best-of-three only as an example. Four separate things
are open, and they are worth asking as one message.

**All plausible answers** — four independent axes, so the space is larger than "best of three or
not":

| axis | plausible answers | which the repo currently assumes |
|---|---|---|
| **how many scored rounds** | 1 · 2 · 3 · more | published against N, never for a chosen N |
| **aggregation** | best of N · **sum** of N · **last** round only · best of the final K | none — `round_strategy.json` models best-of-N and sum/last would need a different functional |
| **mulligan (§10.14)** | offered · not offered | not offered |
| **practice interleaved** | practice between every round · one practice block before all rounds · none | not interleaved |

The **sum** and **last-round** aggregations matter more than they look: under *sum*, variance is
a **liability** rather than an asset, which is the opposite of best-of-N — so this is not a
one-dimensional "how many rounds" question.

**What changes with the answer.** The **objective function**. `data/round_strategy.json` and
**ADR-027** exist because of this: at N = 1 the target is `E[score]`; at N > 1 it is
`E[max(X₁…X_N)]`, which **rewards variance**. That is not a scaling factor — it inverts advice.
Under best-of-three a higher-variance, more ambitious strategy beats a safer one of equal mean.
The mulligan answer separately activates the decision card in `round_strategy.json`.

**Magnitude.** At σ = 20 mm: `E[X] = 216.3`, `E[max₂] = 224.7`, `E[max₃] = 228.8` — **+12.5
points at N = 3**, and the premium *grows* with σ. Strategically it is larger than the number
suggests, because it changes which strategy to pick, not just what it scores.

**Fallback: N = 1, no mulligan, no interleaved practice.** **Consequence if wrong:** the team
optimises for the mean and builds the *safe* robot, then competes in a format that pays for
variance — leaving the premium unclaimed and, worse, having made design choices that suppress
the variance the format rewards. This is the one fallback that is wrong in a direction no later
measurement can correct.

---

<a id="q3"></a>
## 3 · NO-TH (a) — robot limits at national scope

**Quotes.** S4 §5.1 p6: *"maximum robot dimensions before the robot starts a run are
250mm x 250mm x 250mm"* · S4 §5.2.8 p7: *"Elementary: 4 motors"* · S4 §5.2.7: cameras prohibited
· S4 §4.3 and §5.2 permit National Organizers to vary these.

**Why it is ambiguous.** Every figure this repo uses is **international scope**. S4 explicitly
lets the National Organizer change them, and nobody has asked.

**All plausible answers**, per limit — ask each explicitly rather than "are the limits standard?",
because a blanket yes is easy to give and easy to be wrong about:

| limit | international | plausible national variants |
|---|---|---|
| **motors** | 4 (§5.2.8) | fewer (3, 2) · more · unchanged |
| **sensors** | not capped | a cap introduced · unchanged |
| **start envelope** | 250³ mm (§5.1) | smaller · a different shape constraint · unchanged |
| **cameras** | prohibited (§5.2.7) | unchanged (a relaxation is implausible but costs nothing to confirm) |
| **brand mixing** | permitted (§5.2) | EV3-only · SPIKE-only · unchanged |
| **anything local** | — | a restriction not in S4 at all — this is the one a specific question catches and a general one does not |

**What changes with the answer.** **ADR-022**'s motor budget — 2 drive + 0 yaw + 2 manipulator —
is exactly 4. `data/manipulator_requirements.json`, `docs/PHASE7_CONSTRAINTS.md` and the whole of
Phase 7 sit on it. A6 in the ambiguity register is *resolved at international scope only* and
says so.

**Magnitude — unbounded: the full 255, plus the entry.** Not a gradient, so it needs saying as a
number rather than as "structural". A robot that fails inspection **scores nothing and does not
compete**; every other question on this page moves the score by between 0.1 and 24. This is the
only one whose downside is the whole thing.

**The denominator here is 255, not 225.** 225 is the ceiling of what `sim/model.py` can currently
*route* — it excludes the two cables, whose start poses are `nominal_pending`. A disqualification
does not forfeit the model's coverage; it forfeits **the competition**, and the competition is
scored out of S1's 255.

Concretely: a national cap **below 4 motors invalidates ADR-022's budget outright** (2 drive +
2 manipulator is exactly 4), and a start envelope below 250 mm invalidates every dimension in
`PHASE7_CONSTRAINTS` §2. Probability unknown and probably low; **cost of asking, one email.**

It also cannot be de-risked by building conservatively. Staying well under every limit forfeits
capability that ADR-029 and ADR-031 price in real points — carry capacity alone is worth 30 at
the margin — so "build small to be safe" trades a known loss against an unknown one.

**Fallback: the international limits.** **Consequence if wrong:** a robot that fails inspection.
Not a lost mission — a lost competition. Note that this fallback cannot be de-risked by building
conservatively *and* cheaply: staying well under every limit costs capability that ADR-029 and
ADR-031 show is worth real points.

---

<a id="q4"></a>
## 4 · A9 — is the start area the whole bordered panel, or only its white part?

**Quote.** S4 §7.8 p10: *"start area of the robot is exclusively the white area within a coloured
border"*.

**Why it is ambiguous.** `MEASURED(S2)`: the panel is **250.02 × 250.02 mm** inside an 11.5 mm
`#24408f` border — but **29.56 % of that interior is not white.** It carries the WRO logo, a
yellow band, text and a QR code. So §7.8's description does not fit the mat it describes.

**All plausible readings** — again three:

| reading | usable footprint |
|---|---|
| **the whole bordered panel** | 250.02 × 250.02 mm |
| **only the literally white pixels** | a non-convex region, 70.44 % of the panel, unusable as a placement rect |
| **the panel minus the printed band only** | some intermediate rect, not defined anywhere |

**What changes with the answer.** `docs/PHASE7_CONSTRAINTS.md` §2 derives every chassis dimension
from the start footprint. S4 §5.1 caps the robot at 250 mm — so under the whole-panel reading the
constraint is exactly tight, and under any narrower reading **the start area is smaller than the
robot is allowed to be**, which cannot be intended and would move every dimension in Phase 7.

**Magnitude.** Not a score figure: it gates the *chassis*. The narrow reading makes the binding
constraint the mat rather than the rulebook, and no measurement can settle which applies.

**Fallback: the whole 250.02 mm panel.** **Consequence if wrong:** the robot is built to a
footprint the judge will not accept at the line, discovered on the day. Recoverable only by
rebuilding.

---

<a id="q5"></a>
## 5 · A10 — does a mulligan replace that round's score, or the ranking score?

**Quote.** S4 §10.14 p14: *"If a team decides to redo the run the new score will be used for the
ranking **no matter what**."*

**Why it is ambiguous.** Read against §10.13, where the ranking may be *"the best attempt out of
three rounds"*, the phrase *"used for the ranking no matter what"* does not say **what it
replaces**.

**All plausible readings** — three, and they give three different retake rules:

| reading | what the new score does | retake when ahead? |
|---|---|---|
| **round-local** | replaces that round only; earlier rounds still stand | often yes — the downside is capped by the other rounds |
| **ranking-global** | replaces your ranking score outright | almost never — you are betting your best result |
| **additive** | is *added* as a further attempt; the best of all still counts | **always** — a free extra draw with no downside at all |

The **additive** reading is not a stretch: "the new score will be used for the ranking" says the
score counts, not that anything is discarded. It is also the reading under which the phrase *"no
matter what"* does the least work, which argues against it — but not decisively, and the three
readings differ on every case that matters.

They agree only when the round being retaken is at or below your running best; there the retake
is free under either reading, which is why `sim/rounds.py` exposes that case separately.

**What changes with the answer.** The mulligan card in `data/round_strategy.json` — specifically
`mulligan_gamble_rule`, the threshold tabulated per σ. **AMBIGUITY(A10)** retires.

**Magnitude.** Conditional and bounded: it only bites if a mulligan is offered (question 2), and
only when the realised score exceeds the running best. Where it bites it **inverts** the decision
rather than shading it.

**Fallback: ranking-global**, the harsher reading — retake only when clearly behind.
**Consequence if wrong:** points left on the table rather than lost. The conservative direction.

---

<a id="q6"></a>
## 6 · A1 — is "moved" AND or OR?

**Quote.** S1 defines a moved object as *no longer touching its initial position* **and** *no
longer upright*.

**Why it is ambiguous.** S1 p13's own scoring photographs award **0** to a clef that fell over
while still standing in place. That object satisfies *not upright* but **not** *no longer
touching its initial position* — so under the literal AND it should still score, and the
rulebook's own illustration says it does not.

**All plausible readings** — three, because the photographs may be evidence of a different test
rather than of OR:

| reading | a toppled object still on its start marker is… | matches the photos? |
|---|---|---|
| **AND**, literally as written | **not** moved — it still scores | ✗ contradicts p13 |
| **OR** | moved — scores 0 | ✓ |
| **upright alone**, with "touching initial position" describing rather than testing | moved — scores 0 | ✓ equally |

OR and upright-alone agree on the photographed case and **diverge** on an object that has been
pushed off its marker while remaining upright: OR calls it moved, upright-alone does not. That
case is not illustrated anywhere, which is why asking is worth more than re-reading.

**What changes with the answer.** `sim/scoring.py`'s `moved_semantics` parameter, already exposed
as `"or" | "and"` rather than hard-coded, precisely so this can be flipped without a rewrite.

**Magnitude — small, and in the safe direction.** The current OR default is **stricter** than the
literal text: it treats more objects as moved, so it *understates* the score. The risk is
therefore unclaimed points, not lost ones, and no artefact would need rebuilding on an AND answer
beyond re-running the sweep.

**Fallback: OR**, matching the photographs. **Consequence if wrong:** the scorer is pessimistic —
strategy is chosen against a slightly harsher world than the real one.

---

<a id="q7"></a>
## 7 · A8 — bonus-only run: actual elapsed time, or forced 120 s?

**Quote.** S4 §10.12 p14: *"If a team finishes an attempt without having solved a (partial) task
(of the normal season challenge) that yields positive points, the time of that run will be set at
120 seconds."*

**Why it is ambiguous.** The 40 bonus points **are** positive and **are** on the season-challenge
scoring sheet — S6 2026-06-17 confirms a run that starts and immediately stops scores 40. But
passively *not damaging* an object is arguably not "solving a task".

**All plausible readings** — three:

| reading | does a bonus-only run get its time forced? |
|---|---|
| **bonus counts as a solved task** | no — actual elapsed time stands |
| **bonus is not a task at all** | yes — forced to 120 s |
| **bonus counts only if the robot did something** | forced only when the robot never left the start area; S6 2026-06-17 addresses exactly that case, so the distinction is one the Q&A has already shown it draws |

**What changes with the answer.** `data/scoring_model.json`'s `time.forced_120s` list, and
nothing else — the score is unaffected either way.

**Magnitude — the smallest here.** S4 §10.13 makes time a **pure tie-break**, below points. It
therefore separates only teams that already tie, and among bonus-floor runs specifically.
Included because it costs nothing to ask alongside the other four.

**Fallback: forced 120 s.** **Consequence if wrong:** a worse tie-break position than deserved,
in the narrow case of a tie between two runs that solved nothing.

---

## What none of these can settle

**Measurement does not resolve interpretation.** MEAS-4's calipers give `completely_in` more
precise numbers on *both* readings of A7 and cannot choose between them — the ambiguity is in a
sentence, not in a dimension. The reverse also holds: no Q&A answer produces `mass_g`, σ, or a
pick-and-place time. The two tracks are independent, which is why they run in parallel
(`docs/MEASUREMENT_PROTOCOL.md`, `docs/B1_PROCEDURE.md`).
