#!/usr/bin/env python3
"""Build ``data/round_strategy.json`` — the objective under a best-of-N ranking.

    data/expected_score.json  (per-mission tier probabilities vs sigma)  ─┐
    data/scoring_model.json   (the 40-point bonus floor, max_score)      ─┴─► JSON

``data/expected_score.json`` answers *"what does one attempt score on average?"*.
That is the wrong question if the tournament ranks on the best of several rounds,
and S4 says it might:

- **§9.1.2** "A number of robot rounds." — count unspecified.
- **§10.13** "The ranking of teams depends on the overall tournament format. For
  example, the best attempt out of three rounds could be used…" — organizer-set,
  and best-of-three is an *example*.
- **§10.14** "Mulligan (optional element)… the new score will be used for the
  ranking **no matter what**." — a replacement, not a maximum.

``E[max(X1..XN)]`` rewards variance, so it does not rank strategies the way
``E[X]`` does. The premium is large and **grows with sigma** — at sigma = 20 mm
it is worth more than a whole cable mission — which means multiple rounds favour
the less precise, more ambitious strategy. That inverts the naive reading of
Phase 8.

Everything emitted is parametric in N. The real N is a `NEEDS-VERIFY(NO-TH)`
question for the Thai National Organizer, now alongside the robot limits.

This does **not** rank mission subsets — same refusal as ``expected_score.json``,
same reason: that needs the 120 s budget and a route, and a route needs the start
poses (work order B0). CLAUDE.md §5.7 anti-pattern #3.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Final, Sequence

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pdf_extract import R, json_bytes, sha256_file  # noqa: E402
from sim import rounds  # noqa: E402

TOOL_VERSION: Final = "1.0.0"
SCHEMA_VERSION: Final = 1

DEFAULT_OUT: Final = Path("data/round_strategy.json")
SPECS: Final = {
    "expected_score": Path("data/expected_score.json"),
    "scoring_model": Path("data/scoring_model.json"),
}

#: Running-best anchors for the mulligan card. 40 is the bonus floor — the score
#: of a round that did nothing — and the two quantiles bracket a plausible one.
MULLIGAN_ANCHOR_QUANTILES: Final = (0.50, 0.90)

S4_RULES: Final = {
    "s4_9_1_2": "A number of robot rounds.",
    "s4_10_13": (
        "The ranking of teams depends on the overall tournament format. For example, "
        "the best attempt out of three rounds could be used and if competing teams "
        "have the same points, the ranking is decided by the record of time."
    ),
    "s4_10_14": (
        "Mulligan (optional element): The organizer of a competition may allow that "
        "teams can retake a round right on the spot after the run. If a team decides "
        "to redo the run the new score will be used for the ranking no matter what. "
        "This concept is optional and has to be announced by the organizer of an "
        "event upfront."
    ),
}


def rounding_defect(spec: dict[str, Any]) -> dict[str, Any]:
    """Quantify why the published tier cells cannot be used as a distribution."""
    worst_cell, worst_ctx = 1.0, None
    worst_run = 1.0
    for reading, block in spec["readings"].items():
        for sigma in [c["sigma_mm"] for c in block["missions"][0]["cells"]]:
            product = 1.0
            for mission in block["missions"]:
                cell = next(c for c in mission["cells"] if c["sigma_mm"] == sigma)
                mass = rounds.raw_tier_mass(cell)
                product *= mass
                if abs(mass - 1.0) > abs(worst_cell - 1.0):
                    worst_cell = mass
                    worst_ctx = f"{reading}/{mission['object_id']}@sigma={sigma}"
            if abs(product - 1.0) > abs(worst_run - 1.0):
                worst_run = product
    return {
        "adr": "ADR-028",
        "why": (
            "ADR-008 rounds every emitted float to 3 decimals, so a mission's three "
            "tier probabilities need not sum to 1. Harmless in a linear sum; not "
            "harmless in a distribution, where cdf**N amplifies the excess."
        ),
        "worst_mission_mass": R(worst_cell),
        "worst_mission": worst_ctx,
        "worst_run_mass": R(worst_run),
        "worst_run_mass_pow_3": R(worst_run ** 3),
        "consequence": (
            "Un-renormalised, the powered cdf ends above 1 and E[max of 3] came out "
            "at 256.30 against a maximum of 255 — an impossible score."
        ),
        "resolution": "sim.rounds.tier_terms renormalises every mission before use",
        "error_budget": (
            "Renormalising costs nothing real: 3-dp rounding is +/-0.05 pp against "
            "the sweep's +/-0.8 pp sampling noise at 4000 samples per cell."
        ),
    }


def build() -> dict[str, Any]:
    spec, floor, maximum = rounds.load(SPECS["expected_score"], SPECS["scoring_model"])

    readings: dict[str, Any] = {}
    for reading, block in spec["readings"].items():
        missions = block["missions"]
        sigmas = [c["sigma_mm"] for c in missions[0]["cells"]]

        distribution, best_of, mulligan = [], [], []
        for sigma in sigmas:
            pmf = rounds.pmf_at(missions, sigma, floor, maximum)
            mu = rounds.mean(pmf)
            distribution.append({
                "sigma_mm": R(sigma),
                "mean": R(mu),
                "sd": R(rounds.stdev(pmf)),
                "p10": rounds.quantile(pmf, 0.10),
                "p50": rounds.quantile(pmf, 0.50),
                "p90": rounds.quantile(pmf, 0.90),
                "p_max_score": R(float(pmf[maximum])),
            })
            best_of.append({
                "sigma_mm": R(sigma),
                "at_n": [
                    {"n": n, "e_max": R(rounds.e_max(pmf, n)),
                     "premium_over_single_attempt": R(rounds.e_max(pmf, n) - mu)}
                    for n in rounds.DEFAULT_ROUND_COUNTS
                ],
            })
            anchors = [floor] + [rounds.quantile(pmf, q) for q in MULLIGAN_ANCHOR_QUANTILES]
            mulligan.append({
                "sigma_mm": R(sigma),
                "retake_if_realised_at_most": [
                    {"running_best": best, "threshold": rounds.retake_threshold(pmf, best)}
                    for best in sorted(set(anchors))
                ],
            })

        rows = []
        for mission in missions:
            cost = int(mission["bonus_points_exposed"])
            cells = []
            for sigma in sigmas:
                full = rounds.pmf_at(missions, sigma, floor, maximum)
                without = rounds.pmf_at(missions, sigma, floor, maximum,
                                        exclude=mission["object_id"])
                at_n = []
                for n in rounds.DEFAULT_ROUND_COUNTS:
                    p = rounds.breakeven_p_collision(full, without, cost, n)
                    at_n.append({"n": n,
                                 "breakeven_p_collision": None if p is None else R(p),
                                 "pays_even_at_certain_collision": p is None})
                cells.append({"sigma_mm": R(sigma), "at_n": at_n})
            rows.append({
                "object_id": mission["object_id"],
                "mission_id": mission["mission_id"],
                "bonus_points_exposed": cost,
                "cells": cells,
            })

        readings[reading] = {
            "distribution": distribution,
            "best_of": best_of,
            "mulligan": mulligan,
            "missions": rows,
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "provenance": {
            "tool": {"name": "build_round_strategy", "version": TOOL_VERSION},
            "inputs": {name: sha256_file(path) for name, path in sorted(SPECS.items())},
            "round_counts": list(rounds.DEFAULT_ROUND_COUNTS),
        },
        "scope": {
            "answers": (
                "the objective function under a best-of-N ranking, and when a "
                "S4 10.14 mulligan is worth taking"
            ),
            "does_not_answer": "which missions to attempt, or in what order",
            "why_not": (
                "Subset selection needs the 120 s budget and a route; a route needs "
                "the object start poses, still nominal_pending for ten objects "
                "(work order B0). CLAUDE.md 5.7 anti-pattern #3."
            ),
            "n_is_not_known": True,
            "n_source": (
                "S4 10.13 makes the aggregation rule organizer-set and offers "
                "best-of-three only as an example. NEEDS-VERIFY(NO-TH)."
            ),
            "sigma_is_not_measured": True,
            "sigma_source": "work order item B5 (field test P3) measures it",
            "missions_assumed_independent": True,
            "independence_assumption": "AS-10",
        },
        "rules": S4_RULES,
        "rounding_defect": rounding_defect(spec),
        "formula": {
            "objective": "E[max(X1..XN)], from P(max <= k) = P(X <= k)**N",
            "single_attempt_case": "N = 1 reduces to E[X], the Phase 8 objective",
            "why_variance_matters": (
                "E[max of N] is convex in the score distribution, so at equal means "
                "a wider distribution ranks higher. The premium grows with sigma, "
                "which means extra rounds reward the less precise, more ambitious "
                "strategy — the opposite of the single-attempt reading."
            ),
            "breakeven_method": (
                "bisection on P(collision), comparing E[max] of the run with the "
                "mission against the run without it. At N = 1 this reduces to the "
                "closed form in expected_score.json, E[points] / bonus_points_exposed."
            ),
            "breakeven_is_marginal_and_does_not_add_up": (
                "Each figure holds the rest of the run fixed and asks what "
                "P(collision) makes THIS mission stop paying, assuming it is the "
                "only reason the robot approaches its bonus cluster. Six missions "
                "share the 30-point stage cluster and six notes share the 10-point "
                "clef, so a route that attempts several of them risks that cluster "
                "ONCE, not once per mission. Summing these numbers over a route is "
                "wrong; costing the route needs B0. expected_score.json's per-mission "
                "break-evens carry the same restriction and do not state it."
            ),
            "mulligan_free_rule": (
                "Under best-of-N a round at or below your running best contributes "
                "nothing, so replacing it is weakly dominant — free. A run that does "
                "nothing scores exactly the 40-point bonus floor, so a 40 is always "
                "free to retake. AMBIGUITY(A10) qualifies this."
            ),
            "mulligan_gamble_rule": (
                "Above the running best, retake iff realised < E[max(running_best, "
                "fresh)] — the threshold tabulated per sigma."
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
    defect = spec["rounding_defect"]
    print(f"  published tier cells: worst mission mass {defect['worst_mission_mass']}, "
          f"compounded {defect['worst_run_mass']} -> ^3 = {defect['worst_run_mass_pow_3']}")
    for reading, block in spec["readings"].items():
        print(f"\n  === {reading} reading — best of N rounds ===")
        print(f"  {'sigma':>7} {'E[X]':>8} {'sd':>7} " +
              " ".join(f"{'E[max' + str(n) + ']':>9}" for n in rounds.DEFAULT_ROUND_COUNTS[1:]) +
              f" {'premium@3':>10}")
        for dist, row in zip(block["distribution"], block["best_of"]):
            tail = " ".join(f"{c['e_max']:>9.2f}" for c in row["at_n"][1:])
            print(f"  {dist['sigma_mm']:>7.1f} {dist['mean']:>8.2f} {dist['sd']:>7.2f} "
                  f"{tail} {row['at_n'][-1]['premium_over_single_attempt']:>10.2f}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
