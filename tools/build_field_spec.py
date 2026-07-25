#!/usr/bin/env python3
"""Build ``data/field_spec.json`` (S5) from the S2 vector dump plus an area map.

    vector/drawings.json ─┐
                          ├─► build_field_spec.py ─► data/field_spec.json
    docs/area_map.toml   ─┘

**No coordinates are written by hand.** ``area_map.toml`` carries only human
judgement — which canonical ID corresponds to which drawn path, and why. Every
number in the output is re-derived from the extraction, and a selector that does
not resolve to exactly the declared number of paths is a hard failure. A silent
near-miss is the failure mode this design exists to prevent.

Coordinates arrive already in the MAT frame: ``pdf_extract.py`` converted them
once via :class:`~pdf_extract.MatFrame`, and there is deliberately **no second
transform** anywhere in this repo.

Key decisions, all recorded in ``docs/DECISIONS.md``:

* **ADR-013** — every area declares ``scoring`` explicitly, and the schema always
  emits *both* ``polygon_constructed_mm`` and ``polygon_visible_mm``.
  ``polygon_mm`` does not exist, so no invariant can read a field that may be
  absent. ``area_mm2`` binds to *constructed*, because that is what the dump
  cross-check compares against.
* **ADR-014** — object start poses are ``nominal_start_pose_mm`` +
  ``placement_tolerance_mm``; the real initial pose is run-time state.
* **ADR-015** — the selector predicate is fill **and** size **and** position;
  ``match`` governs the full predicate, not the fill alone. ``inset_by`` consumes
  a measured *vertex*, never an area subtraction.
* **ADR-008** — output precision, which is why the provenance block pins it.

Areas are computed by shoelace over the **emitted, rounded** polygon, so
``area_mm2 == w*h`` holds exactly for rectangles. The dump's own ``area_mm2`` is
shoelace over *unrounded* points, so the two differ by a bounded rounding
residue — kept as a cross-check rather than hidden, see :func:`cross_check_bound`.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any, Final, Iterable, Sequence

sys.path.insert(0, str(Path(__file__).parent))
from pdf_extract import (  # noqa: E402  — shared helpers, never reimplemented
    BEZIER_SEGMENTS,
    R,
    RS,
    flatten_cubic,
    json_bytes,
    polygon_area,
    set_precision,
)

TOOL_VERSION: Final = "1.0.0"
SCHEMA_VERSION: Final = 1

#: ADR-015. Justified by a sweep over four orders of magnitude, not fitted to the
#: single known case: the positive fires from 0.02 mm (the real edge delta is
#: 0.013) and holds to 10 mm, while every other scoring area stays negative at
#: every tolerance from 0.001 to 10 mm.
BORDER_MATCH_TOL_MM: Final = 0.5

#: A fill counts as a border, not a region, below this area/bbox ratio.
BORDER_AREA_RATIO: Final = 0.5

DEFAULT_DUMP: Final = Path(
    "docs/extracted/WRO-2026-GameMat-Elementary-Printing-File/vector/drawings.json"
)
DEFAULT_MANIFEST: Final = Path(
    "docs/extracted/WRO-2026-GameMat-Elementary-Printing-File/manifest.json"
)
DEFAULT_IMG_DIR: Final = Path(
    "docs/extracted/WRO-2026-GameMat-Elementary-Printing-File/img"
)
DEFAULT_MAP: Final = Path("docs/area_map.toml")
DEFAULT_OUT: Final = Path("data/field_spec.json")


class BuildError(SystemExit):
    """A selector failed to resolve. Never downgraded to a warning."""


# --------------------------------------------------------------------------- #
# Geometry helpers
# --------------------------------------------------------------------------- #


def polygon_from_items(path: dict[str, Any]) -> list[list[float]]:
    """Emit the path's outline as a rounded polygon, in draw order.

    Curves are already flattened in the dump; here we only need the vertices the
    spec will publish, so downstream shoelace runs on exactly what was written.
    """
    points: list[tuple[float, float]] = []
    for item in path["items"]:
        op = item["op"]
        if op == "re":
            x0, y0, x1, y1 = item["rect_mm"]
            points += [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        elif op == "l":
            if not points:
                points.append(tuple(item["p1_mm"]))
            points.append(tuple(item["p2_mm"]))
        elif op == "c":
            # Flatten with the SAME fixed subdivision the dump used (ADR-004).
            # Collapsing a cubic to its endpoint silently loses real area: the
            # stage's curved right edge is 34,509 mm2 of it, and the loss would
            # never show up in any self-consistent check.
            p1 = tuple(item["p1_mm"])
            if not points:
                points.append(p1)
            points.extend(
                flatten_cubic(
                    p1,
                    tuple(item["p2_mm"]),
                    tuple(item["p3_mm"]),
                    tuple(item["p4_mm"]),
                    BEZIER_SEGMENTS,
                )
            )
        elif op == "qu":
            points += [tuple(p) for p in item["quad_mm"]]

    # Drop a duplicated closing vertex; shoelace closes the ring itself.
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    return [RS(p) for p in points]


def perimeter_mm(polygon: Sequence[Sequence[float]]) -> float:
    total = 0.0
    for i, point in enumerate(polygon):
        nxt = polygon[(i + 1) % len(polygon)]
        total += ((nxt[0] - point[0]) ** 2 + (nxt[1] - point[1]) ** 2) ** 0.5
    return total


def cross_check_bound(polygon: Sequence[Sequence[float]], precision: int) -> float:
    """Max legitimate gap between spec area and the dump's own pre-clip area.

    Each emitted coordinate is rounded to ``precision`` decimals, so it carries at
    most ``0.5e-precision`` of error; propagated through a shoelace the residue is
    bounded by that times the perimeter. **Derived from the precision, not
    chosen** — which is the whole point of keeping this check.
    """
    delta = 0.5 * 10 ** (-precision)
    return delta * perimeter_mm(polygon)


def bbox_of(polygon: Iterable[Sequence[float]]) -> list[float]:
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return RS((min(xs), min(ys), max(xs), max(ys)))


# --------------------------------------------------------------------------- #
# Clip stack — ADR-013
# --------------------------------------------------------------------------- #


def clip_state(paths: list[dict[str, Any]]) -> dict[int, list[list[float]]]:
    """Active clip scissors per painted path, honouring ``q``/``Q`` scoping.

    A clip leaves scope as soon as an entry at a level less than or equal to its
    own appears. Getting this wrong is not academic: a naive "every earlier clip"
    reading reports thousands of active clips for a level-0 path and would mark
    every area clip-divergent.
    """
    active: list[tuple[int, list[float]]] = []
    out: dict[int, list[list[float]]] = {}
    for entry in sorted(paths, key=lambda p: p["seqno"]):
        level = int(entry.get("level", 0))
        active = [c for c in active if c[0] < level]
        if entry["type"] == "clip":
            if entry.get("scissor_mm"):
                active.append((level, entry["scissor_mm"]))
            continue
        out[entry["seqno"]] = [c[1] for c in active]
    return out


def intersect(a: Sequence[float], b: Sequence[float]) -> list[float]:
    return [max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])]


def contains(outer: Sequence[float], inner: Sequence[float], tol: float = 1e-6) -> bool:
    return (
        outer[0] <= inner[0] + tol
        and outer[1] <= inner[1] + tol
        and outer[2] >= inner[2] - tol
        and outer[3] >= inner[3] - tol
    )


# --------------------------------------------------------------------------- #
# Selector resolution — ADR-015
# --------------------------------------------------------------------------- #


def _size_of(path: dict[str, Any]) -> tuple[float, float]:
    b = path["bbox_mm"]
    return (b[2] - b[0], b[3] - b[1])


def _centre_of(path: dict[str, Any]) -> tuple[float, float]:
    b = path["bbox_mm"]
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def resolve(name: str, spec: dict[str, Any], paths: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resolve one selector. Hard-fails unless the count is exactly as declared.

    The predicate is fill **and** size **and** position — all three. Fill alone is
    ambiguous almost everywhere and the ambiguity carries points: ``#4e5252`` has
    six paths of identical size and ``#b5b5b6`` two, so 150 of 255 points are
    separated by position only.
    """
    fill = spec["select"]
    match = spec.get("match", "exact")
    candidates = [p for p in paths if p.get("fill_hex") == fill and p["type"] != "clip"]

    if size := spec.get("size_mm"):
        tol = float(spec.get("size_tol_mm", 0.05))
        candidates = [
            p
            for p in candidates
            if abs(_size_of(p)[0] - size[0]) <= tol and abs(_size_of(p)[1] - size[1]) <= tol
        ]
    if at := spec.get("at_mm"):
        tol = float(spec.get("at_tol_mm", 2.0))
        candidates = [
            p
            for p in candidates
            if abs(_centre_of(p)[0] - at[0]) <= tol and abs(_centre_of(p)[1] - at[1]) <= tol
        ]

    if match == "union":
        expect = spec.get("expect_paths")
        if expect is None:
            raise BuildError(f"{name}: match='union' requires expect_paths (ADR-015)")
        if len(candidates) != int(expect):
            raise BuildError(
                f"{name}: union selector resolved {len(candidates)} paths, "
                f"expect_paths={expect}"
            )
        if want := spec.get("union_bbox_mm"):
            got = bbox_of([pt for p in candidates for pt in polygon_from_items(p)])
            tol = float(spec.get("union_bbox_tol_mm", BORDER_MATCH_TOL_MM))
            if any(abs(got[i] - want[i]) > tol for i in range(4)):
                raise BuildError(
                    f"{name}: union bbox {got} != declared {want} (tol {tol})"
                )
        return candidates

    if match == "largest":
        if not candidates:
            raise BuildError(f"{name}: selector matched no paths")
        return [max(candidates, key=lambda p: p["area_mm2"])]

    if len(candidates) != 1:
        raise BuildError(
            f"{name}: selector resolved {len(candidates)} paths, expected exactly 1. "
            "The predicate is fill AND size AND position (ADR-015)."
        )
    return candidates


def inner_vertex(
    band: dict[str, Any], anchor: Sequence[float], base_bbox: Sequence[float]
) -> tuple[float, float]:
    """The band's inner corner — the vertex furthest from the anchor corner.

    ``backstage`` is S1's pink area *excluding* its grey border, and that polygon
    is not any path in the dump. Deriving it by subtracting the band's area gives
    124,920.48 instead of the correct 124,923.697, because the band overruns the
    pink by 0.013 mm and the L-corner is not a clean rectangle difference. So the
    inset consumes a **measured vertex** instead (ADR-015).
    """
    eps = 1e-6
    verts = polygon_from_items(band)
    # Strictly inside the base on both axes: that excludes the band's own outer
    # corners, which sit ON (or just past) the base edges.
    inside = [
        v for v in verts
        if v[0] < base_bbox[2] - eps and v[1] < base_bbox[3] - eps
    ]
    if not inside:
        raise BuildError("inset_by: the band has no vertex strictly inside the base")
    # Among those, the inner corner is the one FURTHEST from the anchor corner.
    return max(inside, key=lambda v: (v[0] - anchor[0]) ** 2 + (v[1] - anchor[1]) ** 2)


def find_border(area_bbox: Sequence[float], fill: str, paths: list[dict[str, Any]]) -> dict | None:
    """Border signature: different hex, bbox matching on all four edges, thin.

    ``backstage``'s border was originally found by accident. This is the reusable
    form, run over every scoring area so a border in a future mat revision cannot
    slip through the same way.
    """
    for path in paths:
        if path.get("fill_hex") in (None, fill) or path["type"] == "clip":
            continue
        b = path["bbox_mm"]
        if all(abs(b[i] - area_bbox[i]) <= BORDER_MATCH_TOL_MM for i in range(4)):
            ratio = path["area_mm2"] / max(path["bbox_area_mm2"], 1e-9)
            if ratio < BORDER_AREA_RATIO:
                return path
    return None


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #


def build_area(
    name: str,
    spec: dict[str, Any],
    paths: list[dict[str, Any]],
    clips: dict[int, list[list[float]]],
    precision: int,
) -> dict[str, Any]:
    resolved = resolve(name, spec, paths)

    # The border signature must be tested against the SELECTED FILL's extent, not
    # against the final polygon: for an inset area the final bbox is already
    # inside the border, so it could never match the band that frames it.
    select_bbox = resolved[0]["bbox_mm"] if len(resolved) == 1 else None

    if spec.get("inset_by"):
        base = resolved[0]
        band = resolve(
            f"{name}.inset_by", {"select": spec["inset_by"]}, paths
        )[0]
        bb = base["bbox_mm"]
        vx, vy = inner_vertex(band, (bb[0], bb[1]), bb)
        polygon = [RS(p) for p in ((bb[0], bb[1]), (vx, bb[1]), (vx, vy), (bb[0], vy))]
        dump_area = None  # the inset is not a drawn path; no dump area to compare
        seqnos = [base["seqno"], band["seqno"]]
    elif len(resolved) == 1:
        polygon = polygon_from_items(resolved[0])
        dump_area = resolved[0]["area_mm2"]
        seqnos = [resolved[0]["seqno"]]
    else:  # union
        polygon = None
        dump_area = sum(p["area_mm2"] for p in resolved)
        seqnos = sorted(p["seqno"] for p in resolved)

    if polygon is not None:
        constructed = polygon
        area = R(polygon_area([tuple(p) for p in constructed]))
        bbox = bbox_of(constructed)
    else:
        constructed = None
        area = R(dump_area)
        bbox = bbox_of([pt for p in resolved for pt in polygon_from_items(p)])

    # ADR-013: both polygon fields ALWAYS, equal when there is no divergence.
    scissors = [s for p in resolved for s in clips.get(p["seqno"], [])]
    divergent = bool(constructed) and any(not contains(s, bbox) for s in scissors)
    visible = constructed
    if divergent and constructed:
        box = bbox
        for scissor in scissors:
            box = intersect(box, scissor)
        visible = [RS(p) for p in ((box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3]))]

    entry: dict[str, Any] = {
        "id": name,
        "scoring": bool(spec["scoring"]),
        "selector": {k: v for k, v in spec.items() if k != "scoring"},
        "bbox_mm": bbox,
        "area_mm2": area,
        "clip_divergent": divergent,
        "source_seqnos": seqnos,
    }
    if constructed is not None:
        entry["polygon_constructed_mm"] = constructed
        entry["polygon_visible_mm"] = visible
        entry["vertex_count"] = len(constructed)
        if dump_area is not None:
            entry["dump_area_mm2"] = dump_area
            entry["dump_area_delta_mm2"] = R(abs(area - dump_area))
            entry["dump_area_bound_mm2"] = R(cross_check_bound(constructed, precision))
    else:
        entry["polygons_constructed_mm"] = [polygon_from_items(p) for p in resolved]
        entry["polygons_visible_mm"] = entry["polygons_constructed_mm"]
        entry["path_count"] = len(resolved)

    probe_bbox = select_bbox if select_bbox is not None else bbox
    if border := find_border(probe_bbox, spec["select"], paths) if spec.get("select") else None:
        entry["border_detected"] = {
            "fill_hex": border["fill_hex"],
            "area_mm2": border["area_mm2"],
            "handled_by_inset": bool(spec.get("inset_by")),
        }
    return entry


def require_outputs(manifest: dict[str, Any], keys: Sequence[str], path: Path) -> None:
    """Fail clearly when the manifest does not describe a full extraction.

    ``manifest.json`` records the **last** command run, not a merged history —
    deliberately, because a merged manifest would depend on run order and destroy
    the byte-identity guarantee. The consequence is that a later ``probe`` run
    truncates it, and the provenance chain this builder pins would silently lose
    its anchors. Better to say so than to emit a spec with half a chain.
    """
    missing = [k for k in keys if k not in manifest.get("outputs", {})]
    if missing:
        raise BuildError(
            f"{path} describes command '{manifest.get('run', {}).get('command')}' and is "
            f"missing {missing}.\n"
            "field_spec.json pins the whole extraction chain, so it needs a manifest from "
            "a full run:\n"
            "    uv run python tools/pdf_extract.py all "
            "docs/WRO-2026-GameMat-Elementary-Printing-File.pdf"
        )


def build(
    dump_path: Path,
    manifest_path: Path,
    img_dir: Path,
    map_path: Path,
    precision: int,
) -> dict[str, Any]:
    set_precision(precision)
    dump = json.loads(dump_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    amap = tomllib.loads(map_path.read_text())

    raster_ids = [
        s["select_raster"] for s in amap.get("areas", {}).values() if s.get("select_raster")
    ]
    require_outputs(
        manifest,
        ["vector/drawings.json", *(f"img/{r}.json" for r in raster_ids)],
        manifest_path,
    )

    paths = dump["paths"]
    painted = [p for p in paths if p["type"] != "clip"]
    clips = clip_state(paths)
    frame = dump["pages"][0]["frame"]
    mat_w, mat_h = frame["box_used_mm_size"]

    areas: dict[str, Any] = {}
    for name, spec in sorted(amap.get("areas", {}).items()):
        if spec.get("select_raster"):
            sidecar = json.loads((img_dir / f"{spec['select_raster']}.json").read_text())
            rect = sidecar["placement_mm"][0]
            polygon = [RS(p) for p in ((rect[0], rect[1]), (rect[2], rect[1]),
                                       (rect[2], rect[3]), (rect[0], rect[3]))]
            areas[name] = {
                "id": name,
                "scoring": bool(spec["scoring"]),
                "selector": {k: v for k, v in spec.items() if k != "scoring"},
                "polygon_constructed_mm": polygon,
                "polygon_visible_mm": polygon,
                "bbox_mm": bbox_of(polygon),
                "area_mm2": R(polygon_area([tuple(p) for p in polygon])),
                "size_mm": RS((rect[2] - rect[0], rect[3] - rect[1])),
                "clip_divergent": False,
                "vertex_count": 4,
                "raster_source": spec["select_raster"],
                "needs_verify": "S6-startarea",
            }
            continue
        areas[name] = build_area(name, spec, painted, clips, precision)

    note_starts: dict[str, Any] = {}
    for name, spec in sorted(amap.get("note_starts", {}).items()):
        path = resolve(name, spec, painted)[0]
        polygon = polygon_from_items(path)
        entry = {
            "id": name,
            "centre_mm": RS(_centre_of(path)),
            "size_mm": RS(_size_of(path)),
            "polygon_constructed_mm": polygon,
            "polygon_visible_mm": polygon,
            "fill_hex": path["fill_hex"],
            "randomizable": bool(spec["randomizable"]),
        }
        if spec.get("note"):
            entry["note_id"] = spec["note"]
        note_starts[name] = entry

    # ADR-014: the real initial pose is RUN-TIME state (S4 10.8 scores the
    # end-of-attempt field state; 9.6 has judges re-set tables between rounds).
    # The spec therefore carries a nominal + tolerance, never a authoritative
    # constant -- and where no measurement exists yet it says so rather than
    # inventing a coordinate. `moved` always compares against THAT RUN's initial
    # pose, so low absolute precision here costs nothing (see ADR-014).
    fixed_notes = {
        v["note_id"]: k for k, v in note_starts.items() if v.get("note_id")
    }
    randomized_notes = ["note_black", "note_white", "note_yellow", "note_blue"]
    nominal_only = {
        "cable_upper": "S1 p4: close to the stage (left end), upper end of the field",
        "cable_lower": "S1 p4: close to the stage (left end), lower end of the field",
        "mic": "S1 p4: lower end, in the truck",
        "instrument_guitar": "S1 p4: lower end, in the truck",
        "instrument_keyboard": "S1 p4: lower end, in the truck",
        "instrument_congas": "S1 p4: lower end, in the truck",
        "clef": "S1 p6: middle, at the left end of the staff lines",
        "amp": "S1 p6: on the stage, left end of the field",
        "speaker_a": "S1 p6: on the stage, left end of the field",
        "speaker_b": "S1 p6: on the stage, left end of the field",
    }

    object_start_poses: dict[str, Any] = {}
    for note, slot in sorted(fixed_notes.items()):
        object_start_poses[note] = {
            "kind": "measured",
            "start_id": slot,
            "nominal_start_pose_mm": note_starts[slot]["centre_mm"],
            "placement_tolerance_mm": None,
            "source": "S2 measured start square",
        }
    for note in randomized_notes:
        object_start_poses[note] = {
            "kind": "randomized",
            "candidate_slots": sorted(k for k, v in note_starts.items() if v["randomizable"]),
            "nominal_start_pose_mm": None,
            "source": "S1 p7 — assigned at randomization, so there is no fixed pose",
        }
    for obj, where in sorted(nominal_only.items()):
        object_start_poses[obj] = {
            "kind": "nominal_pending",
            "nominal_start_pose_mm": None,
            "placement_tolerance_mm": None,
            "needs_measurement": True,
            "source": where,
            "note": (
                "No marker exists on the mat for this object (see ADR-012 on the four "
                "unassigned markers). A coordinate is NOT invented here; measure it from "
                "a set-up table (FIELD_TEST_PLAN P4) or S1 photography."
            ),
        }
    object_start_poses["robot"] = {
        "kind": "start_area",
        "area_id": "start_area",
        "source": "S4 7.8 — projection completely within the start area",
    }

    randomizable = [k for k, v in note_starts.items() if v["randomizable"]]
    permutations = 1
    for i in range(1, len(randomizable) + 1):
        permutations *= i

    spec_out = {
        "schema_version": SCHEMA_VERSION,
        "provenance": {
            "tool": {"name": "build_field_spec", "version": TOOL_VERSION},
            "source": "S2",
            "s2_sha256": manifest["source"]["sha256"],
            "drawings_json_sha256": manifest["outputs"]["vector/drawings.json"]["sha256"],
            "extraction_argv": manifest["run"]["argv"],
            "extraction_precision": manifest["run"]["precision"],
            "output_precision": precision,
            "area_map": str(map_path),
            "start_area_sidecar_sha256": manifest["outputs"][
                "img/p001_3832.json"
            ]["sha256"],
        },
        "mat": {
            "width_mm": R(mat_w),
            "height_mm": R(mat_h),
            "frame": "origin bottom-left of the mat, +X right, +Y up, mm",
            "box_source": frame["box_source"],
        },
        "table": {
            "tolerance_mm": 5.0,
            "wall_height_mm": 50.0,
            "registration": {"x": "right_wall", "y": "centred"},
            "source": "S4 7.2 + S1 p3",
            "note": (
                "The table may exceed the mat by up to 5 mm per dimension and the mat "
                "registers against the RIGHT wall with Y centred, so slack accumulates "
                "toward -X. The stage-side missions (cables, mic, backstage, all at "
                "x < 535) sit at the far end of that error chain."
            ),
        },
        "areas": areas,
        "note_starts": note_starts,
        "object_start_poses": object_start_poses,
        "randomization": {
            "randomizable_slots": sorted(randomizable),
            "notes": ["note_black", "note_white", "note_yellow", "note_blue"],
            "fixed": {"note_red": "note_start_fixed_red", "note_green": "note_start_fixed_green"},
            "permutations": permutations,
            "source": "S1 p7",
            "note": (
                "S4 9.6 randomizes AFTER quarantine and 10.2 forbids entering data by "
                "moving robot parts, so the permutation can only be resolved by runtime "
                "sensing."
            ),
        },
        "start_groups": {
            name: {"kind": grp["kind"], "members": grp["members"], "source": grp["source"]}
            for name, grp in sorted(amap.get("start_groups", {}).items())
        },
        "notes": [
            "ADR-013: `scoring` is explicit on every area; completely_in ranges over "
            "scoring=true only. polygon_mm does not exist - both polygon fields are "
            "always emitted.",
            "ADR-014: object start poses are run-time state; nominal + tolerance only.",
            "AMBIGUITY(A9): the start-area boundary is measured; S4 7.8's 'white area' "
            "interpretation is open - 29.56% of that interior is not white.",
        ],
    }
    return spec_out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump", type=Path, default=DEFAULT_DUMP)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--img-dir", type=Path, default=DEFAULT_IMG_DIR)
    parser.add_argument("--area-map", type=Path, default=DEFAULT_MAP)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--precision", type=int, default=3)
    args = parser.parse_args(argv)

    spec = build(args.dump, args.manifest, args.img_dir, args.area_map, args.precision)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(json_bytes(spec))

    scoring = [a for a in spec["areas"].values() if a["scoring"]]
    print(f"{args.out}: {len(spec['areas'])} areas ({len(scoring)} scoring), "
          f"{len(spec['note_starts'])} note starts, "
          f"{spec['randomization']['permutations']} permutations")
    for name, area in sorted(spec["areas"].items()):
        flag = "S" if area["scoring"] else "-"
        extra = " CLIP-DIVERGENT" if area["clip_divergent"] else ""
        print(f"  [{flag}] {name:<22} area={area['area_mm2']:>10.3f} mm2{extra}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
