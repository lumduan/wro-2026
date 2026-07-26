#!/usr/bin/env python3
"""Run the derived-artefact pipeline in dependency order.

    docs/area_map.toml ───► field_spec ──┐
                                         ├─► placement_sensitivity ─┬─► manipulator_requirements
    docs/object_map.toml ──► object_spec ┘        (slow, ~2.5 min)   └─► strategy_frame
                                                                            │
                                                    expected_score ◄────────┤
                                                          └─► round_strategy│
                                                       travel_budget ◄──────┘

Eight of the nine files in ``data/`` are derived. Nothing in the repo stated that
chain until this file, and running the builders out of order does **not** fail:
it silently leaves an artefact pinning a ``provenance`` sha that no longer
matches the file on disk. That happened while adding ``mass_g`` to
``object_spec.json`` — ``manipulator_requirements.json`` kept the old pin, and a
determinism sweep reported a bare "DRIFT" naming neither the artefact nor the
input.

So freshness is defined by the pins themselves: an artefact is **stale** when any
sha it records disagrees with the current file. That single definition drives all
three modes — report it (``--check``), act on it (default), or ignore it
(``--force``).

``data/scoring_model.json`` is **hand-authored** and deliberately absent from the
pipeline: it has no builder and no provenance block, because it is a
transcription of S1/S4/S6 rather than a derivation. ``tools/s6_index.py`` is also
separate — it takes a snapshot argument and is the network-facing half.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Sequence

ROOT: Final = Path(__file__).resolve().parents[1]

#: Hand-authored, not derived. Listed so its absence from the pipeline is a
#: recorded fact rather than an oversight.
HAND_AUTHORED: Final = ("data/scoring_model.json",)


@dataclass(frozen=True)
class Artefact:
    """One derived file, its builder, and where its provenance shas live."""

    name: str
    tool: str
    out: str
    #: provenance key -> path it pins. Empty means the artefact uses the
    #: ``provenance.inputs`` mapping, whose keys resolve by convention.
    pin_map: dict[str, str] = field(default_factory=dict)
    slow: bool = False


#: The chain, in dependency order. `tests/test_pipeline.py` asserts this matches
#: what the artefacts actually pin, so the declaration cannot drift from reality.
PIPELINE: Final = (
    Artefact("field_spec", "build_field_spec", "data/field_spec.json", pin_map={
        "drawings_json_sha256":
            "docs/extracted/WRO-2026-GameMat-Elementary-Printing-File/vector/drawings.json",
        "s2_sha256": "docs/WRO-2026-GameMat-Elementary-Printing-File.pdf",
    }),
    Artefact("object_spec", "build_object_spec", "data/object_spec.json", pin_map={
        "object_map_sha256": "docs/object_map.toml",
        "object_parts_sha256": "docs/object_parts.toml",
        "s3_sha256": "docs/WRO-2026-RM-Elementary-BI-All.pdf",
    }),
    Artefact("placement_sensitivity", "run_sensitivity",
             "data/placement_sensitivity.json", slow=True),
    Artefact("manipulator_requirements", "build_manipulator_requirements",
             "data/manipulator_requirements.json"),
    Artefact("strategy_frame", "build_strategy_frame", "data/strategy_frame.json"),
    Artefact("expected_score", "build_expected_score", "data/expected_score.json"),
    Artefact("round_strategy", "build_round_strategy", "data/round_strategy.json"),
    Artefact("travel_budget", "build_travel_budget", "data/travel_budget.json"),
)

#: `provenance.inputs` keys are logical names; these are the files they mean.
INPUT_PATHS: Final = {
    "field_spec": "data/field_spec.json",
    "object_spec": "data/object_spec.json",
    "scoring_model": "data/scoring_model.json",
    "placement_sensitivity": "data/placement_sensitivity.json",
    "strategy_frame": "data/strategy_frame.json",
    "expected_score": "data/expected_score.json",
}


def sha256_of(path: Path) -> str | None:
    """None when the file is absent — source PDFs are gitignored (ADR-001)."""
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pins(artefact: Artefact) -> dict[str, str]:
    """path -> pinned sha, across both provenance shapes the repo uses."""
    out_path = ROOT / artefact.out
    if not out_path.exists():
        return {}
    provenance = json.loads(out_path.read_text(encoding="utf-8")).get("provenance", {})
    recorded: dict[str, str] = {}
    for key, path in artefact.pin_map.items():
        if key in provenance:
            recorded[path] = provenance[key]
    for name, sha in (provenance.get("inputs") or {}).items():
        if name in INPUT_PATHS:
            recorded[INPUT_PATHS[name]] = sha
    return recorded


def staleness(artefact: Artefact) -> list[str]:
    """Human-readable reasons this artefact needs rebuilding. Empty means fresh."""
    out_path = ROOT / artefact.out
    if not out_path.exists():
        return ["output does not exist"]
    recorded = pins(artefact)
    if not recorded:
        return ["no provenance pins found — cannot verify"]
    reasons = []
    for path, pinned in sorted(recorded.items()):
        actual = sha256_of(ROOT / path)
        if actual is None:
            continue          # gitignored source; unverifiable, not stale
        if actual != pinned:
            reasons.append(f"pins a stale {path}")
    return reasons


def run(artefact: Artefact) -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "tools" / f"{artefact.tool}.py")],
        cwd=ROOT, check=True, stdout=subprocess.DEVNULL)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="report staleness and exit 1; write nothing")
    parser.add_argument("--force", action="store_true",
                        help="rebuild everything, including the slow sweep")
    args = parser.parse_args(argv)

    report = [(a, staleness(a)) for a in PIPELINE]

    if args.check:
        stale = [(a, why) for a, why in report if why]
        for artefact, why in report:
            mark = "STALE" if why else "fresh"
            print(f"  {mark:>5}  {artefact.name}")
            for reason in why:
                print(f"         {reason}")
        if stale:
            print(f"\n{len(stale)} of {len(PIPELINE)} artefacts are stale. "
                  f"Run `uv run python tools/build_all.py` to rebuild them.")
            return 1
        print(f"\nall {len(PIPELINE)} derived artefacts are fresh")
        return 0

    built = 0
    for artefact, why in report:
        # Recompute rather than trusting the pre-run report: rebuilding an
        # upstream artefact is exactly what makes a downstream one stale.
        why = [] if not args.force else ["--force"]
        if not args.force:
            why = staleness(artefact)
        if not why:
            print(f"  skip   {artefact.name} (fresh)")
            continue
        note = " — slow, ~2.5 min" if artefact.slow else ""
        print(f"  build  {artefact.name}{note}")
        run(artefact)
        built += 1

    print(f"\n{built} rebuilt, {len(PIPELINE) - built} already fresh")
    for path in HAND_AUTHORED:
        print(f"  (not built: {path} is hand-authored — a transcription, not a derivation)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
