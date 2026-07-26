#!/usr/bin/env python3
"""A :class:`~robot_io.RobotIO` backed by the simulator, for testing mission logic.

Run a mission against this, hand the resulting :class:`~sim.world.WorldState` to
:class:`~sim.scoring.Scorer`, and assert the score. That makes a mission
program's **logic** verifiable today, with no hardware.

**It is not a performance model, and the distinction is the whole point.** There
is no friction, no wheel slip, no odometry drift and no motor response here,
because every one of those is an unmeasured ``ASSUME:`` until field tests P1-P6
run. Phase 6 drew this line for the placement sweep and it is drawn again here
for the same reason: a model built on invented parameters produces
authoritative-looking numbers with nothing behind them.

So this answers *"does the mission put the right objects in the right areas?"*
and never *"will it score on the day?"*.

``read_reflection`` is the sharpest case. Nothing in this repo has sampled the
mat's colours under any lighting — that is field test **P1** — so by default this
backend returns a constant and flags ``reflection_is_modelled = False``. A test
that branches on a reflection reading is testing the stub, not the mission.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "robot"))

from robot_io import RobotIO  # noqa: E402

from .world import ObjectState, WorldState  # noqa: E402

#: Returned by ``read_reflection`` when no surface model is supplied. Not a
#: measurement of anything; field test P1 samples the real mat.
UNMODELLED_REFLECTION = 50.0

#: How close the robot must be to an object to pick it up, in mm. A modelling
#: convenience, not a mechanism specification — ADR-022 leaves the mechanism
#: open, so no reach figure is derivable yet.
DEFAULT_PICKUP_RADIUS_MM = 40.0


class SimRobotIO(RobotIO):
    """Exact kinematics over a :class:`~sim.world.WorldState`.

    Every command completes perfectly. That is deliberate: it isolates mission
    *logic* from execution error, which the placement sweep in
    ``data/placement_sensitivity.json`` already models separately and properly.
    """

    def __init__(self, world: WorldState | None = None,
                 x_mm: float = 0.0, y_mm: float = 0.0, heading_deg: float = 0.0,
                 pickup_radius_mm: float = DEFAULT_PICKUP_RADIUS_MM,
                 surface: Callable[[float, float], float] | None = None):
        self.world = world if world is not None else WorldState()
        self.x_mm = float(x_mm)
        self.y_mm = float(y_mm)
        self.heading_deg = float(heading_deg)
        self.pickup_radius_mm = float(pickup_radius_mm)
        self._surface = surface
        self.reflection_is_modelled = surface is not None
        self._carrying: str | None = None
        self.started = False
        self.stopped = False
        #: Every call, in order. A mission's behaviour is auditable without
        #: instrumenting the mission itself.
        self.log: list[tuple[str, Any]] = []

    # ------------------------------------------------------------------ #
    # Run control
    # ------------------------------------------------------------------ #

    def wait_for_start(self) -> None:
        self.started = True
        self.log.append(("wait_for_start", None))

    def stop(self) -> None:
        self.stopped = True
        self.log.append(("stop", None))

    # ------------------------------------------------------------------ #
    # Motion
    # ------------------------------------------------------------------ #

    def drive_straight(self, distance_mm: float) -> None:
        radians = math.radians(self.heading_deg)
        self.x_mm += distance_mm * math.cos(radians)
        self.y_mm += distance_mm * math.sin(radians)
        if self._carrying:
            self._move_carried()
        self.log.append(("drive_straight", float(distance_mm)))

    def turn(self, angle_deg: float) -> None:
        """CCW positive, matching the MAT frame (CLAUDE.md §5.2)."""
        self.heading_deg = (self.heading_deg + angle_deg) % 360.0
        if self._carrying:
            self._move_carried()
        self.log.append(("turn", float(angle_deg)))

    def heading(self) -> float:
        """Exact here. On hardware it is odometry and it drifts (P3)."""
        return self.heading_deg

    # ------------------------------------------------------------------ #
    # Manipulation
    # ------------------------------------------------------------------ #

    def pick_up(self) -> None:
        """Acquire the single object in reach — and refuse if there are two.

        Ambiguity raises rather than picking one. This is not pedantry: 15 of
        the 17 object start poses are ``nominal_pending`` with null coordinates
        (ADR-014 refuses to invent them), so unplaced objects sit at the origin
        and several are genuinely equidistant. Silently taking the first in dict
        order once made a test carry the **amplifier** to a note target — losing
        10 bonus points and 20 note points — and report it as a pass.
        """
        if self._carrying:
            raise RuntimeError(
                "already carrying " + self._carrying + "; place() it first")
        in_reach = self._objects_in_reach()
        if len(in_reach) > 1:
            raise RuntimeError(
                "ambiguous pick_up: " + ", ".join(sorted(in_reach)) + " are all "
                "within " + str(self.pickup_radius_mm) + " mm. A real robot "
                "grabs whatever is in front of it; a test must be explicit.")
        nearest, distance = self._nearest_object()
        if nearest is None or distance > self.pickup_radius_mm:
            raise RuntimeError(
                "nothing within " + str(self.pickup_radius_mm) + " mm of "
                "(" + str(round(self.x_mm, 1)) + ", " + str(round(self.y_mm, 1)) + ")")
        self._carrying = nearest
        state = self.world.get(nearest)
        self.world.objects[nearest] = ObjectState(
            nearest, state.x_mm, state.y_mm, state.theta_deg,
            upright=state.upright, damaged=state.damaged, held=True, displaced=True)
        self._move_carried()
        self.log.append(("pick_up", nearest))

    def place(self) -> None:
        if not self._carrying:
            raise RuntimeError("not carrying anything")
        object_id = self._carrying
        state = self.world.get(object_id)
        self.world.objects[object_id] = ObjectState(
            object_id, self.x_mm, self.y_mm, self.heading_deg,
            upright=state.upright, damaged=state.damaged, held=False, displaced=True)
        self._carrying = None
        self.log.append(("place", object_id))

    def carrying(self) -> bool:
        return self._carrying is not None

    def carried_object(self) -> str | None:
        """Which object is held. Not part of the contract — a test convenience."""
        return self._carrying

    # ------------------------------------------------------------------ #
    # Sensing
    # ------------------------------------------------------------------ #

    def read_reflection(self) -> float:
        """0-100. Constant unless a surface model was supplied — see the module
        docstring: nothing here has sampled the mat, that is field test P1."""
        value = (self._surface(self.x_mm, self.y_mm) if self._surface
                 else UNMODELLED_REFLECTION)
        self.log.append(("read_reflection", float(value)))
        return float(value)

    # ------------------------------------------------------------------ #

    def _move_carried(self) -> None:
        object_id = self._carrying
        if object_id is None:
            return
        state = self.world.get(object_id)
        self.world.objects[object_id] = ObjectState(
            object_id, self.x_mm, self.y_mm, self.heading_deg,
            upright=state.upright, damaged=state.damaged,
            held=True, displaced=True)

    def _objects_in_reach(self) -> list[str]:
        return [object_id for object_id, state in self.world.objects.items()
                if not state.held
                and math.hypot(state.x_mm - self.x_mm,
                               state.y_mm - self.y_mm) <= self.pickup_radius_mm]

    def _nearest_object(self) -> tuple[str | None, float]:
        best_id, best = None, float("inf")
        for object_id, state in self.world.objects.items():
            if state.held:
                continue
            distance = math.hypot(state.x_mm - self.x_mm, state.y_mm - self.y_mm)
            if distance < best:
                best_id, best = object_id, distance
        return best_id, best
