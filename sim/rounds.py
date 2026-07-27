#!/usr/bin/env python3
"""The run-score *distribution*, and the objective a best-of-N ranking implies.

    data/expected_score.json   (per-mission tier probabilities vs sigma)  ─┐
    data/scoring_model.json    (the 40-point bonus floor, max_score)      ─┴─► pmf

Phase 8 optimises ``E[score]`` of a **single attempt**. S4 does not say the
ranking works that way:

- **§9.1.2** "A number of robot rounds." — the count is unspecified.
- **§10.13** "The ranking of teams depends on the overall tournament format. For
  example, the best attempt out of three rounds could be used…" — the
  aggregation rule is set by the organizer, and best-of-three is offered as an
  *example*, not as the rule.
- **§10.14** "Mulligan (optional element)… If a team decides to redo the run the
  new score will be used for the ranking **no matter what**." — a replacement,
  not a maximum.

Under a best-of-N ranking the objective is ``E[max(X1..XN)]``, and that
functional **rewards variance**: two strategies with equal means but different
spreads are no longer equivalent, and ranking them by ``E[X]`` gives the wrong
order. The premium is not small — at sigma = 20 mm it is worth more than a whole
cable mission — and it *grows* with sigma, so multiple rounds favour the less
precise, more ambitious strategy. That inverts the naive reading of Phase 8.

Nothing here picks a strategy. It supplies the objective function; subset
selection still needs the 120 s budget and a route (work order B0/B5), exactly as
``data/expected_score.json`` already refuses. CLAUDE.md §5.7 anti-pattern #3.

**The tier probabilities are not a probability distribution.** ADR-008 rounds
every emitted float to 3 decimals, so a mission's ``p_full + p_partial + p_none``
can be 1.001, and across the 12 missions of a run the excess compounds to
1.002001. Used as a *mean* that is harmless — the linear sum is forgiving. Used
as a **distribution** it is not: ``cdf ** N`` amplifies the excess, and the first
version of this module returned ``E[max3] = 256.30`` against a maximum of 255.
Every mission is therefore renormalised before use (:func:`tier_terms`), which
costs nothing real: the rounding is +/-0.05 pp against the underlying sweep's
+/-0.8 pp sampling noise at 4000 samples per cell. See ADR-028.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Final, Iterable, Sequence

import numpy as np

DEFAULT_EXPECTED_SCORE: Final = Path("data/expected_score.json")
DEFAULT_SCORING_MODEL: Final = Path("data/scoring_model.json")

#: Round counts to tabulate. 1 is the current (single-attempt) objective; 3 is
#: the example S4 §10.13 gives. The real value is organizer-set — see the
#: `NEEDS-VERIFY(NO-TH)` tracker in docs/DECISIONS.md.
DEFAULT_ROUND_COUNTS: Final = (1, 2, 3)

#: What a collision can cost. 40 is the whole bonus floor, matching the worst
#: case `expected_score.json` tabulates; 30 and 10 are the two clusters a route
#: actually exposes (ADR-024).
COLLISION_COSTS: Final = (40, 30, 10)


# --------------------------------------------------------------------------- #
# Tiers -> a valid probability distribution
# --------------------------------------------------------------------------- #


def raw_tier_mass(cell: dict[str, float]) -> float:
    """``p_full + p_partial + p_none`` exactly as published, defect included.

    Emitted into the artefact as evidence rather than described in prose: the
    claim "the published cells are not a pmf" should be checkable by a reader
    who has only the JSON.
    """
    return cell["p_full"] + cell["p_partial"] + cell["p_none"]


def tier_terms(cell: dict[str, float], full: int, partial: int) -> list[tuple[int, float]]:
    """``[(points, probability)]`` for one mission at one sigma, renormalised.

    Renormalisation is the whole point — see the module docstring. Without it
    the compounded excess produces scores above the 255 maximum.
    """
    mass = raw_tier_mass(cell)
    if mass <= 0.0:
        raise ValueError(f"tier probabilities sum to {mass}, which cannot be normalised")
    return [
        (int(full), cell["p_full"] / mass),
        (int(partial), cell["p_partial"] / mass),
        (0, cell["p_none"] / mass),
    ]


# --------------------------------------------------------------------------- #
# The distribution
# --------------------------------------------------------------------------- #


def run_score_pmf(terms_per_mission: Iterable[Sequence[tuple[int, float]]],
                  bonus_floor: int, max_score: int) -> np.ndarray:
    """Exact pmf of a full-attempt score, over the integers ``0..max_score``.

    Every point value in this game is an integer, so the convolution is exact
    and needs no sampling: start with all mass on the bonus floor (S6
    2026-06-17 — a run that does nothing scores 40) and convolve one mission at
    a time. 12 missions x 256 points is trivially cheap, and being exact means
    the result is deterministic by construction rather than by seeding.
    """
    size = max_score + 1
    pmf = np.zeros(size)
    pmf[bonus_floor] = 1.0
    for terms in terms_per_mission:
        shifted = np.zeros(size)
        for points, probability in terms:
            if probability <= 0.0:
                continue
            if points == 0:
                shifted += probability * pmf
            else:
                shifted[points:] += probability * pmf[:size - points]
        pmf = shifted
    total = pmf.sum()
    if not np.isclose(total, 1.0, rtol=0, atol=1e-9):
        raise ValueError(f"pmf mass is {total!r}, not 1 — a mission was not renormalised")
    return pmf / total


def with_collision(pmf: np.ndarray, p_collision: float, cost: int) -> np.ndarray:
    """Mix in the branch where the robot topples a bonus object.

    A collision subtracts ``cost`` points. The score can never fall below the
    subtraction: the pmf's support starts at the bonus floor, and every cost in
    :data:`COLLISION_COSTS` is at most that floor.
    """
    if p_collision == 0.0 or cost == 0:
        return pmf
    if not 0.0 <= p_collision <= 1.0:
        raise ValueError(f"p_collision must be a probability, got {p_collision!r}")
    shifted = np.zeros_like(pmf)
    shifted[:pmf.size - cost] = pmf[cost:]
    if not np.isclose(shifted.sum(), 1.0, rtol=0, atol=1e-9):
        raise ValueError(f"collision cost {cost} pushed mass below zero")
    return (1.0 - p_collision) * pmf + p_collision * shifted


def mean(pmf: np.ndarray) -> float:
    return float(np.arange(pmf.size) @ pmf)


def stdev(pmf: np.ndarray) -> float:
    mu = mean(pmf)
    variance = float((np.arange(pmf.size) ** 2) @ pmf) - mu * mu
    return float(np.sqrt(max(variance, 0.0)))   # clamp float noise, never a nan


def quantile(pmf: np.ndarray, q: float) -> int:
    """Smallest score whose cdf reaches ``q``. Discrete, so no interpolation."""
    return int(np.searchsorted(np.cumsum(pmf), q))


def e_max(pmf: np.ndarray, n: int) -> float:
    """``E[max]`` of ``n`` independent runs drawn from ``pmf``.

    ``P(max <= k) = P(X <= k) ** n``, so the maximum's pmf is the difference of
    the powered cdf. Exact for any n >= 1, and ``n = 1`` returns the mean.

    At n = 2 there is a closed form worth knowing, because it is what makes
    "extra rounds reward variance" a statement rather than an intuition::

        E[max(X1, X2)] = E[X] + E|X1 - X2| / 2

    The premium *is* half the Gini mean difference — a pure dispersion measure.
    ``tests/test_rounds.py`` checks this module against that identity.
    """
    if n < 1:
        raise ValueError(f"n must be at least 1, got {n}")
    cdf = np.cumsum(pmf)
    cdf[-1] = 1.0                                # kill accumulated float error
    powered = cdf ** n
    return float(np.arange(pmf.size) @ np.diff(np.concatenate([[0.0], powered])))


# --------------------------------------------------------------------------- #
# The two decisions this enables
# --------------------------------------------------------------------------- #


def survival(pmf: np.ndarray) -> np.ndarray:
    """``P(score > k)`` for every k. The primary metric under best-of-2.

    Under a single attempt the mean ranks strategies. Under best-of-2 it does
    not: round 2 only matters where it **exceeds** round 1, so what matters is
    the upper tail, not the centre. The survival curve carries that whole tail
    where a mean collapses it to one number.
    """
    return 1.0 - np.cumsum(pmf)


def premium_with_correlation(score_sd: float, rounds_n: int = 2,
                             rho: float = 0.0) -> float:
    """Best-of-N gain over a single attempt, for a correlated normal approximation.

    For two iid normals ``E[max] = mu + sd/sqrt(pi)``. Two rounds are **not**
    iid: they share one robot, one program and one calibration, so a systematic
    component repeats. With correlation ``rho`` only the independent part varies
    between rounds, and the effective spread is ``sd * sqrt(1 - rho)``::

        gain = sd * sqrt(1 - rho) / sqrt(pi)

    **The `sd` here is the SCORE standard deviation in points, not the placement
    error in millimetres.** At sigma = 20 mm the run's score sd is 15.11 points;
    using 20 in this formula overstates the gain by a third. The two quantities
    have different units and there is no reason they should be close.

    **Systematic variance is pure cost. Only independent variance is an asset.**
    At rho = 0.9 the gain collapses from +8.5 to +2.7, which materially narrows
    ADR-027's "extra rounds reward variance" — that claim did not distinguish
    the two components. See ADR-037.

    Exact only for N = 2; higher N uses the same ``sqrt(1 - rho)`` scaling on the
    iid expectation, which is an approximation and is labelled as one.
    """
    if not 0.0 <= rho < 1.0:
        raise ValueError(f"rho must be in [0, 1), got {rho!r}")
    if rounds_n < 1:
        raise ValueError(f"rounds_n must be at least 1, got {rounds_n}")
    if rounds_n == 1:
        return 0.0
    effective = score_sd * math.sqrt(1.0 - rho)
    if rounds_n == 2:
        return effective / math.sqrt(math.pi)
    # E[max of n iid standard normals], Blom's approximation.
    alpha = 0.375
    from statistics import NormalDist
    expected_max = NormalDist().inv_cdf((rounds_n - alpha) / (rounds_n - 2 * alpha + 1))
    return effective * expected_max


def conditional_gain(pmf: np.ndarray, realised: int) -> float:
    """``E[(X - realised)+]`` — what a second round is worth given the first.

    This is the round-2 objective, and it is **not** the mean. Best-of-2 makes
    round 2 a call option struck at the realised round-1 score: only the excess
    counts, everything below is discarded. So a **low** round 1 argues for the
    safe strategy (any competent run beats it) and a **high** round 1 argues for
    the aggressive one (only the tail can beat it) — the opposite of the naive
    reading, in which round 2 is simply another draw.

    Requires that the program may differ between rounds, which S4 §9.3 permits
    only during practice time — open until the organizer confirms whether a
    practice block sits between the two rounds.
    """
    scores = np.arange(pmf.size)
    excess = np.clip(scores - realised, 0, None)
    return float(excess @ pmf)


def breakeven_p_collision(with_mission: np.ndarray, without_mission: np.ndarray,
                          cost: int, n: int, tolerance: float = 1e-9) -> float | None:
    """P(collision) at which attempting a mission stops paying, under best-of-N.

    At ``n = 1`` this reduces to the closed form already in
    ``expected_score.json`` — ``E[points] / cost``. Above it there is no closed
    form, because ``E[max]`` is not linear, so it is found by bisection on a
    monotone function: raising P(collision) can only move probability mass
    downward, so ``E[max]`` decreases in it.

    Returns ``None`` when the mission pays even at P(collision) = 1, which
    happens whenever its expected points exceed what it risks.
    """
    target = e_max(without_mission, n)
    low, high = 0.0, 1.0
    if e_max(with_collision(with_mission, high, cost), n) >= target:
        return None
    if e_max(with_collision(with_mission, low, cost), n) <= target:
        return 0.0
    while high - low > tolerance:
        mid = (low + high) / 2.0
        if e_max(with_collision(with_mission, mid, cost), n) > target:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def retake_is_free(realised: int, running_best: int) -> bool:
    """Whether a §10.14 mulligan costs nothing, given the rounds already run.

    Under a best-of-N ranking, a round scoring at or below your running best
    contributes nothing to your final position. Replacing it with a fresh draw
    can only equal or beat it, so the retake is **weakly dominant** — free.

    The corollary is the one worth carrying to the table: a run that does
    nothing scores exactly the 40-point bonus floor, which is at most any
    completed round, so **a 40 is always free to retake.**

    This holds only under the reading that a mulligan replaces *that round's*
    score. AMBIGUITY(A10): §10.14's "used for the ranking no matter what" can
    also be read as replacing the team's ranking score outright, which reverses
    the advice whenever ``realised > running_best``.
    """
    return realised <= running_best


def retake_threshold(pmf: np.ndarray, running_best: int) -> int:
    """Highest realised score still worth replacing with a fresh run.

    Above the running best a retake is a genuine gamble: it trades a known
    ``realised`` for ``max(running_best, fresh)``. The indifference point is the
    largest score below that expectation.
    """
    fresh = np.zeros_like(pmf)
    fresh[running_best] = pmf[:running_best + 1].sum()
    fresh[running_best + 1:] = pmf[running_best + 1:]
    expectation = mean(fresh / fresh.sum())
    # Retake iff realised < E[max(best, fresh)], so the highest score still worth
    # replacing is one below that expectation. `ceil - 1` rather than `floor`,
    # which would be off by one whenever the expectation lands on an integer —
    # and the epsilon because it often does: a running best of 255 leaves all
    # mass on 255, where float noise alone would otherwise round the answer up.
    return int(np.ceil(expectation - 1e-9)) - 1


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


def load(expected_score: Path = DEFAULT_EXPECTED_SCORE,
         scoring_model: Path = DEFAULT_SCORING_MODEL) -> tuple[dict[str, Any], int, int]:
    """``(expected_score spec, bonus_floor, max_score)``."""
    spec = json.loads(expected_score.read_text(encoding="utf-8"))
    model = json.loads(scoring_model.read_text(encoding="utf-8"))
    bonus_floor = int(next(m["max"] for m in model["missions"] if m["id"] == "m4_bonus"))
    return spec, bonus_floor, int(model["max_score"])


def pmf_at(missions: Sequence[dict[str, Any]], sigma: float,
           bonus_floor: int, max_score: int,
           exclude: str | None = None) -> np.ndarray:
    """Run-score pmf at one sigma, optionally with one mission not attempted.

    A skipped mission scores nothing and — because it is never approached — also
    risks nothing, which is what makes the pair comparable in
    :func:`breakeven_p_collision`.
    """
    terms = []
    for mission in missions:
        if mission["object_id"] == exclude:
            continue
        cell = next(c for c in mission["cells"] if c["sigma_mm"] == sigma)
        terms.append(tier_terms(cell, mission["full_points"], mission["partial_points"]))
    return run_score_pmf(terms, bonus_floor, max_score)
