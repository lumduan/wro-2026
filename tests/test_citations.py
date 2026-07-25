"""Constraints on docs/citations.json.

The file exists so every cited rule number is auditable from git without
redistributing WRO's rulebook. That boundary is enforced here rather than left to
discipline: an uncapped citation file accumulates into the very document it was
designed not to reproduce.

The uniqueness constraint matters more than the word cap. Without it a long rule
can be split across several entries and reassembled in full while every
individual entry passes the cap.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

CITATIONS = Path(__file__).resolve().parents[1] / "docs" / "citations.json"
MAX_QUOTE_WORDS = 15


@pytest.fixture(scope="module")
def doc() -> dict:
    return json.loads(CITATIONS.read_text(encoding="utf-8"))


def test_file_exists_and_declares_its_own_constraints(doc: dict):
    assert doc["constraints"]["max_quote_words"] == MAX_QUOTE_WORDS
    assert doc["constraints"]["unique_key"] == ["source", "rule"]


def test_every_quote_is_within_the_word_cap(doc: dict):
    over = [
        (c["source"], c["rule"], len(c["quote"].split()))
        for c in doc["citations"]
        if len(c["quote"].split()) > MAX_QUOTE_WORDS
    ]
    assert not over, f"quotes over {MAX_QUOTE_WORDS} words: {over}"


def test_at_most_one_entry_per_source_and_rule(doc: dict):
    """Guards against reassembling a long rule from several capped fragments."""
    counts = Counter((c["source"], c["rule"]) for c in doc["citations"])
    dupes = [k for k, n in counts.items() if n > 1]
    assert not dupes, f"duplicate (source, rule) keys: {dupes}"


def test_every_citation_is_complete(doc: dict):
    for c in doc["citations"]:
        assert c["source"] in doc["sources"], f"unknown source {c['source']}"
        assert c["rule"] and c["quote"] and c["used_for"]


def test_sources_carry_a_sha256(doc: dict):
    for name, src in doc["sources"].items():
        assert len(src["sha256"]) == 64, f"{name} has no usable sha256"


def test_s4_is_the_january_15_2026_version(doc: dict):
    """Other S4 versions circulate; only Jan 15 2026 matches S1's date."""
    s4 = doc["sources"]["S4"]
    assert s4["version_line"] == "VERSION: JANUARY 15TH 2026"
    assert s4["pages"] == 31


def test_the_four_superseding_s6_answers_are_present(doc: dict):
    """S6 outranks S4, so these four must never silently drop out."""
    rules = {c["rule"] for c in doc["citations"] if c["source"] == "S6"}
    for required in (
        "QA/2026-05-14/voltage",
        "QA/2026-05-14/current",
        "QA/2026-06-17/bonus",
        "QA/2026-06-30/upright",
    ):
        assert required in rules, f"missing S6 citation {required}"


def test_rules_that_corrections_depend_on_are_cited(doc: dict):
    """Each correction names exactly one load-bearing rule; none may go missing."""
    s4_rules = {c["rule"] for c in doc["citations"] if c["source"] == "S4"}
    # C2 cites 7.7 and nothing else; 9.6 and 10.2 are the randomization premise.
    for required in ("7.7", "7.8", "9.6", "10.2", "10.4", "10.12", "5.2.8"):
        assert required in s4_rules, f"missing S4 citation for {required}"
