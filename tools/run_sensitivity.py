#!/usr/bin/env python3
"""Build ``data/placement_sensitivity.json`` — required placement accuracy.

    data/field_spec.json    ─┐
    data/scoring_model.json ─┼──► sim.Scorer ──► sim.sensitivity.sweep ──► JSON
    data/object_spec.json   ─┘

For every object that has to land inside an area, this reports ``P(success)``
across a grid of placement-error sigmas, under **both** readings of A7 (contact
patch and silhouette), and the sigma at which each mission clears 90 % and 99 %.

Each row also carries the **closed-form slack** — half the difference between
the target extent and the footprint — which is what the Monte Carlo must agree
with. The two are computed by completely different routes, so a disagreement
means the simulation is wrong, not the geometry.

`ASSUME:` sigma itself. Nothing here measures how accurately the robot places an
object; field tests **P2** (start-area repeatability) and **P3** (odometry
drift) do. What this fixes is the *requirement* — the accuracy each mission
demands — which does not depend on the robot at all.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any, Final, Sequence

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pdf_extract import R, RS, json_bytes, sha256_file  # noqa: E402
from sim.geometry import bbox  # noqa: E402
from sim.scoring import Scorer, ScoringParams  # noqa: E402
from sim.sensitivity import (  # noqa: E402
    DEFAULT_SAMPLES,
    DEFAULT_SEED,
    DEFAULT_SIGMA_MM,
    DEG_PER_MM,
    sweep,
    threshold_sigma,
)

TOOL_VERSION: Final = "1.0.0"
SCHEMA_VERSION: Final = 1

DEFAULT_OUT: Final = Path("data/placement_sensitivity.json")
SPECS: Final = {
    "field_spec": Path("data/field_spec.json"),
    "scoring_model": Path("data/scoring_model.json"),
    "object_spec": Path("data/object_spec.json"),
}

#: The cable evaluated a second time laid ACROSS its area rather than along it.
#: Not a hypothetical: it is the placement a naive route planner would choose.
EXTRA_ORIENTATIONS: Final = {"cable_upper@across_area": 80.0}


def closed_form_slack(scorer: Scorer, object_id: str, target_id: str,
                      aim_x: float, aim_y: float, theta_deg: float) -> dict[str, Any]:
    """How far the placement may drift, measured **at its actual aim point**.

    Not "half the gap if it were centred": the three instruments share one
    backstage area and are therefore aimed off-centre, so a centred figure would
    describe a placement nobody makes. Reporting it next to a Monte Carlo run at
    the real aim point would make the two columns disagree for no reason.

    ``centred_slack_per_side_mm`` is kept alongside as the best case the aim
    point could achieve — the gap between the two is what spreading costs.
    """
    footprint = scorer.footprints[object_id]
    shape = footprint.polygon(aim_x, aim_y, theta_deg)
    rect = scorer.area_rect(target_id)

    # Work in the AREA's own frame, not the mat's. The two cable areas are
    # tilted 80 deg / 100 deg, so their axis-aligned bounding box is 114.47 mm
    # across where the area itself is only 79.70 mm — a 35 mm overstatement that
    # would silently flatter every cable number in this table.
    rad = math.radians(rect.angle_deg)
    ux, uy = math.cos(rad), math.sin(rad)          # along the LONG axis
    pts = np.asarray(shape, dtype=float)
    along = pts[:, 0] * ux + pts[:, 1] * uy
    across = pts[:, 0] * -uy + pts[:, 1] * ux
    centre_along = rect.cx * ux + rect.cy * uy
    centre_across = rect.cx * -uy + rect.cy * ux
    half_long, half_short = rect.height_mm / 2.0, rect.width_mm / 2.0

    margins = {
        "-long": float(along.min()) - (centre_along - half_long),
        "+long": (centre_along + half_long) - float(along.max()),
        "-short": float(across.min()) - (centre_across - half_short),
        "+short": (centre_across + half_short) - float(across.max()),
    }
    binding = min(margins, key=lambda k: margins[k])
    extent_long = float(np.ptp(along))
    extent_short = float(np.ptp(across))
    centred_long = (rect.height_mm - extent_long) / 2.0
    centred_short = (rect.width_mm - extent_short) / 2.0
    return {
        "frame": "the target area's own axes, NOT the mat axes",
        "area_rect_mm": RS((rect.width_mm, rect.height_mm)),
        "area_angle_deg": R(rect.angle_deg),
        "area_is_axis_aligned": bool(min(abs(rect.angle_deg),
                                         abs(rect.angle_deg - 90.0),
                                         abs(rect.angle_deg - 180.0)) < 1e-6),
        "footprint_extent_in_area_frame_mm": RS((extent_short, extent_long)),
        "aim_point_mm": RS((aim_x, aim_y)),
        "aim_theta_deg": R(theta_deg),
        "margin_mm": {k: R(v) for k, v in sorted(margins.items())},
        "fits": bool(centred_long >= 0.0 and centred_short >= 0.0),
        "binding_edge": binding,
        "binding_slack_mm": R(margins[binding]),
        "centred_slack_per_side_mm": RS((centred_short, centred_long)),
    }


def build(samples: int, seed: int, sigmas: Sequence[float]) -> dict[str, Any]:
    readings: dict[str, Any] = {}
    for reading in ("contact", "projection"):
        scorer = Scorer.load(params=ScoringParams(footprint_reading=reading))
        cells = sweep(scorer, sigmas=sigmas, samples=samples, seed=seed,
                      extra_orientations=EXTRA_ORIENTATIONS)
        placements = scorer.nominal_placements()
        rows = []
        for label in sorted(cells):
            object_id = label.split("@")[0]
            series = cells[label]
            target_id = series[0].target_id
            theta = (EXTRA_ORIENTATIONS[label] if label in EXTRA_ORIENTATIONS
                     else placements[object_id][3])
            _t, aim_x, aim_y, _th = placements[object_id]
            footprint = scorer.footprints[object_id]
            # A threshold equal to the grid maximum is not a threshold: the
            # requirement was still met at the widest sigma tested. Say so
            # rather than reporting the grid's edge as if it were a result.
            top = max(series, key=lambda c: c.sigma_mm)
            rows.append({
                "label": label,
                "object_id": object_id,
                "target_id": target_id,
                "theta_deg": R(theta),
                "footprint_is_bound": footprint.is_bound,
                "footprint_source": footprint.source,
                "geometry": closed_form_slack(scorer, object_id, target_id,
                                              aim_x, aim_y, theta),
                "sigma_for_p90_mm": (None if threshold_sigma(series, 0.90) is None
                                     else R(threshold_sigma(series, 0.90))),
                "sigma_for_p99_mm": (None if threshold_sigma(series, 0.99) is None
                                     else R(threshold_sigma(series, 0.99))),
                "p90_exceeds_grid": bool(top.p_full >= 0.90),
                "p99_exceeds_grid": bool(top.p_full >= 0.99),
                "cells": [
                    {"sigma_mm": R(c.sigma_mm), "sigma_deg": R(c.sigma_deg),
                     "p_full": R(c.p_full), "p_partial": R(c.p_partial),
                     "p_none": R(c.p_none), "samples": c.samples}
                    for c in series
                ],
            })
        readings[reading] = rows

    return {
        "schema_version": SCHEMA_VERSION,
        "provenance": {
            "tool": {"name": "run_sensitivity", "version": TOOL_VERSION},
            "inputs": {name: sha256_file(path) for name, path in sorted(SPECS.items())},
            "seed": seed,
            "samples_per_cell": samples,
            "sigma_grid_mm": RS(sigmas),
            "deg_per_mm": DEG_PER_MM,
        },
        "method": {
            "models": "the placement-error DISTRIBUTION, not the robot",
            "why": (
                "A time-stepped robot needs friction, odometry drift and motor "
                "response, every one of which is an unmeasured ASSUME until field "
                "tests P1-P6 run. Modelling the outcome keeps exactly one unknown."
            ),
            "sigma_status": "ASSUME — field tests P2 and P3 measure it",
            "sigma_is_not_measured_here": True,
            "heading_error": (
                f"ASSUME: {DEG_PER_MM} deg of heading error per mm of sigma. A "
                f"placeholder shape, not a measurement; P3 replaces it."
            ),
            "cross_check": (
                "Every row carries the closed-form slack alongside the Monte "
                "Carlo. They are computed by different routes: if p_full at "
                "sigma -> 0 is not 1.0 wherever slack is positive, or not 0.0 "
                "wherever slack is negative, the simulation is wrong."
            ),
        },
        "parameters": {
            "a7_readings_both_reported": ["contact", "projection"],
            "note": (
                "A7 is open: `completely_in` may consume the contact patch or the "
                "silhouette. Both are swept rather than one being chosen."
            ),
        },
        "readings": readings,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    spec = build(args.samples, args.seed, DEFAULT_SIGMA_MM)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(json_bytes(spec))

    print(f"{args.out}: {args.samples} samples/cell, seed {args.seed}\n")
    for reading, rows in spec["readings"].items():
        print(f"  === {reading} reading ===")
        print(f"  {'placement':<26} {'slack':>9}  {'sigma@90%':>10} {'sigma@99%':>10}")
        for row in rows:
            g = row["geometry"]
            slack = f"{g['binding_slack_mm']:.2f}" if g["fits"] else "IMPOSSIBLE"

            def fmt(key: str, exceeds: str) -> str:
                if row[key] is None:
                    return "never"
                return f">{row[key]:.0f}" if row[exceeds] else f"{row[key]:.2f}"

            p90 = fmt("sigma_for_p90_mm", "p90_exceeds_grid")
            p99 = fmt("sigma_for_p99_mm", "p99_exceeds_grid")
            bound = " (bound)" if row["footprint_is_bound"] else ""
            print(f"  {row['label']:<26} {slack:>9}  {p90:>10} {p99:>10}{bound}")
        print()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
