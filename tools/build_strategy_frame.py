#!/usr/bin/env python3
"""Build ``data/strategy_frame.json`` — what each mission costs and risks.

    data/field_spec.json           (area geometry, start area)     ─┐
    data/scoring_model.json        (points, the EV form)           ─┼─► JSON
    data/placement_sensitivity.json (P(success) vs sigma)          ─┘

Phase 8 proper — mission ordering — needs sigma from field tests P2/P3 and the
object pickup locations, 15 of which are ``nominal_pending`` with null
coordinates because ADR-014 refuses to invent them. So this builds the **inputs**
to that decision, not the decision. `CLAUDE.md` §5.7 anti-pattern #3 forbids
claiming one strategy beats another without simulator evidence, and nothing here
claims one.

Two things it does establish.

**The scoring opportunity is spatially lopsided.** The start area sits at
x = 2175.5; the scoring work spans x = 77 to 1858. The six notes (120 points)
cluster near the start area on the plaza. The cables, microphone and instruments
(95 points) sit at the far left, roughly two metres away — and inside or beside
the stage, which is where S1 puts the amplifier and both speakers.

**The stated risk term is a worst case, not a constant.** `CLAUDE.md` §5.6 and
``scoring_model.json`` both give::

    E[delta_score] = P(success) * points - P(collision) * 40

but the 40 is four separate objects — clef 10, speakers 2x10, amp 10 — and S1
places them apart. A route through the stage exposes the 30-point amp/speaker
cluster; a route along the staff lines exposes the 10-point clef. Which figure
applies decides whether a mission can ever be not-worth-attempting, so all three
tiers are swept and **40 is retained as the conservative default**.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Final, Sequence

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pdf_extract import R, RS, json_bytes, sha256_file  # noqa: E402
from sim.geometry import bbox, centroid  # noqa: E402
from sim.scoring import Scorer  # noqa: E402

TOOL_VERSION: Final = "1.0.0"
SCHEMA_VERSION: Final = 1

DEFAULT_OUT: Final = Path("data/strategy_frame.json")
SPECS: Final = {
    "field_spec": Path("data/field_spec.json"),
    "scoring_model": Path("data/scoring_model.json"),
    "placement_sensitivity": Path("data/placement_sensitivity.json"),
}

#: Bonus-point clusters, grouped by where S1 places them. The grouping is
#: sourced even though the coordinates are not: 15 of 17 object start poses are
#: `nominal_pending` (ADR-014).
BONUS_CLUSTERS: Final = (
    {
        "id": "stage_cluster",
        "objects": ("amp", "speaker_a", "speaker_b"),
        "points": 30,
        "source": "S1 p6: 'an amplifier together with 2 speakers ... on the stage "
                  "at the left end of the game field'",
        "zone": "stage",
    },
    {
        "id": "clef",
        "objects": ("clef",),
        "points": 10,
        "source": "S1 p6: 'in the middle on the left end of the staff lines'",
        "zone": "staff",
    },
)

#: Risk tiers swept for the break-even calculation.
RISK_TIERS: Final = (10, 30, 40)


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def build() -> dict[str, Any]:
    scorer = Scorer.load()
    field = json.loads(SPECS["field_spec"].read_text(encoding="utf-8"))
    model = json.loads(SPECS["scoring_model"].read_text(encoding="utf-8"))
    sensitivity = json.loads(SPECS["placement_sensitivity"].read_text(encoding="utf-8"))

    sigma = {
        reading: {r["label"]: r["sigma_for_p90_mm"] for r in rows}
        for reading, rows in sensitivity["readings"].items()
    }
    points = {oid: int(m["each"]) for m in model["missions"] if m["id"] != "m4_bonus"
              for oid in m["objects"]}
    mission_of = {oid: m["id"] for m in model["missions"] if m["id"] != "m4_bonus"
                  for oid in m["objects"]}

    stage = [(float(x), float(y)) for x, y in field["areas"]["stage"]["polygon_visible_mm"]]
    start = centroid([(float(x), float(y))
                      for x, y in field["areas"]["start_area"]["polygon_visible_mm"]])

    # Zone by which SIDE of the mat the target sits on, not by whether it
    # overlaps the stage polygon. `backstage` (x 0-394) does not intersect the
    # stage (y 324-1182) — there is a 6.3 mm gap — but it is 2 m from the start
    # area in the same far-left region as the cables and microphone, and nowhere
    # near the staff lines. Overlap-based zoning filed the three instruments
    # with the notes and credited them the clef's 10-point risk instead of the
    # stage cluster's 30.
    stage_right_edge = bbox(stage)[2]

    rows: list[dict[str, Any]] = []
    for object_id, (target_id, x, y, _theta) in sorted(scorer.nominal_placements().items()):
        target = scorer.scoring_areas[target_id]
        left_side = centroid(target)[0] < stage_right_edge
        zone = "left_stage_end" if left_side else "right_staff_end"
        exposed = [c for c in BONUS_CLUSTERS
                   if (c["zone"] == "stage") == left_side]
        exposed_points = sum(c["points"] for c in exposed)
        value = points[object_id]
        distance = _distance(start, centroid(target))
        rows.append({
            "object_id": object_id,
            "mission_id": mission_of[object_id],
            "target_id": target_id,
            "points": value,
            "zone": zone,
            "distance_from_start_mm": R(distance),
            "round_trip_mm": R(2 * distance),
            "points_per_metre_round_trip": R(value / (2 * distance / 1000.0)),
            "bonus_clusters_exposed": [c["id"] for c in exposed],
            "bonus_points_exposed": exposed_points,
            "sigma_for_p90_mm": {
                "contact": sigma["contact"].get(object_id),
                "projection": sigma["projection"].get(object_id),
            },
            # EV = P(success)*points - P(collision)*risk. Zero when
            # P(collision) = P(success) * points / risk. Reported at
            # P(success) = 1, so a caller scales by its own P(success).
            "breakeven_p_collision_at_p_success_1": {
                "risk_" + str(tier): R(value / tier) for tier in RISK_TIERS
            },
            "always_worth_attempting_at_exposed_risk": bool(
                value / max(exposed_points, 1) >= 1.0),
        })

    zones: dict[str, dict[str, Any]] = {}
    for row in rows:
        z = zones.setdefault(row["zone"], {
            "zone": row["zone"], "objects": [], "points": 0,
            "bonus_points_exposed": row["bonus_points_exposed"],
            "distance_min_mm": float("inf"), "distance_max_mm": 0.0,
        })
        z["objects"].append(row["object_id"])
        z["points"] += row["points"]
        z["distance_min_mm"] = min(z["distance_min_mm"], row["distance_from_start_mm"])
        z["distance_max_mm"] = max(z["distance_max_mm"], row["distance_from_start_mm"])
    for z in zones.values():
        z["objects"].sort()
        z["count"] = len(z["objects"])
        z["distance_min_mm"] = R(z["distance_min_mm"])
        z["distance_max_mm"] = R(z["distance_max_mm"])

    centres = [centroid(scorer.scoring_areas[a]) for a in scorer.scoring_areas]
    x0, _y0, x1, _y1 = bbox(centres)
    return {
        "schema_version": SCHEMA_VERSION,
        "provenance": {
            "tool": {"name": "build_strategy_frame", "version": TOOL_VERSION},
            "inputs": {name: sha256_file(path) for name, path in sorted(SPECS.items())},
            "risk_tiers_swept": list(RISK_TIERS),
        },
        "scope": {
            "answers": "what each mission costs in travel and risks in bonus points",
            "does_not_answer": "which missions to attempt, or in what order",
            "why_not": (
                "Mission ordering needs sigma from field tests P2/P3 and the object "
                "pickup locations, 15 of which are nominal_pending with null "
                "coordinates (ADR-014). CLAUDE.md 5.7 anti-pattern #3 forbids "
                "claiming one strategy beats another without simulator evidence."
            ),
        },
        "geometry": {
            "start_area_centre_mm": RS(start),
            "scoring_work_x_span_mm": RS((x0, x1)),
            "stage_bbox_mm": RS(bbox(stage)),
            "zone_boundary_x_mm": R(stage_right_edge),
            "zone_rule": (
                "a target whose centre lies left of the stage's right edge is in "
                "the left_stage_end zone. Not polygon overlap: backstage misses "
                "the stage by 6.3 mm yet sits 2 m away in the same region."
            ),
            "note": (
                "Distances are centre-to-centre Euclidean and are a LOWER BOUND on "
                "travel, not a route length: the robot cannot fly, though the mat "
                "is open between these areas."
            ),
        },
        "risk_model": {
            "stated_form": next(m for m in model["missions"]
                                if m["id"] == "m4_bonus")["floor_not_prize"][
                                    "expected_value_form"],
            "stated_in": ["CLAUDE.md 5.6", "data/scoring_model.json"],
            "refinement": (
                "The 40 is four separate objects, and S1 places them apart. A route "
                "exposes the cluster it passes, not all of them. 40 is retained as "
                "the conservative default; see ADR-024."
            ),
            "clusters": [
                {k: (list(v) if isinstance(v, tuple) else v) for k, v in c.items()}
                for c in BONUS_CLUSTERS
            ],
            "breakeven_formula": "P(collision)* = P(success) * points / risk",
            "linear_in_p_success": True,
        },
        "zones": [zones[k] for k in sorted(zones)],
        "missions": rows,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    spec = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(json_bytes(spec))

    print(f"{args.out}\n")
    print("  zones:")
    for z in spec["zones"]:
        print(f"    {z['zone']:<7} {z['count']:>2} objects  {z['points']:>3} pts  "
              f"{z['distance_min_mm']:>6.0f}-{z['distance_max_mm']:<6.0f} mm from start  "
              f"risks {z['bonus_points_exposed']} bonus pts")
    print(f"\n  {'mission':<22} {'pts':>4} {'dist':>7} {'pts/m':>7} {'risk':>5} "
          f"{'breakeven P(coll) @ P(succ)=1':>30}")
    for r in spec["missions"]:
        be = r["breakeven_p_collision_at_p_success_1"]
        flag = "  <- always worth it" if r["always_worth_attempting_at_exposed_risk"] else ""
        print(f"  {r['object_id']:<22} {r['points']:>4} {r['distance_from_start_mm']:>7.0f} "
              f"{r['points_per_metre_round_trip']:>7.1f} {r['bonus_points_exposed']:>5} "
              f"  10:{be['risk_10']:.2f}  30:{be['risk_30']:.2f}  40:{be['risk_40']:.2f}{flag}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
