#!/usr/bin/env python3
"""Build ``data/object_spec.json`` from S3's parts callouts plus the object map.

    S3 img/p*.png ──► s3_callouts.run_boundaries   ──┐
                 └──► s3_callouts.cluster_callouts ──┤
                                                     ├──► data/object_spec.json
    docs/object_map.toml   (page range → object ID) ─┤
    docs/object_parts.toml (part render → LEGO part)─┘

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

Part 3 adds two things. Model boundaries now come from the cream **run-preview**
box rather than the parts callout, which resolved all three of part 1's
unresolved spans and corrected three of its page ranges. And the **parts
inventory** on pages 176-177 supplies canonical LEGO part numbers, which are
cross-checked against the extraction rather than trusted (see ``_crosscheck``).
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
    SHAPE_AGREE,
    SHAPE_SLACK_PX,
    STUD_MM,
    cluster_callouts,
    run_boundaries,
    shape_groups,
    step_pages,
)

TOOL_VERSION: Final = "2.0.0"
SCHEMA_VERSION: Final = 2

DEFAULT_IMG: Final = Path("docs/extracted/WRO-2026-RM-Elementary-BI-All/img")
DEFAULT_PROBE: Final = Path("docs/extracted/WRO-2026-RM-Elementary-BI-All/probe.json")
DEFAULT_MAP: Final = Path("docs/object_map.toml")
DEFAULT_PARTS: Final = Path("docs/object_parts.toml")
DEFAULT_OUT: Final = Path("data/object_spec.json")


class BuildError(SystemExit):
    """A curated entry disagrees with the extraction. Never downgraded."""


def studs_to_mm(studs: Sequence[int]) -> list[float]:
    return RS((studs[0] * STUD_MM, studs[1] * STUD_MM))


def _resolve_curated(parts: dict[str, Any], groups: Sequence[dict[str, Any]]
                     ) -> dict[int, dict[str, Any]]:
    """shape_id → curated part entry, hard-failing on any disagreement."""
    where = {member: g for g in groups for member in g["members"]}
    by_shape: dict[int, dict[str, Any]] = {}
    for entry in parts["parts"]:
        key = (entry["cluster_id"], entry.get("part_index", 0))
        group = where.get(key)
        if group is None:
            raise BuildError(
                f"object_parts.toml names render {key}, which the extraction "
                f"did not produce")
        detected = group["studs"]
        curated = entry.get("studs")
        if detected is not None and curated is not None and detected != curated:
            raise BuildError(
                f"{entry['part']} (render {key}, shape {group['shape_id']}): "
                f"object_parts.toml says {curated} studs, the extraction "
                f"self-checked {detected}")
        if group["shape_id"] in by_shape:
            raise BuildError(
                f"shape {group['shape_id']} is named twice in object_parts.toml: "
                f"{by_shape[group['shape_id']]['part']} and {entry['part']}")
        by_shape[group["shape_id"]] = entry
    return by_shape


def _shape_record(group: dict[str, Any], curated: dict[str, Any] | None) -> dict[str, Any]:
    """One shape's stud count, with the provenance of that count.

    Three provenances, in descending strength:

    ``self_check``     every render of this shape counted its own studs and
                       ``rows * cols == count`` held
    ``shape_transfer`` at least one render self-checked and the rest inherit it
                       through the calibrated silhouette match
    ``curated``        no render self-checks — the count comes from the parts
                       inventory on pages 176-177 and is named in
                       ``object_parts.toml`` with its evidence

    The distinction is kept in the output because a consumer should be able to
    tell a verified count from a transcribed one.
    """
    clusters_in_group = {m[0] for m in group["members"]}
    if group["studs"] is not None:
        source = ("self_check"
                  if set(group["self_checked_from"]) == clusters_in_group
                  else "shape_transfer")
        studs, lattice = group["studs"], group["lattice"]
    elif curated is not None and curated.get("studs") is not None:
        source = "curated"
        studs, lattice = curated["studs"], curated.get("lattice")
    else:
        source, studs, lattice = None, None, None
    return {
        "shape_id": group["shape_id"],
        "size_px": group["size_px"],
        "studs": studs,
        "lattice": lattice,
        "count_source": source,
        "self_checked_from_clusters": group["self_checked_from"],
        "renders": len(group["members"]),
        "part": curated["part"] if curated else None,
        "lego_id": curated.get("lego_id") if curated else None,
        "pages": group["pages"],
    }


def _crosscheck(parts: dict[str, Any], clusters: Sequence[dict[str, Any]],
                objects: dict[str, Any]) -> list[dict[str, Any]]:
    """Verify the hand-transcribed inventory against the extraction."""
    by_cluster = {c["cluster_id"]: c for c in clusters}
    inventory = {(i["lego_id"], i["colour"]): i for i in parts["inventory"]}
    results = []
    for check in parts.get("crosschecks", []):
        key = (check["lego_id"], check["colour"])
        if key not in inventory:
            raise BuildError(f"crosscheck names {key}, absent from the inventory")
        stated = inventory[key]["quantity"]
        if stated != check["expect_quantity"]:
            raise BuildError(
                f"crosscheck for {key}: expects {check['expect_quantity']}, "
                f"the transcribed inventory says {stated}")
        kind = check["against"]
        if kind == "callout_pages":
            found = len(by_cluster[check["cluster_id"]]["pages"])
        elif kind == "object_count":
            found = len(check["object_ids"])
        elif kind == "object_count_times":
            found = len(check["object_ids"]) * check["per_object"]
        else:  # pragma: no cover - guarded by the schema test
            raise BuildError(f"unknown crosscheck kind {kind!r}")
        if found != stated:
            raise BuildError(
                f"crosscheck for {key}: inventory says {stated}, "
                f"the extraction counts {found} via {kind}")
        for oid in check.get("object_ids", []):
            if oid not in objects:
                raise BuildError(f"crosscheck names unknown object {oid!r}")
        results.append({"lego_id": check["lego_id"], "colour": check["colour"],
                        "quantity": stated, "against": kind, "agrees": True,
                        "note": check["note"].strip()})
    return results


def build(img_dir: Path, probe: Path, map_path: Path, parts_path: Path) -> dict[str, Any]:
    omap = tomllib.loads(map_path.read_text(encoding="utf-8"))
    parts = tomllib.loads(parts_path.read_text(encoding="utf-8"))

    pages = step_pages(img_dir)
    runs = run_boundaries(img_dir, pages)
    clusters, missing = cluster_callouts(img_dir, pages)

    groups = shape_groups(clusters)
    by_shape = _resolve_curated(parts, groups)
    shape_of_render = {m: g["shape_id"] for g in groups for m in g["members"]}

    # page -> the parts its callout shows, named where the curation reaches
    page_parts: dict[int, list[str]] = {}
    for cluster in clusters:
        names = []
        for member in sorted(m for m in shape_of_render if m[0] == cluster["cluster_id"]):
            shape = shape_of_render[member]
            entry = by_shape.get(shape)
            names.append(entry["part"] if entry else f"shape_{shape}")
        for page in cluster["pages"]:
            page_parts[page] = names

    # --- run boundaries must agree with the curated map -------------------- #
    # Every model AND every sub-assembly must begin on a page that actually
    # carries a run-preview box; the models must tile the build steps exactly;
    # and a sub-assembly must sit INSIDE the model it claims to belong to.
    preview_pages = {r["start"] for r in runs}
    models = {m["id"]: tuple(m["pages"]) for m in omap["models"]}
    for name, (lo, _hi) in models.items():
        if lo not in preview_pages:
            raise BuildError(
                f"{name} starts at page {lo}, which carries no run-preview box")
    flat = sorted((lo, hi, name) for name, (lo, hi) in models.items())
    if flat[0][0] != pages[0] or flat[-1][1] != pages[-1]:
        raise BuildError(
            f"the models cover {flat[0][0]}..{flat[-1][1]}, "
            f"the build steps are {pages[0]}..{pages[-1]}")
    for (a_lo, a_hi, a), (b_lo, _b_hi, b) in zip(flat, flat[1:]):
        if a_hi + 1 != b_lo:
            raise BuildError(f"{a} ends at {a_hi} but {b} starts at {b_lo}")

    for sub in omap["subassemblies"]:
        lo, hi = sub["pages"]
        if lo not in preview_pages:
            raise BuildError(
                f"{sub['id']} starts at page {lo}, which carries no run-preview box")
        parent = models.get(sub["inside"])
        if parent is None:
            raise BuildError(f"{sub['id']} claims to be inside unknown model "
                             f"{sub['inside']!r}")
        if not (parent[0] <= lo and hi <= parent[1]):
            raise BuildError(
                f"{sub['id']} spans {lo}..{hi}, outside its parent "
                f"{sub['inside']} ({parent[0]}..{parent[1]})")

    # Every preview page must be accounted for as either a model or a sub-run.
    claimed = {lo for lo, _hi in models.values()}
    claimed |= {s["pages"][0] for s in omap["subassemblies"]}
    if claimed != preview_pages:
        raise BuildError(
            f"run previews on {sorted(preview_pages - claimed)} are unaccounted "
            f"for; map claims previews on {sorted(claimed - preview_pages)} "
            f"that do not exist")

    objects: dict[str, Any] = {}
    for model in omap["models"]:
        lo, hi = model["pages"]
        bom: dict[str, int] = {}
        for page in range(lo, hi + 1):
            for name in page_parts.get(page, []):
                bom[name] = bom.get(name, 0) + 1

        base = model.get("base")
        entry: dict[str, Any] = {
            "source_pages": [lo, hi],
            "source_steps": model["steps"],
            "identification_confidence": model["confidence"],
            "identification_evidence": model["evidence"].strip(),
            "bom_steps": dict(sorted(bom.items())),
            # ADR-014 discipline: no number without a source. `mass_g` is read
            # from object_map.toml if a measurement has been recorded there and
            # is None otherwise -- it is never defaulted, because a plausible
            # placeholder is worse than an obvious gap. Work order item A2.
            "mass_g": (R(model["mass_g"]) if model.get("mass_g") is not None else None),
            "mass_source": model.get("mass_source"),
            "needs_measurement": model.get("mass_g") is None,
        }
        if base:
            entry["contact_footprint_studs"] = base["contact_studs"]
            entry["contact_footprint_mm"] = studs_to_mm(base["contact_studs"])
            # Work order item A4. Calipers measure the object directly, where
            # everything in Phase 4 came from counting studs in a raster and
            # multiplying by 8.00 mm. A caliper reading supersedes the derived
            # one -- and the derived one is KEPT, because a disagreement between
            # two independent methods is a finding, not a value to overwrite.
            measured = base.get("measured_contact_mm")
            if measured:
                entry["derived_contact_footprint_mm"] = entry["contact_footprint_mm"]
                entry["contact_footprint_mm"] = RS(measured)
                entry["contact_footprint_source"] = "MEASURED(calipers)"
                entry["contact_footprint_agrees_with_derived"] = bool(
                    all(abs(a - b) <= 0.5 for a, b in
                        zip(RS(measured), entry["derived_contact_footprint_mm"])))
                entry["measured_contact_evidence"] = base.get(
                    "measured_contact_evidence", "")
            else:
                entry["contact_footprint_source"] = "derived from stud count x 8.00 mm"
            entry["max_projection_studs"] = base["projection_studs"]
            entry["max_projection_mm"] = studs_to_mm(base["projection_studs"])
            entry["overhang_height_mm"] = R(base.get("overhang_height_mm", 0.0))
            entry["base_evidence"] = base["evidence"].strip()
            # ADR-017: a flexible element gets the rigid carrier's footprint.
            if base.get("flexible_element"):
                entry["flexible_element"] = True
                entry["hose_footprint_studs"] = None
                entry["footprint_covers"] = "the rigid carrier only"
            if base.get("per_instance"):
                entry["contact_patches"] = base["per_instance"]
                entry["pair_extent_known"] = bool(base.get("pair_extent_known", True))
        else:
            entry["contact_footprint_studs"] = None
            entry["contact_footprint_mm"] = None
            entry["max_projection_studs"] = None
            entry["max_projection_mm"] = None
            entry["footprint_needs_analysis"] = True
            pending = model.get("footprint_pending")
            if pending:
                bound = pending.get("fitted_extent_studs")
                entry["footprint_pending"] = {
                    "reason": pending["reason"],
                    "base_parts": pending["base_parts"].strip(),
                    "why_the_self_check_cannot_apply":
                        pending["why_the_self_check_cannot_apply"].strip(),
                    "upper_bound_studs": bound,
                    "upper_bound_mm": studs_to_mm(bound) if bound else None,
                    "upper_bound_is_not_a_measurement":
                        bool(pending.get("fitted_extent_is_a_bound")),
                    "bound_note": pending["bound_note"].strip(),
                }

        for oid in model.get("instances", [model["id"]]):
            objects[oid] = dict(entry)

    # ADR-018: sub-assemblies live beside `objects`, never inside it.
    subassemblies = {
        s["id"]: {
            "source_pages": s["pages"],
            "inside": s["inside"],
            "copies": s["copies"],
            "evidence": s["evidence"].strip(),
        }
        for s in omap["subassemblies"]
    }
    clash = set(subassemblies) & set(objects)
    if clash:
        raise BuildError(f"sub-assembly ids collide with object ids: {sorted(clash)}")

    scoring = omap["scoring_relevance"]
    missing_fp = [o for o in scoring["needs_containment"]
                  if objects[o]["contact_footprint_studs"] is None]

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
            "shape_slack_px": SHAPE_SLACK_PX,
            "shape_agree": SHAPE_AGREE,
        },
        "lego_geometry": {
            "stud_mm": STUD_MM,
            "plate_mm": PLATE_MM,
            "brick_mm": BRICK_MM,
            "source": "S4 7.4 — elements are WRO Brick Set 45811 / Expansion 45819",
        },
        "structure": {
            "build_step_pages": [pages[0], pages[-1]],
            "steps": len(pages),
            "inventory_pages": [176, 177],
            "runs": [{"start": r["start"], "end": r["end"],
                      "preview_px": [r["bbox"][2], r["bbox"][3]]} for r in runs],
        },
        "callout_inventory": {
            "build_pages": len(pages),
            "pages_with_callout": len(pages) - len(missing),
            "pages_without_callout": sorted(missing),
            "distinct_parts": len(clusters),
            "distinct_shapes": len(groups),
            "shapes": [_shape_record(g, by_shape.get(g["shape_id"]))
                       for g in sorted(groups, key=lambda g: g["shape_id"])],
        },
        "parts_inventory": {
            "source_pages": [176, 177],
            "elements": [
                {"lego_id": i["lego_id"], "colour": i["colour"],
                 "quantity": i["quantity"], "name": i["name"]}
                for i in sorted(parts["inventory"],
                                key=lambda i: (i["lego_id"], i["colour"]))
            ],
            "total_elements": sum(i["quantity"] for i in parts["inventory"]),
            "crosschecks": _crosscheck(parts, clusters, objects),
        },
        "objects": dict(sorted(objects.items())),
        "subassemblies": dict(sorted(subassemblies.items())),
        "scoring_relevance": {
            "needs_containment": sorted(scoring["needs_containment"]),
            "scored_by_not_moving": sorted(scoring["scored_by_not_moving"]),
            "containment_objects_without_a_footprint": sorted(missing_fp),
            "note": scoring["note"].strip(),
        },
        "cable_orientation": {k: v for k, v in omap["cable_orientation"].items()},
        "congas_pair_extent": {k: v for k, v in omap["congas_pair_extent"].items()},
        "unresolved": [],
        "notes": [
            "footprint = the CONTACT patch with the mat, not the silhouette. See the "
            "module docstring: eight models place a 4x8 plate ON TOP of a 4x4 core, so "
            "the plate overhangs at +9.6 mm and is not what touches the mat.",
            "mass_g is null for every object: it cannot be derived from a building "
            "instruction. It needs the physical sets on a scale (ADR-014 discipline).",
            "the clef, amp and both speakers score by NOT being moved (S1), so a "
            "missing footprint for them blocks no scoring path.",
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
    st = spec["structure"]
    print(f"{args.out}: {len(spec['objects'])} objects, "
          f"{len(spec['subassemblies'])} sub-assemblies, "
          f"{inv['distinct_shapes']} distinct part shapes")
    print(f"   {st['steps']} build steps on pages {st['build_step_pages'][0]}-"
          f"{st['build_step_pages'][1]}, {len(st['runs'])} runs, "
          f"inventory on {st['inventory_pages']}")
    for name, obj in sorted(spec["objects"].items()):
        fp = obj["contact_footprint_mm"]
        shown = f"{fp[0]:>5.1f} x {fp[1]:<6.1f} mm" if fp else "footprint pending"
        print(f"   {name:<22} {shown}")
    gap = spec["scoring_relevance"]["containment_objects_without_a_footprint"]
    print(f"   containment objects still without a footprint: {gap or 'none'}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
