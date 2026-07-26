#!/usr/bin/env python3
"""Build ``data/expected_score.json`` — E[score] as a function of σ and P(collision).

    data/scoring_model.json        (points, partial tiers, the bonus floor)  ─┐
    data/placement_sensitivity.json (p_full / p_partial / p_none vs σ)       ─┼─► JSON
    data/strategy_frame.json        (which bonus cluster each mission risks) ─┘

The piece that connects Phase 6 to Phase 8. The sweep says how often a placement
lands in each containment tier; the scoring model says what each tier pays; this
multiplies them.

**The partial tier is why this exists.** ``data/strategy_frame.json`` reports a
break-even collision probability at ``P(success) = 1`` — correct as the σ → 0
limit — and then attaches the scaling rule *"P(collision)* = P(success) × points
/ risk, linear in P(success)"*. That rule is wrong for every σ > 0, because a
missed placement usually does not score zero. It scores the **partial** tier:

======  ========  ===========  ========  ==============  ================
σ (mm)  p_full    p_partial    p_none    EV, that rule   EV, this module
======  ========  ===========  ========  ==============  ================
15      0.749     0.251        0.000     14.98           **17.49**
20      0.522     0.469        0.008     10.44           **15.13**
30      0.278     0.625        0.097      5.56           **11.81**
======  ========  ===========  ========  ==============  ================

``note_blue``, contact reading. Up to **45 %** understated — and the shape
matters more than the size: ``p_none`` stays near zero, so a note almost never
scores *nothing*. It scores 20 or 10.

**The tier is not uniform, so this cannot be a blanket factor.** Cable 5/15,
microphone 10/20, note 10/20, and **instruments have no partial tier at all** —
for those three a geometric near-miss really does score zero, and the naive form
is exactly right.

This does **not** rank mission subsets. That needs the 120 s budget and a route,
and a route needs the object start poses, which are still `nominal_pending` for
ten objects (work order item B0). ``CLAUDE.md`` §5.7 anti-pattern #3 applies.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Final, Sequence

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pdf_extract import R, RS, json_bytes, sha256_file  # noqa: E402

TOOL_VERSION: Final = "1.0.0"
SCHEMA_VERSION: Final = 1

DEFAULT_OUT: Final = Path("data/expected_score.json")
SPECS: Final = {
    "scoring_model": Path("data/scoring_model.json"),
    "placement_sensitivity": Path("data/placement_sensitivity.json"),
    "strategy_frame": Path("data/strategy_frame.json"),
}

#: Collision probabilities to tabulate the full-run score at. P(collision) is
#: not measured anywhere — see the `scope` block — so it stays a free parameter.
P_COLLISION_GRID: Final = (0.0, 0.05, 0.10, 0.25, 0.50)


def tiers(model: dict[str, Any]) -> dict[str, dict[str, int]]:
    """object id -> {"full": points, "partial": points}. 0 where no tier exists."""
    out: dict[str, dict[str, int]] = {}
    for mission in model["missions"]:
        if mission["id"] == "m4_bonus":
            continue
        partial = (mission.get("partial") or {}).get("points") or 0
        for object_id in mission["objects"]:
            out[object_id] = {"full": int(mission["each"]), "partial": int(partial)}
    return out


def build() -> dict[str, Any]:
    model = json.loads(SPECS["scoring_model"].read_text(encoding="utf-8"))
    sensitivity = json.loads(SPECS["placement_sensitivity"].read_text(encoding="utf-8"))
    frame = json.loads(SPECS["strategy_frame"].read_text(encoding="utf-8"))

    pay = tiers(model)
    exposed = {r["object_id"]: r["bonus_points_exposed"] for r in frame["missions"]}
    bonus_floor = int(next(m["max"] for m in model["missions"] if m["id"] == "m4_bonus"))
    maximum = int(model["max_score"])

    readings: dict[str, Any] = {}
    for reading, rows in sensitivity["readings"].items():
        missions: list[dict[str, Any]] = []
        by_sigma: dict[float, float] = {}
        for row in rows:
            object_id = row["object_id"]
            if "@" in row["label"] or object_id not in pay:
                continue                      # alternate orientations are not a mission
            full, partial = pay[object_id]["full"], pay[object_id]["partial"]
            cells = []
            for cell in row["cells"]:
                expected = cell["p_full"] * full + cell["p_partial"] * partial
                naive = cell["p_full"] * full
                # Derived from the EMITTED expected_points, not the unrounded
                # value, so a reader dividing two published numbers gets the
                # published third. Internal consistency beats a hidden extra
                # digit of precision.
                emitted = R(expected)
                cells.append({
                    "sigma_mm": cell["sigma_mm"],
                    "p_full": cell["p_full"],
                    "p_partial": cell["p_partial"],
                    "p_none": cell["p_none"],
                    "expected_points": emitted,
                    "expected_points_ignoring_partial": R(naive),
                    "understatement": R(emitted - R(naive)),
                    # EV = 0 when P(collision) = expected / risk_exposed
                    "breakeven_p_collision": R(emitted / exposed[object_id]),
                })
                by_sigma[cell["sigma_mm"]] = by_sigma.get(cell["sigma_mm"], 0.0) + expected
            missions.append({
                "object_id": object_id,
                "mission_id": row["target_id"],
                "full_points": full,
                "partial_points": partial,
                "has_partial_tier": partial > 0,
                "bonus_points_exposed": exposed[object_id],
                "cells": cells,
            })

        run = []
        for sigma in sorted(by_sigma):
            placement = by_sigma[sigma]
            run.append({
                "sigma_mm": R(sigma),
                "expected_placement_points": R(placement),
                "at_p_collision": [
                    {
                        "p_collision": R(p),
                        # Worst case: the whole 40 is exposed. A route exposes
                        # less (ADR-024), but which cluster depends on the route,
                        # and there is no route until B0 lands the start poses.
                        "expected_total": R(bonus_floor + placement - p * bonus_floor),
                        "share_of_max": R(
                            (bonus_floor + placement - p * bonus_floor) / maximum),
                    }
                    for p in P_COLLISION_GRID
                ],
            })
        readings[reading] = {"missions": missions, "full_attempt_run": run}

    return {
        "schema_version": SCHEMA_VERSION,
        "provenance": {
            "tool": {"name": "build_expected_score", "version": TOOL_VERSION},
            "inputs": {name: sha256_file(path) for name, path in sorted(SPECS.items())},
            "p_collision_grid": RS(P_COLLISION_GRID),
        },
        "scope": {
            "answers": "E[score] for a given sigma and P(collision)",
            "does_not_answer": "which missions to attempt, or in what order",
            "why_not": (
                "Subset selection needs the 120 s budget and a route; a route needs "
                "the object start poses, still nominal_pending for ten objects "
                "(work order B0). CLAUDE.md 5.7 anti-pattern #3."
            ),
            "sigma_is_not_measured": True,
            "sigma_source": "work order item B5 (field test P3) measures it",
            "p_collision_is_not_measured": True,
        },
        "formula": {
            "expected_points": "p_full(sigma)*full + p_partial(sigma)*partial",
            "expected_total": "40 + sum(expected_points) - P(collision)*risk",
            "bonus_floor": bonus_floor,
            "bonus_floor_rule": "S6 2026-06-17 — a run that does nothing scores 40",
            "supersedes": (
                "strategy_frame.json's 'linear_in_p_success' scaling rule. Its stored "
                "break-even values are the sigma -> 0 limit and are correct; the rule "
                "attached to them is not, and following it understates EV by up to 45%."
            ),
            "not_a_blanket_factor": (
                "the partial tier is 5/15 for a cable, 10/20 for the microphone and "
                "notes, and ABSENT for the three instruments, where the naive form is "
                "exactly right"
            ),
        },
        "readings": readings,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    spec = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(json_bytes(spec))

    print(f"{args.out}\n")
    for reading, block in spec["readings"].items():
        print(f"  === {reading} reading — full-attempt run ===")
        print(f"  {'sigma':>7} {'placement':>10} {'E[total] at P(collision)':>34}")
        print(f"  {'':>7} {'':>10}   " + "  ".join(
            f"{p:>5.2f}" for p in spec["provenance"]["p_collision_grid"]))
        for row in block["full_attempt_run"]:
            totals = "  ".join(f"{c['expected_total']:>5.0f}" for c in row["at_p_collision"])
            print(f"  {row['sigma_mm']:>7.1f} {row['expected_placement_points']:>10.1f}   {totals}")
        note = next(m for m in block["missions"] if m["object_id"] == "note_blue")
        worst = max(note["cells"], key=lambda c: c["understatement"])
        print(f"  note_blue: partial tier adds up to {worst['understatement']:.2f} pts "
              f"(at sigma {worst['sigma_mm']:.0f} mm)\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
