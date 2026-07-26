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

**Parsing is structural, and that is a correction (2026-07-27).** The first
version matched a generic ``>text< ... >name< ... >timestamp<`` shape anywhere on
the page. That also matched the page's own JSON-LD ``schema.org`` block, adding a
tenth phantom entry::

    admin | "Questions & Answers" | 2026-06-30T18:45:33+02:00

whose timestamp **is** the page's modified time. So a theme or footer edit moved
the phantom and ``--check`` reported a content change that had not happened --
exactly the false positive the paragraph above was written to prevent,
reintroduced through the back door. Anchoring on the FAQ panel markup fixes it,
and the panel's CSS class also carries the **age group**, which the diff tuple
always claimed to include and never did.
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

TOOL_VERSION = "2.0.0"
SCHEMA_VERSION = 2

#: One FAQ answer, anchored on its own panel. The page wraps every answer in
#: ``<div class="... fusion-faq-post fusion-faq-post-NNNN AGEGROUP">`` followed
#: immediately by three hidden rich-snippet spans.
_PANEL_RE = re.compile(
    r'fusion-faq-post-(\d+)\s+([a-z0-9 _-]*?)"\s*>\s*'
    r'<span class="entry-title[^"]*">(.*?)</span>\s*'
    r'<span class="vcard[^"]*">\s*<span class="fn">\s*<a[^>]*>(.*?)</a>\s*</span>\s*</span>\s*'
    r'<span class="updated[^"]*">\s*([0-9T:+\-]{20,})\s*</span>',
    re.S,
)
_MODIFIED_RE = re.compile(r'article:modified_time"\s*content="([^"]+)"')

#: Panel CSS class -> the section heading the page shows.
SECTION_NAMES = {
    "robomission": "RoboMission - All Age Groups",
    "robomission-elementary": "RoboMission - Elementary",
    "robomission-junior": "RoboMission - Junior",
    "robomission-senior": "RoboMission - Senior",
    "robosports": "RoboSports",
    "future-innovators": "Future Innovators",
    "future-engineers": "Future Engineers",
}

#: Sections whose answers bind THIS project. An answer to a Junior or RoboSports
#: question changes nothing here, and a weekly check that cries wolf over one
#: will stop being run.
BINDING_SECTIONS = frozenset({"robomission", "robomission-elementary"})


def _binds(section_class: str) -> bool:
    """Does an answer in this section bind this project?

    An **unrecognised** section returns True. If WRO adds a category, the
    conservative answer is "look at it", not "ignore it".
    """
    if section_class in BINDING_SECTIONS:
        return True
    return section_class not in SECTION_NAMES


def parse(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    entries: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for _post_id, classes, question, author, stamp in _PANEL_RE.findall(raw):
        section_class = classes.strip().split()[0] if classes.strip() else ""
        question = html.unescape(re.sub(r"\s+", " ", question)).strip()
        author = html.unescape(re.sub(r"\s+", " ", author)).strip()
        key = (question[:120], stamp)
        if key in seen:
            continue
        seen.add(key)
        entries.append({
            "section": SECTION_NAMES.get(section_class, section_class or "unknown"),
            "section_class": section_class,
            "question": question,
            "author": author,
            "timestamp": stamp,
            "binds_this_project": _binds(section_class),
        })
    entries.sort(key=lambda e: (e["timestamp"], e["question"]))

    binding = [e for e in entries if e["binds_this_project"]]
    sections: dict[str, int] = {}
    for entry in entries:
        sections[entry["section"]] = sections.get(entry["section"], 0) + 1

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
            "render/cache timestamp on this site and moves independently of content. "
            "Entries are parsed from the FAQ panel markup, NOT by generic shape: "
            "schema v1 also matched the page's JSON-LD block and produced a tenth "
            "phantom entry carrying the page's own modified time."
        ),
        "entry_count": len(entries),
        "binding_entry_count": len(binding),
        "sections": dict(sorted(sections.items())),
        "entries": entries,
    }


def _key(entry: dict[str, Any]) -> tuple[str, str, str, str]:
    """The diff tuple the module docstring has always specified."""
    return (entry.get("section", ""), entry["timestamp"], entry["author"],
            entry["question"][:160])


def check(snapshot: Path, committed: Path) -> int:
    """Diff a fresh snapshot against the committed index. **Both directions.**

    Guarding only against disappearance is the trap: a *new* answer is the whole
    reason to re-read S6, and S6 outranks S4. An extra entry must pause and
    report, not pass silently.

    A delta in a non-binding section (Junior, RoboSports, Future Innovators) is
    still reported, but flagged as such, so the reader can tell a rule change
    that affects this project from one that does not.
    """
    committed_index = json.loads(committed.read_text())
    old_schema = int(committed_index.get("schema_version", 1)) < SCHEMA_VERSION

    def key(entry: dict[str, Any]) -> tuple[str, ...]:
        # A committed index written before `section` existed cannot be compared
        # on it. Falling back to the common fields is the difference between a
        # schema upgrade that reports itself once and one that screams for ever.
        return _key(entry)[1:] if old_schema else _key(entry)

    if old_schema:
        print(f"note: {committed} is schema v{committed_index.get('schema_version', 1)}; "
              f"comparing on (timestamp, author, question) only. Regenerate to "
              f"upgrade to v{SCHEMA_VERSION}.")

    fresh = {key(e): e for e in parse(snapshot)["entries"]}
    known = {key(e): e for e in committed_index["entries"]}

    added = [fresh[k] for k in fresh.keys() - known.keys()]
    removed = [known[k] for k in known.keys() - fresh.keys()]

    if not added and not removed:
        binding = sum(1 for e in fresh.values() if e.get("binds_this_project"))
        print(f"S6 unchanged: {len(fresh)} entries match {committed} "
              f"({binding} bind this project)")
        return 0

    binding_delta = sum(1 for e in added + removed if e.get("binds_this_project"))
    print(f"S6 CHANGED - {len(added)} added, {len(removed)} removed "
          f"({binding_delta} in a section that binds this project)")
    for entry in sorted(added, key=lambda e: e["timestamp"]):
        flag = "**" if entry.get("binds_this_project") else "  "
        print(f"  +{flag} [{entry.get('section', '?')}] {entry['timestamp']}  "
              f"{entry['author']:<18} {entry['question'][:60]}")
    for entry in sorted(removed, key=lambda e: e["timestamp"]):
        flag = "**" if entry.get("binds_this_project") else "  "
        print(f"  -{flag} [{entry.get('section', '?')}] {entry['timestamp']}  "
              f"{entry['author']:<18} {entry['question'][:60]}")
    if binding_delta:
        print("\n** = binds this project. S6 outranks S1 and S4 (S4 4.4). Re-read")
        print("before any scoring or robot-limit claim, then regenerate the index.")
    else:
        print("\nNo binding section changed; this project's claims are unaffected.")
        print("Regenerate the index so the next check starts from here.")
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
    print(f"{index['entry_count']} entries ({index['binding_entry_count']} binding) "
          f"-> {args.out}")
    for entry in index["entries"]:
        flag = "**" if entry["binds_this_project"] else "  "
        print(f"  {flag} [{entry['section_class']:<22}] {entry['timestamp']}  "
              f"{entry['author']:<16} {entry['question'][:58]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
