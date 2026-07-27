#!/usr/bin/env python3
"""Build ``data/feasibility_frontier.json`` — which missions fit, and what they score.

    data/field_spec.json     (start area, note slots, truck bodies, targets)  ─┐
    data/scoring_model.json  (points per mission, the 120 s attempt)          ─┼─► JSON
    data/expected_score.json (per-mission E[points] vs sigma)                 ─┤
    data/travel_budget.json  (the tours this frontier is cut from)            ─┘

Three units built the pieces and nothing joined them — ``travel_budget.json`` was
a leaf, consumed by nothing. This answers the question they were built for:

    given a robot that drives at *v* and picks-and-places in *t*, which missions
    fit in the attempt, and what do they score?

**Why the refusal lifts.** ``strategy_frame.json`` declined mission ordering in as
many words — *"needs sigma from field tests P2/P3 and the object pickup
locations, 15 of which are nominal_pending"* — and CLAUDE.md §5.7 anti-pattern #3
forbids strategy claims without simulator evidence. ADR-029 and ADR-030 supplied
the tours; feasibility does not need sigma, because sigma decides whether a
placement *scores*, not whether it *fits*. So the ban lifts for the ten costable
missions and stays for the two cables.

**What the answer looks like.** Speed saturates and pick-and-place does not. All
185 points are reachable at **83.9 mm/s** with instant handling and **251.7 mm/s**
at 8 s per object; above that line more speed buys *nothing*, while each extra
second of handling costs about 15 points — one instrument. The drop order is not
the obvious one either: the microphone is shed ahead of a cheaper instrument at
7 s, because it costs more travel than the points it brings back.

Everything is swept over all **384 joint start states**, so the published frontier
is the **worst case — guaranteed whatever the randomization draws** — with the
best case beside it.
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
from sim import frontier, travel  # noqa: E402
from sim.scoring import Scorer  # noqa: E402

TOOL_VERSION: Final = "1.0.0"
SCHEMA_VERSION: Final = 1

DEFAULT_OUT: Final = Path("data/feasibility_frontier.json")
SPECS: Final = {
    "field_spec": Path("data/field_spec.json"),
    "scoring_model": Path("data/scoring_model.json"),
    "expected_score": Path("data/expected_score.json"),
    "travel_budget": Path("data/travel_budget.json"),
}

#: Matching `build_travel_budget.FULL_RUN_CAPACITIES` — the tours cost s! x s!
#: per batch, so ten missions are tractable at 1 and 2 and not above.
CAPACITIES: Final = (1, 2)

#: Sigma anchors for the expected-value view. Three, not the whole grid: the
#: question it answers is "does accounting for accuracy change the subset?",
#: which is a comparison, not a surface.
SIGMA_ANCHORS: Final = (10.0, 20.0, 30.0)


def sweep(tours_by_state: list[dict[int, float]], counts: Sequence[int],
          points: Sequence[float], seconds: float) -> list[dict[str, Any]]:
    """Worst and best reachable score at every (speed, pick-and-place) cell."""
    cells = []
    for speed in frontier.DEFAULT_SPEEDS:
        for pick_place in frontier.DEFAULT_PICK_PLACE:
            reachable = [frontier.best_points(tours, counts, points,
                                              speed, pick_place, seconds)
                         for tours in tours_by_state]
            cells.append({
                "speed_mm_s": speed,
                "pick_place_s": R(pick_place),
                "worst_case_points": R(min(reachable)),
                "best_case_points": R(max(reachable)),
            })
    return cells


def robustness(expected: dict[str, Any], field_spec: dict[str, Any],
               nominal: dict[str, Any]) -> dict[str, Any]:
    """How much each mission's value survives placement error, and where they cross.

    Raw points rank a note (20) above an instrument (15) by a third. Expected
    points do not, past a point: the instruments deliver to ``backstage``, which
    is **124 924 mm2** against a note target's 6 352, so their ``p_full`` is
    still 1.0 at sigma = 30 mm while a note has lost a third of its value.
    """
    missions = {m["object_id"]: m for m in expected["readings"]["contact"]["missions"]}
    areas = field_spec["areas"]

    def curve(object_id: str) -> list[dict[str, float]]:
        return [{"sigma_mm": R(c["sigma_mm"]), "expected_points": R(c["expected_points"]),
                 "p_full": R(c["p_full"])}
                for c in missions[object_id]["cells"]]

    note, instrument = curve("note_blue"), curve("instrument_keyboard")
    crossover = None
    for lower, upper in zip(zip(note, instrument), zip(note[1:], instrument[1:])):
        (n0, i0), (n1, i1) = lower, upper
        if n0["expected_points"] >= i0["expected_points"] > 0 and \
                n1["expected_points"] < i1["expected_points"]:
            # Linear in sigma between the two grid points that straddle it.
            gap0 = n0["expected_points"] - i0["expected_points"]
            gap1 = n1["expected_points"] - i1["expected_points"]
            span = n1["sigma_mm"] - n0["sigma_mm"]
            crossover = n0["sigma_mm"] + span * gap0 / (gap0 - gap1)
            break

    return {
        "why": (
            "Raw points rank a note above an instrument by a third. Expected points "
            "stop doing so once placement error is real, because the targets are not "
            "the same size."
        ),
        "target_area_mm2": {
            "backstage": R(areas["backstage"]["area_mm2"]),
            "note_target_blue": R(areas["note_target_blue"]["area_mm2"]),
            "mic_target": R(areas["mic_target"]["area_mm2"]),
            "ratio_backstage_to_note": R(areas["backstage"]["area_mm2"]
                                         / areas["note_target_blue"]["area_mm2"]),
        },
        "note_blue": note,
        "instrument_keyboard": instrument,
        "crossover_sigma_mm": None if crossover is None else R(crossover),
        "crossover_note": (
            "Below this sigma a note is worth more; above it an instrument is, "
            "despite being worth five fewer points at full credit. The instrument "
            "has no partial tier at all (ADR-026) and does not need one - its "
            "p_full is still 1.0 at sigma = 30 mm."
        ),
        "consequence": (
            "CLAUDE.md 5.6's 'notes are 47% of the total' is a statement about the "
            "MAXIMUM score. At realistic placement error it overstates their share "
            "of the EXPECTED score, and the three instruments are the robust play."
        ),
    }


def build() -> dict[str, Any]:
    field_spec = json.loads(SPECS["field_spec"].read_text(encoding="utf-8"))
    model = json.loads(SPECS["scoring_model"].read_text(encoding="utf-8"))
    expected = json.loads(SPECS["expected_score"].read_text(encoding="utf-8"))

    seconds = float(model["time"]["attempt_seconds"])
    value = {oid: float(m["each"]) for m in model["missions"]
             if m["id"] != "m4_bonus" for oid in m["objects"]}
    bonus_floor = int(next(m["max"] for m in model["missions"] if m["id"] == "m4_bonus"))

    notes = travel.NoteField(field_spec)
    nominal = Scorer.load().nominal_placements()
    members = tuple(field_spec["start_groups"]["truck"]["members"])
    field = travel.FullField(field_spec, notes,
                            {m: (nominal[m][1], nominal[m][2]) for m in members})
    objects = field.objects
    exposure = {row["object_id"]: int(row["bonus_points_exposed"])
                for row in expected["readings"]["contact"]["missions"]}

    counts, points = frontier.subset_profile(objects, value)
    assignments = field.assignments()

    blocks = []
    for capacity in CAPACITIES:
        tours_by_state = [
            frontier.subset_tours([a[o] for o in objects],
                                  [field.targets[o] for o in objects],
                                  field.start, capacity)
            for a in assignments
        ]
        # The median state, for the views that need one concrete route rather
        # than a bound: the state whose full-set tour is the middle one.
        order = sorted(range(len(tours_by_state)),
                       key=lambda i: tours_by_state[i][(1 << len(objects)) - 1])
        median = tours_by_state[order[len(order) // 2]]

        saturation = []
        for pick_place in frontier.DEFAULT_PICK_PLACE:
            speeds = [frontier.saturation_speed(t, objects, value, pick_place, seconds)
                      for t in tours_by_state]
            attained = [s for s in speeds if s is not None]
            saturation.append({
                "pick_place_s": R(pick_place),
                "ceiling_points": R(frontier.ceiling(median, objects, value,
                                                     pick_place, seconds)),
                "speed_mm_s": None if len(attained) < len(speeds) else R(max(attained)),
                "best_case_speed_mm_s": None if not attained else R(min(attained)),
            })

        drops = []
        for pick_place in frontier.DEFAULT_PICK_PLACE:
            best = frontier.best_reachable(median, objects, value,
                                           120.0, pick_place, seconds)
            dropped = sorted(set(objects) - set(best.objects))
            drops.append({
                "pick_place_s": R(pick_place),
                "at_speed_mm_s": 120.0,
                "points": R(best.points),
                "missions": len(best.objects),
                "seconds_used": R(best.seconds),
                "dropped": dropped,
                "bonus_points_exposed": frontier.exposed_bonus(best.objects, exposure),
            })

        differ = []
        for sigma in SIGMA_ANCHORS:
            worth = frontier.expected_value(expected, "contact", sigma)
            for speed in frontier.DEFAULT_SPEEDS:
                for pick_place in frontier.DEFAULT_PICK_PLACE:
                    raw = frontier.best_reachable(median, objects, value,
                                                  speed, pick_place, seconds)
                    ev = frontier.best_reachable(median, objects, worth,
                                                 speed, pick_place, seconds)
                    if set(raw.objects) != set(ev.objects):
                        differ.append({
                            "sigma_mm": R(sigma),
                            "speed_mm_s": speed,
                            "pick_place_s": R(pick_place),
                            "attemptable_subset": sorted(raw.objects),
                            "expected_subset": sorted(ev.objects),
                        })

        blocks.append({
            "capacity": capacity,
            "attemptable": sweep(tours_by_state, counts, points, seconds),
            "saturation": saturation,
            "drop_order": drops,
            "expected_value_changes_the_subset": {
                "sigma_anchors": [R(s) for s in SIGMA_ANCHORS],
                "cells_compared": len(SIGMA_ANCHORS) * len(frontier.DEFAULT_SPEEDS)
                                  * len(frontier.DEFAULT_PICK_PLACE),
                "cells_that_differ": len(differ),
                "differences": differ,
                "note": (
                    "Feasibility maximises raw points; the expected view maximises "
                    "E[points] from expected_score.json at that sigma. Where they "
                    "agree, accuracy does not change WHICH missions to attempt - "
                    "only what they are worth."
                ),
            },
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "provenance": {
            "tool": {"name": "build_feasibility_frontier", "version": TOOL_VERSION},
            "inputs": {name: sha256_file(path) for name, path in sorted(SPECS.items())},
            "capacities": list(CAPACITIES),
            "speeds_mm_s": list(frontier.DEFAULT_SPEEDS),
            "pick_place_seconds": [R(t) for t in frontier.DEFAULT_PICK_PLACE],
            "joint_start_states": len(assignments),
        },
        "scope": {
            "answers": (
                "which missions fit in the 120 s attempt at a given driving speed "
                "and pick-and-place time, and what they score"
            ),
            "covers": (
                "the ten costable placement missions - the six notes and the four "
                "truck objects, 185 of the 215 placement points"
            ),
            "does_not_cover": (
                "the two cables: still nominal_pending, so every subset here is "
                "missing them and the frontier is a LOWER BOUND on reachable points"
            ),
            "why_this_is_allowed_now": (
                "strategy_frame.json refused mission ordering because it needed the "
                "pickup locations and a route; ADR-029 and ADR-030 supplied both for "
                "these ten. Feasibility does not need sigma - sigma decides whether a "
                "placement SCORES, not whether it FITS. CLAUDE.md 5.7 anti-pattern #3 "
                "asks for simulator evidence, and this is it."
            ),
            "speed_is_not_measured": True,
            "speed_source": "field test P6 (motor characterisation)",
            "pick_place_is_not_measured": True,
            "pick_place_source": "work order MEAS-3, once a mechanism exists",
            "feasibility_is_not_success": (
                "A mission that fits still has to be placed accurately enough to "
                "score. That is what the expected-value view keeps visible, and why "
                "the bonus floor of 40 is excluded from every figure here."
            ),
            "excludes_the_bonus_floor": bonus_floor,
        },
        "reads": {
            "worst_case_points": (
                "guaranteed whatever the randomization draws - the minimum over all "
                "384 joint start states"
            ),
            "best_case_points": "the luckiest draw, for the width of the band",
            "saturation_speed_mm_s": (
                "the exact lowest speed that reaches the ceiling, over the WORST "
                "state; null means no finite speed does, which happens once "
                "pick-and-place alone consumes the attempt (ADR-030's 12 s cliff)"
            ),
            "drop_order": (
                "at a fixed 120 mm/s, which missions the optimal subset sheds as "
                "handling time grows - computed on the median state"
            ),
        },
        "robustness": robustness(expected, field_spec, nominal),
        "capacity_blocks": blocks,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    spec = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(json_bytes(spec))

    print(f"{args.out}\n")
    shown = (0.0, 2.0, 4.0, 6.0, 8.0)
    for block in spec["capacity_blocks"]:
        print(f"  === capacity {block['capacity']} — worst-case points of 185, "
              f"guaranteed over {spec['provenance']['joint_start_states']} start states ===")
        print(f"  {'v mm/s':>7}" + "".join(f"{'t=' + str(int(t)) + 's':>8}" for t in shown))
        cells = {(c["speed_mm_s"], c["pick_place_s"]): c for c in block["attemptable"]}
        for speed in frontier.DEFAULT_SPEEDS:
            row = "".join(f"{cells[(speed, t)]['worst_case_points']:>8.0f}" for t in shown)
            print(f"  {speed:>7}{row}")
        print(f"\n  {'t':>4} {'ceiling':>8} {'needs mm/s':>11}   drop order at 120 mm/s")
        sat = {s["pick_place_s"]: s for s in block["saturation"]}
        for drop in block["drop_order"]:
            s = sat[drop["pick_place_s"]]
            need = "-" if s["speed_mm_s"] is None else f"{s['speed_mm_s']:.1f}"
            print(f"  {drop['pick_place_s']:>4.0f} {s['ceiling_points']:>8.0f} {need:>11}   "
                  f"{drop['points']:>3.0f} pts, dropped {drop['dropped'] or '-'}")
        diff = block["expected_value_changes_the_subset"]
        print(f"\n  accounting for sigma changes the subset in "
              f"{diff['cells_that_differ']} of {diff['cells_compared']} cells\n")

    rob = spec["robustness"]
    print(f"  === robustness: backstage is {rob['target_area_mm2']['ratio_backstage_to_note']:.0f}x "
          f"a note target ===")
    print(f"  {'sigma':>6} {'note (20 full)':>15} {'instrument (15)':>16}")
    for n, i in zip(rob["note_blue"], rob["instrument_keyboard"]):
        mark = "  <- instrument ahead" if i["expected_points"] > n["expected_points"] else ""
        print(f"  {n['sigma_mm']:>6.1f} {n['expected_points']:>15.2f} "
              f"{i['expected_points']:>16.2f}{mark}")
    print(f"\n  they cross at sigma = {rob['crossover_sigma_mm']:.1f} mm\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
