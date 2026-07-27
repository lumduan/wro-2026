# The unasked questions

`last_reviewed: 2026-07-27`

**Ten questions: six for the official Q&A (S6) and four for the Thai National Organizer (NO-TH).**
None has ever been sent. They remain the only items on the critical path that cost minutes rather
than an afternoon.

**Three changed since the last issue.** The tournament format is **confirmed** — 2 rounds, best
single round counts — so the old "how many rounds?" question is retired and replaced by the one
piece of it that survives and now matters more: *is there a practice time **between** the two
rounds?* The 250 mm start envelope is **answered** by S4 §5.1 and is no longer asked on its own;
it survives only as one row in question 3's national-variants table, as *"did you change it?"*
rather than *"what is it?"*. Three questions are **new**.

**Ordered by magnitude, descending.** Two questions (3 and 4) have an *unbounded worst case* but
low likelihood; they are placed by expected impact, with the worst case stated in the row rather
than hidden. Every other magnitude is read out of a committed artefact, not estimated.

| # | ask | to | magnitude | if never answered |
|---|---|---|---:|---|
| [1](#q1) | `completely_in`: contact patch or silhouette? (**A7**) | S6 | **24 pts** | silhouette |
| [2](#q2) | practice **between** the two rounds? mulligan? surprise elements? | NO-TH | **gates the adaptive round 2** | no practice between |
| [3](#q3) | robot limits at national scope | NO-TH | **unbounded — all 255 + the entry** | international |
| [4](#q4) | does Thailand change the **game** rules (S1)? | NO-TH | **unbounded — the mission set itself** | S1 as published |
| [5](#q5) | start area: whole panel or white part only? (**A9**) | S6 | **chassis width** | whole panel |
| [6](#q6) | mulligan: replaces the round or the ranking? (**A10**) | S6 | **inverts retake rule** | ranking-global |
| [7](#q7) | technical summary: scored? and where is Attachment B? | NO-TH + S6 | **unknown, non-zero, and dated** | assume scored, self-authored |
| [8](#q8) | "moved": AND or OR? (**A1**) | S6 | **conservative already** | OR |
| [9](#q9) | bonus-only run: elapsed or 120 s? (**A8**) | S6 | **tie-break only** | 120 s |
| [10](#q10) | what breaks a tie in **both** score and time? | S6 | **tie-break of a tie** | unknown — no default possible |

> **How to send.** S6 questions go to the Q&A form at
> `wro-association.org/competition/questions-answers/`. NO-TH questions go to the Thai National
> Organizer directly. **Send the NO-TH message first** — question 4 can invalidate the premise of
> several S6 questions, since an S6 answer about a mission Thailand does not run is wasted. Then
> send **all six S6 questions together**; they are independent and the Q&A answers in batches.
> Record the send date in `docs/DECISIONS.md`'s operator-state table, which currently reads
> *"not submitted"*.

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
## 2 · NO-TH (b) — is there a practice time **between** the two rounds?

**The round count is no longer being asked.** Confirmed by organizer reply, relayed 2026-07-27:
**2 rounds, best single round counts.** That is recorded in `data/round_strategy.json` and
**ADR-037**. What survives is the piece the old question buried, and it is now the whole question.

**Quotes.** S4 §9.3 p12: *"Teams… are only allowed to modify the construction or code of their own
robot **during practice times**."* · S4 §9.5 p12: *"**Before practice time is over, the teams must
place their robots in the quarantine area.**"* · S4 §9.6 p12: *"Once the practice time is over,
the judges check the robots. After that they prepare the competition tables **for the next
round**."* · S4 §9.1.1 p12: *"Every tournament should **start** with a practice time…"* · S4
§10.14 p14: *"Mulligan (optional element)… has to be announced by the organizer of an event
upfront."* · S4 §8.2 p11: a Surprise Rule *"enforces the teams to **re-program their robot**."*

**Why it is ambiguous.** S4 gives the **mechanism** but not the **schedule**. The cycle is
*practice → quarantine → round* (§9.3, §9.5, §9.6), and §9.3 makes code changes legal **only**
inside practice. So round 2's program may differ from round 1's **if and only if** a practice
block sits between them — and §9.1.1 only requires a tournament to *start* with one. The document
is silent on whether more follow.

**All plausible answers** — three axes, still worth asking as one message:

| axis | plausible answers | which the repo currently assumes |
|---|---|---|
| **practice between the rounds** | a full practice block between round 1 and round 2 · one practice block before both rounds · practice on a *different* table only · none | **none** — round 2 runs round 1's program |
| **mulligan (§10.14)** | offered · not offered | not offered |
| **surprise elements (ch. 8)** | Surprise Task · Surprise **Rule** · Extra Task announced in advance · none | none |

The surprise axis rides along because §8.2 and §9.3 interact badly: a Surprise Rule *"switching
the colour of objects"* must be absorbed **inside practice time, on the day**. If there is no
practice between rounds, a surprise rule announced at the opening has exactly one window to be
solved in.

**What changes with the answer.** Whether the **adaptive round-2 strategy** exists at all.
ADR-037 shows round 2 is a call option struck at the realised round-1 score `S₁`:
`E[max(X₁,X₂)] = E[X₁] + E[(X₂ − S₁)⁺]`. A **low** round 1 argues for the *safe* strategy, a
**high** one for the *aggressive* strategy. Executing that switch requires editing or
re-parameterising the program between rounds, which §9.3 permits only during practice.

**Magnitude — it gates the switch; the switch itself is not yet priced.** From
`data/round_strategy.json` at σ = 20 mm, contact reading, round 2 is worth **+21.8** points after a
p10 round and **+0.6** after a p90 round — a factor of **37** between the two. So the *correct*
strategy differs sharply by `S₁`, and the value of being able to act on that is bounded below by
nothing and above by the gap. **Pricing it needs two costed strategy distributions, which needs
B0** (CLAUDE.md §5.7 anti-pattern #3), so no single number is claimed here.

The survival curves in `round_strategy.json` are useful either way — they are the better primary
metric under best-of-2 regardless of the schedule. Only the **switch** is contingent.

**Fallback: no practice between the rounds, no mulligan, no surprise elements.**
**Consequence if wrong:** the team arrives with one program and one plan, and forfeits an
adaptation the format allowed — worst when round 1 goes badly, which is exactly when the option is
worth the most. The failure is silent: nothing at the table announces that a second practice block
existed and went unused.

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
| **start envelope** | 250³ mm (§5.1) | smaller · a different shape constraint · unchanged. **§5.1 settles this internationally**, so it is asked only as *did you change it?* — it is no longer a question in its own right |
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
## 4 · NO-TH (c) — does Thailand change the **game** rules (S1), not just the general ones?

**New question.** It exists because **ADR-036** recorded the operator's assertion that Thailand
follows the international rules — and that assertion was about the **General Rules (S4)**. Nothing
has been said about the **Game Rules (S1)**: the missions, the scoring sheet, the mat, the
randomization.

**Quotes.** S1 p2 warns that some markings on the mat may be **unused at local and national
events**. · S4 §8.4 p11 describes an Extra Day Challenge that relocates game objects on the same
mat. · S4 §8.3 p11: an Extra Task is *"communicated before the competition so teams can prepare."*

**Why it is ambiguous.** It is not ambiguous — it is **unasked**, and S1's own warning is direct
evidence that national events *do* deviate. This repo has four `unassigned_marker_{1..4}` IDs
precisely because four `#979797` squares on the mat have no established object semantics; S1 p2
and S4 §8.4 are the two candidate explanations, and both are national-scope mechanisms.

**All plausible answers** — the deviations are of different kinds and a blanket "we follow the
rules" would not distinguish them:

| kind of deviation | plausible answers | what it would hit |
|---|---|---|
| **mission set** | all missions run · some missions omitted at national level · an added national mission | `data/scoring_model.json` — the 255 itself |
| **the four unassigned markers** | unused, as S1 p2 anticipates · used for an Extra Day Challenge (§8.4) · used for something national | `unassigned_marker_{1..4}`, currently deliberately meaning-free |
| **scoring values** | as S1 publishes · re-weighted nationally | every EV number in the repo |
| **randomization** | the published 4! = 24 permutations · a fixed layout at national level · a different randomization | ADR-029's 24-permutation tour analysis, and the case for runtime sensing |
| **the mat itself** | the published printing file · a locally printed variant · a previous-season mat | all 50 479 measured paths, and `field_spec.json` |

**What changes with the answer.** Potentially `data/scoring_model.json`, which is the one
hand-authored file in `data/` and the transcription every derived artefact reads. A mission omitted
nationally does not merely lower the ceiling — it changes which missions are worth routing to, and
therefore ADR-029, ADR-030 and ADR-031.

**Magnitude — unbounded, like question 3, and for the same structural reason.** It is not a
gradient. If the national mission set differs, work built against the published set is not
degraded, it is **aimed at the wrong target**. Against that: the published S1 is the overwhelmingly
likely answer, which is why this sits at 4 and not at 1.

**Fallback: S1 exactly as published, all missions, 24 permutations, the printed mat.**
**Consequence if wrong:** a strategy optimised for missions that will not be run, discovered no
earlier than the opening briefing — and under §9.3 the only window to react is practice time.
Note this is the **same message** as questions 2 and 3, so it costs nothing extra to ask.

---

<a id="q5"></a>
## 5 · A9 — is the start area the whole bordered panel, or only its white part?

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

<a id="q6"></a>
## 6 · A10 — does a mulligan replace that round's score, or the ranking score?

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

<a id="q7"></a>
## 7 · The technical summary — is it scored, and where is Attachment B?

**New question.** S4 chapter 6 is cited in this repo and had no consumer until
`docs/HARDWARE_SESSION.md` **D1**. It is the only scored item that sits **outside** the 255.

**Quotes.** S4 §6.1 p9: *"Teams should bring a filled technical summary of their robot (see
**attachment B**) on paper. The summary **must reflect the actual robot**. In addition, teams can
be asked to upload it shortly before the competition."* · S4 §6.2 p9: *"The summary may not be
longer than **two (2) DIN A4 page** or US LETTER."* · S4 §6.3 p9: points **can** be awarded for
bringing it, **or** it can be mandatory. · S4 §8.1 p11: *"The points for the technical summary
(chapter 6) will be part of this."*

**Why it is ambiguous.** §6.3 and §8.1 are in tension: §8.1 states the points *"will be"* part of
the Season Challenge, while §6.3 leaves scored-versus-mandatory to the organizer. And
**Attachment B is referenced twice in S4 and is not in the 31-page document** — neither is
Attachment D. There is a form to fill in and no copy of it.

**All plausible answers** — two separable things, asked together:

| item | plausible answers |
|---|---|
| **is it scored?** | yes, with a stated point value · yes, but pass/fail · mandatory, unscored — missing it disqualifies · not used at national level |
| **where is Attachment B?** | a separate download on the WRO site · issued by the National Organizer · superseded, use any two-page format · genuinely omitted from the 2026 pack |
| **when is it due?** | on paper at the table only · uploaded before the event, on a stated date · both |

**What changes with the answer.** Nothing in `data/` — this is deliberately **not** folded into
`scoring_model.json`, because its value is unknown and it is not a mission. What changes is a
**deadline**: §6.1's *"must reflect the actual robot"* means it cannot be written before the robot
is final, and *"asked to upload it shortly before the competition"* means it cannot be left to the
morning. Those two together define a real date that nothing currently owns.

**Magnitude — unknown, non-zero, and the only one on this page that is a deadline rather than a
number.** §8.1 confirms the points exist; nothing states their size. If it is *mandatory* rather
than scored, the magnitude is the entry — the same failure mode as question 3, reached by
paperwork instead of by inspection.

**Fallback: assume it is scored, write it to a self-authored two-page format, and treat the upload
date as real.** **Consequence if wrong:** two pages of work spent for nothing — the cheapest wrong
answer on this page. The reverse error is not cheap, which is why the fallback leans this way.

---

<a id="q8"></a>
## 8 · A1 — is "moved" AND or OR?

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

<a id="q9"></a>
## 9 · A8 — bonus-only run: actual elapsed time, or forced 120 s?

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
Included because it costs nothing to ask alongside the other five.

**Fallback: forced 120 s.** **Consequence if wrong:** a worse tie-break position than deserved,
in the narrow case of a tie between two runs that solved nothing.
<a id="q10"></a>
## 10 · What breaks a tie in **both** score and time?

**New question**, and openly the smallest. It rides along with the other five S6 asks.

**Quote.** S4 §10.13 p14: *"The ranking of teams depends on the overall tournament format. For
example, the best attempt out of three rounds could be used and **if competing teams have the same
points, the ranking is decided by the record of time**."*

**Why it is ambiguous.** §10.13 gives exactly one tie-break and then stops. It does not say what
happens when two teams match on **both** points and time, nor at what resolution time is compared —
and with only 2 rounds and a 120 s cap, forced-120 s outcomes (§10.11, §10.12) make exact time
ties **structurally likely**, not merely possible. Two teams whose runs were both time-forced to
120 s and who both scored the 40-point bonus floor tie exactly, by construction.

**All plausible answers:**

| answer | consequence |
|---|---|
| **the other round's score** is compared next | a second good round has value even when it is not your best — which would partly contradict "best single round counts" |
| **the other round's time** | same, weaker |
| **finer time resolution** (tenths, hundredths) | no rule change; the tie simply resolves lower down |
| **a run-off** | announced by the organizer; nothing in S4 provides for it |
| **shared rank** | both teams take the higher rank, next rank skipped |
| **undefined — the judge decides** (§10.6) | *"If there is any uncertainty during the robot attempt, the judge makes the final decision"* — though §10.6 is about the attempt, not the ranking |

**What changes with the answer.** Possibly nothing in the repo — but if the answer is *the other
round's score*, then **ADR-037's objective is incomplete**: `E[max(X₁,X₂)]` discards the losing
round entirely, and a tie-break that reads it means the losing round is not worthless. That would
be a small, second-order correction to the objective function, and it is the only reason this
question is asked at all rather than dropped.

**Magnitude — a tie-break of a tie, and the smallest item on this page.** Included because it
costs one extra line in a message that is being sent anyway, and because of the ADR-037 hook above.

**Fallback: none is possible** — this is the one question with no usable default, because the repo
cannot model a rule it cannot guess. It is recorded as unmodelled rather than assumed.
**Consequence if wrong:** a rank decided by something the team never considered, in a case it
could not have prepared for either way.

---

## What none of these can settle

**Measurement does not resolve interpretation.** MEAS-4's calipers give `completely_in` more
precise numbers on *both* readings of A7 and cannot choose between them — the ambiguity is in a
sentence, not in a dimension. The reverse also holds: no Q&A answer produces `mass_g`, σ, or a
pick-and-place time. The two tracks are independent, which is why they run in parallel
(`docs/MEASUREMENT_PROTOCOL.md`, `docs/B1_PROCEDURE.md`).
