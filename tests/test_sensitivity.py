"""Invariants on sim/sensitivity.py and data/placement_sensitivity.json.

A Monte Carlo is only trustworthy if something independent agrees with it, so
the central test here derives ``P(success)`` in closed form from the Gaussian
CDF and checks the simulation against it. For a square footprint in a square
target with rotation disabled, the two must agree:

    P = (2 * Phi(slack / sigma) - 1) ** 2

If they disagree, the simulation is wrong — the geometry has three independent
confirmations behind it and the arithmetic has none.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from sim.scoring import Scorer, ScoringParams
from sim.sensitivity import DEFAULT_SEED, success_probability, sweep, threshold_sigma

ROOT = Path(__file__).resolve().parents[1]
SENSITIVITY = ROOT / "data" / "placement_sensitivity.json"

#: Small but sufficient: at P ~ 0.8 the standard error over 3000 draws is 0.007.
SAMPLES = 3000


@pytest.fixture(scope="module")
def scorer() -> Scorer:
    return Scorer.load()


def _phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


# --------------------------------------------------------------------------- #
# The cross-check
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("sigma", [8.0, 12.0, 18.0])
def test_monte_carlo_matches_the_closed_form_for_a_note(scorer: Scorer, sigma: float):
    """32 mm note in a 79.7 mm square target: slack 23.85 mm on both axes."""
    target, x, y, theta = scorer.nominal_placements()["note_blue"]
    cell = success_probability(scorer, "note_blue", target, x, y, theta, sigma,
                               samples=SAMPLES, deg_per_mm=0.0)
    slack = (79.699 - 32.0) / 2.0
    expected = (2.0 * _phi(slack / sigma) - 1.0) ** 2
    assert cell.p_full == pytest.approx(expected, abs=0.02)


def test_the_three_tiers_are_a_partition(scorer: Scorer):
    target, x, y, theta = scorer.nominal_placements()["mic"]
    cell = success_probability(scorer, "mic", target, x, y, theta, 15.0, samples=500)
    assert cell.p_full + cell.p_partial + cell.p_none == pytest.approx(1.0)


def test_perfect_placement_always_succeeds(scorer: Scorer):
    for object_id, (target, x, y, theta) in scorer.nominal_placements().items():
        cell = success_probability(scorer, object_id, target, x, y, theta, 0.0)
        assert cell.p_full == 1.0, object_id


def test_success_falls_monotonically_with_sigma(scorer: Scorer):
    target, x, y, theta = scorer.nominal_placements()["note_red"]
    series = [success_probability(scorer, "note_red", target, x, y, theta, s,
                                  samples=SAMPLES)
              for s in (2.0, 10.0, 20.0, 40.0)]
    values = [c.p_full for c in series]
    assert values == sorted(values, reverse=True), values


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #


def test_a_cell_is_reproducible_and_order_independent(scorer: Scorer):
    """Seeded per cell, so adding a mission cannot perturb another's numbers."""
    target, x, y, theta = scorer.nominal_placements()["note_white"]
    first = success_probability(scorer, "note_white", target, x, y, theta, 12.0,
                                samples=800, seed=DEFAULT_SEED)
    second = success_probability(scorer, "note_white", target, x, y, theta, 12.0,
                                 samples=800, seed=DEFAULT_SEED)
    assert first.p_full == second.p_full


def test_a_different_seed_gives_a_different_but_close_answer(scorer: Scorer):
    target, x, y, theta = scorer.nominal_placements()["note_white"]
    a = success_probability(scorer, "note_white", target, x, y, theta, 12.0,
                            samples=SAMPLES, seed=1)
    b = success_probability(scorer, "note_white", target, x, y, theta, 12.0,
                            samples=SAMPLES, seed=2)
    assert a.p_full == pytest.approx(b.p_full, abs=0.05)


# --------------------------------------------------------------------------- #
# The impossible placement
# --------------------------------------------------------------------------- #


def test_a_cable_across_its_area_never_succeeds_at_any_sigma(scorer: Scorer):
    rect = scorer.area_rect("cable_area_upper")
    for sigma in (0.0, 1.0, 5.0, 20.0):
        cell = success_probability(scorer, "cable_upper", "cable_area_upper",
                                   rect.cx, rect.cy, rect.angle_deg, sigma,
                                   samples=400)
        assert cell.p_full == 0.0, sigma


def test_threshold_is_None_when_the_requirement_is_never_met(scorer: Scorer):
    rect = scorer.area_rect("cable_area_upper")
    cells = [success_probability(scorer, "cable_upper", "cable_area_upper",
                                 rect.cx, rect.cy, rect.angle_deg, s, samples=200)
             for s in (0.0, 5.0, 10.0)]
    assert threshold_sigma(cells, 0.90) is None


def test_threshold_is_monotone_in_the_requirement(scorer: Scorer):
    """A stricter requirement can only demand a tighter sigma."""
    cells = sweep(scorer, sigmas=(0.0, 5.0, 10.0, 20.0, 40.0), samples=600)
    for label, series in cells.items():
        p90, p99 = threshold_sigma(series, 0.90), threshold_sigma(series, 0.99)
        if p90 is not None and p99 is not None:
            assert p99 <= p90 + 1e-9, label


# --------------------------------------------------------------------------- #
# The built artefact
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def built() -> dict:
    return json.loads(SENSITIVITY.read_text(encoding="utf-8"))


def test_both_a7_readings_are_reported(built: dict):
    assert set(built["readings"]) == {"contact", "projection"}
    assert built["parameters"]["a7_readings_both_reported"] == ["contact", "projection"]


def test_the_silhouette_reading_is_never_easier_than_the_contact_one(built: dict):
    """A7's cost, as an assertion: the larger extent can only be stricter."""
    contact = {r["label"]: r for r in built["readings"]["contact"]}
    projection = {r["label"]: r for r in built["readings"]["projection"]}
    for label, row in projection.items():
        a, b = contact[label]["sigma_for_p90_mm"], row["sigma_for_p90_mm"]
        if a is None or b is None:
            continue
        assert b <= a + 1e-6, f"{label}: projection {b} must not exceed contact {a}"


def test_the_notes_cost_a_factor_of_two_between_the_a7_readings(built: dict):
    """The finding that makes A7 worth submitting to the Q&A."""
    contact = next(r for r in built["readings"]["contact"] if r["label"] == "note_blue")
    projection = next(r for r in built["readings"]["projection"]
                      if r["label"] == "note_blue")
    ratio = contact["sigma_for_p90_mm"] / projection["sigma_for_p90_mm"]
    assert ratio > 2.0, f"expected the silhouette reading to be much stricter, got {ratio}"


def test_every_row_carries_its_closed_form_geometry(built: dict):
    for reading, rows in built["readings"].items():
        for row in rows:
            geometry = row["geometry"]
            assert "frame" in geometry and "area" in geometry["frame"]
            assert len(geometry["margin_mm"]) == 4
            assert geometry["binding_edge"] in geometry["margin_mm"]


def test_the_geometry_and_the_simulation_agree_on_feasibility(built: dict):
    """p_full at sigma = 0 must be 1 exactly where the closed form says it fits."""
    for reading, rows in built["readings"].items():
        for row in rows:
            zero = next(c for c in row["cells"] if c["sigma_mm"] == 0.0)
            feasible = row["geometry"]["binding_slack_mm"] >= 0.0
            assert zero["p_full"] == (1.0 if feasible else 0.0), \
                f"{reading}/{row['label']}"


def test_the_impossible_cable_row_is_reported_as_never(built: dict):
    """Laid across its area, the cable cannot score — at its intended heading.

    ``p_full`` is 0 at every sigma except the widest, where it reads 0.001. That
    is not a defect: at sigma = 45 mm the heading noise is +/-22.5 deg, and the
    cable fits once it comes within ~31 deg of the area's long axis, so a few
    samples in 4000 are rotated back into a legal pose by chance. The model is
    coupling rotation and translation, which is the point of sampling both.

    What must hold is that it is never a *strategy*: 0 at zero error, and
    negligible everywhere.
    """
    for reading in ("contact", "projection"):
        row = next(r for r in built["readings"][reading]
                   if r["label"] == "cable_upper@across_area")
        assert row["sigma_for_p90_mm"] is None
        assert row["sigma_for_p99_mm"] is None
        assert row["geometry"]["binding_slack_mm"] < 0.0
        zero = next(c for c in row["cells"] if c["sigma_mm"] == 0.0)
        assert zero["p_full"] == 0.0, "perfect placement across the area must fail"
        assert all(c["p_full"] < 0.01 for c in row["cells"])


def test_sigma_is_declared_unmeasured(built: dict):
    """The honesty guard: nothing here measures how accurate the robot is."""
    assert built["method"]["sigma_is_not_measured_here"] is True
    assert "P2" in built["method"]["sigma_status"]
    assert "ASSUME" in built["method"]["sigma_status"]


def test_provenance_pins_every_input(built: dict):
    inputs = built["provenance"]["inputs"]
    assert set(inputs) == {"field_spec", "object_spec", "scoring_model"}
    assert all(len(v) == 64 for v in inputs.values())
    assert built["provenance"]["seed"] == DEFAULT_SEED
