"""Offline guards on the committed S6 index.

S6 (the official Q&A) sits at the top of the source hierarchy — S4 §4.4 orders
general rules < game document < Q&A < judge on the day — and it is **live and
unversioned**. It has already overwritten two S4 clauses.

Division of labour, deliberate:

* **this file** is the *offline* half. It pins the committed index so a silent
  edit, a dropped anchor or an unnoticed addition fails in CI.
* ``s6_index.py --check`` is the *network* half. It fetches nothing itself but
  diffs a freshly-taken snapshot against the committed index in **both**
  directions. It is a manual/scheduled step and is deliberately **not** invoked
  from pytest, so the test suite stays offline and deterministic.

Guarding only against disappearance is the trap worth naming: a *new* answer is
the entire reason to re-read S6.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

INDEX = Path(__file__).resolve().parents[1] / "docs" / "s6_index.json"

#: The four answers that supersede or resolve something this repo depends on.
#: Losing any of them silently would un-resolve an ambiguity.
REQUIRED_TIMESTAMPS = {
    "2026-02-03T11:21:10+01:00",  # optical hub-to-hub link
    "2026-05-14T01:22:18+02:00",  # battery 14.8 V; 4 A limit removed
    "2026-06-17T16:46:30+02:00",  # bonus without leaving the start area
    "2026-06-30T18:43:01+02:00",  # microphone / upright -> A2, A3, A5
}

#: Pinned so an ADDITION fails too, not just a removal. Bump deliberately, with
#: the new answer read and its consequences worked through.
EXPECTED_ENTRY_COUNT = 10


@pytest.fixture(scope="module")
def index() -> dict:
    return json.loads(INDEX.read_text(encoding="utf-8"))


def test_entry_count_is_pinned(index: dict):
    """Fails on ADDITION as well as removal - that is the point."""
    assert index["entry_count"] == EXPECTED_ENTRY_COUNT, (
        f"S6 index has {index['entry_count']} entries, expected "
        f"{EXPECTED_ENTRY_COUNT}. A new Q&A answer may have appeared - read it, "
        "work through its consequences, then bump EXPECTED_ENTRY_COUNT."
    )
    assert len(index["entries"]) == index["entry_count"]


def test_the_four_load_bearing_answers_are_present(index: dict):
    stamps = {e["timestamp"] for e in index["entries"]}
    missing = REQUIRED_TIMESTAMPS - stamps
    assert not missing, f"S6 anchors missing from the index: {sorted(missing)}"


def test_content_timestamp_is_recorded_not_the_http_header(index: dict):
    """The diff target must be content, never the HTTP Last-Modified header.

    Observed while building this: the header read 13 Jul 2026 while
    article:modified_time still read 2026-06-30 - theme churn, not content.
    """
    assert index["article_modified_time"], "no article:modified_time captured"
    assert any(t.startswith("2026-06-30") for t in index["article_modified_time"])
    # Structural, not a substring scan: the `note` field explains WHY the header
    # is not used, so grepping the serialised document would match its own prose.
    assert not [k for k in index if "modified" in k.lower() and k != "article_modified_time"]
    assert "last_modified" not in index and "http_headers" not in index


def test_every_entry_carries_the_full_tuple(index: dict):
    for entry in index["entries"]:
        assert entry["timestamp"] and entry["author"] and entry["question"]


def test_answer_bodies_are_not_stored(index: dict):
    """Only the tuple is indexed; answer text is WRO's and stays out of git.

    Short identifying quotes belong in docs/citations.json under its word cap.
    """
    for entry in index["entries"]:
        assert set(entry) == {"timestamp", "author", "question"}


def test_snapshot_provenance_is_recorded(index: dict):
    src = index["source"]
    assert len(src["sha256"]) == 64
    assert src["url"].startswith("https://wro-association.org/")
