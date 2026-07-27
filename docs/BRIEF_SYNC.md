# Brief sync — where the project instructions have drifted from the repo

`last_reviewed: 2026-07-27`

The project-level instructions this repo is worked from carry **factual claims that were true
once and are now wrong**. They are wrong in the most expensive direction: they describe the
sources as *less* usable than they are, which invites re-solving problems already solved.

This document is the diff. **Every "current fact" below is read out of a committed file**, cited
so the rewrite can be checked rather than trusted.

## How to use it

The **decays?** column is the point. A fact marked **decays** will go stale again — those should
be *deleted* from the instructions and replaced with a pointer at the repo. A fact marked
**stable** is safe to restate.

The durable parts of a brief — role, response protocol, decision framework, anti-patterns — are
not facts about the sources and do not appear here. Those are what should survive the rewrite.

---

## 1 · The five the brief names

| # | the brief says | current fact | source | decays? |
|---|---|---|---|---|
| 1 | S2 is a **1568 × 758 raster** | **VECTOR — 50,479 painted vector paths** on the single page. Decisively: *"no raster of the required size or aspect exists"* — the largest embedded raster is 2953 × 2953 px and square, while a full-mat raster would need 9300 × 4500 px at 100 dpi. The 4,448 raster placements are decorative. | `EXTRACTION_REPORT.md` §2 | **stable** — S2 will not change |
| 2 | S3 is a **403-byte stub** | Real: **15,358,983 bytes, 177 parseable pages** across 4 object streams — *"not the 403-byte stub seen previously."* Verdict **DEGRADED, not broken**: 179/179 rasters extract cleanly, but it is fully rasterized (zero vector paths, 52 characters of text in the whole document), so dimensions must be read visually or measured physically. | `EXTRACTION_REPORT.md` §1 | **stable** |
| 3 | mat scale **1.5064 mm/px** | **There is no pixel scale.** The mat is vector, so no px→mm conversion exists or is needed; the string `1.5064` appears nowhere in the repo. The mat is **measured at 2361.999 × 1143.000 mm** — 0.001 mm under nominal on width, exact on height. | `EXTRACTION_REPORT.md` §3, `data/field_spec.json` | **stable** |
| 4 | the ambiguity register **ends at A6** | **A1–A10.** Five resolved (A2–A6), five open (A1, A7, A8, A9, A10) — and all five open ones are drafted and ready to send in `docs/QUESTIONS.md`. | `docs/AMBIGUITIES.md` | **decays** — the register grows |
| 5 | **there is no S6** | S6 is **row 1** of the source table and **overrides everything below it** (S4 §4.4). It is the official Q&A, snapshotted at 2026-07-25 with content dated 2026-06-30. Its scope: *any question a lower source leaves ambiguous* — it reinterprets, it does not originate geometry or robot limits. | `CLAUDE.md` §5.1 | **stable** — but its *snapshot date* decays weekly |

---

## 2 · Drift the brief does not name

Found by scanning rather than by being told. These matter as much as the five above.

| # | likely stale claim | current fact | source | decays? |
|---|---|---|---|---|
| 6 | the project is **blocked on procurement** | **Nothing is blocked.** All hardware is held — EV3 45544, SPIKE Prime 45678 + 45681, WRO Brick Set 45811 + 45819, the printed mat, a competition-spec table. The repo recorded itself as blocked from Phase 4 until 2026-07-27 on an operator answer of *"partially / not sure yet"* that was never re-asked. | **ADR-025** | **decays** |
| 7 | bench work is **Block A, items A1–A5** | **Block MEAS, items MEAS-1…5.** Renamed 2026-07-27 because `A1`–`A5` collided with ambiguities A1–A5, two of which are *resolved* entries — so an unqualified "A5" read as settled fact in one document and an unstarted task in another. | **ADR-033** | **stable** once renamed |
| 8 | the maximum score is **255** | 255 **is** the maximum. But the model reaches **225** — the two cables are `nominal_pending`, so no route through them can be costed and every published expected score is against 225. Quoting /255 overstates by 30. | **ADR-030**, `sim/model.py` | **decays** — B0 closes it |
| 9 | *(counts, if the brief states any)* | 10 derived artefacts + 1 hand-authored · 19 areas · 16 objects mapped · 35 ADRs · 12 assumptions · 10 ambiguities · 522 tests | `data/`, `docs/` | **decays** — all of them |

---

## 3 · What the rewrite should keep, and what it should point at

**Delete from the instructions and point at the repo:**

| topic | point at |
|---|---|
| source status, extraction verdicts, what is usable | `docs/EXTRACTION_REPORT.md` |
| the source ranking and what each is authoritative for | `CLAUDE.md` §5.1 |
| every open question and its fallback | `docs/QUESTIONS.md` |
| the ambiguity register | `docs/AMBIGUITIES.md` |
| what is measured vs assumed | `docs/ASSUMPTIONS.md` |
| current state, phases, blockers | `docs/plans/ROADMAP.md` |
| what to do next, in what order, with time estimates | `docs/HARDWARE_SESSION.md` |
| any number at all | the artefact that derives it — every one carries a provenance sha |

**Keep in the instructions** — these do not decay because they are not facts about the sources:

- **Role and standing agreements** — including *"propose before starting"* and *"no derived
  artefact #12 while the Q&A is open"*, which are working agreements, not repo state.
- **Response protocol** — reporting style, tables over prose, the git-result table format.
- **Decision framework** — cite the rule number never the intermediate; no number without a
  source; a bound beats an invented value; record superseded values rather than deleting them.
- **Anti-patterns** — `CLAUDE.md` §5.7 is the repo-side list and is itself maintained; the brief
  should point at it rather than duplicate it.

**The general rule this document argues for:** a brief should carry *how to work*, and the repo
should carry *what is true*. Every fact duplicated across the two is a fact that will disagree
with itself eventually — and the disagreement is silent, because both copies look authoritative.

---

## 4 · How this was checked

Not by reading the brief and trusting it — by reading the repo:

```bash
grep -rn "1.5064\|mm/px" .            # nothing: the mat is vector, no pixel scale exists
grep -c "^| A[0-9]* |" docs/AMBIGUITIES.md    # 10, not 6
sed -n '/^## 5.1 Source ranking/,/^Rule:/p' CLAUDE.md   # S6 is row 1
```

Anything in §1 or §2 can be re-derived the same way. If a row here is wrong, the repo is the
arbiter — not this file.
