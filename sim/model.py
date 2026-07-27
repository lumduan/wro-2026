#!/usr/bin/env python3
"""The end-to-end score, and what each unmeasured parameter is worth.

    frontier (which missions fit)  ─┐
    expected_score (what they pay) ─┼─► expected_run_score
    rounds (best of N)             ─┘

Eleven artefacts and nothing composed them. Each declares its own free parameter
and stops:

======================  =====================================  ============
parameter               declared in                            closed by
======================  =====================================  ============
sigma, placement error  expected_score, placement_sensitivity  **B5**
v, driving speed        travel_budget, feasibility_frontier    **P6**
t, pick-and-place       feasibility_frontier                   **MEAS-3**
N, rounds               round_strategy                         **NO-TH**
P(collision)            expected_score                         nothing
carry capacity          travel_budget                          **MEAS-2/3**
======================  =====================================  ============

Six unknowns across five files, and no statement anywhere of **which one
matters**. The operator is about to spend an afternoon measuring; this module
exists so the repo has an opinion on the order.

**There is no new arithmetic here.** Every step already existed:
:func:`sim.frontier.best_reachable` chooses the subset that fits at ``(v, t,
capacity)``; ``data/expected_score.json`` prices each mission at sigma;
:func:`sim.frontier.exposed_bonus` charges the collision risk once per cluster
(ADR-024); :func:`sim.rounds.e_max` applies best-of-N. The value is in saying so
in one place.

**The ceiling is 225, not 255.** The two cables are still `nominal_pending`, so
40 (the bonus floor) plus 185 (the costable placement points) is everything on
the table. Quoting /255 here would overstate by the 30 points nobody can cost yet.

**Nothing here is a prediction.** Every figure is an evaluation at an *assumed*
operating point. Across the corners of the six ranges the answer spans 109 to
225 — which is the honest measure of how much is still unknown, and the reason
the ranking is published as a measurement order rather than a forecast.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Mapping, Sequence

from . import frontier, rounds

#: S1 + S4: the 40-point bonus floor plus the twelve placement missions.
MAX_SCORE: Final = 255

#: What this model can actually reach — 40 + 185. The two cables are absent from
#: every subset because their start poses are `nominal_pending` (work order B0).
REACHABLE_MAX: Final = 225


@dataclass(frozen=True)
class Outcome:
    """One evaluation: what was attempted, and what it is worth."""

    expected_score: float
    subset: tuple[str, ...]
    travel_mm: float
    seconds: float
    bonus_exposed: int


def mission_value(missions: Mapping[str, Any], sigma: float) -> dict[str, float]:
    """``E[points]`` per mission at one sigma, from ``expected_score.json``."""
    out = {}
    for object_id, mission in missions.items():
        cell = next(c for c in mission["cells"] if c["sigma_mm"] == sigma)
        out[object_id] = cell["expected_points"]
    return out


def expected_run_score(missions: Mapping[str, Any], exposure: Mapping[str, int],
                       tours: Mapping[int, float], objects: Sequence[str],
                       *, sigma: float, speed_mm_s: float, pick_place_s: float,
                       rounds_n: int, p_collision: float,
                       bonus_floor: int = 40,
                       attempt: float = 120.0) -> Outcome:
    """The whole chain, in the order the run actually happens.

    1. **Choose.** The highest-*expected*-value subset that fits the attempt at
       this speed and handling time. Not the highest raw-points subset: at
       sigma > 20.4 mm an instrument is worth more than a note (ADR-031), and
       choosing on raw points would attempt the wrong missions.
    2. **Price.** Convolve the chosen missions' tier probabilities into an exact
       score distribution over the integers, starting from the bonus floor.
    3. **Risk.** Subtract the bonus cluster the route exposes — once, not once
       per mission (ADR-024).
    4. **Repeat.** Take ``E[max]`` over N rounds, which rewards variance (ADR-027).

    Steps 2-4 are :mod:`sim.rounds` verbatim; step 1 is :mod:`sim.frontier`.
    """
    worth = mission_value(missions, sigma)
    chosen = frontier.best_reachable(tours, objects, worth, speed_mm_s,
                                     pick_place_s, attempt)
    terms = []
    for object_id in chosen.objects:
        cell = next(c for c in missions[object_id]["cells"] if c["sigma_mm"] == sigma)
        terms.append(rounds.tier_terms(cell, missions[object_id]["full_points"],
                                       missions[object_id]["partial_points"]))
    pmf = rounds.run_score_pmf(terms, bonus_floor, MAX_SCORE)
    exposed = frontier.exposed_bonus(chosen.objects, exposure)
    pmf = rounds.with_collision(pmf, p_collision, exposed)
    return Outcome(
        expected_score=rounds.e_max(pmf, rounds_n),
        subset=chosen.objects,
        travel_mm=chosen.travel_mm,
        seconds=chosen.seconds,
        bonus_exposed=exposed,
    )


def load_missions(expected_score: dict[str, Any], reading: str = "contact",
                  covered: Sequence[str] | None = None
                  ) -> tuple[dict[str, Any], dict[str, int]]:
    """``(missions, exposure)`` keyed by object id, restricted to ``covered``.

    ``expected_score.json`` carries all twelve placement missions; only ten are
    costable, so the caller passes the ten and the two cables drop out here
    rather than silently appearing in a subset that has no tour.
    """
    rows = {m["object_id"]: m for m in expected_score["readings"][reading]["missions"]}
    if covered is not None:
        missing = set(covered) - set(rows)
        if missing:
            raise KeyError(f"expected_score has no mission for {sorted(missing)}")
        rows = {k: v for k, v in rows.items() if k in set(covered)}
    exposure = {k: int(v["bonus_points_exposed"]) for k, v in rows.items()}
    return rows, exposure
