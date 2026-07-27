"""Invariants on the end-to-end score and on ``data/parameter_sensitivity.json``.

This is the first artefact that produces **one number for a whole run**, which
makes it the easiest place in the project to be quietly wrong. The guards are
therefore anchors and monotonicity rather than agreement with itself:

- the perfect corner must return **exactly 225** — σ = 0, unlimited speed,
  instant handling, one round, no collision. Not 255: the two cables are still
  `nominal_pending`, so 40 + 185 is everything on the table.
- a run where nothing fits must return **exactly the 40-point bonus floor**.
- every parameter must move the score the way physics says, and no other way.

The finding the artefact exists for is that the **rank order changes between
operating contexts** — σ leads when the robot is comfortably fast, speed leads
when it is not. :func:`test_the_rank_order_is_not_stable` asserts that directly,
because a single league table would have been the natural thing to publish and
would have been misleading.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest

from sim import frontier, model, travel

ROOT = Path(__file__).resolve().parents[1]
SENSITIVITY = ROOT / "data" / "parameter_sensitivity.json"


@pytest.fixture(scope="module")
def spec() -> dict:
    return json.loads(SENSITIVITY.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rig():
    """(missions, exposure, tours-by-capacity, objects) for one start state."""
    from sim.scoring import Scorer
    field_spec = json.loads((ROOT / "data" / "field_spec.json").read_text(encoding="utf-8"))
    expected = json.loads((ROOT / "data" / "expected_score.json").read_text(encoding="utf-8"))
    nominal = Scorer.load().nominal_placements()
    members = field_spec["start_groups"]["truck"]["members"]
    field = travel.FullField(field_spec, travel.NoteField(field_spec),
                             {m: (nominal[m][1], nominal[m][2]) for m in members})
    assign = field.assignments()[0]
    tours = {c: frontier.subset_tours([assign[o] for o in field.objects],
                                      [field.targets[o] for o in field.objects],
                                      field.start, c) for c in (1, 2)}
    missions, exposure = model.load_missions(expected, "contact", field.objects)
    return missions, exposure, tours, field.objects


def score(rig, capacity=2, **kwargs) -> model.Outcome:
    missions, exposure, tours, objects = rig
    defaults = dict(sigma=15.0, speed_mm_s=200, pick_place_s=4.0,
                    rounds_n=1, p_collision=0.0)
    return model.expected_run_score(missions, exposure, tours[capacity], objects,
                                    **{**defaults, **kwargs})


# --------------------------------------------------------------------------- #
# Anchors
# --------------------------------------------------------------------------- #


def test_the_perfect_corner_is_exactly_the_reachable_maximum(rig):
    """Not 255 — the two cables are absent from every subset."""
    out = score(rig, sigma=0.0, speed_mm_s=10 ** 6, pick_place_s=0.0,
                rounds_n=1, p_collision=0.0)
    assert out.expected_score == pytest.approx(model.REACHABLE_MAX, abs=1e-9)
    assert model.REACHABLE_MAX == 225 < model.MAX_SCORE == 255
    assert len(out.subset) == 10


def test_a_run_that_fits_nothing_scores_the_bonus_floor(rig):
    out = score(rig, speed_mm_s=1, pick_place_s=1000.0)
    assert out.expected_score == pytest.approx(40.0, abs=1e-9)
    assert out.subset == ()
    assert out.bonus_exposed == 0, "attempting nothing risks nothing"


def test_the_score_stays_between_the_floor_and_the_ceiling(rig):
    for sigma, speed, pick, n, p in itertools.product(
            (0.0, 15.0, 45.0), (100, 400), (0.0, 8.0), (1, 3), (0.0, 0.5)):
        out = score(rig, sigma=sigma, speed_mm_s=speed, pick_place_s=pick,
                    rounds_n=n, p_collision=p)
        assert 0.0 <= out.expected_score <= model.REACHABLE_MAX + 1e-9


def test_the_reported_subset_is_what_was_scored(rig):
    out = score(rig, speed_mm_s=120, pick_place_s=6.0)
    assert out.seconds <= 120.0 + 1e-9
    assert out.bonus_exposed in (0, 10, 30)
    assert set(out.subset) <= set(rig[3])


# --------------------------------------------------------------------------- #
# Monotonicity — each parameter must move the score the way physics says
# --------------------------------------------------------------------------- #


def test_more_placement_error_never_helps(rig):
    scores = [score(rig, sigma=s).expected_score
              for s in (0.0, 5.0, 10.0, 15.0, 20.0, 30.0, 45.0)]
    assert scores == sorted(scores, reverse=True)


def test_more_speed_never_hurts(rig):
    scores = [score(rig, speed_mm_s=v).expected_score for v in (75, 100, 150, 250, 400)]
    assert scores == sorted(scores)


def test_slower_handling_never_helps(rig):
    scores = [score(rig, pick_place_s=t).expected_score for t in (0.0, 2.0, 4.0, 8.0, 12.0)]
    assert scores == sorted(scores, reverse=True)


def test_more_rounds_never_hurt(rig):
    scores = [score(rig, sigma=20.0, rounds_n=n).expected_score for n in (1, 2, 3, 5)]
    assert scores == sorted(scores)


def test_more_collision_risk_never_helps(rig):
    scores = [score(rig, p_collision=p).expected_score for p in (0.0, 0.1, 0.25, 0.5)]
    assert scores == sorted(scores, reverse=True)


def test_more_capacity_never_hurts(rig):
    for speed, pick in ((100, 8.0), (150, 6.0), (200, 4.0)):
        one = score(rig, capacity=1, speed_mm_s=speed, pick_place_s=pick).expected_score
        two = score(rig, capacity=2, speed_mm_s=speed, pick_place_s=pick).expected_score
        assert two >= one - 1e-9, (speed, pick)


def test_the_subset_is_chosen_on_expected_value_not_raw_points(rig):
    """ADR-031: past σ = 20.4 mm an instrument outranks a note."""
    missions, exposure, tours, objects = rig
    raw = {o: float(missions[o]["full_points"]) for o in objects}
    worth = model.mission_value(missions, 30.0)
    assert worth["instrument_keyboard"] > worth["note_blue"]
    assert raw["instrument_keyboard"] < raw["note_blue"]


# --------------------------------------------------------------------------- #
# The artefact
# --------------------------------------------------------------------------- #


def test_every_parameter_is_declared_with_what_closes_it(spec):
    names = {p["name"] for p in spec["parameters"]}
    assert names == {"sigma", "speed_mm_s", "pick_place_s",
                     "rounds_n", "p_collision", "capacity"}
    for parameter in spec["parameters"]:
        assert parameter["closed_by"], parameter["name"]
        assert parameter["declared_in"], parameter["name"]
        assert parameter["low"] < parameter["high"]


def test_every_context_ranks_every_parameter(spec):
    for context in spec["contexts"]:
        swings = context["swings"]
        assert len(swings) == 6
        assert [s["rank"] for s in swings] == [1, 2, 3, 4, 5, 6]
        assert [s["swing"] for s in swings] == sorted(
            (s["swing"] for s in swings), reverse=True)
        for swing in swings:
            assert swing["swing"] == pytest.approx(
                abs(swing["score_at_high"] - swing["score_at_low"]), abs=1e-3)


def test_the_rank_order_is_not_stable(spec):
    """Three contexts do not agree — but three points are not a shape."""
    orders = spec["rank_order"]["by_context"]
    assert len(orders) == 3
    assert spec["rank_order"]["differs_between_contexts"] is True
    assert len({tuple(o) for o in orders.values()}) > 1
    assert orders["comfortable"][0] == "sigma"
    assert orders["tight"][0] == "speed_mm_s"


def test_the_flip_is_a_band_not_a_regime(spec):
    """The correction: three contexts suggested a regime split; the grid denies it.

    Sweeping speed against handling time shows σ leading in the large majority of
    cells, with driving speed taking the lead only in a narrow band of handling
    time — and σ retaking it beyond that band. Publishing only the three contexts
    would have implied a clean "fast robot vs slow robot" split that the data does
    not support.
    """
    stability = spec["rank_stability"]
    leads = stability["leads_in_cells"]
    assert sum(leads.values()) == stability["cells"]
    assert leads["sigma"] > stability["cells"] // 2, \
        "sigma must lead in most of the grid, or the correction is wrong"
    assert leads.get("speed_mm_s", 0) > 0, "the band must exist"
    assert leads["sigma"] > 2 * leads.get("speed_mm_s", 0)

    # Where speed leads, it is handling time that put it there — not low speed.
    speed_cells = [c for c in stability["grid"] if c["leads"] == "speed_mm_s"]
    assert speed_cells
    picks = {c["pick_place_s"] for c in speed_cells}
    assert len(picks) <= 2, (
        "if speed led across many handling times it would be a regime, not a band")
    assert min(c["speed_mm_s"] for c in speed_cells) < 150 < \
        max(c["speed_mm_s"] for c in speed_cells), \
        "speed leads at both slow and fast robots — so speed is not what causes it"


def test_the_finding_describes_a_band(spec):
    finding = spec["rank_order"]["finding"]
    assert "band" in finding
    assert "most" in finding or "majority" in finding or "nearly everywhere" in finding
    # The finding may *quote* the superseded phrasing while rejecting it, so the
    # guard is on the superseded record existing, not on a token being absent.
    superseded = spec["rank_order"]["superseded_2026_07_27"]
    assert "comfortably fast" in superseded
    assert "does not support it" in superseded
    assert "handling time causes the flip, not speed" in superseded


def test_speed_leads_at_every_speed_inside_the_band(spec):
    """The clinching evidence that handling time, not speed, causes the flip.

    If low speed caused it, speed would lead in the slow rows and not the fast
    ones. Instead it leads across the entire 100-300 mm/s sweep at one handling
    time and nowhere else — a column, not a region.
    """
    grid = spec["rank_stability"]["grid"]
    speeds = set(spec["rank_stability"]["speeds_mm_s"])
    by_pick: dict[float, set[int]] = {}
    for cell in grid:
        if cell["leads"] == "speed_mm_s":
            by_pick.setdefault(cell["pick_place_s"], set()).add(cell["speed_mm_s"])
    assert by_pick, "the band must exist"
    full_columns = [t for t, found in by_pick.items() if found == speeds]
    assert full_columns, (
        "speed must lead at EVERY swept speed for at least one handling time — "
        "otherwise the flip is about speed after all")
    assert len(full_columns) == 1, full_columns


def test_the_perfect_corner_is_published_as_the_anchor(spec):
    assert spec["model"]["anchor_perfect_corner"] == pytest.approx(225.0, abs=1e-9)
    assert spec["scope"]["reachable_max"] == 225
    assert "B0" in spec["scope"]["why_not_255"]


def test_capacity_and_randomization_are_boundary_effects(spec):
    """Both cost nothing at either extreme and a great deal at the margin."""
    bands = {c["name"]: c["randomization_band"]["width"] for c in spec["contexts"]}
    assert bands["comfortable"] == 0.0 and bands["tight"] == 0.0
    assert bands["marginal"] > 0.0, "the margin is where the permutation bites"

    capacity = {c["name"]: next(s["swing"] for s in c["swings"] if s["parameter"] == "capacity")
                for c in spec["contexts"]}
    assert capacity["marginal"] > 10 * max(capacity["comfortable"], capacity["tight"], 1.0)
    note = spec["qualifies"]["both_are_boundary_effects"]
    assert "margin" in note and "borderline" in note
    assert "Subset selection absorbs them" in note


def test_the_qualification_does_not_retract_adr_029(spec):
    """ADR-029's travel findings stand; only their score consequence is scoped."""
    note = spec["qualifies"]["carry_capacity"]
    assert "ADR-029" in note and "stand unchanged" in note
    assert "2213 mm" in note


def test_the_envelope_spans_most_of_the_scale(spec):
    envelope = spec["envelope"]
    assert envelope["corners"] == 64
    assert envelope["max"] == pytest.approx(225.0, abs=1e-9)
    assert envelope["min"] < 120
    assert envelope["max"] - envelope["min"] > 100


# --------------------------------------------------------------------------- #
# Honesty guards
# --------------------------------------------------------------------------- #


def test_the_artefact_refuses_to_predict(spec):
    scope = spec["scope"]
    assert "not a forecast" in scope["does_not_answer"]
    assert "ASSUMED" in scope["does_not_answer"]
    assert "all six parameters are unmeasured" in scope["does_not_answer"]


def test_the_one_at_a_time_limitation_is_stated(spec):
    note = spec["scope"]["one_at_a_time"]
    assert "interactions are invisible" in note
    assert "two contexts" in note or "contexts are published" in note


def test_the_model_claims_no_new_arithmetic(spec):
    assert "composed" in spec["model"]["no_new_arithmetic"]
    assert "sim.frontier" in spec["model"]["chain"]
    assert "sim.rounds" in spec["model"]["chain"]


def test_load_missions_rejects_an_unknown_object():
    expected = json.loads((ROOT / "data" / "expected_score.json").read_text(encoding="utf-8"))
    with pytest.raises(KeyError, match="no mission for"):
        model.load_missions(expected, "contact", ["not_a_mission"])


def test_load_missions_drops_the_two_uncostable_cables():
    expected = json.loads((ROOT / "data" / "expected_score.json").read_text(encoding="utf-8"))
    all_missions, _ = model.load_missions(expected, "contact")
    assert {"cable_upper", "cable_lower"} <= set(all_missions)
    ten = [o for o in all_missions if "cable" not in o]
    covered, _ = model.load_missions(expected, "contact", ten)
    assert "cable_upper" not in covered and len(covered) == 10


def test_the_adr_swing_table_matches_the_artefact(spec):
    """ADR-032's ranking table, parsed back out and checked against the data.

    The table is one row per rank with two columns per context, so it is read by
    position rather than by label — and every number in it must be a swing the
    artefact actually computed.
    """
    text = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    body = text.split("## ADR-032")[1].split("\n## ")[0]
    swings = {c["name"]: {s["rank"]: s for s in c["swings"]} for c in spec["contexts"]}
    order = ("comfortable", "marginal", "tight")
    seen = 0
    for line in body.splitlines():
        cells = [c.strip().replace("*", "").replace("`", "")
                 for c in line.strip().strip("|").split("|")]
        if len(cells) != 7 or not cells[0].isdigit():
            continue
        rank = int(cells[0])
        for index, context in enumerate(order):
            printed = float(cells[2 + index * 2])
            # The ADR prints one decimal, so compare at that precision rather
            # than with a tolerance equal to the rounding half-width.
            assert printed == pytest.approx(
                round(swings[context][rank]["swing"], 1), abs=1e-9), (context, rank)
        seen += 1
    assert seen == 6, f"expected six ranked rows in ADR-032, parsed {seen}"


def test_the_adr_quotes_the_stability_grid(spec):
    """The correction's own numbers must come from the artefact, not the prose."""
    text = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    body = text.split("## ADR-032")[1].split("\n## ")[0]
    stability = spec["rank_stability"]
    leads = stability["leads_in_cells"]
    assert f"{leads['sigma']} of {stability['cells']} cells" in body
    speeds = stability["speeds_mm_s"]
    assert f"{min(speeds)} to {max(speeds)} mm/s" in body
    full = {c["pick_place_s"] for c in stability["grid"] if c["leads"] == "speed_mm_s"
            if len({d["speed_mm_s"] for d in stability["grid"]
                    if d["pick_place_s"] == c["pick_place_s"]
                    and d["leads"] == "speed_mm_s"}) == len(speeds)}
    assert len(full) == 1
    assert f"{int(full.pop())} s per object" in body


def test_the_adr_quotes_the_nominals_and_the_envelope(spec):
    text = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    body = text.split("## ADR-032")[1].split("\n## ")[0]
    for context in spec["contexts"]:
        assert f"{context['expected_score']:.1f}" in body, context["name"]
    envelope = spec["envelope"]
    assert f"{envelope['min']:.1f}" in body and f"{envelope['max']:.1f}" in body
    assert "225.000" in body and "40.000" in body, "both anchors must be quoted"


def test_provenance_pins_every_input(spec):
    inputs = spec["provenance"]["inputs"]
    assert set(inputs) == {"field_spec", "scoring_model", "expected_score", "travel_budget"}
    assert all(len(v) == 64 for v in inputs.values())
    assert spec["provenance"]["joint_start_states"] == 384
