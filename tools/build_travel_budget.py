#!/usr/bin/env python3
"""Build ``data/travel_budget.json`` — how far the notes are, and how fast is fast enough.

    data/field_spec.json     (start area, note slots, target polygons)  ─┐
    data/scoring_model.json  (the 120 s attempt, points per note)       ─┼─► JSON
    data/strategy_frame.json (the travel figure this corrects)          ─┘

Eight phases went into **accuracy**. Nothing asked whether a run fits in the 120
seconds S4 §10.1 allows. CLAUDE.md §5.7 anti-pattern #5 forbids optimising for
255/255 without reporting ``P(success)``; a strategy that places perfectly and
runs out of clock fails the same way, and was invisible.

**Two findings, both free of measurement.**

*Manipulator capacity deletes the randomization.* S1 p7 assigns four notes to
four slots at randomization and S4 §9.6 does it after quarantine, so which colour
lands where is drawn fresh every round. At capacity 1 that is worth 1000 mm of
travel — 15.2 % — across the 24 permutations. At capacity 6 the spread is
**exactly zero**, and structurally so: a robot that collects every note before
delivering any visits the same set of points whatever the permutation. Going
from 1 to 2 alone takes 2213 mm off the worst case. That lands on ADR-022, which
left the mechanism open.

*``strategy_frame.json`` never included the fetch leg.* It reports
``2 x d(start_area, target)``; the object's own starting position never enters.
The error runs **both ways** — ``note_yellow`` overstated by ~650 mm,
``note_white`` understated by up to 1027 mm — so ``points_per_metre_round_trip``
does not preserve the ranking it appears to give. Same failure class as ADR-024,
ADR-026 and ADR-028: a correct computation carrying a claim it cannot support.

**Everything here is a lower bound** — straight-line, no turning radius, no
acceleration, no pick or place time (AS-11). A required speed is a floor the
robot must clear, published so field test **P6** has a target, never a prediction.

Only the six notes are covered: they hold 120 of 255 points and their start
geometry is known. The other six placement missions are ``nominal_pending`` in
``field_spec.json`` and wait on work order **B0**.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Final, Sequence

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pdf_extract import R, RS, json_bytes, sha256_file  # noqa: E402
from sim import travel  # noqa: E402

TOOL_VERSION: Final = "1.0.0"
SCHEMA_VERSION: Final = 1

DEFAULT_OUT: Final = Path("data/travel_budget.json")
SPECS: Final = {
    "field_spec": Path("data/field_spec.json"),
    "scoring_model": Path("data/scoring_model.json"),
    "strategy_frame": Path("data/strategy_frame.json"),
}

#: Round counts to illustrate against, matching `sim.rounds.DEFAULT_ROUND_COUNTS`.
ROUND_COUNTS: Final = (1, 2, 3)

RULES: Final = {
    "s4_10_1": "Each robot attempt is 2 minutes",
    "s4_9_6": (
        "prepare the competition tables for the next round (including possible "
        "randomization of game objects)"
    ),
    "s4_10_2": (
        "not allowed to enter data to a program by changing positions or orientation "
        "of robot parts"
    ),
    "s1_p7": "four notes are randomly assigned to the four light-green squares",
}


def expected_best_of(values: Sequence[float], n: int) -> float:
    """E[shortest of n independent draws] from a uniform discrete distribution.

    The permutation is redrawn every round (§9.6), so under the best-of-N ranking
    of ADR-027 a team sees N independent draws. This is the travel analogue of
    ``sim.rounds.e_max`` — travel, not score, so the favourable tail is the
    *short* one.
    """
    ordered = sorted(values)
    total = len(ordered)
    # P(min > k-th) = ((total - k) / total) ** n, summed as a survival function
    return sum(ordered[k] * (((total - k) / total) ** n - ((total - k - 1) / total) ** n)
               for k in range(total))


def spearman(a: dict[str, float], b: dict[str, float]) -> float:
    """Rank correlation between two orderings of the same keys, ties absent.

    Used on six notes with distinct values, so the textbook shortcut applies:
    ``1 - 6*sum(d^2) / (n*(n^2-1))``.
    """
    rank_a = {k: i for i, k in enumerate(sorted(a, key=lambda k: -a[k]))}
    rank_b = {k: i for i, k in enumerate(sorted(b, key=lambda k: -b[k]))}
    n = len(a)
    squares = sum((rank_a[k] - rank_b[k]) ** 2 for k in a)
    return 1.0 - 6.0 * squares / (n * (n * n - 1))


def build() -> dict[str, Any]:
    field_spec = json.loads(SPECS["field_spec"].read_text(encoding="utf-8"))
    model = json.loads(SPECS["scoring_model"].read_text(encoding="utf-8"))
    frame = json.loads(SPECS["strategy_frame"].read_text(encoding="utf-8"))

    field = travel.NoteField(field_spec)
    assignments = field.assignments()
    seconds = float(model["time"]["attempt_seconds"])
    note_points = {oid: int(m["each"]) for m in model["missions"]
                   if m["id"] != "m4_bonus" for oid in m["objects"]}
    frame_rows = {row["object_id"]: row for row in frame["missions"]}

    curve = []
    for capacity in travel.DEFAULT_CAPACITIES:
        tours = sorted(travel.tour(a, field, capacity) for a in assignments)
        # Spread is derived from the EMITTED min and max, not from the unrounded
        # values: ADR-008 rounds each to 3 decimals, so the two can disagree by a
        # unit in the last place, and a reader subtracting two published numbers
        # should get the published third. Same rule as build_expected_score.py.
        low, high = R(tours[0]), R(tours[-1])
        curve.append({
            "capacity": capacity,
            "min_mm": low,
            "median_mm": R(statistics.median(tours)),
            "max_mm": high,
            "spread_mm": R(high - low),
            "sd_mm": R(statistics.pstdev(tours)),
            "distinct_tour_lengths": len({round(t, 6) for t in tours}),
            "permutation_invariant": travel.spread(tours) == 0.0,
            "required_speed_mm_s": {
                "at_median": R(travel.required_speed(statistics.median(tours), seconds)),
                "at_worst_permutation": R(travel.required_speed(tours[-1], seconds)),
            },
            "expected_best_of_n_mm": [
                {"n": n, "mm": R(expected_best_of(tours, n))} for n in ROUND_COUNTS
            ],
        })

    per_note = []
    for note_id in field.notes:
        target = field.targets[note_id]
        randomized = note_id in field.randomized
        origins = field.slots if randomized else (field.fixed_starts[note_id],)
        legs = sorted(travel.distance(field.start, o) + travel.distance(o, target)
                      for o in origins)
        row = frame_rows[note_id]
        modelled = float(row["round_trip_mm"])
        per_note.append({
            "note_id": note_id,
            "target_id": row["target_id"],
            "points": note_points[note_id],
            "randomized": randomized,
            "fetch_and_deliver_mm": {"min": R(legs[0]), "max": R(legs[-1])},
            "strategy_frame_round_trip_mm": R(modelled),
            "error_mm": {"min": R(legs[0] - modelled), "max": R(legs[-1] - modelled)},
            "strategy_frame_direction": (
                "overstates" if legs[-1] < modelled else
                "understates" if legs[0] > modelled else "brackets"),
        })

    at_one = next(c for c in curve if c["capacity"] == 1)
    at_full = next(c for c in curve if c["capacity"] == len(field.notes))

    return {
        "schema_version": SCHEMA_VERSION,
        "provenance": {
            "tool": {"name": "build_travel_budget", "version": TOOL_VERSION},
            "inputs": {name: sha256_file(path) for name, path in sorted(SPECS.items())},
            "capacities": list(travel.DEFAULT_CAPACITIES),
            "permutation_count": len(assignments),
            "round_counts": list(ROUND_COUNTS),
        },
        "scope": {
            "answers": (
                "how far the six notes are to fetch and deliver, how that varies over "
                "the 24 randomization permutations, and the mean speed each capacity "
                "demands to fit 120 s"
            ),
            "covers": "the six notes only - 120 of 255 points",
            "does_not_cover": (
                "the two cables, the microphone and the three instruments: their start "
                "poses are nominal_pending in field_spec.json (work order B0)"
            ),
            "does_not_choose_a_capacity": True,
            "capacity_gated_on": (
                "note mass and grip geometry - work order A2/A3. ADR-022 left the "
                "manipulator mechanism open and this does not close it."
            ),
            "speed_is_not_measured": True,
            "speed_source": "field test P6 (motor characterisation) measures it",
            "every_distance_is_a_lower_bound": True,
            "lower_bound_assumption": "AS-11",
        },
        "rules": RULES,
        "bounds": {
            "why_a_lower_bound": (
                "Straight-line centre-to-centre distance. A real path carries turning "
                "radius, acceleration and deceleration, and neither pick nor place "
                "actuation time is included. Matches tools/build_strategy_frame.py, "
                "so the two are comparable."
            ),
            "consequence": (
                "A required speed here is a floor the robot must clear, not a "
                "prediction that it will. Clearing it is necessary, never sufficient."
            ),
        },
        "headline": {
            "capacity_one_to_two_saves_mm": R(
                at_one["max_mm"] - next(c for c in curve if c["capacity"] == 2)["max_mm"]),
            "capacity_deletes_randomization_variance": at_full["permutation_invariant"],
            "why_structural": (
                "At full capacity the robot collects every note before delivering any, "
                "so it visits the same set of points whatever the permutation - the "
                "four slots and the six targets. The tour length cannot depend on which "
                "colour sits in which slot. The zero is structural, not numerical."
            ),
            "spread_is_not_monotone_in_capacity": True,
            "phase_change_not_a_slope": (
                "Total travel falls monotonically with capacity - a tour feasible at k "
                "is feasible at k+1 - but the SPREAD does not: it runs 1000, 658, 426, "
                "552, 425, 0, rising again from capacity 3 to 4. Only carrying every "
                "note at once removes the randomization, so a mechanism that carries "
                "'most' of them buys distance without buying predictability. All six "
                "capacities are published so the curve cannot be read as a smooth "
                "trend to zero."
            ),
            "sensing_interaction": (
                "S4 10.2 forbids entering the permutation before the run, so it must be "
                "sensed. At high capacity the robot passes every slot anyway and sensing "
                "is free; at capacity 1 it must spend a scanning pass or commit blind."
            ),
        },
        "capacity_curve": curve,
        "per_note": per_note,
        "corrects": {
            "artefact": "data/strategy_frame.json",
            "what": (
                "distance_from_start_mm and round_trip_mm measure start_area to target "
                "and omit the leg that fetches the object. The claim in scope.answers, "
                "'what each mission costs in travel', is therefore not supported."
            ),
            "why_it_matters": (
                "The error runs both ways, so points_per_metre_round_trip does not "
                "preserve the ranking it appears to give."
            ),
            "ranking_validity": {
                "spearman_at_best_permutation": R(spearman(
                    {r["note_id"]: r["points"] / r["fetch_and_deliver_mm"]["min"]
                     for r in per_note},
                    {r["note_id"]: note_points[r["note_id"]]
                     / frame_rows[r["note_id"]]["round_trip_mm"] for r in per_note})),
                "spearman_at_worst_permutation": R(spearman(
                    {r["note_id"]: r["points"] / r["fetch_and_deliver_mm"]["max"]
                     for r in per_note},
                    {r["note_id"]: note_points[r["note_id"]]
                     / frame_rows[r["note_id"]]["round_trip_mm"] for r in per_note})),
                "note": (
                    "The metric is not uniformly wrong - it is EXACTLY right on the "
                    "luckiest permutation and ANTI-CORRELATED on the unluckiest, and "
                    "S4 9.6 decides which after quarantine. note_white ranks first on "
                    "the model and last at the worst draw: its target is the closest "
                    "to the start area while its note can begin 1760 mm away."
                ),
                "mechanism": (
                    "Ranking by distance to TARGET flatters any target near the start "
                    "area regardless of where its object begins."
                ),
            },
            "adr": "ADR-029",
            "pattern": (
                "Fourth instance of a correct computation carrying a claim it cannot "
                "support - see ADR-024, ADR-026, ADR-028."
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
    print(f"  six notes, {spec['provenance']['permutation_count']} permutations, "
          f"straight-line lower bound\n")
    print(f"  {'cap':>4} {'min':>7} {'median':>7} {'max':>7} {'spread':>8} {'sd':>6} "
          f"{'mm/s @120s':>11}")
    for row in spec["capacity_curve"]:
        flag = "  <- permutation-invariant" if row["permutation_invariant"] else ""
        print(f"  {row['capacity']:>4} {row['min_mm']:>7.0f} {row['median_mm']:>7.0f} "
              f"{row['max_mm']:>7.0f} {row['spread_mm']:>8.1f} {row['sd_mm']:>6.0f} "
              f"{row['required_speed_mm_s']['at_worst_permutation']:>11.1f}{flag}")
    print(f"\n  capacity 1 -> 2 saves {spec['headline']['capacity_one_to_two_saves_mm']:.0f} mm "
          f"off the worst case\n")
    print(f"  {'note':<14} {'fetch+deliver':>16} {'strategy_frame':>15}  direction")
    for row in spec["per_note"]:
        span = (f"{row['fetch_and_deliver_mm']['min']:.0f}"
                if row["fetch_and_deliver_mm"]["min"] == row["fetch_and_deliver_mm"]["max"]
                else f"{row['fetch_and_deliver_mm']['min']:.0f}-"
                     f"{row['fetch_and_deliver_mm']['max']:.0f}")
        print(f"  {row['note_id']:<14} {span:>16} "
              f"{row['strategy_frame_round_trip_mm']:>15.0f}  {row['strategy_frame_direction']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
