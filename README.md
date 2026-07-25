# WRO 2026 RoboMission Elementary — "Robot Rockstars"

Engineering repository for a WRO 2026 RoboMission Elementary team.

Read [`CLAUDE.md`](CLAUDE.md) first — it holds the source ranking, units and frames, tagging
conventions and anti-patterns that everything in this repo obeys.
Current state and dependencies: [`docs/plans/ROADMAP.md`](docs/plans/ROADMAP.md).

---

## Where things are

| Path | What |
|---|---|
| `docs/*.pdf` | S1–S3 source documents. **Read-only. Never modified.** |
| `docs/extracted/<pdf-stem>/` | Machine-readable extraction output. Generated — never hand-edit. |
| `docs/EXTRACTION_REPORT.md` | Human-readable verdict on extraction quality. |
| `docs/ASSUMPTIONS.md` | Every `ASSUME:` with its consequence-if-wrong. |
| `docs/AMBIGUITIES.md` | Ambiguity register A1–A6 with conservative defaults. |
| `docs/DECISIONS.md` | ADRs: context → options → decision → consequence. |
| `docs/plans/ROADMAP.md` | Phase dependency diagram and status. |
| `tools/pdf_extract.py` | The extraction CLI. |
| `data/` | `field_spec.json` (S5) lands here **later** — not yet. |

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

- No rule, number or dimension may be stated unless it traces to S1–S3.
- **S4 (RoboMission General Rules 2026) is missing.** Anything needing it is tagged
  `NEEDS-VERIFY(S4):` and left open. Prior-season WRO rules are not a substitute — the 2026
  general rules changed.
- Coordinates live in `data/field_spec.json`, nowhere else.
