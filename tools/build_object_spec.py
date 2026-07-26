#!/usr/bin/env python3
"""Build ``data/object_spec.json`` from S3's parts callouts plus the object map.

    S3 img/p*.png ──► s3_callouts.cluster_callouts ──┐
                                                      ├──► data/object_spec.json
    docs/object_map.toml   (page range → object ID)  ─┤
    docs/object_parts.toml (cluster → part, curated) ─┘

Same split as ``build_field_spec.py``: the TOML files carry human judgement, this
tool carries the arithmetic and writes no dimension it did not derive.

**Footprint means the CONTACT patch, not the silhouette.** This distinction was
established the hard way. Eight of the models share one base pattern:

======  ===========================  ================================
step    part                         effect
======  ===========================  ================================
n       2 x (2x4 brick)              a 4x4 core -- THIS touches the mat
n+1     1 x (4x8 plate)              sandwiched at +9.6 mm, overhangs
n+2     2 x (2x4 brick)              stacked on top of the plate
======  ===========================  ================================

Reading the 4x8 plate as the base gives 32 x 64 mm and a 7.85 mm containment
slack; the true contact patch is 4x4 = 32 x 32 mm and 23.85 mm. Both fit inside
the 79.699 mm note target, so A7's default holds either way -- but the spec
records both, because ``completely_in`` consumes one of them and which one is a
scoring-interpretation question, not an arithmetic one.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any, Final, Sequence

sys.path.insert(0, str(Path(__file__).parent))
from pdf_extract import R, RS, json_bytes, sha256_file  # noqa: E402
from s3_callouts import (  # noqa: E402
    BRICK_MM,
    CALLOUT_MATCH_TOL,
    PLATE_MM,
    STUD_MM,
    build_pages,
    cluster_callouts,
)

TOOL_VERSION: Final = "1.0.0"
SCHEMA_VERSION: Final = 1

DEFAULT_IMG: Final = Path("docs/extracted/WRO-2026-RM-Elementary-BI-All/img")
DEFAULT_PROBE: Final = Path("docs/extracted/WRO-2026-RM-Elementary-BI-All/probe.json")
DEFAULT_MAP: Final = Path("docs/object_map.toml")
DEFAULT_PARTS: Final = Path("docs/object_parts.toml")
DEFAULT_OUT: Final = Path("data/object_spec.json")


class BuildError(SystemExit):
    """A curated entry disagrees with the extraction. Never downgraded."""


def studs_to_mm(studs: Sequence[int]) -> list[float]:
    return RS((studs[0] * STUD_MM, studs[1] * STUD_MM))


def build(img_dir: Path, probe: Path, map_path: Path, parts_path: Path) -> dict[str, Any]:
    omap = tomllib.loads(map_path.read_text(encoding="utf-8"))
    parts = tomllib.loads(parts_path.read_text(encoding="utf-8"))
    pages = build_pages(img_dir)
    clusters, missing = cluster_callouts(img_dir, pages)

    by_id = {c["cluster_id"]: c for c in clusters}
    page_cluster = {p: c["cluster_id"] for c in clusters for p in c["pages"]}

    # Curated part entries must match what the extraction actually found.
    curated: dict[int, dict[str, Any]] = {}
    for entry in parts["parts"]:
        cid = entry["cluster_id"]
        if cid not in by_id:
            raise BuildError(f"object_parts.toml names cluster {cid}, which does not exist")
        found = by_id[cid]
        if entry.get("studs") is not None and entry["studs"] != found["studs"]:
            raise BuildError(
                f"cluster {cid}: object_parts.toml says {entry['studs']} studs, "
                f"the extraction detected {found['studs']}"
            )
        curated[cid] = entry

    objects: dict[str, Any] = {}
    for model in omap["models"]:
        lo, hi = model["pages"]
        bom: dict[str, int] = {}
        for page in range(lo, hi + 1):
            cid = page_cluster.get(page)
            if cid is None:
                continue
            name = curated.get(cid, {}).get("part", f"cluster_{cid}")
            bom[name] = bom.get(name, 0) + 1

        base = model.get("base")
        entry: dict[str, Any] = {
            "source_pages": [lo, hi],
            "source_steps": model["steps"],
            "identification_confidence": model["confidence"],
            "identification_evidence": model["evidence"],
            "bom_steps": dict(sorted(bom.items())),
            # ADR-014 discipline: no number without a source.
            "mass_g": None,
            "needs_measurement": True,
        }
        if base:
            entry["contact_footprint_studs"] = base["contact_studs"]
            entry["contact_footprint_mm"] = studs_to_mm(base["contact_studs"])
            entry["max_projection_studs"] = base["projection_studs"]
            entry["max_projection_mm"] = studs_to_mm(base["projection_studs"])
            entry["overhang_height_mm"] = R(base.get("overhang_height_mm", 0.0))
            entry["base_evidence"] = base["evidence"]
        else:
            entry["contact_footprint_studs"] = None
            entry["contact_footprint_mm"] = None
            entry["footprint_needs_analysis"] = True

        for oid in model.get("instances", [model["id"]]):
            objects[oid] = dict(entry)

    probe_data = json.loads(probe.read_text())
    return {
        "schema_version": SCHEMA_VERSION,
        "provenance": {
            "tool": {"name": "build_object_spec", "version": TOOL_VERSION},
            "source": "S3",
            "s3_sha256": probe_data["source"]["sha256"],
            "object_map": str(map_path),
            "object_parts": str(parts_path),
            "object_map_sha256": sha256_file(map_path),
            "object_parts_sha256": sha256_file(parts_path),
            "callout_match_tol": CALLOUT_MATCH_TOL,
        },
        "lego_geometry": {
            "stud_mm": STUD_MM,
            "plate_mm": PLATE_MM,
            "brick_mm": BRICK_MM,
            "source": "S4 7.4 — elements are WRO Brick Set 45811 / Expansion 45819",
        },
        "callout_inventory": {
            "build_pages": len(pages),
            "pages_with_callout": len(pages) - len(missing),
            "pages_without_callout": sorted(missing),
            "distinct_parts": len(clusters),
            "clusters": [
                {
                    "cluster_id": c["cluster_id"],
                    "size_px": c["size_px"],
                    "detected_studs": c["studs"],
                    "lattice": c["lattice"],
                    "lattice_consistent": c["consistent"],
                    "pages": c["pages"],
                    "part": curated.get(c["cluster_id"], {}).get("part"),
                }
                for c in clusters
            ],
        },
        "objects": dict(sorted(objects.items())),
        "unresolved": [
            {k: v for k, v in u.items()} for u in omap.get("unresolved", [])
        ],
        "notes": [
            "footprint = the CONTACT patch with the mat, not the silhouette. See the "
            "module docstring: eight models place a 4x8 plate ON TOP of a 4x4 core, so "
            "the plate overhangs at +9.6 mm and is not what touches the mat.",
            "mass_g is null for every object: it cannot be derived from a building "
            "instruction. It needs the physical sets on a scale (ADR-014 discipline).",
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--img-dir", type=Path, default=DEFAULT_IMG)
    parser.add_argument("--probe", type=Path, default=DEFAULT_PROBE)
    parser.add_argument("--object-map", type=Path, default=DEFAULT_MAP)
    parser.add_argument("--object-parts", type=Path, default=DEFAULT_PARTS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    spec = build(args.img_dir, args.probe, args.object_map, args.object_parts)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(json_bytes(spec))

    inv = spec["callout_inventory"]
    print(f"{args.out}: {len(spec['objects'])} objects, {inv['distinct_parts']} distinct parts, "
          f"{inv['pages_with_callout']}/{inv['build_pages']} pages with a callout")
    for name, obj in sorted(spec["objects"].items()):
        fp = obj["contact_footprint_mm"]
        shown = f"{fp[0]:>5.1f} x {fp[1]:<5.1f} mm" if fp else "footprint pending"
        print(f"   {name:<22} {shown}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
