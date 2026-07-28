# Run procedure — what happens on the day

`last_reviewed: 2026-07-27` · source: **S4**, verified byte-identical to
`wro-association.org` on 2026-07-27, VERSION JANUARY 15TH 2026.

The repo modelled *scoring* thoroughly and *procedure* not at all. Chapters 8–10 govern how a run
actually happens, and several of their rules constrain the robot as hard as chapter 5 does.

Every line below quotes S4 with its rule number. Nothing here is inferred.

---

## The cycle: practice → quarantine → round

This is the single most important structural fact, and it is what decides whether a strategy can
differ between rounds.

| § | rule |
|---|---|
| **9.1.1** | *"A number of practice times. Every tournament should start with a practice time to align for local circumstances (e.g. light conditions in the venue)."* |
| **9.3** | *"Teams work in designated team areas and are only allowed to modify the construction or code of their own robot **during practice times**. If teams want to make test runs, they need to queue with their robot (controller included) in hand. No laptops should be brought to the competition table."* |
| **9.5** | *"**Before practice time is over, the teams must place their robots in the quarantine area.** A robot that is not handed in on time cannot participate in the following round."* |
| **9.6** | *"Once the practice time is over, the judges check the robots. After that they prepare the competition tables for the next round (including possible **randomization of game objects**)."* |
| **9.7** | *"Before the robot is placed in quarantine, the robot must be ready to go. Only one further push on the start button is allowed to start a run. **Any wireless communication has to be turned off.**"* |
| **9.9** | *"In the case of a competition lasting several days, the organizers can define that the robots remain in the quarantine areas overnight. If charging at the robot parking is not possible, the battery may be removed and charged overnight."* |

**Consequences that bind design:**

- **Code changes are legal only during practice time** (§9.3). Whether round 2's program may
  differ from round 1's therefore reduces to *"is there a practice time between the rounds?"* —
  which S4 does not say, because §9.1.1 only requires a tournament to *start* with one. That is
  an open question, and it gates any adaptive round-2 strategy.
- **Randomization happens after quarantine** (§9.6), which is why the 24 note permutations can
  only be resolved by runtime sensing (`PHASE7_CONSTRAINTS` §5).
- **Wireless off before quarantine** (§9.7) — not merely during the run. This is where the
  requirement lives; there is no §5.9.
- **No laptops at the table** (§9.3). Anything the team needs at the table must be on paper or in
  the robot.

## The run itself

| § | rule |
|---|---|
| **10.1** | *"Each robot attempt is 2 minutes. Time begins when the judge gives the signal to start."* |
| **10.2** | *"The robot must be placed in the starting area so the projection of the robot on the game…"* — and it is **not allowed to enter data to a program by changing positions or orientation of robot parts.** |
| **10.3** | *"A start module / start frame can be used to adjust the starting position of the robot."* |
| **10.5** | *"**Only one press of the start button is allowed** to set the robot in motion. If further preparation is needed, this needs to be done before the quarantine."* |
| **10.6** | *"If there is any uncertainty during the robot attempt, the judge makes the final decision."* |

**There is no restart.** §10.5 gives one press; §9.7 gives one further push before quarantine.
A run that goes wrong runs to its end or is stopped — it is not re-attempted within the round.

## How an attempt ends — §10.7

| § | ending |
|---|---|
| **10.7.1** | the 2 minutes elapse |
| **10.7.2** | *"any team member touches the robot or any mission objects on the table during the run"* |
| **10.7.3** | *"the robot has completely left the game table"* |
| **10.7.4** | *"the robot or the team violated rules or regulations"* |
| **10.7.5** | *"a team member shouts **“STOP”** and the robot does not move anymore. If the robot is still moving, the robot attempt will only end once the robot stops by itself or is stopped by the team or judge."* |

**§10.7.5 is a usable tactic, not just a rule.** Calling STOP ends the attempt at the current
field state. Combined with §10.8 — *"Once the robot attempt has ended, time is stopped and the
judge scores the attempt"* — and with A5's resolution that held objects score the **partial**
tier, a deliberate STOP is the correct move when the robot is about to undo scored work. **The
abort decision belongs on the printed card the team takes to the table.**

## After the attempt

| § | rule |
|---|---|
| **10.8** | judge scores the end-of-attempt field state |
| **10.9** | *"If a team does not want to sign off after a certain period of time, the judge can decide to disqualify the team for this round."* Video or photo proofs are not accepted; the coach may not join the scoring discussion. |
| **10.10** | touching or changing task objects during the attempt ⇒ **disqualified for this round** |
| **10.11** | disqualification ⇒ *"the worst possible score (usually 0) and maximum time (120 seconds)"* |
| **10.12** | finishing without solving a (partial) task that yields positive points ⇒ **time set to 120 s** (see A8) |
| **10.13** | ranking depends on tournament format; ties broken by **time** |
| **10.14** | mulligan — optional, organizer-announced upfront (see A10) |

## Competition-day elements — chapter 8

The National Organizer chooses which apply. **This is a live strategic risk, not background.**

| § | element |
|---|---|
| **8.1** | **Season Challenge (obligatory).** *"The points for the technical summary (chapter 6) will be part of this."* |
| **8.2** | **Surprise Task / Surprise Rule.** *"A Surprise Rule is a small change to the existing Season Challenge that requires teams to solve it (e.g. **switching the colour of objects**). This enforces the teams to **re-program their robot**."* Presented **at the opening on the day**, solved throughout the day. *"Additional points might be awarded."* |
| **8.3** | **Extra Task** — like a Surprise Task but communicated **before** the competition so teams can prepare. |

> **A Surprise Rule can invalidate a hard-coded route on the morning of the event.** "Switching
> the colour of objects" is precisely the assumption the note-target mapping rests on. Combined
> with §9.3 — code changes only during practice — a surprise rule must be absorbed **inside
> practice time**, on the day, under time pressure.
>
> This raises the value of runtime sensing well beyond the 24 permutations: a program that
> *reads* the field survives a surprise rule; one that assumes the published mapping does not.
> Whether Thailand uses surprise elements is an open question.

## Technical summary — chapter 6, outside the 255

| § | rule |
|---|---|
| **6.1** | *"Teams should bring a filled technical summary of their robot (see **attachment B**) on paper. The summary **must reflect the actual robot**. In addition, teams can be asked to upload it shortly before the competition."* |
| **6.2** | *"The summary may not be longer than **two (2) DIN A4 page** or US LETTER."* |
| **6.3** | Points can be awarded for bringing the filled summary, **or** the summary can be mandatory. |

**Two pages, not one.** And **Attachment B is referenced twice in S4 but not included** in the
31-page document — as is Attachment D (chapter 8 examples). Where to obtain them is an open
question.

**It sits outside the 255-point model.** §8.1 says its points *"will be part of"* the Season
Challenge, but §6.3 leaves scored-vs-mandatory to the organizer, so the repo tracks it separately
and does not fold it into `scoring_model.json`.

---

## What S4 says that this repo had missed — §5.5 to §5.13

**RETRACTION.** The first issue of this document reported these rules as *absent document-wide*.
They are not: all nine exist on **page 9**, and the absence was an extraction defect in this
repo's own toolchain, not a gap in the rulebook. See **ADR-038**. Quoted here in full because
three of them bind design decisions that were being made without them.

| § | rule |
|---|---|
| **5.5** | *"Teams can bring **tools** to repair or modify their robot. The tools must be safe, must not pose a major risk of injury, have to fit on the table of the team and must be **battery operated**. Especially the following items are not permitted: 3D printer, saws, soldering irons, knives."* |
| **5.6** | *"A robot must be **autonomous** and finish the missions by itself. Any radio communication, remote control and wired control systems are not allowed while the robot is running. **No wireless communication is allowed between components within the robot.**"* |
| **5.7** | *"A team is not allowed to perform any actions or movements to **interfere or assist the robot after randomization** of the game objects."* |
| **5.8** | *"Any software to code the robot is allowed and teams can prepare the code before the competition day. If a team uses a software that requires an online connection (e.g. a browser-based tool), **the team should check if there is an offline version for the competition day.** The competition organizer is not responsible for providing an online infrastructure (e.g. WiFi for everyone). The online connection can only be used for coding."* |
| **5.9** | *"**Bluetooth, Wi-Fi or any remote connection must be switched off during check time and robot runs.** If there is any doubt about this, the team must be able to show that wireless transmission has been deactivated and how this is done. If the team cannot do this, **it is assumed that the wireless transmission has not been deactivated.** In case the feature cannot be turned off for technical reasons, it may remain activated, but it is strictly not allowed to use it. However, it is strongly recommended to **transfer code via cable**…"* |
| **5.10** | *"Use of hardware (like **SD cards or USB sticks**) to store programs is allowed. The hardware **must be inserted before the end of practice time and may not be removed until the next practice time starts.**"* |
| **5.11** | *"A team should prepare and bring all the equipment, enough spare parts, software and portable computers… **Teams are not allowed to share a laptop and / or the program** for a robot on the competition day."* |
| **5.12** | *"The robot and components can be **marked** (label, ribbons, mini-flags, etc.)."* |
| **5.13** | *"Teams can bring supportive materials such as **measuring tape** (to check the robot size) or **pens and paper** (to make notes). **Documentation about the robot and games and rules is allowed as well.**"* |

**§5.9 and §9.7 are two statements of the same requirement**, not a relocation — §5.9 carries the
burden-of-proof clause (*if you cannot demonstrate it, it is assumed not deactivated*), §9.7 pins
the deadline to quarantine. Both bind.

**What each one changes** is worked through in `PHASE7_CONSTRAINTS.md` §6c. In short: §5.8 makes
an offline coding path the **team's** responsibility, §5.10 puts a hard deadline on inserting
storage hardware, and §5.13 makes the printed abort card and randomization decision table
**explicitly legal** — which had been an open question.

---

## What S4 genuinely does not say

Now verified against the **repaired** extraction, in which 132 of 132 rule numbers round-trip.
Each was searched by content across all 31 pages, not by rule number:

| topic | status |
|---|---|
| how many rounds a tournament has | **absent** — §9.1.2 says only *"A number of robot rounds"*; organizer-set (confirmed for Thailand: 2) |
| whether a practice block sits **between** rounds | **absent** — §9.1.1 requires only that a tournament *start* with one. `QUESTIONS.md` #2 |
| what breaks a tie in **both** score and time | **absent** — §10.13 gives one tie-break and stops. `QUESTIONS.md` #10 |
| Attachment B and Attachment D | **referenced twice, not included** in the 31 pages |

**The difference between this table and the one it replaces:** these four are absences in a
document whose extraction has been verified complete. The previous table's entries were absences
in a file that had silently lost a page.
