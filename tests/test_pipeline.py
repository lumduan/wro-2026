"""Guards on the derived-artefact pipeline and on cross-document references.

Two failure modes, both of which have actually happened here.

**Stale provenance.** Six files in ``data/`` are derived through a dependency
chain. Running the builders out of order does not fail — it leaves an artefact
pinning a sha that no longer matches the file on disk. Adding ``mass_g`` to
``object_spec.json`` left ``manipulator_requirements.json`` pinning the old one,
and the determinism sweep reported a bare "DRIFT" naming neither the artefact nor
the input. These tests name both.

**Dangling references.** Documents cite ADRs, assumptions and ambiguities by
number. A citation to something that does not exist reads as authority.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from build_all import HAND_AUTHORED, INPUT_PATHS, PIPELINE, pins, sha256_of, staleness

ROOT = Path(__file__).resolve().parents[1]
DOCS = sorted(list((ROOT / "docs").rglob("*.md")) + [ROOT / "CLAUDE.md", ROOT / "README.md"])

DECISIONS = ROOT / "docs" / "DECISIONS.md"
ASSUMPTIONS = ROOT / "docs" / "ASSUMPTIONS.md"
AMBIGUITIES = ROOT / "docs" / "AMBIGUITIES.md"

#: Paths a document may name that legitimately do not exist on disk.
#: Two categories, both deliberate — and writing them down is the point: it
#: makes "absent by design" a recorded fact rather than an accident.
ALLOWED_ABSENT = (
    # gitignored third-party content (ADR-001, and the S6 snapshot rule)
    ".pdf",
    "s6-qa-snapshot-",
    "/img/",
    "vector/drawings.json",
    # prose containing an ellipsis rather than a real path
    "...",
)


# --------------------------------------------------------------------------- #
# The pipeline
# --------------------------------------------------------------------------- #


def test_every_derived_artefact_is_fresh():
    """The guard that would have turned "DRIFT" into a diagnosis."""
    problems = []
    for artefact in PIPELINE:
        for reason in staleness(artefact):
            problems.append(f"{artefact.name}: {reason}")
    assert not problems, (
        "stale pins:\n  " + "\n  ".join(problems)
        + "\nRun: uv run python tools/build_all.py"
    )


def test_the_declared_graph_matches_what_the_artefacts_pin():
    """`build_all.PIPELINE` cannot drift from reality.

    Every path an artefact records in its provenance must be one the declaration
    knows how to resolve; anything else means a builder started pinning
    something the pipeline does not model.
    """
    for artefact in PIPELINE:
        recorded = pins(artefact)
        assert recorded, f"{artefact.name} records no provenance pins"
        known = set(artefact.pin_map.values()) | set(INPUT_PATHS.values())
        unknown = set(recorded) - known
        assert not unknown, f"{artefact.name} pins unmodelled inputs: {sorted(unknown)}"


def test_the_pipeline_is_in_dependency_order():
    """An artefact may only pin outputs that appear before it."""
    produced: set[str] = set()
    for artefact in PIPELINE:
        for path in pins(artefact):
            if path.startswith("data/") and path not in HAND_AUTHORED:
                assert path in produced, (
                    f"{artefact.name} pins {path}, which the pipeline builds later")
        produced.add(artefact.out)


def test_every_derived_artefact_exists_and_is_declared_once():
    outs = [a.out for a in PIPELINE]
    assert len(outs) == len(set(outs)) == 7
    for out in outs:
        assert (ROOT / out).exists(), out


def test_hand_authored_files_are_excluded_from_the_pipeline():
    """`scoring_model.json` is a transcription, not a derivation."""
    import json
    built = {a.out for a in PIPELINE}
    for path in HAND_AUTHORED:
        assert path not in built, path
        assert (ROOT / path).exists(), path
        content = json.loads((ROOT / path).read_text())
        assert "provenance" not in content, (
            f"{path} has a provenance block — is it derived after all?")


def test_every_data_file_is_either_derived_or_declared_hand_authored():
    """Nothing may appear in data/ unaccounted for."""
    on_disk = {f"data/{p.name}" for p in (ROOT / "data").glob("*.json")}
    accounted = {a.out for a in PIPELINE} | set(HAND_AUTHORED)
    assert on_disk == accounted, f"unaccounted: {sorted(on_disk ^ accounted)}"


def test_sha256_of_returns_none_for_a_gitignored_source(tmp_path):
    """A missing source PDF is unverifiable, not stale — a fresh clone has none."""
    assert sha256_of(tmp_path / "absent.pdf") is None
    probe = tmp_path / "present.txt"
    probe.write_text("x")
    assert len(sha256_of(probe)) == 64


# --------------------------------------------------------------------------- #
# Cross-document references
# --------------------------------------------------------------------------- #


def _cited(pattern: str) -> set[str]:
    found: set[str] = set()
    for path in DOCS:
        found |= set(re.findall(pattern, path.read_text(encoding="utf-8")))
    return found


def test_every_cited_adr_exists():
    defined = set(re.findall(r"^## (ADR-\d{3})", DECISIONS.read_text(), re.M))
    cited = _cited(r"\bADR-\d{3}\b")
    assert cited - defined == set(), f"dangling ADR citations: {sorted(cited - defined)}"
    assert defined, "no ADRs found at all — has the heading format changed?"


def test_every_adr_is_indexed_in_the_table():
    text = DECISIONS.read_text()
    defined = set(re.findall(r"^## (ADR-\d{3})", text, re.M))
    indexed = set(re.findall(r"\|\s*\[(ADR-\d{3})\]\(#adr-\d{3}\)", text))
    assert defined == indexed, (
        f"defined but not indexed: {sorted(defined - indexed)}; "
        f"indexed but not defined: {sorted(indexed - defined)}")


def test_every_cited_assumption_exists():
    # `\d+`, not `\d`: with `AS-\d` the heading "## AS-10" defines "AS-1" and no
    # citation of AS-10 matches at all, so the guard passes while checking
    # nothing. Same latent off-by-one as the ambiguity pattern below.
    defined = set(re.findall(r"^## (AS-\d+)", ASSUMPTIONS.read_text(), re.M))
    cited = _cited(r"\bAS-\d+\b")
    assert cited - defined == set(), f"dangling: {sorted(cited - defined)}"


def test_every_cited_ambiguity_exists():
    text = AMBIGUITIES.read_text()
    defined = set(re.findall(r"^#{2,3} (A\d+)\b", text, re.M))
    # The register's summary table is the other place they are declared.
    defined |= set(re.findall(r"^\| (A\d+) \|", text, re.M))
    # `A\d+`, not `A[1-9]`: the old pattern stopped matching at A9, so A10 would
    # have gone silently unguarded the moment it was written. A9 was the last
    # value it caught.
    cited = {c for c in _cited(r"\bA\d+\b")}
    assert cited - defined == set(), f"dangling ambiguity citations: {sorted(cited - defined)}"


def test_the_reference_guards_would_catch_a_dangling_citation(tmp_path):
    """A guard that has never fired is not a guard."""
    defined = set(re.findall(r"^## (ADR-\d{3})", DECISIONS.read_text(), re.M))
    assert "ADR-099" not in defined
    fake = tmp_path / "scratch.md"
    fake.write_text("This cites ADR-099, which does not exist.\n")
    cited = set(re.findall(r"\bADR-\d{3}\b", fake.read_text()))
    assert cited - defined == {"ADR-099"}, "the pattern must catch a bad citation"


# --------------------------------------------------------------------------- #
# Paths named in documents
# --------------------------------------------------------------------------- #


PATH_RE = re.compile(
    r"\b((?:docs|data|tools|sim|robot|tests)/[A-Za-z0-9_./*-]+"
    r"\.(?:py|json|toml|md|html|pdf))")


def test_every_path_named_in_a_document_exists():
    missing: dict[str, list[str]] = {}
    for doc in DOCS:
        for candidate in set(PATH_RE.findall(doc.read_text(encoding="utf-8"))):
            if any(token in candidate for token in ALLOWED_ABSENT):
                continue
            if "*" in candidate:            # a glob in a command example
                continue
            if not (ROOT / candidate).exists():
                missing.setdefault(candidate, []).append(doc.name)
    assert not missing, "paths named in docs that do not exist: " + repr(missing)


def test_the_allowlist_only_covers_things_that_really_are_absent():
    """An allowlist entry for a file that exists would hide a future break."""
    for doc in DOCS:
        for candidate in set(PATH_RE.findall(doc.read_text(encoding="utf-8"))):
            if candidate.endswith(".pdf") or "s6-qa-snapshot-" in candidate:
                continue                     # gitignored; may or may not be present
            if "..." in candidate:
                assert not (ROOT / candidate).exists(), candidate
