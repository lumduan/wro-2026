# WRO 2026 RoboMission Elementary — "Robot Rockstars"

Engineering repository for a WRO 2026 RoboMission Elementary team.

Read [`CLAUDE.md`](CLAUDE.md) first — it holds the source ranking, units and frames, tagging
conventions and anti-patterns that everything in this repo obeys.
Current state and dependencies: [`docs/plans/ROADMAP.md`](docs/plans/ROADMAP.md).

**Where the project is.** Every phase that can be done from documents is done, and nothing is
blocked. The scoring rules, field geometry, game-object dimensions, a scorer, the placement
accuracy each mission demands and the expected score as a function of that accuracy are all
derived and tested. What remains is measurement on real hardware, ordered by leverage in
[`docs/HARDWARE_SESSION.md`](docs/HARDWARE_SESSION.md).

**Ten questions outrank the measurements**, and they are questions rather than tasks: six routed
to the official Q&A and four never asked of the National Organizer. They cost minutes. All ten
are drafted, ordered by magnitude, with fallbacks, in
**[`docs/QUESTIONS.md`](docs/QUESTIONS.md)**.

**The tournament format is confirmed — 2 rounds, best single round counts** (ADR-037), so the
objective is `E[max(X₁,X₂)]` rather than `E[score]`. That **narrows** the earlier "extra rounds
reward variance" finding: only *independent* variance re-rolls between rounds, and at correlation
ρ = 0.9 the premium collapses from +8.5 points to +2.7. Systematic error is pure cost. `P(score >
t)` is now the primary metric, because round 2 is an option struck at the round-1 score and a
mean collapses the tail it trades on.

---

## Getting the source documents

**The WRO source PDFs are not in this repository.** They are © 2026 World Robot Olympiad
Association Ltd; this repo publishes the toolchain and our own analysis, not WRO's
documents. Download them from the WRO website and drop them in `docs/`:

| Expected filename | Role | sha256 (the copy this analysis was built from) |
|---|---|---|
| `WRO-2026-RoboMission-Elementary-Game-Rules.pdf` | S1 — missions, scoring, randomization (**Version: January 15th 2026**) | `3ec1bb2b16c298676f180da0b664963a4ab4e36a85408ab4b54fb4c8b187877f` |
| `WRO-2026-GameMat-Elementary-Printing-File.pdf` | S2 — all field geometry | `8d58381fdcd9bc1784ae893e5b133707ca81f19aff51e31ca41c02276466c4d9` |
| `WRO-2026-RM-Elementary-BI-All.pdf` | S3 — game-object dimensions | `ab7fa33bcae102d800bcc390e1155125c07c1fdcdf06d55df1e8ea38d166bd7a` |
| `WRO-2026-RoboMission-General-Rules.pdf` | S4 — robot limits, run procedure, table setup | `90a28d8bf77f628227e5f544ec57b5230d620f3ae581f092bed1fda23de9e795` |

**S4 re-verified against source, 2026-07-27.** Fetched from
`https://wro-association.org/wp-content/uploads/WRO-2026-RoboMission-General-Rules.pdf` and
compared byte-for-byte with the committed copy: **identical** — 3 967 741 bytes, sha256 as above.
The document's own version string is **"VERSION: JANUARY 15TH 2026"**, which is later than the
`UPDATED-2025-12-16` revision also in circulation, so this is the current one. **S1 carries the
same version date** — *"Official Game Rules for the WRO International Final. Version: January 15th
2026"* — so the two documents are a matched pair, not one newer than the other. 31 pages;
**Attachment B and Attachment D are referenced but not included** (ADR-036).

> **Extraction defect, found and fixed 2026-07-28 (ADR-038).** Page 9 of S4 lost 75 % of its text
> to a spurious table detection, taking §5.5–§5.13 with it — and the absence was written up as a
> finding. The extractor now discards any table that does not reproduce the prose it displaces,
> and a test compares every page's markdown against its spans so a future loss fails CI rather
> than becoming a conclusion. **132 of 132 rule numbers round-trip.**

**Two ceilings, and they are different quantities.** **255** is the rule maximum — what S1's
scoring sheet awards, printed as *"Maximum Score 255"* on S1 p14. It never changes. **225** is the
top of `sim/model.py`'s coverage envelope: the 40-point bonus floor plus the 185 placement points
it can currently *route*, with the two cables still `nominal_pending` (work order B0 closes it).
A score or a rule total is always out of **255**; only a statement about the model's present reach
is out of 225. Neither number corrects the other.

**S6** is the official Q&A at `wro-association.org/competition/questions-answers/`. It sits
**above** S1 and S4 in the precedence hierarchy (S4 §4.4) and is live and unversioned, so it
is snapshotted rather than linked:

```bash
curl -sS -A "Mozilla/5.0" -o docs/s6-qa-snapshot-$(date +%F).html \
     https://wro-association.org/competition/questions-answers/
uv run python tools/s6_index.py docs/s6-qa-snapshot-$(date +%F).html --check
```

`docs/s6_index.json` (committed) holds the per-answer `(section, question, author, timestamp)`
tuples. **Diff on those, never on the page's HTTP `Last-Modified` header** — that is a
render/cache timestamp on this site and moves on theme edits independently of content.
`--check` exits 1 on any delta and marks with `**` the answers in sections that bind this
project: only 4 of the 9 do.

`pdf_extract.py` records the sha256 of whatever it actually read into `manifest.json`, so a
different revision of a source document is detectable rather than silently mixed in. Then:

```bash
uv sync
uv run python tools/pdf_extract.py all docs/*.pdf
```

Extraction is deterministic — same input hash + same params ⇒ byte-identical output — so
regenerating reproduces exactly what `docs/EXTRACTION_REPORT.md` describes.

Text extractions (`docs/extracted/*/text/`) are gitignored for the same copyright reason:
they reproduce the rulebook verbatim. Everything else — the structural probe, the vector
fill inventory, the report and the decision records — is committed.

## Where things are

| Path | What |
|---|---|
| `docs/*.pdf` | S1–S4 source documents. **Not committed** (see above). Read-only. Never modified. |
| `docs/extracted/<pdf-stem>/` | Machine-readable extraction output. Generated — never hand-edit. |
| `docs/extracted/*/probe.json` | Structural report: boxes in pt+mm, rotation, colourspaces, fonts, op counts. |
| `docs/extracted/*/vector/fills_by_colour.json` | Raw fill-colour inventory from the mat, in mm. |
| `docs/EXTRACTION_REPORT.md` | Human-readable verdict on extraction quality. |
| `docs/ASSUMPTIONS.md` | Every `ASSUME:` with its consequence-if-wrong. |
| `docs/AMBIGUITIES.md` | Ambiguity register A1–A10; five resolved by S4/S6, the rest routed to the official Q&A. |
| `docs/citations.json` | Every cited rule, quoted and page-referenced. |
| `docs/s6_index.json` | Q&A answer timestamps — the change-detection diff target. |
| `docs/DECISIONS.md` | ADRs: context → options → decision → consequence. |
| `docs/plans/ROADMAP.md` | Phase dependency diagram and status. |
| `docs/HARDWARE_SESSION.md` | **The current work order** — every measurement, ordered by what it unblocks. |
| `docs/QUESTIONS.md` | **The ten unasked questions** — six for the official Q&A, four for the National Organizer — ordered by magnitude, each with a fallback and its consequence-if-wrong. |
| `docs/MEASUREMENT_PROTOCOL.md` | How to run MEAS-1…5: resolutions, repeat counts with the arithmetic, the destination field for every number, proxies decided in advance. |
| `docs/B1_PROCEDURE.md` | Minimum viable chassis for B1, throwaway parts named, pass/fail without interpretation, and the one-or-two-implementations decision rule. |
| `docs/BRIEF_SYNC.md` | Where the project-level instructions have drifted from the repo — every stale fact, its current value, its source, and whether it will decay again. |
| `docs/RUN_PROCEDURE.md` | What happens on the day — S4 chapters 8–10, quoted with rule numbers: the practice→quarantine→round cycle, how an attempt ends, and the surprise elements. |
| `docs/PHASE7_CONSTRAINTS.md` | Robot-design constraints, recorded before a chassis is chosen. |
| `docs/FIELD_TEST_PLAN.md` | Step 0–1 and P1–P7, each naming the `ASSUME:` it replaces. |
| `docs/area_map.toml` | Hand-written input to S5: canonical ID → drawn path, with citations. |
| `docs/object_map.toml`, `object_parts.toml` | Hand-written inputs to the object spec: S3 page ranges → object IDs, and part identification. |
| `sim/` | `geometry` · `world` · `scoring` (the scorer) · `sensitivity` · `rounds` (the score distribution) · `travel` (tours) · `frontier` (what fits in 120 s) · `model` (the end-to-end score) · `robot_io_sim`. |
| `robot/` | `robot_io.py` — the one contract mission code imports — plus the EV3 and SPIKE backends and `missions/`. Must run on **MicroPython**; `tools/check_portability.py` enforces that. |
| `tools/pdf_extract.py` | The extraction CLI. |
| `tools/build_all.py` | Runs the derived-artefact pipeline in dependency order. |

### `data/` — ten derived files and one that is not

**Never hand-edit a derived file.** Edit its input and re-run `tools/build_all.py`.

| File | What it carries | Built by |
|---|---|---|
| `field_spec.json` | **S5** — mat geometry, areas, start poses | `build_field_spec.py` |
| `object_spec.json` | Game-object footprints, BOMs, the parts inventory | `build_object_spec.py` |
| `placement_sensitivity.json` | `P(success)` per mission across a placement-error σ | `run_sensitivity.py` |
| `manipulator_requirements.json` | Grip span, yaw tolerance, handling classes, the motor budget | `build_manipulator_requirements.py` |
| `strategy_frame.json` | Travel cost and bonus-points-at-risk per mission | `build_strategy_frame.py` |
| `expected_score.json` | E[score] as a function of σ and P(collision) — the **N = 1** case | `build_expected_score.py` |
| `round_strategy.json` | The run-score *distribution*, `E[max of N rounds]`, survival curves, the correlation-split premium and the conditional round-2 option at the **confirmed N = 2** (ADR-027, ADR-037) | `build_round_strategy.py` |
| `travel_budget.json` | Tour length per carry capacity — the six notes over all 24 randomization permutations (ADR-029), and the full ten-mission run over 384 joint start states with the pick-and-place cliff (ADR-030) | `build_travel_budget.py` |
| `feasibility_frontier.json` | Which missions fit in 120 s at a given driving speed and pick-and-place time, and what they score (ADR-031) | `build_feasibility_frontier.py` |
| `parameter_sensitivity.json` | The end-to-end score, and every unmeasured parameter ranked by how far it moves it — the measurement order (ADR-032) | `build_parameter_sensitivity.py` |
| `scoring_model.json` | Missions, predicates, time rules, randomization | **hand-authored** — a transcription of S1/S4/S6, not a derivation |

## The build chain

```bash
uv run python tools/build_all.py            # rebuild only what is stale
uv run python tools/build_all.py --check    # report staleness, exit 1, write nothing
uv run python tools/build_all.py --force    # rebuild everything
```

Freshness is defined by the artefacts themselves: each records the sha256 of every input it
read, and is stale when one of those no longer matches. That makes a no-op run take about a
second rather than the two and a half minutes the Monte Carlo sweep needs — and it turns a
mis-ordered build from a silent wrong answer into a named one.

## Setup

```bash
uv sync
uv run pytest
```

## Extraction CLI

```bash
# structural report on all three sources
uv run python tools/pdf_extract.py probe docs/*.pdf

# everything: probe + text + images + render + vector
uv run python tools/pdf_extract.py all docs/WRO-2026-GameMat-Elementary-Printing-File.pdf

# a single region of the mat at high resolution, in MAT-frame mm
uv run python tools/pdf_extract.py render docs/WRO-2026-GameMat-Elementary-Printing-File.pdf \
    --bbox 0,0,600,400 --px-per-mm 12 --colorspace cmyk
```

Output lands in `docs/extracted/<pdf-stem>/`. `manifest.json` records the input sha256, the
per-command parameters and a sha256 for every emitted file: same input + same params ⇒
byte-identical `text/` and `vector/` JSON.

## Coordinate frame

MAT frame: **origin bottom-left of the mat, `+X` right, `+Y` up, millimetres.**
PDF user space is points with a bottom-left origin; PyMuPDF's page space is points with a
**top-left** origin and `+Y` down. One function in `tools/pdf_extract.py` (`MatFrame`) owns
that conversion and every command calls it — there is deliberately no second copy.

## Ground rules

- No rule, number or dimension may be stated unless it traces to S1, S2, S4 or S6.
- **S6 (official Q&A) outranks everything** and has already overwritten two S4 clauses.
  Re-read it before any scoring or robot-limit claim. Prior-season WRO rules are never a
  substitute — the 2026 general rules changed.
- **Cite the rule number, never an intermediate document.** Every rule this repo relies on is
  quoted and page-referenced in `docs/citations.json`, capped at 15 words per quote and one
  entry per rule (enforced by `tests/test_citations.py`).
- Coordinates live in `data/field_spec.json`, nowhere else — and they are **derived**, so edit `docs/area_map.toml` and re-run the builder rather than the JSON.

## Licence

[MIT](LICENSE) — © 2026 Sarat Sonsuk. Scope details in [NOTICE](NOTICE).

The licence covers **this repository's** contents: the toolchain, its tests and the analysis
documents. It does not cover and cannot grant rights in WRO's source PDFs, which are
© 2026 World Robot Olympiad Association Ltd and are deliberately not distributed here.

"World Robot Olympiad" and the WRO logo are trademarks of the World Robot Olympiad
Association Ltd. This project is not affiliated with or endorsed by WRO.
