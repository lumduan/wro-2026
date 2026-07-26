#!/usr/bin/env python3
"""Travel distance as a budget, and what manipulator capacity buys against it.

    data/field_spec.json  (start area, note slots, truck bodies, targets)  ─► tours

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

**Ten missions, not six** (ADR-030). :class:`NoteField` is the notes;
:class:`TruckGroup` adds the microphone and three instruments, whose start S1 p4
puts *"in the truck"* — two measured bodies, so their start is **bounded** even
though no pose is known. :class:`FullField` composes them: 185 of the 215
placement points, over a 24 x 16 grid of note permutations against vehicle
choices. Only the two cables are genuinely pending; *"close to the stage"* is not
a measured region.

**Time is spent on objects, not only on distance.** With ten objects, every
second of pick-and-place costs ten seconds of the attempt, and at
``ATTEMPT_SECONDS / 10 = 12`` s per object the run cannot be completed at any
driving speed — see :func:`impossible_beyond`. That threshold touches no geometry,
so no route and no motor moves it.

**Everything here is a lower bound.** Distances are straight-line, matching
``tools/build_strategy_frame.py``. A real path has turning radius, acceleration
and pick/place time, all unmeasured until field test **P6**. So a required speed
computed here is a floor the robot must clear, never a prediction that it will.
See AS-11, and AS-12 for the truck's residual.

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


def tour_points(sources: Sequence[Point], targets: Sequence[Point],
                start: Point, capacity: int) -> float:
    """Shortest distance to fetch and deliver every object, then return to start.

    Exact, by dynamic programming over ``(objects remaining, current position)``.
    The robot works in batches of at most ``capacity``, picking a batch up and
    then delivering it, which is what a magazine or multi-slot gripper does.

    Exact rather than heuristic, and with no sampling anywhere, so the result is
    deterministic by construction — the same property ``sim.rounds`` gets from
    convolving instead of simulating.

    **Cost grows steeply.** Each batch of size *s* enumerates ``s! x s!`` pickup
    and delivery orders, and the states are ``2**n`` subsets. Six notes at any
    capacity is instant; ten missions cost ~0.08 s at capacity 1, ~0.5 s at 2,
    ~3.5 s at 3, and are intractable above that. `build_travel_budget.py` bounds
    what it asks for accordingly.
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
        return best_from((1 << n) - 1, start)
    finally:
        best_from.cache_clear()      # positions are per-assignment; never reuse


def tour(assign: dict[str, Point], field: NoteField, capacity: int) -> float:
    """The six-note case: :func:`tour_points` over ``field.notes``."""
    return tour_points([assign[n] for n in field.notes],
                       [field.targets[n] for n in field.notes],
                       field.start, capacity)


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
# The truck — a bounded start, not a pending one
# --------------------------------------------------------------------------- #

#: The two `#afbbdf` vehicle bodies, added as measured areas by ADR-030.
TRUCK_VEHICLES: Final = ("truck_vehicle_left", "truck_vehicle_right")


class TruckGroup:
    """Where the microphone and three instruments start, bounded rather than known.

    S1 p4 puts all four *"in the truck"*, and the truck is two disjoint bodies at
    the mat's lower edge. `field_spec.json` gives them no pose — ADR-014 refuses
    to invent one — which left 65 of 255 points with no geometry at all, so no
    route through them could be costed.

    A bound is not a pose. Two things are unknown and they are different in kind:

    1. **Which vehicle** each object sits on. Discrete, four objects, so 2**4 = 16
       assignments — enumerated, exactly as the notes' 24 permutations are.
    2. **Where on that vehicle.** Continuous, and much smaller: the targets are
       over a metre away, so moving an object across its own vehicle body barely
       moves the leg. Reported separately as a residual rather than folded in.

    Work order **B0** collapses both to a measurement.
    """

    def __init__(self, field_spec: dict[str, Any], targets: dict[str, Point]) -> None:
        areas = field_spec["areas"]
        self.members: tuple[str, ...] = tuple(field_spec["start_groups"]["truck"]["members"])
        self.vehicles: tuple[Point, ...] = tuple(
            tuple(centroid([(float(x), float(y))
                            for x, y in areas[v]["polygon_visible_mm"]]))
            for v in TRUCK_VEHICLES)
        self.vehicle_corners: tuple[tuple[Point, ...], ...] = tuple(
            tuple((float(x), float(y)) for x, y in areas[v]["polygon_visible_mm"])
            for v in TRUCK_VEHICLES)
        self.targets: dict[str, Point] = {m: targets[m] for m in self.members}

    def assignments(self) -> list[dict[str, Point]]:
        """All 2**4 vehicle choices. A free product, not a bijection.

        Unlike the notes, nothing says the four objects occupy distinct vehicles
        — S1 says only "in the truck".
        """
        return [dict(zip(self.members, combo))
                for combo in itertools.product(self.vehicles, repeat=len(self.members))]

    def within_vehicle_span(self, start: Point) -> dict[str, float]:
        """How much the *unknown position on a vehicle* is worth, per object.

        Measured, not bounded by the diagonal: the fetch-and-deliver leg is
        evaluated at every corner of both bodies and the span reported. It is the
        residual left after :meth:`assignments` has enumerated the discrete part.
        """
        corners = [c for body in self.vehicle_corners for c in body]
        out = {}
        for member in self.members:
            target = self.targets[member]
            legs = [distance(start, c) + distance(c, target) for c in corners]
            out[member] = max(legs) - min(legs)
        return out


class FullField:
    """Every placement mission whose start geometry is known: the notes plus the truck.

    Ten of twelve — **185 of the 215 placement points**. The two cables are the
    genuine remainder: S1 puts them *"close to the stage (left end)"*, which is
    not a measured region, so they stay `nominal_pending` until work order **B0**.
    """

    def __init__(self, field_spec: dict[str, Any], notes: NoteField,
                 truck_targets: dict[str, Point]) -> None:
        self.notes = notes
        self.truck = TruckGroup(field_spec, truck_targets)
        self.start = notes.start
        self.objects: tuple[str, ...] = notes.notes + self.truck.members
        self.targets: dict[str, Point] = {**notes.targets, **self.truck.targets}

    def assignments(self) -> list[dict[str, Point]]:
        """24 note permutations x 16 vehicle choices = 384 joint start states."""
        return [{**note_assign, **truck_assign}
                for note_assign in self.notes.assignments()
                for truck_assign in self.truck.assignments()]

    def tour(self, assign: dict[str, Point], capacity: int) -> float:
        return tour_points([assign[o] for o in self.objects],
                           [self.targets[o] for o in self.objects],
                           self.start, capacity)


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


def driving_seconds(objects: int, seconds_per_object: float,
                    attempt: float = ATTEMPT_SECONDS) -> float:
    """Clock left for driving once pick-and-place has taken its share.

    The multiplier is the point: with *n* objects, **every second of
    pick-and-place costs n seconds of the attempt**. Ten objects and 12 s each
    consumes the whole 120 s, so beyond that threshold the run cannot be
    completed at any driving speed — a constraint on the *mechanism* that no
    motor can buy back. See :func:`impossible_beyond`.
    """
    return attempt - objects * seconds_per_object


def impossible_beyond(objects: int, attempt: float = ATTEMPT_SECONDS) -> float:
    """Seconds per object at which no driving time remains, whatever the speed."""
    if objects <= 0:
        raise ValueError(f"objects must be positive, got {objects}")
    return attempt / objects


def spread(values: Iterable[float]) -> float:
    ordered = sorted(values)
    return ordered[-1] - ordered[0]
