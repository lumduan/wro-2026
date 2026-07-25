#!/usr/bin/env python3
"""Index an S6 (official Q&A) snapshot into a diffable provenance file.

S6 sits at the top of the source hierarchy (S4 §4.4: general rules < game document
< Q&A < judge on the day) and it is **live and unversioned**, so change detection
has to be reliable.

Do NOT diff on the page's ``Last-Modified`` header: on a WordPress site that is a
render/cache timestamp and moves on plugin, theme and footer edits. Observed
directly while building this: the header read ``Mon, 13 Jul 2026`` while the
content field ``article:modified_time`` still read ``2026-06-30T16:45:33+02:00``.

The durable diff target is the per-answer tuple::

    (section, question, author, iso_timestamp)

which is immune to theme churn and detects a genuinely new entry -- something a
page-level header cannot distinguish from a CSS change.

Answer *bodies* are deliberately not stored: they are WRO's text. Short
identifying quotes belong in ``docs/citations.json`` under its word cap.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from pdf_extract import json_bytes, sha256_file  # noqa: E402  (shared helpers)

TOOL_VERSION = "1.0.0"
SCHEMA_VERSION = 1

#: question ... author ... ISO-8601 timestamp, each in its own element.
_ENTRY_RE = re.compile(
    r">([^<>]{20,600}?)<[^>]*>(?:\s*<[^>]*>)*\s*"
    r"([A-Za-z][A-Za-z .'À-ɏ-]{2,40})<[^>]*>(?:\s*<[^>]*>)*\s*"
    r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2})<"
)
_MODIFIED_RE = re.compile(r'article:modified_time"\s*content="([^"]+)"')


def parse(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    entries: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for match in _ENTRY_RE.finditer(raw):
        question = html.unescape(re.sub(r"\s+", " ", match.group(1))).strip()
        author = html.unescape(match.group(2)).strip()
        stamp = match.group(3)
        key = (question[:120], stamp)
        if key in seen:
            continue
        seen.add(key)
        entries.append({"question": question, "author": author, "timestamp": stamp})
    entries.sort(key=lambda e: (e["timestamp"], e["question"]))

    modified = _MODIFIED_RE.findall(raw)
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": {"name": "s6_index", "version": TOOL_VERSION},
        "source": {
            "name": path.name,
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "url": "https://wro-association.org/competition/questions-answers/",
        },
        "article_modified_time": sorted(set(modified)),
        "note": (
            "Diff on `entries`, never on the HTTP Last-Modified header - that is a "
            "render/cache timestamp on this site and moves independently of content."
        ),
        "entry_count": len(entries),
        "entries": entries,
    }


def _key(entry: dict[str, str]) -> tuple[str, str, str]:
    return (entry["timestamp"], entry["author"], entry["question"][:160])


def check(snapshot: Path, committed: Path) -> int:
    """Diff a fresh snapshot against the committed index. **Both directions.**

    Guarding only against disappearance is the trap: a *new* answer is the whole
    reason to re-read S6, and S6 outranks S4. An eleventh entry must pause and
    report, not pass silently.
    """
    fresh = {_key(e): e for e in parse(snapshot)["entries"]}
    known = {_key(e): e for e in json.loads(committed.read_text())["entries"]}

    added = [fresh[k] for k in fresh.keys() - known.keys()]
    removed = [known[k] for k in known.keys() - fresh.keys()]

    if not added and not removed:
        print(f"S6 unchanged: {len(fresh)} entries match {committed}")
        return 0

    print(f"S6 CHANGED - {len(added)} added, {len(removed)} removed")
    for entry in sorted(added, key=lambda e: e["timestamp"]):
        print(f"  + {entry['timestamp']}  {entry['author']:<20} {entry['question'][:70]}")
    for entry in sorted(removed, key=lambda e: e["timestamp"]):
        print(f"  - {entry['timestamp']}  {entry['author']:<20} {entry['question'][:70]}")
    print("\nS6 outranks S1 and S4 (S4 4.4). Re-read before any scoring or")
    print("robot-limit claim, then regenerate docs/s6_index.json.")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("-o", "--out", type=Path, default=Path("docs/s6_index.json"))
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare against the committed index; exit 1 on ANY delta. "
             "Network-facing, so it is a manual/scheduled step, never part of pytest.",
    )
    args = parser.parse_args(argv)

    if args.check:
        return check(args.snapshot, args.out)

    index = parse(args.snapshot)
    args.out.write_bytes(json_bytes(index))
    print(f"{index['entry_count']} entries -> {args.out}")
    for entry in index["entries"]:
        print(f"  {entry['timestamp']}  {entry['author']:<20} {entry['question'][:74]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
