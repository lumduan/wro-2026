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

#: Capacities the ten-mission run is solved at. Bounded by cost, not by choice:
#: each batch of size s enumerates s! x s! orders, so ten missions take ~27 s of
#: wall clock at capacity 1, ~150 s at 2, and ~22 min at 3. Physically the cap is
#: lower still — an instrument is not a 31.9 mm note, so carrying four of them is
#: not a design point anyone would reach.
FULL_RUN_CAPACITIES: Final = (1, 2)

#: Pick-and-place seconds per object to tabulate the time budget at.
PICK_PLACE_SECONDS: Final = (0.0, 1.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0)

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


def full_run(field_spec: dict[str, Any], notes: travel.NoteField,
             note_points: dict[str, int], seconds: float) -> dict[str, Any]:
    """The ten missions whose start geometry is known — notes plus the truck.

    Enumerated as a 24 x 16 grid: note permutations down, vehicle choices across.
    Keeping the grid rather than a flat list is what makes the uncertainty
    *decomposable* — the note spread at a fixed vehicle choice is irreducible
    (S1 p7 randomizes it and S4 §9.6 does so after quarantine), while the vehicle
    spread at a fixed permutation is exactly what work order B0 removes.
    """
    from sim.scoring import Scorer
    nominal = Scorer.load().nominal_placements()
    members = tuple(field_spec["start_groups"]["truck"]["members"])
    truck_targets = {m: (nominal[m][1], nominal[m][2]) for m in members}
    field = travel.FullField(field_spec, notes, truck_targets)

    note_assigns = notes.assignments()
    truck_assigns = field.truck.assignments()

    curve = []
    for capacity in FULL_RUN_CAPACITIES:
        grid = [[field.tour({**na, **ta}, capacity) for ta in truck_assigns]
                for na in note_assigns]
        flat = sorted(v for row in grid for v in row)
        low, high = R(flat[0]), R(flat[-1])
        # Down a column: the vehicle choice is fixed, so only the permutation moves.
        note_only = max(max(col) - min(col)
                        for col in zip(*grid))
        # Across a row: the permutation is fixed, so only the vehicle choice moves.
        vehicle_only = max(max(row) - min(row) for row in grid)
        curve.append({
            "capacity": capacity,
            "min_mm": low,
            "median_mm": R(statistics.median(flat)),
            "max_mm": high,
            "spread_mm": R(high - low),
            "required_speed_mm_s": {
                "at_best_case": R(travel.required_speed(flat[0], seconds)),
                "at_worst_case": R(travel.required_speed(flat[-1], seconds)),
            },
            "spread_sources_mm": {
                "note_permutation": R(note_only),
                "vehicle_choice": R(vehicle_only),
            },
        })

    worst = max(row["max_mm"] for row in curve)
    objects = len(field.objects)
    cliff = travel.impossible_beyond(objects, seconds)
    return {
        "covers": list(field.objects),
        "count": objects,
        "points_covered": sum(note_points[o] for o in field.objects),
        "excludes": {
            "cable_upper": "S1 p4: 'close to the stage (left end)' is not a measured region",
            "cable_lower": "S1 p4: 'close to the stage (left end)' is not a measured region",
        },
        "joint_assignments": len(note_assigns) * len(truck_assigns),
        "grid": f"{len(note_assigns)} note permutations x {len(truck_assigns)} vehicle choices",
        "capacity_curve": curve,
        "capacities_not_computed": {
            "capacities": [c for c in travel.DEFAULT_CAPACITIES
                           if c not in FULL_RUN_CAPACITIES],
            "why": (
                "Cost, and physics. The batch enumeration is s! x s! per batch, so "
                "ten missions cost ~27 s at capacity 1, ~150 s at 2 and ~22 min at 3. "
                "And an instrument is not a 31.9 mm note: carrying three of them plus "
                "the microphone is not a design point. The six-note curve above still "
                "runs to capacity 6 because there it is both cheap and meaningful."
            ),
        },
        "uncertainty": {
            "what_b0_removes": "the vehicle choice, and the position on that vehicle",
            "what_nothing_removes": (
                "the note permutation - S1 p7 randomizes it and S4 9.6 does so after "
                "quarantine, so it is drawn fresh every round and can only be sensed"
            ),
            "within_vehicle_residual_mm": {
                k: R(v) for k, v in field.truck.within_vehicle_span(field.start).items()
            },
            "within_vehicle_note": (
                "Leg span with the object moved over every corner of both bodies. "
                "Small because the targets are more than a metre away, which is why "
                "the vehicle CHOICE is enumerated and the position on it is not."
            ),
        },
        "pick_and_place": {
            "objects": objects,
            "multiplier": (
                f"every second of pick-and-place costs {objects} seconds of the "
                f"attempt, because there are {objects} objects"
            ),
            "impossible_beyond_s_per_object": R(cliff),
            "impossible_note": (
                f"At {cliff:.0f} s per object the attempt is entirely consumed by "
                "pick-and-place and the run cannot be completed at ANY driving speed. "
                "That is a constraint on the mechanism that no motor can buy back."
            ),
            "cliff_is_independent_of_distance": True,
            "why_independent": (
                f"The threshold is attempt_seconds / objects = {seconds:.0f} / "
                f"{objects} exactly. It does not move with the route, the capacity or "
                "the randomization - shortening the tour buys driving speed, never "
                "pick-and-place time."
            ),
            "by_capacity": [
                {
                    "capacity": row["capacity"],
                    "worst_case_distance_mm": row["max_mm"],
                    "cells": [
                        {
                            "seconds_per_object": R(t),
                            "driving_seconds": R(travel.driving_seconds(objects, t, seconds)),
                            "required_speed_mm_s": (
                                None if travel.driving_seconds(objects, t, seconds) <= 0
                                else R(row["max_mm"]
                                       / travel.driving_seconds(objects, t, seconds))),
                            "feasible_at_any_speed":
                                travel.driving_seconds(objects, t, seconds) > 0,
                        }
                        for t in PICK_PLACE_SECONDS
                    ],
                }
                for row in curve
            ],
        },
    }


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
            "covers": (
                "the six notes exactly, and under `full_run` the four truck objects "
                "as well - ten of the twelve placement missions, 185 of the 215 "
                "placement points"
            ),
            "does_not_cover": (
                "the two cables: S1 puts them 'close to the stage (left end)', which "
                "is not a measured region, so they stay nominal_pending (work order B0)"
            ),
            "truck_is_bounded_not_known": (
                "ADR-030 added the two vehicle bodies as measured areas, so each truck "
                "object's start is bounded by their union. A bound is not a pose: "
                "nominal_start_pose_mm stays null for all four and ADR-014 is untouched."
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
        "full_run": full_run(field_spec, field, note_points, seconds),
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

    run = spec["full_run"]
    print(f"\n  === full run: {run['count']} of 12 missions, "
          f"{run['points_covered']} of 215 placement points, "
          f"{run['joint_assignments']} joint start states ===")
    print(f"  {'cap':>4} {'min':>7} {'median':>7} {'max':>7} {'spread':>8} "
          f"{'mm/s @120s':>12}  spread from")
    for row in run["capacity_curve"]:
        src = row["spread_sources_mm"]
        print(f"  {row['capacity']:>4} {row['min_mm']:>7.0f} {row['median_mm']:>7.0f} "
              f"{row['max_mm']:>7.0f} {row['spread_mm']:>8.0f} "
              f"{row['required_speed_mm_s']['at_worst_case']:>12.0f}  "
              f"notes {src['note_permutation']:.0f} / vehicles {src['vehicle_choice']:.0f}")
    pp = run["pick_and_place"]
    print(f"\n  pick-and-place: {pp['multiplier']}")
    caps = [b["capacity"] for b in pp["by_capacity"]]
    print(f"  {'s/object':>9} {'driving s':>10}" +
          "".join(f"{'req mm/s cap ' + str(c):>18}" for c in caps))
    for i, cell in enumerate(pp["by_capacity"][0]["cells"]):
        speeds = ""
        for block in pp["by_capacity"]:
            value = block["cells"][i]["required_speed_mm_s"]
            speeds += f"{('IMPOSSIBLE' if value is None else f'{value:.0f}'):>18}"
        print(f"  {cell['seconds_per_object']:>9.0f} {cell['driving_seconds']:>10.0f}{speeds}")
    print(f"\n  the {pp['impossible_beyond_s_per_object']:.0f} s cliff is independent of "
          f"distance: {pp['why_independent']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
