"""Invariants on the run-score distribution and on ``data/round_strategy.json``.

Two of these guards exist because the code failed them during development, and
both failures were silent — they produced numbers that looked reasonable.

**A score above the maximum.** The first version of ``sim/rounds.py`` fed the
published tier probabilities straight into a convolution. ADR-008 rounds them to
3 decimals, so a mission's three tiers can sum to 1.001; across the 12 missions
of a run that compounds to 1.002001, and ``cdf ** 3`` turns it into 1.006. The
result was ``E[max of 3] = 256.30`` against a maximum of **255**. Nothing about
that number looks wrong until you check it against the ceiling — which is what
:func:`test_e_max_never_exceeds_the_maximum_score` now does.

**A standard deviation of nan.** The same excess mass drove ``E[X**2] - E[X]**2``
negative at sigma = 10. Reported as ``nan``, it would have propagated silently
into any table it landed in.

The lesson is narrow and worth stating: *a correct number can carry a wrong usage
instruction*. ``expected_score.json``'s cells are correct as inputs to a mean and
wrong as inputs to a distribution. Same failure class as ADR-026. See ADR-028.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from sim import rounds

ROOT = Path(__file__).resolve().parents[1]
ROUND_STRATEGY = ROOT / "data" / "round_strategy.json"
EXPECTED = ROOT / "data" / "expected_score.json"

READINGS = ("contact", "projection")


@pytest.fixture(scope="module")
def loaded() -> tuple[dict, int, int]:
    return rounds.load(ROOT / "data" / "expected_score.json",
                       ROOT / "data" / "scoring_model.json")


@pytest.fixture(scope="module")
def spec() -> dict:
    return json.loads(ROUND_STRATEGY.read_text(encoding="utf-8"))


def _missions(loaded, reading="contact"):
    return loaded[0]["readings"][reading]["missions"]


def _sigmas(loaded, reading="contact"):
    return [c["sigma_mm"] for c in _missions(loaded, reading)[0]["cells"]]


def _raw_terms(mission: dict, sigma: float) -> list[tuple[int, float]]:
    """Tier terms exactly as published — the un-renormalised path that broke."""
    cell = next(c for c in mission["cells"] if c["sigma_mm"] == sigma)
    return [(mission["full_points"], cell["p_full"]),
            (mission["partial_points"], cell["p_partial"]),
            (0, cell["p_none"])]


# --------------------------------------------------------------------------- #
# The distribution is a distribution
# --------------------------------------------------------------------------- #


def test_the_pmf_is_a_valid_distribution(loaded):
    _, floor, maximum = loaded
    for reading in READINGS:
        for sigma in _sigmas(loaded, reading):
            pmf = rounds.pmf_at(_missions(loaded, reading), sigma, floor, maximum)
            assert pmf.sum() == pytest.approx(1.0, abs=1e-12), (reading, sigma)
            assert (pmf >= 0).all(), (reading, sigma)
            assert pmf.size == maximum + 1


def test_the_support_lies_between_the_bonus_floor_and_the_maximum(loaded):
    """A run can never score below 40 — the bonus is a floor (S6 2026-06-17)."""
    _, floor, maximum = loaded
    for sigma in _sigmas(loaded):
        pmf = rounds.pmf_at(_missions(loaded), sigma, floor, maximum)
        support = np.nonzero(pmf > 1e-15)[0]
        assert support.min() >= floor, sigma
        assert support.max() <= maximum, sigma


def test_a_collision_shifts_the_whole_distribution_down_by_its_cost(loaded):
    _, floor, maximum = loaded
    pmf = rounds.pmf_at(_missions(loaded), 20.0, floor, maximum)
    for cost in rounds.COLLISION_COSTS:
        hit = rounds.with_collision(pmf, 1.0, cost)
        assert rounds.mean(hit) == pytest.approx(rounds.mean(pmf) - cost, abs=1e-9)
        assert hit.sum() == pytest.approx(1.0, abs=1e-12)


def test_the_standard_deviation_is_never_nan(loaded):
    """It was, at sigma = 10, from exactly the excess mass ADR-028 describes."""
    _, floor, maximum = loaded
    for reading in READINGS:
        for sigma in _sigmas(loaded, reading):
            sd = rounds.stdev(rounds.pmf_at(_missions(loaded, reading), sigma, floor, maximum))
            assert not np.isnan(sd) and sd >= 0.0, (reading, sigma)


# --------------------------------------------------------------------------- #
# The guards that bite — ADR-028
# --------------------------------------------------------------------------- #


def test_the_published_tier_cells_really_do_not_sum_to_one(loaded):
    """The premise of ADR-028, asserted against the data rather than described."""
    defective = [
        (reading, m["object_id"], c["sigma_mm"])
        for reading in READINGS
        for m in _missions(loaded, reading)
        for c in m["cells"]
        if abs(rounds.raw_tier_mass(c) - 1.0) > 1e-9
    ]
    assert defective, (
        "no rounding defect found — if the emission precision changed, ADR-028 "
        "and the renormalisation in sim.rounds.tier_terms need revisiting")


def test_feeding_the_raw_cells_is_rejected(loaded):
    """The renormalisation is load-bearing, so removing it must fail loudly."""
    _, floor, maximum = loaded
    missions = _missions(loaded)
    broken = [
        sigma for sigma in _sigmas(loaded)
        if abs(np.prod([sum(p for _, p in _raw_terms(m, sigma)) for m in missions]) - 1.0) > 1e-9
    ]
    assert broken, "expected at least one sigma where the compounded mass is off"
    for sigma in broken:
        with pytest.raises(ValueError, match="not 1"):
            rounds.run_score_pmf([_raw_terms(m, sigma) for m in missions], floor, maximum)


def test_e_max_never_exceeds_the_maximum_score(loaded):
    """The 256.30 guard."""
    _, floor, maximum = loaded
    for reading in READINGS:
        for sigma in _sigmas(loaded, reading):
            pmf = rounds.pmf_at(_missions(loaded, reading), sigma, floor, maximum)
            for n in (1, 2, 3, 5, 10):
                assert rounds.e_max(pmf, n) <= maximum + 1e-9, (reading, sigma, n)


def test_the_unrenormalised_path_would_have_produced_an_impossible_score(loaded):
    """Reproduce the original bug, so the guard above is known to be necessary.

    This deliberately bypasses :func:`rounds.run_score_pmf`'s mass check to
    rebuild what the first version computed. Without it the guard is a claim
    about history rather than a tested fact.
    """
    _, floor, maximum = loaded
    missions = _missions(loaded)
    pmf = np.zeros(maximum + 1)
    pmf[floor] = 1.0
    for mission in missions:
        shifted = np.zeros(maximum + 1)
        for points, probability in _raw_terms(mission, 10.0):
            if probability > 0:
                shifted[points:] += probability * pmf[:maximum + 1 - points]
        pmf = shifted
    assert pmf.sum() > 1.0 + 1e-6, "the historical input must carry excess mass"
    cdf = np.cumsum(pmf)                       # no cdf[-1] = 1.0 correction, as before
    impossible = float(np.arange(maximum + 1)
                       @ np.diff(np.concatenate([[0.0], cdf ** 3])))
    assert impossible > maximum, f"expected an impossible score, got {impossible}"
    assert impossible == pytest.approx(256.30, abs=0.05), impossible


# --------------------------------------------------------------------------- #
# E[max of N]
# --------------------------------------------------------------------------- #


def test_one_round_is_exactly_the_mean(loaded):
    _, floor, maximum = loaded
    for sigma in _sigmas(loaded):
        pmf = rounds.pmf_at(_missions(loaded), sigma, floor, maximum)
        assert rounds.e_max(pmf, 1) == pytest.approx(rounds.mean(pmf), abs=1e-9), sigma


def test_one_round_reproduces_expected_score_json(loaded):
    """Agreement with the artefact this one is built on top of.

    Tolerance 0.05, not exact: `expected_score.json` sums the *published*
    3-dp cells while this renormalises them first. The gap peaked at 0.034
    points across the whole grid — an order of magnitude below the underlying
    sweep's own sampling noise.
    """
    spec, floor, maximum = loaded
    for reading in READINGS:
        for row in spec["readings"][reading]["full_attempt_run"]:
            pmf = rounds.pmf_at(_missions(loaded, reading), row["sigma_mm"], floor, maximum)
            theirs = next(c["expected_total"] for c in row["at_p_collision"]
                          if c["p_collision"] == 0.0)
            assert rounds.mean(pmf) == pytest.approx(theirs, abs=0.05), (reading, row["sigma_mm"])


def test_more_rounds_never_hurt(loaded):
    _, floor, maximum = loaded
    for reading in READINGS:
        for sigma in _sigmas(loaded, reading):
            pmf = rounds.pmf_at(_missions(loaded, reading), sigma, floor, maximum)
            values = [rounds.e_max(pmf, n) for n in (1, 2, 3, 4, 5)]
            assert values == sorted(values), (reading, sigma)


def test_a_degenerate_distribution_gains_nothing_from_extra_rounds(loaded):
    """No variance, no premium — the sanity anchor for the whole argument."""
    _, floor, maximum = loaded
    pmf = rounds.pmf_at(_missions(loaded), 0.0, floor, maximum)
    assert rounds.stdev(pmf) == pytest.approx(0.0, abs=1e-9)
    assert rounds.e_max(pmf, 3) == pytest.approx(rounds.e_max(pmf, 1), abs=1e-9)


def test_two_rounds_equal_the_mean_plus_half_the_gini_mean_difference(loaded):
    """An independent check of `e_max`, via a completely different route.

    For two iid draws, ``E[max(X1, X2)] = E[X] + E|X1 - X2| / 2`` exactly. The
    right-hand term is the Gini mean difference — a pure dispersion measure — so
    this identity is also the precise form of the claim that extra rounds
    *reward variance*: at N = 2 the premium **is** half the mean absolute
    difference, and nothing else.

    Computed here by double summation over the pmf, which shares no code path
    with the powered-cdf method `e_max` uses.
    """
    _, floor, maximum = loaded
    scores = np.arange(maximum + 1)
    for sigma in (0.0, 10.0, 20.0, 45.0):
        pmf = rounds.pmf_at(_missions(loaded), sigma, floor, maximum)
        gini = float(np.abs(scores[:, None] - scores[None, :]) @ pmf @ pmf)
        assert rounds.e_max(pmf, 2) == pytest.approx(rounds.mean(pmf) + gini / 2,
                                                     abs=1e-9), sigma


def test_the_premium_is_material_at_a_plausible_sigma(loaded):
    """+12.5 points at sigma = 20 mm — more than a whole cable mission (15)."""
    _, floor, maximum = loaded
    pmf = rounds.pmf_at(_missions(loaded), 20.0, floor, maximum)
    premium = rounds.e_max(pmf, 3) - rounds.mean(pmf)
    assert premium == pytest.approx(12.5, abs=0.5)


def test_e_max_rejects_a_round_count_below_one(loaded):
    _, floor, maximum = loaded
    with pytest.raises(ValueError):
        rounds.e_max(rounds.pmf_at(_missions(loaded), 20.0, floor, maximum), 0)


# --------------------------------------------------------------------------- #
# Break-even under best-of-N
# --------------------------------------------------------------------------- #


def test_breakeven_at_one_round_matches_the_closed_form(loaded):
    """Bisection must agree with `expected_score.json`'s E[points] / risk.

    Only where that closed form is a probability: it is emitted unclamped, so a
    mission that pays even at certain collision shows values above 1.
    """
    spec, floor, maximum = loaded
    missions = _missions(loaded)
    for mission in missions:
        cost = mission["bonus_points_exposed"]
        for cell in mission["cells"]:
            closed = cell["breakeven_p_collision"]
            if closed >= 1.0:
                continue
            sigma = cell["sigma_mm"]
            got = rounds.breakeven_p_collision(
                rounds.pmf_at(missions, sigma, floor, maximum),
                rounds.pmf_at(missions, sigma, floor, maximum, exclude=mission["object_id"]),
                cost, 1)
            assert got == pytest.approx(closed, abs=2e-3), (mission["object_id"], sigma)


def test_extra_rounds_raise_the_tolerable_collision_risk(spec):
    """The decision this artefact exists to change."""
    for reading in READINGS:
        for mission in spec["readings"][reading]["missions"]:
            for cell in mission["cells"]:
                values = [a["breakeven_p_collision"] for a in cell["at_n"]]
                if any(v is None for v in values):
                    # `None` means "pays even at P(collision) = 1"; once a mission
                    # reaches that it cannot un-reach it as N grows.
                    first = values.index(None)
                    assert all(v is None for v in values[first:]), (mission, cell)
                    values = values[:first]
                assert values == sorted(values), (reading, mission["object_id"], cell)


def test_a_mission_that_always_pays_is_reported_as_such_not_as_a_probability(spec):
    """`expected_score.json` emits 1.957 for note_blue at sigma = 10, which is
    not a probability. This artefact reports the fact instead of the artefact."""
    note = next(m for m in spec["readings"]["contact"]["missions"]
                if m["object_id"] == "note_blue")
    cell = next(c for c in note["cells"] if c["sigma_mm"] == 10.0)
    for entry in cell["at_n"]:
        assert entry["breakeven_p_collision"] is None
        assert entry["pays_even_at_certain_collision"] is True
    for reading in READINGS:
        for mission in spec["readings"][reading]["missions"]:
            for c in mission["cells"]:
                for entry in c["at_n"]:
                    p = entry["breakeven_p_collision"]
                    assert p is None or 0.0 <= p <= 1.0, (mission["object_id"], c["sigma_mm"])


# --------------------------------------------------------------------------- #
# The mulligan — S4 §10.14
# --------------------------------------------------------------------------- #


def test_a_round_at_or_below_the_running_best_is_free_to_retake():
    assert rounds.retake_is_free(40, 40) is True
    assert rounds.retake_is_free(180, 215) is True
    assert rounds.retake_is_free(216, 215) is False


def test_a_do_nothing_run_is_always_free_to_retake(loaded):
    """It scores exactly the bonus floor, which is at most any completed round."""
    _, floor, _ = loaded
    for running_best in range(floor, 256, 25):
        assert rounds.retake_is_free(floor, running_best) is True


def test_the_retake_threshold_is_the_indifference_point(loaded):
    """Retake iff realised < E[max(running_best, fresh)], by construction."""
    _, floor, maximum = loaded
    pmf = rounds.pmf_at(_missions(loaded), 20.0, floor, maximum)
    for running_best in (floor, 150, 215, 235):
        threshold = rounds.retake_threshold(pmf, running_best)
        fresh = np.zeros_like(pmf)
        fresh[running_best] = pmf[:running_best + 1].sum()
        fresh[running_best + 1:] = pmf[running_best + 1:]
        expectation = rounds.mean(fresh)
        assert threshold < expectation <= threshold + 1, (running_best, expectation)


def test_a_perfect_round_is_never_worth_retaking(loaded):
    _, floor, maximum = loaded
    pmf = rounds.pmf_at(_missions(loaded), 20.0, floor, maximum)
    assert rounds.retake_threshold(pmf, maximum) < maximum


# --------------------------------------------------------------------------- #
# The artefact
# --------------------------------------------------------------------------- #


def test_the_artefact_covers_both_a7_readings_and_the_whole_sigma_grid(spec, loaded):
    for reading in READINGS:
        block = spec["readings"][reading]
        assert [r["sigma_mm"] for r in block["distribution"]] == _sigmas(loaded, reading)
        assert {m["object_id"] for m in block["missions"]} == \
            {m["object_id"] for m in _missions(loaded, reading)}
        for row in block["best_of"]:
            assert [a["n"] for a in row["at_n"]] == list(rounds.DEFAULT_ROUND_COUNTS)


def test_the_premium_grows_with_sigma_on_the_contact_reading(spec):
    """The result that inverts the single-attempt reading of Phase 8."""
    premiums = [row["at_n"][-1]["premium_over_single_attempt"]
                for row in spec["readings"]["contact"]["best_of"]]
    assert premiums == sorted(premiums)
    assert premiums[0] == 0.0 and premiums[-1] > 15.0


def test_the_breakevens_are_labelled_as_marginal(spec, loaded):
    """Six missions share one 30-point cluster, so these must not be summed."""
    note = spec["formula"]["breakeven_is_marginal_and_does_not_add_up"]
    assert "ONCE, not once per mission" in note
    assert "B0" in note
    shared = {}
    for mission in _missions(loaded):
        shared.setdefault(mission["bonus_points_exposed"], []).append(mission["object_id"])
    assert all(len(ids) > 1 for ids in shared.values()), (
        "if no cluster is shared any more, this caveat needs rewriting, not deleting")


def test_the_rounding_defect_is_recorded_with_evidence(spec):
    defect = spec["rounding_defect"]
    assert defect["adr"] == "ADR-028"
    assert defect["worst_mission_mass"] > 1.0
    assert defect["worst_run_mass_pow_3"] > defect["worst_run_mass"] > 1.0
    assert "256.30" in defect["consequence"]


def test_the_free_parameters_are_named_and_n_is_no_longer_one(spec):
    """N was confirmed on 2026-07-27; rho took its place as the open parameter.

    The point of the original guard survives unchanged: nothing unmeasured may
    be silently asserted. Only the membership of that set moved.
    """
    scope = spec["scope"]
    assert scope["n_is_not_known"] is False and scope["n"] == 2
    assert "operator" in scope["n_source"].lower(), \
        "a confirmed N must still carry its provenance, not become a bare fact"
    assert scope["rho_is_not_measured"] is True
    assert "B5" in scope["rho_source"]
    assert scope["sigma_is_not_measured"] is True
    assert scope["missions_assumed_independent"] is True
    assert scope["independence_assumption"] == "AS-10"


def test_the_artefact_refuses_to_rank_subsets(spec):
    """Same refusal as expected_score.json, and for the same reason."""
    assert "which missions to attempt" in spec["scope"]["does_not_answer"]
    assert "anti-pattern #3" in spec["scope"]["why_not"]
    assert "B0" in spec["scope"]["why_not"]


def test_the_three_s4_rules_are_quoted_not_paraphrased(spec):
    rules = spec["rules"]
    assert "depends on the overall tournament format" in rules["s4_10_13"]
    assert "no matter what" in rules["s4_10_14"]
    assert rules["s4_9_1_2"] == "A number of robot rounds."


def test_provenance_pins_every_input(spec):
    inputs = spec["provenance"]["inputs"]
    assert set(inputs) == {"expected_score", "scoring_model"}
    assert all(len(v) == 64 for v in inputs.values())
