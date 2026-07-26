#!/usr/bin/env python3
"""Build ``data/manipulator_requirements.json`` — what the gripper must do.

    data/object_spec.json          (footprints, bounds)   ─┐
    data/scoring_model.json        (mission values)       ─┼─► sim.Scorer ──► JSON
    data/field_spec.json           (target geometry)      ─┤
    data/placement_sensitivity.json (required accuracy)   ─┘

`docs/PHASE7_CONSTRAINTS.md` §1 asks for the manipulator topology to be recorded
as an ADR **with the arithmetic shown**. This is that arithmetic. It answers one
question — *what must the manipulator be able to do?* — and deliberately does not
answer *how*, because that needs object mass and grip points and no document
contains either.

Three quantities per object, each derived rather than assumed:

``grip_span_mm``
    the longest extent the mechanism has to span. For most objects this is the
    contact footprint; for ``instrument_keyboard`` and ``instrument_congas`` it
    is an upper **bound**, and the flag says so.

``yaw_tolerance_deg``
    **measured, not assumed** — scan the containment predicate over heading at
    the nominal aim point and find the first angle at which ``full`` is lost.
    This is the number that decides whether yaw needs a motor at all.

``sigma_for_p90_mm``
    read from ``data/placement_sensitivity.json`` under both A7 readings.

Handling classes are then derived by clustering ``grip_span_mm``, never
hand-assigned, so a new object cannot silently land in the wrong class.
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
from sim.scoring import Scorer, ScoringParams  # noqa: E402
from sim.world import ObjectState  # noqa: E402

TOOL_VERSION: Final = "1.0.0"
SCHEMA_VERSION: Final = 1

DEFAULT_OUT: Final = Path("data/manipulator_requirements.json")
SPECS: Final = {
    "field_spec": Path("data/field_spec.json"),
    "scoring_model": Path("data/scoring_model.json"),
    "object_spec": Path("data/object_spec.json"),
    "placement_sensitivity": Path("data/placement_sensitivity.json"),
}

#: Yaw scan resolution before bisection. 1 deg is finer than any mechanism will
#: hold, and the bisection that follows refines to 0.01 deg.
YAW_SCAN_STEP_DEG: Final = 1.0
YAW_BISECT_TOL_DEG: Final = 0.01

#: Two objects whose grip span differs by less than this are the same class.
#: 8.0 mm is one stud: classes are separated by whole studs or not at all.
CLASS_GAP_MM: Final = 8.0

#: S4 chapter 5, quoted in docs/citations.json.
MOTOR_BUDGET: Final = 4          # 5.2.8, Elementary
DRIVE_MOTORS: Final = 2          # a differential drive


def yaw_tolerance(scorer: Scorer, object_id: str, target_id: str,
                  x: float, y: float, theta: float) -> float | None:
    """First heading offset at which ``full`` containment is lost, in degrees.

    ``None`` means no offset up to 180 deg loses it — the object is indifferent
    to yaw, which is true of every 32 mm object in a 79.7 mm square target.

    Scanned before bisecting rather than bisected directly: containment need not
    be monotone in heading (a square object can re-fit at 90 deg), so a plain
    bisection could step over the first failure and report a tolerance the
    mechanism does not have.
    """
    def full_at(delta: float) -> bool:
        tier, _ = scorer.containment(
            ObjectState(object_id, x, y, theta + delta), target_id)
        return tier == "full"

    if not full_at(0.0):
        return 0.0
    lo = 0.0
    hi: float | None = None
    step = YAW_SCAN_STEP_DEG
    while lo < 180.0:
        probe = min(lo + step, 180.0)
        if not full_at(probe):
            hi = probe
            break
        lo = probe
    if hi is None:
        return None
    while hi - lo > YAW_BISECT_TOL_DEG:
        mid = (lo + hi) / 2.0
        if full_at(mid):
            lo = mid
        else:
            hi = mid
    return lo


def grip_span(obj: dict[str, Any], congas_bound_mm: float | None,
              object_id: str) -> tuple[float, bool, str]:
    """(span_mm, is_bound, source) — the longest extent to be spanned."""
    if object_id == "instrument_congas" and congas_bound_mm:
        return (congas_bound_mm, True,
                "upper bound: two 4-stud drums joined by a 6-stud bridge")
    footprint = obj.get("contact_footprint_mm")
    if footprint:
        return max(footprint), False, "MEASURED(S3) contact footprint"
    pending = obj.get("footprint_pending") or {}
    bound = pending.get("upper_bound_mm")
    if bound:
        return max(bound), True, f"upper bound ({pending.get('reason')})"
    raise KeyError(f"{object_id} has neither a footprint nor a bound")


def classify(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group objects into handling classes by grip span, largest gap first.

    Single-link clustering with a one-stud threshold: objects whose spans differ
    by less than a stud belong together, and a gap of a stud or more starts a
    new class. Derived, so adding an object cannot land it in the wrong class.
    """
    ordered = sorted(rows, key=lambda r: r["grip_span_mm"])
    classes: list[list[dict[str, Any]]] = [[ordered[0]]]
    for previous, row in zip(ordered, ordered[1:]):
        if row["grip_span_mm"] - previous["grip_span_mm"] >= CLASS_GAP_MM:
            classes.append([row])
        else:
            classes[-1].append(row)
    out = []
    for index, members in enumerate(classes):
        letter = chr(ord("A") + index)
        spans = [m["grip_span_mm"] for m in members]
        out.append({
            "class": letter,
            "objects": sorted(m["object_id"] for m in members),
            "count": len(members),
            "grip_span_min_mm": R(min(spans)),
            "grip_span_max_mm": R(max(spans)),
            "points": sum(m["points"] for m in members),
            "tightest_sigma_contact_mm": min(
                (m["sigma_for_p90_mm"]["contact"] for m in members
                 if m["sigma_for_p90_mm"]["contact"] is not None), default=None),
            "tightest_sigma_projection_mm": min(
                (m["sigma_for_p90_mm"]["projection"] for m in members
                 if m["sigma_for_p90_mm"]["projection"] is not None), default=None),
            "any_bounded": any(m["grip_span_is_bound"] for m in members),
        })
    return out


def capability_ladder(rows: Sequence[dict[str, Any]],
                      model: dict[str, Any]) -> list[dict[str, Any]]:
    """Cumulative points reachable as the mechanism's span grows.

    The bonus floor is included in the run total because it is a floor: S6
    2026-06-17 says a robot that never moves still scores 40. So a mechanism
    that handles nothing does not score 0 — it scores 40, and every rung is an
    increment on that.
    """
    bonus = next(m["max"] for m in model["missions"] if m["id"] == "m4_bonus")
    maximum = model["max_score"]
    ladder = []
    for span in sorted({r["grip_span_mm"] for r in rows}):
        reached = [r for r in rows if r["grip_span_mm"] <= span]
        placement = sum(r["points"] for r in reached)
        ladder.append({
            "span_mm": R(span),
            "objects_reachable": len(reached),
            "placement_points": placement,
            "run_total_with_bonus_floor": placement + int(bonus),
            "share_of_max": R((placement + int(bonus)) / int(maximum)),
            "points_left_on_the_table": int(maximum) - (placement + int(bonus)),
        })
    return ladder


def build() -> dict[str, Any]:
    scorer = Scorer.load()
    object_spec = json.loads(SPECS["object_spec"].read_text(encoding="utf-8"))
    model = json.loads(SPECS["scoring_model"].read_text(encoding="utf-8"))
    sensitivity = json.loads(SPECS["placement_sensitivity"].read_text(encoding="utf-8"))

    sigma = {
        reading: {r["label"]: r["sigma_for_p90_mm"] for r in rows}
        for reading, rows in sensitivity["readings"].items()
    }
    points = {oid: int(m["each"]) for m in model["missions"] if m["id"] != "m4_bonus"
              for oid in m["objects"]}
    congas_bound = (object_spec.get("congas_pair_extent") or {}).get("long_extent_bound_mm")

    placements = scorer.nominal_placements()
    rows: list[dict[str, Any]] = []
    for object_id, (target_id, x, y, theta) in sorted(placements.items()):
        obj = object_spec["objects"][object_id]
        span, is_bound, source = grip_span(obj, congas_bound, object_id)
        yaw = yaw_tolerance(scorer, object_id, target_id, x, y, theta)
        rows.append({
            "object_id": object_id,
            "target_id": target_id,
            "points": points[object_id],
            "contact_footprint_mm": obj.get("contact_footprint_mm"),
            "max_projection_mm": obj.get("max_projection_mm"),
            "grip_span_mm": R(span),
            "grip_span_is_bound": is_bound,
            "grip_span_source": source,
            "nominal_heading_deg": R(theta),
            "yaw_tolerance_deg": None if yaw is None else R(yaw),
            "yaw_is_unbounded": yaw is None,
            "sigma_for_p90_mm": {
                "contact": sigma["contact"].get(object_id),
                "projection": sigma["projection"].get(object_id),
            },
        })

    classes = classify(rows)
    tightest_yaw = min((r["yaw_tolerance_deg"] for r in rows
                        if r["yaw_tolerance_deg"] is not None), default=None)
    distinct_headings = sorted({r["nominal_heading_deg"] for r in rows})

    return {
        "schema_version": SCHEMA_VERSION,
        "provenance": {
            "tool": {"name": "build_manipulator_requirements", "version": TOOL_VERSION},
            "inputs": {name: sha256_file(path) for name, path in sorted(SPECS.items())},
            "yaw_scan_step_deg": YAW_SCAN_STEP_DEG,
            "yaw_bisect_tol_deg": YAW_BISECT_TOL_DEG,
            "class_gap_mm": CLASS_GAP_MM,
        },
        "scope": {
            "answers": "what the manipulator must be able to do",
            "does_not_answer": "how — gripper vs fork vs scoop vs passive",
            "why_not": (
                "Choosing a mechanism needs object mass and grip points. mass_g is "
                "null for all 16 objects because no building instruction contains "
                "it, and grip points need the physical parts. Asserting a topology "
                "on footprints alone is exactly what PHASE7_CONSTRAINTS §1 forbids."
            ),
        },
        "objects": rows,
        "handling_classes": classes,
        "grip_requirement": {
            "min_span_mm": R(min(r["grip_span_mm"] for r in rows)),
            "max_span_mm": R(max(r["grip_span_mm"] for r in rows)),
            "span_ratio": R(max(r["grip_span_mm"] for r in rows)
                            / min(r["grip_span_mm"] for r in rows)),
            "capability_ladder": capability_ladder(rows, model),
            "note": (
                "The ladder is what a span buys. It is the input to the mechanism "
                "choice, not the choice itself: a mechanism that stops at 32 mm is "
                "not thereby wrong, it is a decision to leave 60 points."
            ),
        },
        "yaw_requirement": {
            "tightest_tolerance_deg": tightest_yaw,
            "objects_indifferent_to_yaw": sorted(
                r["object_id"] for r in rows if r["yaw_is_unbounded"]),
            "distinct_nominal_headings_deg": distinct_headings,
            "needs_a_dedicated_actuator": bool(
                tightest_yaw is not None and tightest_yaw < 5.0),
            "finding": (
                "Yaw comes free from chassis heading if the tightest tolerance is "
                "wide compared with what a differential drive can hold. It costs a "
                "motor slot only if some object demands finer control than the "
                "drivetrain provides."
            ),
        },
        "motor_budget": {
            "total": MOTOR_BUDGET,
            "rule": "S4 5.2.8 — Elementary: 4 motors",
            "differential_drive": DRIVE_MOTORS,
            "yaw": 0,
            "available_for_manipulator": MOTOR_BUDGET - DRIVE_MOTORS,
            "exemptions": [
                {"mechanism": "pneumatics ≤ 3 bar, tanks ≤ 150 ml",
                 "counts": "only the compressor", "rule": "S4 5.2.16"},
                {"mechanism": "pullback motor without electronic control",
                 "counts": "no — but the robot must wind it itself", "rule": "S4 5.2.8"},
                {"mechanism": "electromagnet used only to hold",
                 "counts": "no; counts if used as a linear motor", "rule": "S4 5.2.10"},
                {"mechanism": "solenoid ≤ 20 N / ≤ 20 mm",
                 "counts": "yes", "rule": "S4 5.2.10"},
            ],
            "post_start_size_is_unrestricted": True,
            "post_start_size_rule": "S4 5.1 — deployable mechanisms are legal",
        },
        "gated_on": {
            "measurement": "object mass and grip points",
            "why": "mass_g is null for all 16 objects; no document contains it",
            "closed_by": "WRO Brick Set 45811 + Expansion Set 45819 on a scale",
            "field_test": "P5, and a new grip-point pass — see docs/FIELD_TEST_PLAN.md",
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
    print(f"  {'object':<22} {'span':>8} {'yaw':>9} {'sigma90 c/p':>14} {'pts':>4}")
    for row in spec["objects"]:
        yaw = "free" if row["yaw_is_unbounded"] else f"{row['yaw_tolerance_deg']:.1f}°"
        s = row["sigma_for_p90_mm"]
        sig = f"{s['contact'] or 0:.1f}/{s['projection'] or 0:.1f}"
        bound = "*" if row["grip_span_is_bound"] else " "
        print(f"  {row['object_id']:<22} {row['grip_span_mm']:>7.0f}{bound} {yaw:>9} "
              f"{sig:>14} {row['points']:>4}")
    print("\n  handling classes (derived by grip span, one-stud separation):")
    for c in spec["handling_classes"]:
        print(f"    {c['class']}  {c['count']} objects  "
              f"{c['grip_span_min_mm']:.0f}-{c['grip_span_max_mm']:.0f} mm  "
              f"{c['points']:>3} pts  {', '.join(c['objects'])}")
    print("\n  capability ladder (what a grip span buys):")
    for rung in spec["grip_requirement"]["capability_ladder"]:
        print(f"    span <= {rung['span_mm']:>3.0f} mm -> {rung['objects_reachable']:>2} objects, "
              f"{rung['run_total_with_bonus_floor']:>3}/255 "
              f"({rung['share_of_max']*100:.0f}%), "
              f"{rung['points_left_on_the_table']:>3} left")
    mb = spec["motor_budget"]
    yr = spec["yaw_requirement"]
    print(f"\n  motor budget: {mb['total']} total = {mb['differential_drive']} drive "
          f"+ {mb['yaw']} yaw + {mb['available_for_manipulator']} manipulator")
    print(f"  yaw: tightest tolerance {yr['tightest_tolerance_deg']}°, "
          f"dedicated actuator needed = {yr['needs_a_dedicated_actuator']}")
    print("  * = upper bound, not a measurement")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
