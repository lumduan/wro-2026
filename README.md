# WRO 2026 RoboMission Elementary — "Robot Rockstars"

Engineering repository for a WRO 2026 RoboMission Elementary team.

Read [`CLAUDE.md`](CLAUDE.md) first — it holds the source ranking, units and frames, tagging
conventions and anti-patterns that everything in this repo obeys.
Current state and dependencies: [`docs/plans/ROADMAP.md`](docs/plans/ROADMAP.md).

---

## Getting the source documents

**The WRO source PDFs are not in this repository.** They are © 2026 World Robot Olympiad
Association Ltd; this repo publishes the toolchain and our own analysis, not WRO's
documents. Download them from the WRO website and drop them in `docs/`:

| Expected filename | Role | sha256 (the copy this analysis was built from) |
|---|---|---|
| `WRO-2026-RoboMission-Elementary-Game-Rules.pdf` | S1 — missions, scoring, randomization | `3ec1bb2b16c298676f180da0b664963a4ab4e36a85408ab4b54fb4c8b187877f` |
| `WRO-2026-GameMat-Elementary-Printing-File.pdf` | S2 — all field geometry | `8d58381fdcd9bc1784ae893e5b133707ca81f19aff51e31ca41c02276466c4d9` |
| `WRO-2026-RM-Elementary-BI-All.pdf` | S3 — game-object dimensions | `ab7fa33bcae102d800bcc390e1155125c07c1fdcdf06d55df1e8ea38d166bd7a` |

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
| `docs/*.pdf` | S1–S3 source documents. **Not committed** (see above). Read-only. Never modified. |
| `docs/extracted/<pdf-stem>/` | Machine-readable extraction output. Generated — never hand-edit. |
| `docs/extracted/*/probe.json` | Structural report: boxes in pt+mm, rotation, colourspaces, fonts, op counts. |
| `docs/extracted/*/vector/fills_by_colour.json` | Raw fill-colour inventory from the mat, in mm. |
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

## Licence

[MIT](LICENSE) — © 2026 Sarat Sonsuk. Scope details in [NOTICE](NOTICE).

The licence covers **this repository's** contents: the toolchain, its tests and the analysis
documents. It does not cover and cannot grant rights in WRO's source PDFs, which are
© 2026 World Robot Olympiad Association Ltd and are deliberately not distributed here.

"World Robot Olympiad" and the WRO logo are trademarks of the World Robot Olympiad
Association Ltd. This project is not affiliated with or endorsed by WRO.
