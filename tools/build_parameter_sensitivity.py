#!/usr/bin/env python3
"""Build ``data/parameter_sensitivity.json`` — which unknown to measure first.

    data/field_spec.json     ─┐
    data/scoring_model.json  ─┼─► the end-to-end model ─► per-parameter swing
    data/expected_score.json ─┤
    data/travel_budget.json  ─┘

The repo carries **six unmeasured parameters declared in five artefacts**, and
nothing ranks them. Each says *"this one is not measured"* and stops. The
operator is about to spend an afternoon measuring, and the repo has no opinion
on the order. This gives it one, by composing the end-to-end score
(:mod:`sim.model`) and varying one parameter at a time.

**The ranking is not stable, and that is the finding.** Placement error dominates
when the robot is comfortably fast; driving speed and handling time dominate when
it is not — and you cannot tell which regime you are in without measuring speed
and handling time. A single league table would have hidden that, so two operating
contexts are published and the orders compared explicitly.

**It also qualifies two of this project's own earlier emphases.** Carry capacity
moves the score by about a point, because once subset selection exists, dropping
a mission is cheaper than the travel capacity saves — ADR-029's travel findings
stand, their score consequence does not. And the randomization costs *nothing*
when the budget is comfortable: the band across all 384 joint start states is
zero-width until the budget is tight enough to change which missions fit.

**Nothing here is a prediction.** Every figure is an evaluation at an assumed
point, and the envelope over the corners spans 109 to 225 for exactly that reason.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path
from typing import Any, Final, Sequence

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pdf_extract import R, json_bytes, sha256_file  # noqa: E402
from sim import frontier, model, travel  # noqa: E402
from sim.scoring import Scorer  # noqa: E402

TOOL_VERSION: Final = "1.0.0"
SCHEMA_VERSION: Final = 1

DEFAULT_OUT: Final = Path("data/parameter_sensitivity.json")
SPECS: Final = {
    "field_spec": Path("data/field_spec.json"),
    "scoring_model": Path("data/scoring_model.json"),
    "expected_score": Path("data/expected_score.json"),
    "travel_budget": Path("data/travel_budget.json"),
}

#: Each unknown, the range it plausibly spans, and the work-order item that
#: closes it. The last column is what turns a ranking into a measurement order.
PARAMETERS: Final = (
    {"name": "sigma", "low": 5.0, "high": 30.0, "unit": "mm",
     "what": "placement error", "closed_by": "B5",
     "declared_in": ["expected_score", "placement_sensitivity", "round_strategy"]},
    {"name": "speed_mm_s", "low": 100, "high": 400, "unit": "mm/s",
     "what": "driving speed", "closed_by": "P6 (work order B6)",
     "declared_in": ["travel_budget", "feasibility_frontier"]},
    {"name": "pick_place_s", "low": 2.0, "high": 8.0, "unit": "s per object",
     "what": "pick-and-place time", "closed_by": "MEAS-3",
     "declared_in": ["feasibility_frontier"]},
    {"name": "rounds_n", "low": 1, "high": 3, "unit": "rounds",
     "what": "how many rounds are ranked", "closed_by": "NEEDS-VERIFY(NO-TH)",
     "declared_in": ["round_strategy"]},
    {"name": "p_collision", "low": 0.0, "high": 0.25, "unit": "probability",
     "what": "chance of toppling a bonus object", "closed_by": "nothing measures it",
     "declared_in": ["expected_score", "strategy_frame"]},
    {"name": "capacity", "low": 1, "high": 2, "unit": "objects carried",
     "what": "manipulator carry capacity", "closed_by": "MEAS-2/3",
     "declared_in": ["travel_budget"]},
)

#: Two operating points, chosen to straddle the regime change rather than to
#: flatter anything. Neither is a prediction.
CONTEXTS: Final = (
    {"name": "comfortable",
     "why": "a robot that is not short of time - the full ten missions fit",
     "nominal": {"sigma": 15.0, "speed_mm_s": 200, "pick_place_s": 4.0,
                 "rounds_n": 1, "p_collision": 0.10, "capacity": 2}},
    {"name": "marginal",
     "why": (
         "the boundary, where the randomization draw decides whether one more "
         "mission fits - the only place the permutation costs anything"
     ),
     "nominal": {"sigma": 15.0, "speed_mm_s": 150, "pick_place_s": 6.0,
                 "rounds_n": 1, "p_collision": 0.10, "capacity": 2}},
    {"name": "tight",
     "why": "slow driving and slow handling - the budget binds hard",
     "nominal": {"sigma": 15.0, "speed_mm_s": 100, "pick_place_s": 8.0,
                 "rounds_n": 1, "p_collision": 0.10, "capacity": 2}},
)


#: The grid the rank stability is checked over. Three contexts are three points,
#: and three points are not a shape — publishing only them implied a clean
#: "fast robot vs slow robot" split that this grid does not support.
STABILITY_SPEEDS: Final = (100, 125, 150, 175, 200, 250, 300)
STABILITY_PICK_PLACE: Final = (2.0, 4.0, 6.0, 8.0, 10.0)


def rank_stability(evaluate_at, base: dict[str, Any]) -> dict[str, Any]:
    """Which parameter leads across the whole operating grid, not at three points.

    The three published contexts disagree on the top-ranked parameter, which is
    easy to read as a regime split — placement error for a fast robot, driving
    speed for a slow one. Sweeping the grid says otherwise: sigma leads in the
    large majority of cells, and speed takes the lead only in a **narrow band of
    handling time**, at every speed in the sweep. Beyond the band sigma leads
    again. It is a band, not a regime, and only a grid shows that.
    """
    grid, tally = [], {}
    for speed in STABILITY_SPEEDS:
        for pick_place in STABILITY_PICK_PLACE:
            point = {**base, "speed_mm_s": speed, "pick_place_s": pick_place}
            swings = {}
            for parameter in PARAMETERS:
                name = parameter["name"]
                low = evaluate_at({**point, name: parameter["low"]})
                high = evaluate_at({**point, name: parameter["high"]})
                swings[name] = abs(high.expected_score - low.expected_score)
            leader = max(swings, key=swings.get)
            tally[leader] = tally.get(leader, 0) + 1
            grid.append({
                "speed_mm_s": speed,
                "pick_place_s": R(pick_place),
                "leads": leader,
                "swing": R(swings[leader]),
            })
    band = sorted({c["pick_place_s"] for c in grid if c["leads"] != "sigma"})
    return {
        "cells": len(grid),
        "speeds_mm_s": list(STABILITY_SPEEDS),
        "pick_place_seconds": [R(t) for t in STABILITY_PICK_PLACE],
        "leads_in_cells": tally,
        "sigma_leads_fraction": R(tally.get("sigma", 0) / len(grid)),
        "handling_times_where_sigma_does_not_lead": band,
        "grid": grid,
        "why_this_exists": (
            "The three contexts disagree on the top-ranked parameter, which reads "
            "as a regime split - placement error for a fast robot, driving speed "
            "for a slow one. The grid does not support that: sigma leads in most "
            "cells, and speed leads only in a narrow band of HANDLING time, at "
            "every speed swept. Beyond the band sigma leads again."
        ),
        "what_causes_the_band": (
            "At about 8 s per object, ten objects consume 80 of the 120 s and only "
            "40 s of driving is left, so how far the robot can travel decides how "
            "many missions fit at all. Below that, speed is not binding; above it, "
            "so little fits that speed stops changing the count."
        ),
    }


def build() -> dict[str, Any]:
    field_spec = json.loads(SPECS["field_spec"].read_text(encoding="utf-8"))
    scoring = json.loads(SPECS["scoring_model"].read_text(encoding="utf-8"))
    expected = json.loads(SPECS["expected_score"].read_text(encoding="utf-8"))

    attempt = float(scoring["time"]["attempt_seconds"])
    bonus_floor = int(next(m["max"] for m in scoring["missions"] if m["id"] == "m4_bonus"))

    notes = travel.NoteField(field_spec)
    nominal_poses = Scorer.load().nominal_placements()
    members = tuple(field_spec["start_groups"]["truck"]["members"])
    field = travel.FullField(field_spec, notes,
                            {m: (nominal_poses[m][1], nominal_poses[m][2]) for m in members})
    objects = field.objects
    missions, exposure = model.load_missions(expected, "contact", objects)

    assignments = field.assignments()
    tours_by_capacity = {
        capacity: [frontier.subset_tours([a[o] for o in objects],
                                         [field.targets[o] for o in objects],
                                         field.start, capacity)
                   for a in assignments]
        for capacity in (1, 2)
    }
    # A single representative state for the one-at-a-time sweep. The permutation
    # is swept separately, per context, so it is a reported band rather than a
    # hidden average.
    representative = {c: tours_by_capacity[c][0] for c in (1, 2)}

    def evaluate(tours: dict[int, float], **kwargs: Any) -> model.Outcome:
        return model.expected_run_score(
            missions, exposure, tours, objects,
            bonus_floor=bonus_floor, attempt=attempt, **kwargs)

    def at(point: dict[str, Any], state: dict[int, float] | None = None) -> model.Outcome:
        knobs = {k: v for k, v in point.items() if k != "capacity"}
        tours = state if state is not None else representative[point["capacity"]]
        return evaluate(tours, **knobs)

    contexts = []
    for context in CONTEXTS:
        point = dict(context["nominal"])
        base = at(point)
        band = [at(point, state).expected_score
                for state in tours_by_capacity[point["capacity"]]]
        swings = []
        for parameter in PARAMETERS:
            name = parameter["name"]
            low = at({**point, name: parameter["low"]})
            high = at({**point, name: parameter["high"]})
            swings.append({
                "parameter": name,
                "what": parameter["what"],
                "low": parameter["low"], "high": parameter["high"],
                "unit": parameter["unit"],
                "score_at_low": R(low.expected_score),
                "score_at_high": R(high.expected_score),
                "swing": R(abs(high.expected_score - low.expected_score)),
                "closed_by": parameter["closed_by"],
            })
        swings.sort(key=lambda s: -s["swing"])
        for rank, swing in enumerate(swings, 1):
            swing["rank"] = rank
        contexts.append({
            "name": context["name"],
            "why": context["why"],
            "nominal": {k: (R(v) if isinstance(v, float) else v) for k, v in point.items()},
            "expected_score": R(base.expected_score),
            "of_reachable_max": model.REACHABLE_MAX,
            "missions_attempted": len(base.subset),
            "subset": sorted(base.subset),
            "travel_mm": R(base.travel_mm),
            "seconds_used": R(base.seconds),
            "bonus_points_exposed": base.bonus_exposed,
            "randomization_band": {
                "states": len(band),
                "min": R(min(band)), "max": R(max(band)),
                "width": R(max(band) - min(band)),
            },
            "swings": swings,
        })

    orders = {c["name"]: [s["parameter"] for s in c["swings"]] for c in contexts}
    distinct = len({tuple(o) for o in orders.values()}) > 1

    corners = []
    for values in itertools.product(*[(p["low"], p["high"]) for p in PARAMETERS]):
        point = dict(zip((p["name"] for p in PARAMETERS), values))
        corners.append(at(point).expected_score)

    perfect = evaluate(representative[2], sigma=0.0, speed_mm_s=10 ** 6,
                       pick_place_s=0.0, rounds_n=1, p_collision=0.0)

    return {
        "schema_version": SCHEMA_VERSION,
        "provenance": {
            "tool": {"name": "build_parameter_sensitivity", "version": TOOL_VERSION},
            "inputs": {name: sha256_file(path) for name, path in sorted(SPECS.items())},
            "joint_start_states": len(assignments),
            "corners_evaluated": len(corners),
        },
        "scope": {
            "answers": "which unmeasured parameter moves the expected score most",
            "does_not_answer": (
                "what the score will be. Every figure is an evaluation at an ASSUMED "
                "operating point, not a forecast - all six parameters are unmeasured"
            ),
            "covers": (
                "the ten costable placement missions; the two cables are still "
                "nominal_pending, so the ceiling here is 225 and never 255"
            ),
            "reachable_max": model.REACHABLE_MAX,
            "why_not_255": (
                f"{bonus_floor} bonus floor + 185 costable placement points. The two "
                "cables add 30 more, and no route through them can be costed until "
                "work order B0."
            ),
            "one_at_a_time": (
                "Each swing varies ONE parameter with the others at the context "
                "nominal, so interactions are invisible within a context. That is why "
                "two contexts are published rather than one - the interaction between "
                "sigma, speed and handling time is the whole finding."
            ),
        },
        "model": {
            "chain": (
                "choose the highest-expected-value subset that fits (sim.frontier) -> "
                "convolve its tier probabilities into a score distribution (sim.rounds) "
                "-> subtract the exposed bonus cluster once (ADR-024) -> take E[max] "
                "over N rounds (ADR-027)"
            ),
            "no_new_arithmetic": (
                "Every step already existed in sim/. Eleven artefacts and none had "
                "composed them; the value is in stating the chain in one place."
            ),
            "anchor_perfect_corner": R(perfect.expected_score),
            "anchor_note": (
                "sigma = 0, unlimited speed, instant handling, one round, no collision "
                f"-> exactly {model.REACHABLE_MAX}"
            ),
        },
        "parameters": [
            {k: v for k, v in p.items() if k != "name"} | {"name": p["name"]}
            for p in PARAMETERS
        ],
        "contexts": contexts,
        "rank_stability": rank_stability(at, dict(CONTEXTS[0]["nominal"])),
        "rank_order": {
            "by_context": orders,
            "differs_between_contexts": distinct,
            "finding": (
                "The three contexts disagree, but a grid sweep says sigma leads in most "
                "cells: driving speed takes the top rank only inside a narrow BAND of "
                "handling time near 8 s per object, and sigma leads again beyond it. "
                "So the measurement order is simply sigma (B5) first, with the band as "
                "a named exception - not 'find out which regime you are in'. See "
                "rank_stability."
            ),
            "superseded_2026_07_27": (
                "This block first read 'placement error dominates when the robot is "
                "comfortably fast; driving speed and handling time dominate when it is "
                "not', generalised from two chosen operating points. The grid sweep "
                "does not support it: speed leads at EVERY swept speed inside the band "
                "and at none outside it, so handling time causes the flip, not speed."
            ),
        },
        "envelope": {
            "corners": len(corners),
            "min": R(min(corners)),
            "max": R(max(corners)),
            "note": (
                "Across the corners of all six ranges the answer spans nearly the whole "
                "scale. That is the honest summary of how much is still unknown."
            ),
        },
        "qualifies": {
            "both_are_boundary_effects": (
                "Carry capacity and the randomization behave the same way, and neither "
                "is well described by 'it matters' or 'it does not'. Both cost NOTHING "
                "when the budget is comfortable, nothing when it is tight, and a great "
                "deal at the margin where one more mission is borderline. Subset "
                "selection absorbs them everywhere else: an unlucky draw or a smaller "
                "gripper costs a mission only when a mission was borderline anyway."
            ),
            "carry_capacity": (
                "0.0 points at the comfortable context, 30.0 at the margin, 1.1 when "
                "tight. ADR-029's travel findings stand unchanged - 2213 mm off the "
                "worst-case note tour at the first extra slot, and the randomization "
                "deleted entirely at capacity 6. What this adds is where that travel "
                "converts into score: only at the boundary."
            ),
            "randomization": (
                "The band across all 384 joint start states is 0.0 at the comfortable "
                "context, 0.0 when tight, and 15.0 at the margin between them - where "
                "the draw decides whether one more mission fits. That is narrower than "
                "'the randomization is expensive when the budget is tight': it is "
                "expensive only at a boundary."
            ),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    spec = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(json_bytes(spec))

    print(f"{args.out}\n")
    print(f"  ceiling {spec['scope']['reachable_max']} "
          f"(perfect corner verifies at {spec['model']['anchor_perfect_corner']:.0f})\n")
    for context in spec["contexts"]:
        band = context["randomization_band"]
        print(f"  === {context['name']}: {context['expected_score']:.1f}/"
              f"{context['of_reachable_max']}, {context['missions_attempted']} missions, "
              f"randomization band {band['width']:.1f} ===")
        print(f"  {'rank':>4} {'parameter':<14}{'range':<20}{'low':>8}{'high':>8}"
              f"{'swing':>8}   closes with")
        for swing in context["swings"]:
            span = f"{swing['low']} - {swing['high']} {swing['unit']}"
            print(f"  {swing['rank']:>4} {swing['parameter']:<14}{span:<20}"
                  f"{swing['score_at_low']:>8.1f}{swing['score_at_high']:>8.1f}"
                  f"{swing['swing']:>8.1f}   {swing['closed_by']}")
        print()
    order = spec["rank_order"]
    print(f"  rank order differs between contexts: {order['differs_between_contexts']}")
    for name, seq in order["by_context"].items():
        print(f"    {name:<12} {' > '.join(seq)}")
    stability = spec["rank_stability"]
    print(f"\n  but across {stability['cells']} grid cells the leader is:")
    for parameter, count in sorted(stability["leads_in_cells"].items(), key=lambda p: -p[1]):
        print(f"    {parameter:<14} {count:>3} cells")
    print(f"  sigma does NOT lead only at handling time "
          f"{stability['handling_times_where_sigma_does_not_lead']} s "
          f"- a band, not a regime")
    env = spec["envelope"]
    print(f"\n  envelope over {env['corners']} corners: {env['min']:.1f} .. {env['max']:.1f}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
