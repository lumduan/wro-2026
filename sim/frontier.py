#!/usr/bin/env python3
"""Which missions fit in 120 seconds, and what they score.

    sim.travel (tours)  +  data/scoring_model.json (points)  ─► frontier

Three units built the pieces and nothing joined them. ``data/travel_budget.json``
knows how far every mission is; ``data/expected_score.json`` knows what each tier
of accuracy pays; ``data/round_strategy.json`` knows how a best-of-N ranking
changes the objective. None of them answers the question a team actually asks:

    given a robot that drives at *v* and picks-and-places in *t*, which missions
    fit in the attempt, and what do they score?

**Why this is allowed now.** ``data/strategy_frame.json`` refused mission
ordering in as many words — *"needs σ from field tests P2/P3 and the object
pickup locations, 15 of which are nominal_pending"* — and CLAUDE.md §5.7
anti-pattern #3 forbids claiming one strategy beats another without simulator
evidence. Both halves have since been built: ADR-029 and ADR-030 give exact tours
for ten of the twelve placement missions. And feasibility does not need σ — σ
governs whether an attempted placement *scores*, not whether it *fits*. So the
refusal lifts for the covered set, and only for it. The two cables are still
`nominal_pending`, so every subset here is missing them and the frontier is a
**lower bound**: 185 of the 215 placement points, never 215.

**The subset tours are free.** ``sim.travel.tour_points`` already memoises
``best_from(remaining, position)``, and ``best_from(S, start)`` *is* the optimal
tour for subset ``S``. Querying every subset against one shared memo costs 0.1 s
at capacity 1 and 0.6 s at capacity 2 for ten missions — the same work the full
tour already did.

**What the answer looks like.** Speed saturates and pick-and-place does not. The
185-point ceiling is reached at 85 mm/s when ``t = 0`` and 255 mm/s when
``t = 8``; above that line more speed buys *nothing*, while every extra second of
pick-and-place costs about 15 points — one instrument. See ADR-031.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Final, Iterable, Mapping, Sequence

from .travel import ATTEMPT_SECONDS, Point, _batch_cost, distance

#: Speeds to tabulate, mm/s. The low end is below anything a LEGO drive does; the
#: high end is past the point where speed stops buying anything, deliberately, so
#: the saturation is visible in the published table rather than asserted.
DEFAULT_SPEEDS: Final = (75, 100, 125, 150, 175, 200, 250, 300, 400, 500)

#: Pick-and-place seconds per object, matching `build_travel_budget`.
DEFAULT_PICK_PLACE: Final = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0)


@dataclass(frozen=True)
class Reachable:
    """The best subset that fits, and what it costs."""

    subset: int
    objects: tuple[str, ...]
    points: float
    travel_mm: float
    seconds: float


def subset_tours(sources: Sequence[Point], targets: Sequence[Point],
                 start: Point, capacity: int) -> dict[int, float]:
    """Optimal tour for **every** subset, from a single dynamic program.

    ``sim.travel.tour_points`` solves ``best_from(remaining, here)`` and asks only
    for the full set. The same memo answers every subset: ``best_from(S, start)``
    is the optimal tour over ``S``. So the whole 2**n table costs barely more than
    the one tour already computed.

    Returns ``{subset bitmask: distance_mm}``, including ``{0: 0.0}`` — doing
    nothing travels nothing, and still scores the 40-point bonus floor.
    """
    if capacity < 1:
        raise ValueError(f"capacity must be at least 1, got {capacity}")
    n = len(sources)
    if n != len(targets):
        raise ValueError(f"{n} sources against {len(targets)} targets")

    @lru_cache(maxsize=None)
    def best_from(remaining: int, here: Point) -> float:
        if not remaining:
            return distance(here, start)
        available = [i for i in range(n) if remaining >> i & 1]
        best = math.inf
        for size in range(1, min(capacity, len(available)) + 1):
            for members in itertools.combinations(available, size):
                cost, end = _batch_cost(sources, targets, members, here)
                bits = sum(1 << i for i in members)
                best = min(best, cost + best_from(remaining & ~bits, end))
        return best

    try:
        # The empty subset is a special case: best_from returns the trip home,
        # which for `start` is zero, but stating it beats relying on it.
        return {subset: (0.0 if subset == 0 else best_from(subset, start))
                for subset in range(1 << n)}
    finally:
        best_from.cache_clear()


def seconds_for(travel_mm: float, count: int, speed_mm_s: float,
                pick_place_s: float) -> float:
    """Attempt time: driving plus one pick-and-place per object attempted."""
    if speed_mm_s <= 0:
        raise ValueError(f"speed must be positive, got {speed_mm_s}")
    return travel_mm / speed_mm_s + count * pick_place_s


def best_reachable(tours: Mapping[int, float], objects: Sequence[str],
                   value: Mapping[str, float], speed_mm_s: float,
                   pick_place_s: float,
                   attempt: float = ATTEMPT_SECONDS) -> Reachable:
    """Highest-scoring subset that fits the attempt.

    An exhaustive maximum over every subset, not a heuristic: 1024 candidates is
    nothing once the tours are in hand, and a greedy rule would get exactly the
    case this exists to expose — ``mic`` being dropped ahead of a cheaper
    instrument because it costs more travel than the points it brings back.

    Ties break toward the shorter tour, so the reported subset is the cheapest
    way to reach its score rather than an arbitrary one.
    """
    best = Reachable(0, (), 0.0, 0.0, 0.0)
    for subset, travel_mm in tours.items():
        members = tuple(o for i, o in enumerate(objects) if subset >> i & 1)
        elapsed = seconds_for(travel_mm, len(members), speed_mm_s, pick_place_s)
        if elapsed > attempt:
            continue
        points = sum(value[o] for o in members)
        if points > best.points or (points == best.points and travel_mm < best.travel_mm):
            best = Reachable(subset, members, points, travel_mm, elapsed)
    return best


def subset_profile(objects: Sequence[str],
                   value: Mapping[str, float]) -> tuple[list[int], list[float]]:
    """``(count, points)`` per subset — **independent of where anything starts**.

    Only the *travel* of a subset depends on the randomization; how many objects
    it contains and what they are worth do not. Hoisting both out of the
    permutation loop is what makes sweeping all 384 start states cheap: 12x
    faster than rebuilding the member tuple per cell, measured.
    """
    n = len(objects)
    counts = [bin(subset).count("1") for subset in range(1 << n)]
    points = [sum(value[objects[i]] for i in range(n) if subset >> i & 1)
              for subset in range(1 << n)]
    return counts, points


def best_points(tours: Mapping[int, float], counts: Sequence[int],
                points: Sequence[float], speed_mm_s: float, pick_place_s: float,
                attempt: float = ATTEMPT_SECONDS) -> float:
    """Highest score that fits, given a profile from :func:`subset_profile`.

    The hot path of the sweep. :func:`best_reachable` answers the same question
    and also names the subset; this one is for the 384 x 90 grid where only the
    number is wanted.
    """
    if speed_mm_s <= 0:
        raise ValueError(f"speed must be positive, got {speed_mm_s}")
    return max((points[s] for s, travel_mm in tours.items()
                if travel_mm / speed_mm_s + counts[s] * pick_place_s <= attempt),
               default=0.0)


def ceiling(tours: Mapping[int, float], objects: Sequence[str],
            value: Mapping[str, float], pick_place_s: float,
            attempt: float = ATTEMPT_SECONDS) -> float:
    """Points reachable with **unlimited** speed — driving time taken to zero.

    The bound that makes saturation meaningful: no speed buys past it, so a
    frontier that has reached it has stopped depending on P6 entirely.
    """
    best = 0.0
    for subset in tours:
        members = [o for i, o in enumerate(objects) if subset >> i & 1]
        if len(members) * pick_place_s <= attempt:
            best = max(best, sum(value[o] for o in members))
    return best


def saturation_speed(tours: Mapping[int, float], objects: Sequence[str],
                     value: Mapping[str, float], pick_place_s: float,
                     attempt: float = ATTEMPT_SECONDS) -> float | None:
    """Exact lowest speed that reaches the ceiling. ``None`` if no speed does.

    This is the number that decides how much field test **P6** matters: above it
    a faster robot scores no more, and the whole budget is pick-and-place.

    Exact rather than the smallest tabulated speed, and by formula rather than
    search: a subset fits iff ``travel / v + count * t <= attempt``, so the speed
    it needs is ``travel / (attempt - count * t)``. The answer is the cheapest of
    those over every subset that reaches the ceiling — several may, and the one
    with fewest objects is not always the one with the shortest tour.
    """
    target = ceiling(tours, objects, value, pick_place_s, attempt)
    if target <= 0:
        return None
    best = math.inf
    for subset, travel_mm in tours.items():
        members = [o for i, o in enumerate(objects) if subset >> i & 1]
        if sum(value[o] for o in members) < target:
            continue
        driving = attempt - len(members) * pick_place_s
        if driving <= 0:
            continue
        best = min(best, travel_mm / driving)
    return None if math.isinf(best) else best


def expected_value(spec: dict[str, Any], reading: str, sigma: float) -> dict[str, float]:
    """Per-mission ``E[points]`` at one σ, straight from ``expected_score.json``.

    Feasibility says a mission *fits*; this says what it is worth once placed
    imperfectly. Keeping them separate is deliberate — a subset can be reachable
    and still not worth reaching.
    """
    out = {}
    for mission in spec["readings"][reading]["missions"]:
        cell = next(c for c in mission["cells"] if c["sigma_mm"] == sigma)
        out[mission["object_id"]] = cell["expected_points"]
    return out


def exposed_bonus(members: Iterable[str], exposure: Mapping[str, int]) -> int:
    """Bonus points a subset puts at risk — the max over its missions, not the sum.

    ADR-024: the 40 is four objects in two clusters, and a route that visits the
    stage exposes that cluster once however many missions it serves there. Summing
    would double-count the same speaker.
    """
    values = [exposure[m] for m in members]
    return max(values) if values else 0
