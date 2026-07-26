#!/usr/bin/env python3
"""The world state the scorer consumes: where every game object ended up.

One object, one :class:`ObjectState`. The fields are chosen so that nothing has
to be invented:

``displaced``
    "no longer touching its initial position" — the first half of S1 p13's
    *moved* definition. It is a **flag, not a computed distance**, because
    ``field_spec.json`` deliberately refuses to invent start coordinates for 15
    of the 17 objects (ADR-014: initial pose is run-time state). A scorer that
    computed displacement would need those coordinates and would therefore need
    them invented.

``held``
    still in the mechanism at time-out. S6 2026-06-30 scores such an object at
    the **partial** tier, not zero (A5) — the old default understated the score.

``upright``
    S6 2026-06-30 makes this a **contact** predicate: the base fully touching
    the mat. It is supplied rather than derived, since deriving it needs the
    tilt-vs-lift relationship that field test P5 will measure.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Iterable, Literal

from .geometry import Polygon, oriented_rect

FootprintReading = Literal["contact", "projection"]

DEFAULT_OBJECT_SPEC: Final = Path("data/object_spec.json")


@dataclass(frozen=True)
class Footprint:
    """An object's contact patch, and whether it is measured or bounded."""

    width_mm: float
    height_mm: float
    is_bound: bool = False
    source: str = "measured"

    def polygon(self, x: float, y: float, theta_deg: float) -> list[tuple[float, float]]:
        return oriented_rect(x, y, self.width_mm, self.height_mm, theta_deg)


@dataclass
class ObjectState:
    """Where one game object is at time-out, and in what condition."""

    object_id: str
    x_mm: float = 0.0
    y_mm: float = 0.0
    theta_deg: float = 0.0
    upright: bool = True
    damaged: bool = False
    held: bool = False
    displaced: bool = False

    def footprint_polygon(self, footprint: Footprint) -> list[tuple[float, float]]:
        return footprint.polygon(self.x_mm, self.y_mm, self.theta_deg)


@dataclass
class WorldState:
    """Every object's end state. Objects omitted are treated as untouched."""

    objects: dict[str, ObjectState] = field(default_factory=dict)
    elapsed_s: float = 120.0

    @classmethod
    def untouched(cls, object_ids: Iterable[str], elapsed_s: float = 120.0) -> "WorldState":
        """The do-nothing run: everything upright, undamaged, where it started.

        This is the state that must score exactly 40 — the bonus floor
        (S6 2026-06-17). It is a useful fixture and a useful assertion.
        """
        return cls({oid: ObjectState(oid) for oid in object_ids}, elapsed_s=elapsed_s)

    def get(self, object_id: str) -> ObjectState:
        return self.objects.get(object_id) or ObjectState(object_id)

    def place(self, object_id: str, x_mm: float, y_mm: float,
              theta_deg: float = 0.0, **kwargs: Any) -> "WorldState":
        """Return a copy with one object moved. Placement implies displacement."""
        objects = dict(self.objects)
        objects[object_id] = ObjectState(
            object_id, x_mm, y_mm, theta_deg,
            upright=kwargs.get("upright", True),
            damaged=kwargs.get("damaged", False),
            held=kwargs.get("held", False),
            displaced=kwargs.get("displaced", True),
        )
        return WorldState(objects, self.elapsed_s)


class FootprintTable:
    """Object id → :class:`Footprint`, read from ``data/object_spec.json``.

    Three cases, kept distinct rather than collapsed:

    * a **measured** footprint — the six notes, mic, guitar, clef, congas, cables
    * a **bounded** one — ``instrument_keyboard``, whose base is an open frame so
      the ``rows × cols`` self-check cannot apply. The bound is used and the
      result is flagged; the direction is safe, since a footprint larger than
      the truth can only under-report success.
    * **none at all** — ``amp``, ``speaker_a``, ``speaker_b``. S1 scores these for
      *not being moved*, so they never need containment and asking for their
      footprint is a bug, not a gap. It raises.
    """

    def __init__(self, spec: dict[str, Any], reading: FootprintReading = "contact"):
        self.reading = reading
        self.spec = spec
        self._table: dict[str, Footprint] = {}
        for oid, obj in spec["objects"].items():
            key = "contact_footprint_mm" if reading == "contact" else "max_projection_mm"
            size = obj.get(key)
            if size:
                self._table[oid] = Footprint(size[0], size[1], is_bound=False,
                                             source=f"MEASURED(S3) {reading}")
                continue
            pending = obj.get("footprint_pending")
            if pending and pending.get("upper_bound_mm"):
                bound = pending["upper_bound_mm"]
                self._table[oid] = Footprint(
                    bound[0], bound[1], is_bound=True,
                    source=f"UPPER BOUND ({pending['reason']}) — may understate success")

    @classmethod
    def load(cls, path: Path = DEFAULT_OBJECT_SPEC,
             reading: FootprintReading = "contact") -> "FootprintTable":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")), reading)

    def __contains__(self, object_id: str) -> bool:
        return object_id in self._table

    def __getitem__(self, object_id: str) -> Footprint:
        if object_id not in self._table:
            raise KeyError(
                f"{object_id} has no footprint in object_spec.json. If it is amp, "
                f"speaker_a or speaker_b this is a bug in the caller: S1 scores "
                f"those for NOT being moved, so they are never placed in an area."
            )
        return self._table[object_id]

    def ids(self) -> list[str]:
        return sorted(self._table)
