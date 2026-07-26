#!/usr/bin/env python3
"""Travel distance as a budget, and what manipulator capacity buys against it.

    data/field_spec.json  (start area, note start slots, target polygons)  ─► tours

Eight phases went into **accuracy**. Nothing asked whether a run fits in the
**120 seconds** S4 §10.1 allows. ``attempt_seconds: 120`` sits in
``data/scoring_model.json`` and is quoted in three documents; no artefact ever
turned geometry into distance. CLAUDE.md §5.7 anti-pattern #5 forbids optimising
for 255/255 without reporting ``P(success)`` — a strategy that places perfectly
and runs out of clock fails the same way, and was invisible.

**What capacity buys.** S1 p7 assigns four notes to four light-green slots at
randomization, giving 4! = 24 permutations, and S4 §9.6 does it *after*
quarantine. Which colour lands where moves real distance — but only if the robot
carries one note at a time:

======== ======= ========== ==================
capacity  worst   spread     over the 24 perms
======== ======= ========== ==================
1         7592     1000 mm    15.2 %
2         5379      658 mm
3         4378      426 mm
4         4045      552 mm    **rises again**
5         3554      425 mm
6         2986        0 mm    **exactly zero**
======== ======= ========== ==================

The zero is **structural, not numerical**. A robot that collects every note
before delivering any visits the same set of points whatever the permutation —
the four slots and the six targets — so the tour length cannot depend on which
colour is in which slot. Capacity does not merely shorten the route, it *deletes
the randomization as a source of variance*.

And it is a **phase change, not the end of a slope**. Total travel falls
monotonically with capacity — a tour feasible at *k* is feasible at *k+1* — but
the spread does not: going from 3 to 4 makes the randomization *worse*. Only
carrying every note at once removes it, so a mechanism that carries "most" of
them buys distance without buying predictability.

It also makes sensing free. §10.2 forbids entering data by moving robot parts, so
the permutation must be read at runtime (``docs/PHASE7_CONSTRAINTS.md`` §5). At
high capacity the robot passes every slot anyway; at capacity 1 it must either
spend a scanning pass or commit blind.

**Everything here is a lower bound.** Distances are straight-line, matching
``tools/build_strategy_frame.py``. A real path has turning radius, acceleration
and pick/place time, all unmeasured until field test **P6**. So a required speed
computed here is a floor the robot must clear, never a prediction that it will.
See AS-11.

This does not choose a capacity — that needs note mass and grip geometry (work
order **A2/A3**), and ADR-022 left the mechanism open on purpose.
"""

from __future__ import annotations

import itertools
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Final, Iterable, Sequence

from .geometry import centroid

DEFAULT_FIELD_SPEC: Final = Path("data/field_spec.json")

Point = tuple[float, float]

#: Every carry capacity, 1 through 6. Reporting all of them is deliberate:
#: total travel falls monotonically with capacity, but the **spread** across the
#: 24 permutations does **not** — it runs 1000, 658, 426, 552, 425, 0. Publishing
#: only 1/2/3/6 would imply a smooth trend to zero that does not exist. Reaching
#: full capacity is a phase change, not the end of a slope: going from 3 to 4
#: makes the randomization *worse*.
DEFAULT_CAPACITIES: Final = (1, 2, 3, 4, 5, 6)

#: S4 §10.1. The whole reason this module exists.
ATTEMPT_SECONDS: Final = 120.0


def distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


# --------------------------------------------------------------------------- #
# The field, read rather than hard-coded
# --------------------------------------------------------------------------- #


class NoteField:
    """Start area, note start slots and note targets, straight from S5."""

    def __init__(self, field_spec: dict[str, Any]) -> None:
        areas = field_spec["areas"]
        self.start: Point = tuple(centroid(
            [(float(x), float(y)) for x, y in areas["start_area"]["polygon_visible_mm"]]))

        randomization = field_spec["randomization"]
        self.randomized: tuple[str, ...] = tuple(randomization["notes"])
        self.fixed: dict[str, str] = dict(randomization["fixed"])
        self.notes: tuple[str, ...] = self.randomized + tuple(sorted(self.fixed))

        starts = field_spec["note_starts"]
        self.slots: tuple[Point, ...] = tuple(
            tuple(starts[slot_id]["centre_mm"])
            for slot_id in randomization["randomizable_slots"])
        self.fixed_starts: dict[str, Point] = {
            note_id: tuple(starts[slot_id]["centre_mm"])
            for note_id, slot_id in self.fixed.items()}
        self.targets: dict[str, Point] = {
            note_id: tuple(centroid(
                [(float(x), float(y))
                 for x, y in areas[f"note_target_{note_id.removeprefix('note_')}"]
                 ["polygon_visible_mm"]]))
            for note_id in self.notes}

    @classmethod
    def load(cls, field_spec: Path = DEFAULT_FIELD_SPEC) -> "NoteField":
        return cls(json.loads(field_spec.read_text(encoding="utf-8")))

    def assignments(self) -> list[dict[str, Point]]:
        """All 24 note -> start-point maps, one per permutation. Order is fixed."""
        out = []
        for slot_order in itertools.permutations(self.slots):
            assign = dict(zip(self.randomized, slot_order))
            assign.update(self.fixed_starts)
            out.append(assign)
        return out


# --------------------------------------------------------------------------- #
# The tour
# --------------------------------------------------------------------------- #


def _batch_cost(sources: Sequence[Point], targets: Sequence[Point],
                members: Sequence[int], frm: Point) -> tuple[float, Point]:
    """Pick up every member, then deliver every member. Exact over both orders."""
    best, end = math.inf, frm
    for pickup in itertools.permutations(members):
        here, collected = frm, 0.0
        for i in pickup:
            collected += distance(here, sources[i])
            here = sources[i]
        if collected >= best:
            continue
        for dropoff in itertools.permutations(members):
            there, delivered = here, 0.0
            for i in dropoff:
                delivered += distance(there, targets[i])
                there = targets[i]
                if collected + delivered >= best:
                    break
            else:
                best, end = collected + delivered, there
    return best, end


def tour(assign: dict[str, Point], field: NoteField, capacity: int) -> float:
    """Shortest distance to fetch and deliver every note, then return to start.

    Exact, by dynamic programming over ``(notes remaining, current position)``:
    64 subsets x 7 positions. The robot works in batches of at most ``capacity``
    notes, picking a batch up and then delivering it, which is what a magazine or
    a multi-slot gripper actually does.

    Exact rather than heuristic, and with no sampling anywhere, so the result is
    deterministic by construction — the same property ``sim.rounds`` gets from
    convolving instead of simulating.
    """
    if capacity < 1:
        raise ValueError(f"capacity must be at least 1, got {capacity}")
    notes = field.notes
    sources = [assign[n] for n in notes]
    targets = [field.targets[n] for n in notes]
    full = (1 << len(notes)) - 1

    @lru_cache(maxsize=None)
    def best_from(remaining: int, here: Point) -> float:
        if not remaining:
            return distance(here, field.start)
        available = [i for i in range(len(notes)) if remaining >> i & 1]
        best = math.inf
        for size in range(1, min(capacity, len(available)) + 1):
            for members in itertools.combinations(available, size):
                cost, end = _batch_cost(sources, targets, members, here)
                bits = sum(1 << i for i in members)
                best = min(best, cost + best_from(remaining & ~bits, end))
        return best

    try:
        return best_from(full, field.start)
    finally:
        best_from.cache_clear()      # positions are per-assignment; never reuse


def tour_by_brute_force(assign: dict[str, Point], field: NoteField,
                        capacity: int) -> float:
    """Independent check of :func:`tour`, tractable only at the two extremes.

    At capacity 1 the tour is a permutation of six fetch-and-deliver trips; at
    capacity 6 it is one pickup order followed by one delivery order. Both are
    6! or 6!x6! enumerations with no dynamic programming, so agreement between
    the two implementations is real evidence rather than a restated assumption.
    """
    notes = field.notes
    sources = [assign[n] for n in notes]
    targets = [field.targets[n] for n in notes]
    n = len(notes)
    if capacity == 1:
        best = math.inf
        for order in itertools.permutations(range(n)):
            here, total = field.start, 0.0
            for i in order:
                total += distance(here, sources[i]) + distance(sources[i], targets[i])
                here = targets[i]
            best = min(best, total + distance(here, field.start))
        return best
    if capacity >= n:
        cost, end = _batch_cost(sources, targets, tuple(range(n)), field.start)
        return cost + distance(end, field.start)
    raise ValueError(f"brute force is only tractable at capacity 1 or >= {n}")


# --------------------------------------------------------------------------- #
# Turning distance into a requirement
# --------------------------------------------------------------------------- #


def required_speed(distance_mm: float, seconds: float = ATTEMPT_SECONDS) -> float:
    """Mean speed in mm/s needed to cover ``distance_mm`` within the attempt.

    The time analogue of the required *placement accuracy* in
    ``data/placement_sensitivity.json``: a number the robot must beat, published
    so that field test P6 has something to test against. It is a **floor** —
    straight-line distance, no turns, no acceleration, no pick or place time.
    """
    if seconds <= 0:
        raise ValueError(f"seconds must be positive, got {seconds}")
    return distance_mm / seconds


def spread(values: Iterable[float]) -> float:
    ordered = sorted(values)
    return ordered[-1] - ordered[0]
