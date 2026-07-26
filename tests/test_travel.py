"""Invariants on the note tour and on ``data/travel_budget.json``.

The claim this file exists to defend is a structural one, and structural claims
are exactly the kind that look true and are not:

    **At full carry capacity, the tour length does not depend on the
    randomization at all.**

A robot that collects every note before delivering any visits the same set of
points whatever the permutation — the four slots and the six targets — so the
length cannot vary. The spread should be **exactly zero**, not merely small, and
:func:`test_full_capacity_deletes_the_randomization` asserts exactly that. If it
ever becomes a small non-zero number, the reasoning has broken somewhere and the
finding in ADR-029 is wrong.

The tour itself is checked against an independent brute-force implementation at
both capacities where brute force is tractable, so agreement is evidence rather
than a restated assumption.
"""

from __future__ import annotations

import itertools
import json
import statistics
from pathlib import Path

import pytest

from sim import travel

ROOT = Path(__file__).resolve().parents[1]
BUDGET = ROOT / "data" / "travel_budget.json"
FRAME = ROOT / "data" / "strategy_frame.json"

NOTES = {"note_black", "note_white", "note_yellow", "note_blue",
         "note_green", "note_red"}


@pytest.fixture(scope="module")
def field() -> travel.NoteField:
    return travel.NoteField.load(ROOT / "data" / "field_spec.json")


@pytest.fixture(scope="module")
def assignments(field: travel.NoteField) -> list[dict]:
    return field.assignments()


@pytest.fixture(scope="module")
def spec() -> dict:
    return json.loads(BUDGET.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tours(field, assignments) -> dict[int, list[float]]:
    return {k: sorted(travel.tour(a, field, k) for a in assignments)
            for k in travel.DEFAULT_CAPACITIES}


# --------------------------------------------------------------------------- #
# The field, read not assumed
# --------------------------------------------------------------------------- #


def test_the_field_matches_the_spec(field: travel.NoteField):
    assert set(field.notes) == NOTES
    assert len(field.slots) == 4, "S1 p7: four light-green squares"
    assert set(field.randomized) == {"note_black", "note_white",
                                     "note_yellow", "note_blue"}
    assert set(field.fixed_starts) == {"note_green", "note_red"}
    assert set(field.targets) == NOTES


def test_there_are_exactly_twenty_four_permutations(assignments):
    assert len(assignments) == 24
    seen = {tuple(sorted((n, tuple(p)) for n, p in a.items())) for a in assignments}
    assert len(seen) == 24, "every permutation must be distinct"


def test_the_fixed_notes_never_move(assignments, field):
    for a in assignments:
        assert a["note_green"] == field.fixed_starts["note_green"]
        assert a["note_red"] == field.fixed_starts["note_red"]


# --------------------------------------------------------------------------- #
# The solver
# --------------------------------------------------------------------------- #


def test_the_dp_agrees_with_brute_force(field, assignments):
    """Independent implementations, tractable only at the two extremes."""
    for capacity in (1, 6):
        for assign in assignments[:4]:
            assert travel.tour(assign, field, capacity) == pytest.approx(
                travel.tour_by_brute_force(assign, field, capacity), abs=1e-9), capacity


def test_more_capacity_is_never_worse(tours):
    for a, b in itertools.pairwise(travel.DEFAULT_CAPACITIES):
        for lower, higher in zip(tours[a], tours[b]):
            assert higher <= lower + 1e-9, (a, b)


def test_capacity_strictly_helps_at_every_quantile(tours):
    """Not just "never worse" — every step of the curve buys real distance."""
    for a, b in itertools.pairwise(travel.DEFAULT_CAPACITIES):
        assert max(tours[b]) < max(tours[a])
        assert min(tours[b]) < min(tours[a])
        assert statistics.median(tours[b]) < statistics.median(tours[a])


def test_capacity_below_one_is_rejected(field, assignments):
    with pytest.raises(ValueError):
        travel.tour(assignments[0], field, 0)


def test_a_tour_returns_to_the_start_area(field, assignments):
    """Sanity floor: the tour must be at least out-and-back to the far note."""
    assign = assignments[0]
    furthest = max(travel.distance(field.start, p) for p in assign.values())
    assert travel.tour(assign, field, 6) >= 2 * furthest - 1e-9


# --------------------------------------------------------------------------- #
# The structural claim — ADR-029
# --------------------------------------------------------------------------- #


def test_full_capacity_deletes_the_randomization(tours, field):
    """EXACTLY zero, not approximately. The whole finding rests on this."""
    at_full = tours[len(field.notes)]
    assert travel.spread(at_full) == 0.0, (
        "carrying every note visits the same point set whatever the permutation, "
        f"so the spread must be exactly 0 — got {travel.spread(at_full)}")
    assert len({round(t, 9) for t in at_full}) == 1


def test_one_at_a_time_is_where_the_randomization_bites(tours):
    at_one = tours[1]
    assert travel.spread(at_one) == pytest.approx(1000, abs=5)
    assert len({round(t, 6) for t in at_one}) == 24, "all 24 permutations distinct"
    assert travel.spread(at_one) / min(at_one) > 0.15


def test_the_spread_is_not_monotone_in_capacity(tours):
    """Full capacity is a phase change, not the end of a slope.

    Distance falls monotonically — a tour feasible at k is feasible at k+1 — but
    the spread across the permutations does not. It rises from capacity 3 to 4.
    Publishing only 1/2/3/6 would have implied a smooth trend to zero, so all six
    are emitted and this asserts the reason.
    """
    spreads = [travel.spread(tours[k]) for k in travel.DEFAULT_CAPACITIES]
    assert spreads != sorted(spreads, reverse=True), (
        "if the spread became monotone, the 'phase change' claim in ADR-029 and "
        "the reason for publishing all six capacities both need revisiting")
    assert travel.spread(tours[4]) > travel.spread(tours[3])
    assert travel.spread(tours[6]) == 0.0


def test_the_first_extra_slot_is_the_biggest_win(tours):
    """Capacity 1 -> 2 must dominate every later step."""
    steps = [max(tours[a]) - max(tours[b])
             for a, b in itertools.pairwise(travel.DEFAULT_CAPACITIES)]
    assert steps[0] == max(steps)
    assert steps[0] == pytest.approx(2213, abs=5)


# --------------------------------------------------------------------------- #
# Required speed
# --------------------------------------------------------------------------- #


def test_required_speed_is_distance_over_time():
    assert travel.required_speed(6000, 120) == pytest.approx(50.0)
    with pytest.raises(ValueError):
        travel.required_speed(6000, 0)


def test_the_attempt_length_comes_from_the_scoring_model(spec):
    model = json.loads((ROOT / "data" / "scoring_model.json").read_text())
    assert travel.ATTEMPT_SECONDS == float(model["time"]["attempt_seconds"]) == 120.0


def test_required_speed_falls_as_capacity_rises(spec):
    speeds = [row["required_speed_mm_s"]["at_worst_permutation"]
              for row in spec["capacity_curve"]]
    assert speeds == sorted(speeds, reverse=True)
    assert speeds[0] == pytest.approx(63.3, abs=0.5)


# --------------------------------------------------------------------------- #
# The artefact
# --------------------------------------------------------------------------- #


def test_the_capacity_curve_covers_every_capacity(spec):
    assert [r["capacity"] for r in spec["capacity_curve"]] == list(travel.DEFAULT_CAPACITIES)
    for row in spec["capacity_curve"]:
        assert row["min_mm"] <= row["median_mm"] <= row["max_mm"]
        assert row["spread_mm"] == pytest.approx(row["max_mm"] - row["min_mm"], abs=1e-3)
        assert row["permutation_invariant"] == (row["spread_mm"] == 0.0)


def test_only_full_capacity_is_permutation_invariant(spec):
    invariant = [r["capacity"] for r in spec["capacity_curve"] if r["permutation_invariant"]]
    assert invariant == [6], "carrying five of six notes does not remove the randomization"
    assert spec["headline"]["spread_is_not_monotone_in_capacity"] is True
    assert "1000, 658, 426, 552, 425, 0" in spec["headline"]["phase_change_not_a_slope"]


def test_all_six_capacities_are_published(spec):
    """Omitting 4 and 5 would hide the rise that makes the point."""
    assert [r["capacity"] for r in spec["capacity_curve"]] == [1, 2, 3, 4, 5, 6]


def test_extra_rounds_shorten_the_expected_best_draw(spec):
    """Travel analogue of ADR-027: the permutation is redrawn every round (§9.6)."""
    for row in spec["capacity_curve"]:
        values = [e["mm"] for e in row["expected_best_of_n_mm"]]
        assert [e["n"] for e in row["expected_best_of_n_mm"]] == [1, 2, 3]
        for value in values:
            assert row["min_mm"] <= value <= row["max_mm"], row["capacity"]
        if row["permutation_invariant"]:
            assert len(set(values)) == 1, "no spread, so no gain from extra draws"
        else:
            assert values[0] > values[1] > values[2], row["capacity"]


def test_expected_best_of_n_matches_brute_force(tours):
    """Check the survival-function shortcut against enumerating every n-tuple.

    ``build_travel_budget.expected_best_of`` sums ``x_k * (P(min > k-1) - P(min > k))``.
    Enumerating all 24**n draws and averaging the minimum shares no algebra with
    it, so agreement is evidence rather than a restatement.
    """
    from build_travel_budget import expected_best_of
    for capacity, values in tours.items():
        for n in (1, 2, 3):
            brute = sum(min(combo) for combo in itertools.product(values, repeat=n))
            brute /= len(values) ** n
            assert expected_best_of(values, n) == pytest.approx(brute, abs=1e-9), (
                capacity, n)


def test_the_best_of_one_draw_is_the_plain_average(spec, tours):
    """E[best of 1] must be the mean over the 24 permutations, not the median."""
    for row in spec["capacity_curve"]:
        first = row["expected_best_of_n_mm"][0]["mm"]
        assert first == pytest.approx(statistics.mean(tours[row["capacity"]]), abs=1e-3)


def test_every_note_fetch_leg_is_bracketed_by_its_slots(spec, field):
    for row in spec["per_note"]:
        note_id = row["note_id"]
        target = field.targets[note_id]
        origins = (field.slots if row["randomized"] else (field.fixed_starts[note_id],))
        legs = sorted(travel.distance(field.start, o) + travel.distance(o, target)
                      for o in origins)
        assert row["fetch_and_deliver_mm"]["min"] == pytest.approx(legs[0], abs=1e-3)
        assert row["fetch_and_deliver_mm"]["max"] == pytest.approx(legs[-1], abs=1e-3)
        assert row["randomized"] == (note_id in field.randomized)


def test_the_strategy_frame_error_runs_both_ways(spec):
    """The reason the metric is not a ranking: it is not a one-sided bound."""
    directions = {r["strategy_frame_direction"] for r in spec["per_note"]}
    assert "overstates" in directions and "understates" in directions


def test_the_ranking_validity_is_computed_not_asserted(spec):
    """Perfect on the luckiest draw, anti-correlated on the unluckiest."""
    validity = spec["corrects"]["ranking_validity"]
    assert validity["spearman_at_best_permutation"] == pytest.approx(1.0, abs=1e-9)
    assert validity["spearman_at_worst_permutation"] < 0.0
    assert "after quarantine" in validity["note"]


def test_spearman_matches_a_hand_computed_case():
    """Guard the helper itself, not just its output."""
    from build_travel_budget import spearman
    same = {"a": 3.0, "b": 2.0, "c": 1.0}
    assert spearman(same, same) == pytest.approx(1.0)
    assert spearman(same, {"a": 1.0, "b": 2.0, "c": 3.0}) == pytest.approx(-1.0)


# --------------------------------------------------------------------------- #
# The truck — a bounded start, not a pending one (ADR-030)
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def field_spec() -> dict:
    return json.loads((ROOT / "data" / "field_spec.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def truck(field_spec, full_field) -> travel.TruckGroup:
    return full_field.truck


@pytest.fixture(scope="module")
def full_field(field_spec, field) -> travel.FullField:
    from sim.scoring import Scorer
    nominal = Scorer.load().nominal_placements()
    members = field_spec["start_groups"]["truck"]["members"]
    return travel.FullField(
        field_spec, field, {m: (nominal[m][1], nominal[m][2]) for m in members})


def test_the_vehicle_areas_match_the_printed_mat(field_spec):
    """Measured from S2, not chosen: two `#afbbdf` bodies identical to 4 µm."""
    drawings = json.loads((
        ROOT / "docs" / "extracted" / "WRO-2026-GameMat-Elementary-Printing-File"
        / "vector" / "drawings.json").read_text(encoding="utf-8"))
    bodies = sorted((p for p in drawings["paths"]
                     if (p.get("fill_hex") or "").lower() == "#afbbdf"),
                    key=lambda p: p["bbox_mm"][0])
    assert len(bodies) == 2, "the truck is exactly two vehicles"
    for area_id, body in zip(travel.TRUCK_VEHICLES, bodies):
        area = field_spec["areas"][area_id]
        assert area["scoring"] is False, f"{area_id} is a START region, never a target"
        for got, want in zip(area["bbox_mm"], body["bbox_mm"]):
            assert got == pytest.approx(want, abs=1e-3), area_id


def test_the_truck_members_still_have_no_pose(field_spec):
    """A bound is not a pose. ADR-014 is untouched by ADR-030."""
    for member in field_spec["start_groups"]["truck"]["members"]:
        pose = field_spec["object_start_poses"][member]
        assert pose["nominal_start_pose_mm"] is None, member
        assert pose["kind"] == "nominal_pending", member


def test_the_truck_enumerates_a_free_product_not_a_bijection(truck):
    """Nothing says the four objects occupy distinct vehicles — S1 says only
    "in the truck". That is the difference from the notes' 24 permutations."""
    assignments = truck.assignments()
    assert len(assignments) == 2 ** len(truck.members) == 16
    assert any(len(set(a.values())) == 1 for a in assignments), \
        "all four on one vehicle must be a member of the space"


def test_the_within_vehicle_residual_is_small_and_measured(truck, field):
    """Why the vehicle CHOICE is enumerated and the position on it is not."""
    spans = truck.within_vehicle_span(field.start)
    assert set(spans) == set(truck.members)
    for member, span in spans.items():
        assert 0 < span < 250, member
    assert max(spans.values()) < 200


def test_the_full_field_is_ten_missions(full_field):
    assert len(full_field.objects) == 10
    assert set(full_field.objects) == NOTES | set(full_field.truck.members)
    assert "cable_upper" not in full_field.objects
    assert len(full_field.assignments()) == 24 * 16 == 384


def test_the_refactor_left_the_six_note_figures_untouched(field, assignments, tours):
    """ADR-029's numbers must survive the generalisation exactly."""
    assert travel.tour(assignments[0], field, 1) == pytest.approx(
        travel.tour_points([assignments[0][n] for n in field.notes],
                           [field.targets[n] for n in field.notes],
                           field.start, 1), abs=1e-12)
    assert max(tours[1]) == pytest.approx(7592, abs=1)
    assert travel.spread(tours[6]) == 0.0


def test_tour_points_rejects_mismatched_inputs():
    with pytest.raises(ValueError, match="sources against"):
        travel.tour_points([(0.0, 0.0)], [(1.0, 1.0), (2.0, 2.0)], (0.0, 0.0), 1)


def test_collapsing_the_vehicle_choice_collapses_that_part_of_the_bracket(full_field):
    """The bracket is a bracket — which is exactly what work order B0 buys.

    Pin every truck object to one vehicle and the vehicle contribution vanishes;
    what survives is the note permutation, which no measurement can remove.
    """
    note_assigns = full_field.notes.assignments()
    pinned = [{**na, **{m: full_field.truck.vehicles[0] for m in full_field.truck.members}}
              for na in note_assigns]
    tours = [full_field.tour(a, 1) for a in pinned]

    # One vehicle, one permutation: nothing left to vary.
    assert len({round(full_field.tour(pinned[0], 1), 9)}) == 1
    # One vehicle, all permutations: only the irreducible part is left.
    residual = travel.spread(tours)
    full = travel.spread([full_field.tour({**na, **ta}, 1)
                          for na in note_assigns[:4]
                          for ta in full_field.truck.assignments()])
    assert 0 < residual < full, (
        "pinning the vehicles must shrink the spread without erasing it — the "
        "note permutation survives any measurement (S1 p7)")


# --------------------------------------------------------------------------- #
# The full run, and the pick-and-place cliff
# --------------------------------------------------------------------------- #


def test_the_full_run_covers_ten_of_twelve_missions(spec):
    run = spec["full_run"]
    assert run["count"] == 10
    assert run["points_covered"] == 185
    assert set(run["excludes"]) == {"cable_upper", "cable_lower"}
    for reason in run["excludes"].values():
        assert "not a measured region" in reason
    assert run["joint_assignments"] == 384


def test_more_capacity_shortens_the_full_run(spec):
    from build_travel_budget import FULL_RUN_CAPACITIES
    curve = spec["full_run"]["capacity_curve"]
    assert [r["capacity"] for r in curve] == list(FULL_RUN_CAPACITIES)
    for a, b in itertools.pairwise(curve):
        assert b["max_mm"] < a["max_mm"] and b["min_mm"] < a["min_mm"]
        assert b["required_speed_mm_s"]["at_worst_case"] < \
            a["required_speed_mm_s"]["at_worst_case"]


def test_the_spread_decomposes_into_what_b0_removes_and_what_it_cannot(spec):
    """The point of the 24 x 16 grid, and the number that prices work order B0."""
    for row in spec["full_run"]["capacity_curve"]:
        src = row["spread_sources_mm"]
        assert src["note_permutation"] > 0 and src["vehicle_choice"] > 0
        assert max(src.values()) <= row["spread_mm"] + 1e-6, \
            "a single source cannot exceed the joint spread"
        assert src["vehicle_choice"] > src["note_permutation"], (
            "B0 is worth MORE than the irreducible randomization — if that ever "
            "flips, the work order's priorities need revisiting")
    note = spec["full_run"]["uncertainty"]
    assert "B0" in note["what_b0_removes"] or "vehicle" in note["what_b0_removes"]
    assert "after quarantine" in note["what_nothing_removes"]


def test_the_pick_and_place_cliff_is_attempt_over_objects(spec):
    pp = spec["full_run"]["pick_and_place"]
    assert pp["objects"] == 10
    assert pp["impossible_beyond_s_per_object"] == pytest.approx(12.0, abs=1e-9)
    assert pp["cliff_is_independent_of_distance"] is True
    assert travel.impossible_beyond(10, 120.0) == pytest.approx(12.0)
    assert travel.impossible_beyond(6, 120.0) == pytest.approx(20.0)
    with pytest.raises(ValueError):
        travel.impossible_beyond(0)


def test_the_cliff_lands_at_the_same_place_at_every_capacity(spec):
    """Distance-independent: shortening the tour never buys pick-and-place time."""
    for block in spec["full_run"]["pick_and_place"]["by_capacity"]:
        infeasible = [c["seconds_per_object"] for c in block["cells"]
                      if not c["feasible_at_any_speed"]]
        assert infeasible == [12.0], block["capacity"]
        for cell in block["cells"]:
            assert (cell["required_speed_mm_s"] is None) == (not cell["feasible_at_any_speed"])


def test_required_speed_rises_with_pick_and_place_time(spec):
    for block in spec["full_run"]["pick_and_place"]["by_capacity"]:
        speeds = [c["required_speed_mm_s"] for c in block["cells"]
                  if c["required_speed_mm_s"] is not None]
        assert speeds == sorted(speeds)
        assert speeds[0] == pytest.approx(
            block["worst_case_distance_mm"] / 120.0, abs=0.05)


def test_the_capacities_not_computed_are_explained(spec):
    block = spec["full_run"]["capacities_not_computed"]
    assert block["capacities"] == [3, 4, 5, 6]
    assert "s! x s!" in block["why"]
    assert "not a 31.9 mm note" in block["why"]


# --------------------------------------------------------------------------- #
# Honesty guards
# --------------------------------------------------------------------------- #


def test_the_artefact_declares_itself_a_lower_bound(spec):
    scope = spec["scope"]
    assert scope["every_distance_is_a_lower_bound"] is True
    assert scope["lower_bound_assumption"] == "AS-11"
    assert scope["speed_is_not_measured"] is True
    assert "P6" in scope["speed_source"]
    assert "turning radius" in spec["bounds"]["why_a_lower_bound"]


def test_the_artefact_refuses_to_choose_a_capacity(spec):
    scope = spec["scope"]
    assert scope["does_not_choose_a_capacity"] is True
    assert "A2/A3" in scope["capacity_gated_on"]
    assert "ADR-022" in scope["capacity_gated_on"]


def test_the_artefact_states_what_it_does_not_cover(spec):
    scope = spec["scope"]
    assert "ten of the twelve" in scope["covers"]
    assert "185 of the 215" in scope["covers"]
    assert "B0" in scope["does_not_cover"]
    assert "cable" in scope["does_not_cover"]
    assert "not a measured region" in scope["does_not_cover"]
    assert "ADR-014 is untouched" in scope["truck_is_bounded_not_known"]


def test_the_rules_are_quoted_not_paraphrased(spec):
    rules = spec["rules"]
    assert rules["s4_10_1"] == "Each robot attempt is 2 minutes"
    assert "randomization of game objects" in rules["s4_9_6"]
    assert "changing positions or orientation" in rules["s4_10_2"]


def test_the_adr_table_matches_the_artefact(spec):
    """ADR-029 prints the capacity curve; a doc that drifts from its data lies.

    This is the guard ADR-029 argues for, turned on ADR-029 itself: every figure
    in its table is parsed back out of the prose and checked against the JSON.
    """
    import re
    text = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    body = text.split("## ADR-029")[1].split("\n## ")[0]
    rows = {}
    for line in body.splitlines():
        cells = [c.strip().replace("*", "") for c in line.strip().strip("|").split("|")]
        if len(cells) == 6 and cells[0].isdigit():
            rows[int(cells[0])] = [float(c) for c in cells[1:]]
    assert set(rows) == set(travel.DEFAULT_CAPACITIES), "the ADR must print every capacity"
    for row in spec["capacity_curve"]:
        printed = rows[row["capacity"]]
        assert printed[0] == pytest.approx(row["min_mm"], abs=0.5)
        assert printed[1] == pytest.approx(row["median_mm"], abs=0.5)
        assert printed[2] == pytest.approx(row["max_mm"], abs=0.5)
        assert printed[3] == pytest.approx(row["spread_mm"], abs=0.05)
        assert printed[4] == pytest.approx(
            row["required_speed_mm_s"]["at_worst_permutation"], abs=0.05)


def test_the_adr_quotes_the_saving_and_the_correlations(spec):
    text = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    # Prose uses the typographic minus U+2212; normalise rather than forcing
    # ASCII into the documents.
    body = text.split("## ADR-029")[1].split("\n## ")[0].replace("−", "-")
    assert f"{spec['headline']['capacity_one_to_two_saves_mm']:.0f} mm" in body
    validity = spec["corrects"]["ranking_validity"]
    assert f"{validity['spearman_at_best_permutation']:+.3f}" in body
    assert f"{validity['spearman_at_worst_permutation']:.3f}" in body


def _adr_body(number: str) -> str:
    text = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    return text.split(f"## ADR-{number}")[1].split("\n## ")[0]


def test_the_adr_030_full_run_table_matches_the_artefact(spec):
    """Same guard as ADR-029's, turned on the full-run numbers.

    The ADR uses thin spaces as thousands separators (`14 789`); they are
    stripped rather than banned, because the prose should stay readable.
    """
    body = _adr_body("030")
    rows = {}
    for line in body.splitlines():
        cells = [c.strip().replace("*", "").replace(" ", "")
                 for c in line.strip().strip("|").split("|")]
        if len(cells) == 6 and cells[0].isdigit() and int(cells[0]) < 10:
            rows[int(cells[0])] = [float(c) for c in cells[1:]]
    curve = spec["full_run"]["capacity_curve"]
    assert set(rows) == {r["capacity"] for r in curve}
    for row in curve:
        printed = rows[row["capacity"]]
        assert printed[0] == pytest.approx(row["min_mm"], abs=0.5)
        assert printed[1] == pytest.approx(row["median_mm"], abs=0.5)
        assert printed[2] == pytest.approx(row["max_mm"], abs=0.5)
        assert printed[3] == pytest.approx(row["spread_mm"], abs=0.5)
        assert printed[4] == pytest.approx(
            row["required_speed_mm_s"]["at_worst_case"], abs=0.5)


def test_the_adr_030_spread_decomposition_matches(spec):
    body = _adr_body("030").replace(" ", "")
    for row in spec["full_run"]["capacity_curve"]:
        for value in row["spread_sources_mm"].values():
            assert f"{value:.0f}" in body, (row["capacity"], value)


def test_the_adr_030_cliff_table_matches_the_artefact(spec):
    """Parse the ADR's own cliff table and check it row by row.

    The ADR tabulates a readable subset of the seconds-per-object grid, so the
    guard reads its header rather than demanding every row the artefact carries.
    """
    body = _adr_body("030")

    def row(prefix: str) -> list[str]:
        line = next(ln for ln in body.splitlines()
                    if ln.startswith(f"| {prefix}"))
        return [c.strip().replace("*", "") for c in line.strip().strip("|").split("|")][1:]

    seconds = [float(c) for c in row("s per object")]
    driving = [float(c) for c in row("driving seconds left")]
    speeds = row("required mm/s, capacity 2")
    assert len(seconds) == len(driving) == len(speeds) > 4

    pp = spec["full_run"]["pick_and_place"]
    assert f"{pp['impossible_beyond_s_per_object']:.0f} s per object" in body
    assert "120 / 10" in body
    cells = {c["seconds_per_object"]: c
             for c in next(b for b in pp["by_capacity"] if b["capacity"] == 2)["cells"]}
    for t, left, printed in zip(seconds, driving, speeds):
        cell = cells[t]
        assert cell["driving_seconds"] == pytest.approx(left, abs=1e-6), t
        if cell["required_speed_mm_s"] is None:
            assert printed == "impossible", t
        else:
            assert float(printed) == pytest.approx(cell["required_speed_mm_s"], abs=0.5), t


def test_provenance_pins_every_input(spec):
    inputs = spec["provenance"]["inputs"]
    assert set(inputs) == {"field_spec", "scoring_model", "strategy_frame"}
    assert all(len(v) == 64 for v in inputs.values())
