#!/usr/bin/env python3
"""Score a :class:`~sim.world.WorldState` against the frozen rules.

    data/scoring_model.json   (missions, tiers, predicates, time rules)  ─┐
    data/field_spec.json      (area polygons, `scoring` flags)           ─┼─► Scorer
    data/object_spec.json     (contact / projection footprints)          ─┘

Every number comes from those three files. This module contributes geometry and
control flow, never a point value — if a tier is worth 5 rather than 10 it is
because ``scoring_model.json`` says so.

Four things a naive implementation gets wrong, all of them costly:

1. **``damaged`` is global.** S4 §7.7 zeroes the object wherever it sits. A
   correctly-placed but damaged note scores 0, not 20. S1's own scoring sheet
   never says this, so it is easy to bury inside the bonus block where it does
   not belong.
2. **Partial credit is not uniform.** The cable's partial is 5/15 = 33.3 %,
   against 50 % for the microphone and notes. Any EV comparison between "many
   rough placements" and "few precise ones" that assumed uniformity is invalid.
3. **The bonus is a floor, not a prize.** S6 2026-06-17: a run that starts and
   immediately stops scores 40/255. Bonus points can only be *lost*, so every
   mission's EV carries a ``− P(collision) × 40`` term.
4. **A held object scores the partial tier, not zero.** S6 2026-06-30 (A5). The
   previous default understated the score, and it inverts the abort policy: when
   the clock runs out mid-placement, leave the object in the area.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

from .geometry import (
    OrientedRect,
    Polygon,
    bbox,
    centroid,
    min_area_rect,
    polygon_contains,
    polygons_intersect,
    require_convex,
)
from .world import FootprintReading, FootprintTable, ObjectState, WorldState

DEFAULT_FIELD_SPEC: Final = Path("data/field_spec.json")
DEFAULT_SCORING_MODEL: Final = Path("data/scoring_model.json")
DEFAULT_OBJECT_SPEC: Final = Path("data/object_spec.json")

Tier = Literal["full", "partial", "none", "zero_damaged"]


@dataclass(frozen=True)
class ScoringParams:
    """Every open interpretation, named and defaulted to its register entry.

    None of these is a free choice: each traces to an ambiguity in
    ``docs/AMBIGUITIES.md`` with a recorded default and a route to resolution.
    """

    #: A1 — S1's written definition ANDs the two conditions; its own photos
    #: award 0 to a clef that toppled in place, which only follows from OR.
    moved_semantics: Literal["or", "and"] = "or"

    #: A2 — demoted by S6 2026-06-30 to a parameter; the operative test is
    #: contact. Retained so an angle-dependent result can be swept (AS-6).
    upright_tolerance_deg: float = 15.0

    #: A5 — RESOLVED: held objects score the partial tier.
    held_at_timeout: Literal["partial", "zero"] = "partial"

    #: A8 — OPEN. Does a bonus-only run count as "solving a task"? Default is
    #: the conservative reading: it does not, so the clock is forced to 120 s.
    bonus_only_forces_120s: bool = True

    #: A7 — which extent `completely_in` consumes. The contact patch is what
    #: touches the mat; the silhouette is what a judge sees overhanging.
    footprint_reading: FootprintReading = "contact"


@dataclass
class ObjectScore:
    object_id: str
    mission_id: str
    points: int
    tier: Tier
    target_id: str | None = None
    reason: str = ""
    footprint_is_bound: bool = False


@dataclass
class MissionScore:
    mission_id: str
    title: str
    points: int
    max_points: int
    rows: list[ObjectScore] = field(default_factory=list)


@dataclass
class ScoreBreakdown:
    total: int
    max_score: int
    missions: list[MissionScore]
    elapsed_s: float
    forced_120s: bool
    forced_120s_reason: str | None
    params: ScoringParams
    any_bounded_footprint: bool

    def by_mission(self) -> dict[str, int]:
        return {m.mission_id: m.points for m in self.missions}


class Scorer:
    """Applies ``scoring_model.json`` to a world state."""

    def __init__(self, field_spec: dict[str, Any], scoring_model: dict[str, Any],
                 object_spec: dict[str, Any], params: ScoringParams | None = None):
        self.params = params or ScoringParams()
        self.field = field_spec
        self.model = scoring_model
        self.footprints = FootprintTable(object_spec, self.params.footprint_reading)

        # ADR-013: `completely_in` ranges over scoring==true areas ONLY. A
        # literal reading of "no other area on the mat" makes the game
        # unscoreable, because every target except backstage is drawn on top of
        # a larger fill.
        self.scoring_areas: dict[str, list[tuple[float, float]]] = {}
        for area_id, area in field_spec["areas"].items():
            if not area.get("scoring"):
                continue
            polygon = area.get("polygon_visible_mm")
            if polygon is None:
                raise ValueError(f"{area_id} is scoring but has no polygon_visible_mm")
            points = [(float(x), float(y)) for x, y in polygon]
            require_convex(points, f"field_spec area {area_id!r}")
            self.scoring_areas[area_id] = points

        self.missions = {m["id"]: m for m in scoring_model["missions"]}

    @classmethod
    def load(cls, field_spec: Path = DEFAULT_FIELD_SPEC,
             scoring_model: Path = DEFAULT_SCORING_MODEL,
             object_spec: Path = DEFAULT_OBJECT_SPEC,
             params: ScoringParams | None = None) -> "Scorer":
        return cls(
            json.loads(Path(field_spec).read_text(encoding="utf-8")),
            json.loads(Path(scoring_model).read_text(encoding="utf-8")),
            json.loads(Path(object_spec).read_text(encoding="utf-8")),
            params,
        )

    # ------------------------------------------------------------------ #
    # Where each object is *meant* to end up
    # ------------------------------------------------------------------ #

    #: Below this target aspect ratio, "align with the long axis" is meaningless
    #: and the heading is left at 0. The note targets are exactly square.
    ELONGATED_ASPECT: Final = 1.05

    def area_rect(self, area_id: str) -> OrientedRect:
        return min_area_rect(self.scoring_areas[area_id])

    def nominal_placements(self) -> dict[str, tuple[str, float, float, float]]:
        """object id → ``(target_id, x_mm, y_mm, theta_deg)`` for a perfect run.

        The aim point is the area's own centre and the heading is the area's own
        long axis — **derived from the polygon, never from its bounding box.**

        That distinction is not academic. The two cable areas are 79.700 ×
        207.201 mm rectangles tilted to **80°** and **100°**; their bounding
        boxes are 114.47 × 217.89 mm. Aiming a 128 mm cable axis-aligned at the
        centre of ``cable_area_upper`` does fit, but with barely half the margin
        of the correct 80° placement, and the two areas tilt in *opposite*
        directions, so the two cables need different headings.

        Instruments share one backstage area and are spread along its long axis
        rather than stacked on one point — three objects cannot occupy the same
        centre on a real table. That spreading costs margin, and the sensitivity
        report states the cost rather than quietly reporting the centred figure.
        """
        out: dict[str, tuple[str, float, float, float]] = {}

        def aim(area_id: str) -> tuple[float, float, float]:
            rect = self.area_rect(area_id)
            theta = rect.angle_deg if rect.aspect >= self.ELONGATED_ASPECT else 0.0
            return rect.cx, rect.cy, theta

        for object_id, area_id in (("cable_upper", "cable_area_upper"),
                                   ("cable_lower", "cable_area_lower")):
            cx, cy, theta = aim(area_id)
            # the cable's own long axis is its local Y, so subtract the 90 deg
            # between "object long axis" and "area long axis" conventions
            out[object_id] = (area_id, cx, cy, theta - 90.0)

        cx, cy, theta = aim("mic_target")
        out["mic"] = ("mic_target", cx, cy, theta - 90.0)

        rect = self.area_rect("backstage")
        instruments = self.missions["m2_prepare_show_instruments"]["objects"]
        half = rect.height_mm / 2.0
        for index, object_id in enumerate(instruments, start=1):
            offset = -half + rect.height_mm * index / (len(instruments) + 1)
            rad = math.radians(rect.angle_deg)
            out[object_id] = ("backstage",
                              rect.cx + offset * math.cos(rad),
                              rect.cy + offset * math.sin(rad), 0.0)

        notes = self.missions["m3_play_the_song"]
        for object_id, target_id in zip(notes["objects"], notes["targets"]):
            cx, cy, theta = aim(target_id)
            out[object_id] = (target_id, cx, cy, theta)
        return out

    def perfect_world(self) -> WorldState:
        """The 255-point run: every object placed at its nominal aim point."""
        world = WorldState.untouched(
            sorted(set(self.footprints.ids()) | {"clef", "amp", "speaker_a", "speaker_b"}))
        for object_id, (_target, x, y, theta) in self.nominal_placements().items():
            world = world.place(object_id, x, y, theta)
        return world

    # ------------------------------------------------------------------ #
    # Predicates
    # ------------------------------------------------------------------ #

    def containment(self, state: ObjectState, target_id: str) -> tuple[Tier, str]:
        """``full`` / ``partial`` / ``none`` for one object against one area.

        ``full`` is S1 p9's *completely in*: contained in the target **and**
        touching no other scoring area. An object contained in its target but
        also touching a second scoring area drops to ``partial`` rather than to
        zero — it is still "partly in the corresponding area", which is exactly
        the partial tier's wording.
        """
        footprint = self.footprints[state.object_id]
        shape = state.footprint_polygon(footprint)
        target = self.scoring_areas[target_id]

        if not polygons_intersect(target, shape):
            return "none", "footprint does not reach the target area"

        others = [aid for aid, poly in self.scoring_areas.items()
                  if aid != target_id and polygons_intersect(poly, shape)]
        if polygon_contains(target, shape):
            if others:
                return "partial", f"contained, but also touching {sorted(others)}"
            return "full", "completely in"
        return "partial", "only partly in the target area"

    def effective_upright(self, state: ObjectState) -> bool:
        """S6 2026-06-30: not fully touching the floor is not upright."""
        if state.held and self.params.held_at_timeout == "partial":
            return False
        return state.upright

    def is_moved(self, state: ObjectState) -> bool:
        """S1 p13, with A1's semantics as a parameter."""
        if self.params.moved_semantics == "and":
            return state.displaced and not state.upright
        return state.displaced or not state.upright

    # ------------------------------------------------------------------ #
    # Missions
    # ------------------------------------------------------------------ #

    def _placement_row(self, mission: dict[str, Any], state: ObjectState,
                       target_id: str, requires_upright: bool) -> ObjectScore:
        mid = mission["id"]
        if state.damaged:
            return ObjectScore(state.object_id, mid, 0, "zero_damaged", target_id,
                               "S4 7.7: damaged objects score 0 wherever they sit")
        if state.held and self.params.held_at_timeout == "zero":
            return ObjectScore(state.object_id, mid, 0, "none", target_id,
                               "held at time-out, scored zero by parameter")

        bound = self.footprints[state.object_id].is_bound
        tier, why = self.containment(state, target_id)
        partial = mission.get("partial") or {}
        partial_points = int(partial.get("points") or 0)

        if tier == "full" and (not requires_upright or self.effective_upright(state)):
            return ObjectScore(state.object_id, mid, int(mission["each"]), "full",
                               target_id, why, bound)
        if tier == "none":
            return ObjectScore(state.object_id, mid, 0, "none", target_id, why, bound)
        # partly in, or fully in but not upright
        if not partial_points:
            reason = "no partial tier for this mission" if tier == "partial" else \
                     "full containment but not upright, and no partial tier exists"
            return ObjectScore(state.object_id, mid, 0, "none", target_id, reason, bound)
        reason = why if tier == "partial" else "completely in but not upright"
        return ObjectScore(state.object_id, mid, partial_points, "partial",
                           target_id, reason, bound)

    def _score_cables(self, world: WorldState) -> MissionScore:
        """S1 p8: two areas, and **only one cable per area** scores."""
        mission = self.missions["m1_connect_amplifier"]
        best: dict[str, ObjectScore] = {}
        rows: list[ObjectScore] = []
        for object_id in mission["objects"]:
            state = world.get(object_id)
            candidates = [self._placement_row(mission, state, t, True)
                          for t in mission["targets"]]
            row = max(candidates, key=lambda r: r.points)
            rows.append(row)

        # one per area: keep the best row per target, zero the rest
        for row in sorted(rows, key=lambda r: -r.points):
            if row.points == 0:
                continue
            if row.target_id in best:
                row.points = 0
                row.tier = "none"
                row.reason = (f"{best[row.target_id].object_id} already scores in "
                              f"{row.target_id}; only one cable per area (S1 p8)")
            else:
                best[row.target_id] = row
        total = sum(r.points for r in rows)
        return MissionScore(mission["id"], mission["title"], total,
                            int(mission["max"]), rows)

    def _score_single_target(self, mission_id: str, world: WorldState,
                             requires_upright: bool) -> MissionScore:
        mission = self.missions[mission_id]
        target = mission["targets"][0]
        rows = [self._placement_row(mission, world.get(oid), target, requires_upright)
                for oid in mission["objects"]]
        total = min(sum(r.points for r in rows), int(mission["max"]))
        return MissionScore(mission["id"], mission["title"], total,
                            int(mission["max"]), rows)

    def _score_notes(self, world: WorldState) -> MissionScore:
        """Each note must reach **its own** colour-matched target."""
        mission = self.missions["m3_play_the_song"]
        pairs = zip(mission["objects"], mission["targets"])
        rows = [self._placement_row(mission, world.get(oid), tid, True)
                for oid, tid in pairs]
        total = min(sum(r.points for r in rows), int(mission["max"]))
        return MissionScore(mission["id"], mission["title"], total,
                            int(mission["max"]), rows)

    def _score_bonus(self, world: WorldState) -> MissionScore:
        """S1 p13 — awarded for NOT touching things. The floor, not a prize."""
        mission = self.missions["m4_bonus"]
        rows: list[ObjectScore] = []
        for entry in mission["entries"]:
            for object_id in entry["objects"]:
                state = world.get(object_id)
                if state.damaged:
                    rows.append(ObjectScore(object_id, mission["id"], 0, "zero_damaged",
                                            None, "damaged (S4 7.7)"))
                elif self.is_moved(state):
                    rows.append(ObjectScore(
                        object_id, mission["id"], 0, "none", None,
                        f"moved under `{self.params.moved_semantics}` semantics"))
                else:
                    rows.append(ObjectScore(object_id, mission["id"], int(entry["each"]),
                                            "full", None, "not damaged and not moved"))
        total = min(sum(r.points for r in rows), int(mission["max"]))
        return MissionScore(mission["id"], mission["title"], total,
                            int(mission["max"]), rows)

    # ------------------------------------------------------------------ #

    def score(self, world: WorldState) -> ScoreBreakdown:
        missions = [
            self._score_cables(world),
            self._score_single_target("m2_prepare_show_microphone", world, True),
            self._score_single_target("m2_prepare_show_instruments", world, False),
            self._score_notes(world),
            self._score_bonus(world),
        ]
        total = sum(m.points for m in missions)

        # S4 10.12 — no positive-scoring (partial) task solved forces 120 s.
        # A8 is whether the bonus counts as "solving a task"; default says no.
        non_bonus = sum(m.points for m in missions if m.mission_id != "m4_bonus")
        forced, reason = False, None
        if non_bonus == 0 and self.params.bonus_only_forces_120s:
            forced = True
            reason = ("S4 10.12: no positive-scoring (partial) task solved. "
                      "A8 OPEN — bonus points are positive but passively not "
                      "damaging an object is arguably not solving a task.")
        elapsed = 120.0 if forced else world.elapsed_s

        return ScoreBreakdown(
            total=total,
            max_score=int(self.model["max_score"]),
            missions=missions,
            elapsed_s=elapsed,
            forced_120s=forced,
            forced_120s_reason=reason,
            params=self.params,
            any_bounded_footprint=any(r.footprint_is_bound
                                      for m in missions for r in m.rows),
        )
