#!/usr/bin/env python3
"""How accurate does placement have to be?

`CLAUDE.md` §5.7 anti-pattern #5 forbids reporting a score without its
`P(success)`. This module is what makes that possible: it perturbs each object's
placement by a Gaussian error and measures how often the placement still scores.

**What is modelled and what is not.** The error *distribution* is modelled; the
robot is not. A time-stepped robot would need friction, odometry drift and
motor response, every one of which is an unmeasured ``ASSUME:`` until field
tests P1-P6 run — it would produce authoritative-looking numbers with nothing
behind them. Modelling the outcome instead keeps exactly one unknown, ``sigma``,
and names it: **field tests P2 and P3 measure it.**

So the output is not "we will score N". It is the far more useful shape:

    for each mission, the placement accuracy at which it becomes worth attempting

which Phase 7 needs to size the gripper, and which is available today.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from typing import Any, Final, Sequence

import numpy as np

from .scoring import Scorer
from .world import ObjectState

#: Fixed seed: the sweep is a build artefact and must be byte-reproducible.
DEFAULT_SEED: Final = 20260726

#: Samples per (object, sigma) cell. At P = 0.9 the standard error of the
#: estimate is sqrt(0.9*0.1/4000) = 0.005, i.e. +/-0.5 pp — an order of
#: magnitude finer than any decision made from this table.
DEFAULT_SAMPLES: Final = 4000

#: Placement-error grid in mm. Spans from far better than any LEGO robot
#: achieves to far worse, so every mission's threshold lands inside the grid.
DEFAULT_SIGMA_MM: Final = (0.0, 1.0, 2.0, 3.0, 5.0, 7.5, 10.0, 15.0, 20.0, 30.0, 45.0)

#: Heading error in degrees, held proportional to the translation error.
#: `ASSUME:` 0.5 deg per mm of sigma — a placeholder shape, not a measurement.
#: Field test P3 (odometry drift per 90 deg) replaces it.
DEG_PER_MM: Final = 0.5


@dataclass(frozen=True)
class Cell:
    """One (object, sigma) outcome."""

    object_id: str
    target_id: str
    sigma_mm: float
    sigma_deg: float
    p_full: float
    p_partial: float
    p_none: float
    samples: int


def success_probability(scorer: Scorer, object_id: str, target_id: str,
                        x_mm: float, y_mm: float, theta_deg: float,
                        sigma_mm: float, *, samples: int = DEFAULT_SAMPLES,
                        seed: int = DEFAULT_SEED,
                        deg_per_mm: float = DEG_PER_MM) -> Cell:
    """Fraction of perturbed placements that reach each containment tier.

    The RNG is seeded per (object, target, sigma) so a cell's value does not
    depend on the order cells are evaluated in — without that, adding a mission
    to the sweep would silently change every later mission's numbers.
    """
    sigma_deg = sigma_mm * deg_per_mm
    if sigma_mm == 0.0:
        tier, _ = scorer.containment(
            ObjectState(object_id, x_mm, y_mm, theta_deg), target_id)
        return Cell(object_id, target_id, 0.0, 0.0,
                    float(tier == "full"), float(tier == "partial"),
                    float(tier == "none"), 1)

    # zlib.crc32, not hash(): Python randomises string hashing per process
    # (PYTHONHASHSEED), so `hash` here produced a different stream on every run
    # and the artefact was not byte-reproducible. Caught by the determinism
    # check, which is exactly what it is for.
    key = f"{object_id}|{target_id}|{sigma_mm}"
    rng = np.random.default_rng([seed, zlib.crc32(key.encode("utf-8"))])
    dx = rng.normal(0.0, sigma_mm, samples)
    dy = rng.normal(0.0, sigma_mm, samples)
    dth = rng.normal(0.0, sigma_deg, samples)

    counts = {"full": 0, "partial": 0, "none": 0}
    for i in range(samples):
        state = ObjectState(object_id, x_mm + dx[i], y_mm + dy[i], theta_deg + dth[i])
        tier, _ = scorer.containment(state, target_id)
        counts[tier] += 1
    return Cell(object_id, target_id, sigma_mm, sigma_deg,
                counts["full"] / samples, counts["partial"] / samples,
                counts["none"] / samples, samples)


def threshold_sigma(cells: Sequence[Cell], p_target: float) -> float | None:
    """Largest sigma whose ``p_full`` still clears ``p_target``, interpolated.

    Returns ``None`` when the requirement is never met — which is the honest
    answer for a placement that is geometrically impossible, and must not be
    reported as "0 mm" as if a perfect robot could do it.
    """
    ordered = sorted(cells, key=lambda c: c.sigma_mm)
    if not ordered or ordered[0].p_full < p_target:
        return None
    best = ordered[0].sigma_mm
    for lo, hi in zip(ordered, ordered[1:]):
        if hi.p_full >= p_target:
            best = hi.sigma_mm
            continue
        span = lo.p_full - hi.p_full
        if span > 0:
            frac = (lo.p_full - p_target) / span
            best = lo.sigma_mm + frac * (hi.sigma_mm - lo.sigma_mm)
        break
    return float(best)


def sweep(scorer: Scorer, *, sigmas: Sequence[float] = DEFAULT_SIGMA_MM,
          samples: int = DEFAULT_SAMPLES, seed: int = DEFAULT_SEED,
          extra_orientations: dict[str, float] | None = None
          ) -> dict[str, list[Cell]]:
    """Run the grid for every object with a nominal placement.

    ``extra_orientations`` adds a second heading for an object under a distinct
    key, so the cable can be evaluated both along and across its target area.
    """
    placements = scorer.nominal_placements()
    jobs: dict[str, tuple[str, float, float, float]] = dict(placements)
    for label, theta in (extra_orientations or {}).items():
        base = label.split("@")[0]
        target, x, y, _ = placements[base]
        jobs[label] = (target, x, y, theta)

    out: dict[str, list[Cell]] = {}
    for label, (target, x, y, theta) in sorted(jobs.items()):
        object_id = label.split("@")[0]
        out[label] = [
            success_probability(scorer, object_id, target, x, y, theta, sigma,
                                samples=samples, seed=seed)
            for sigma in sigmas
        ]
    return out
