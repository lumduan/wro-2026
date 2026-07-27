"""Invariants on the feasibility frontier and on ``data/feasibility_frontier.json``.

This is the first artefact in the project that **ranks missions**, so the guards
here are about earning that right rather than assuming it.

``strategy_frame.json`` refused mission ordering in as many words — *"needs sigma
from field tests P2/P3 and the object pickup locations, 15 of which are
nominal_pending"* — and CLAUDE.md §5.7 anti-pattern #3 forbids strategy claims
without simulator evidence. ADR-029 and ADR-030 supplied the tours; feasibility
does not need sigma, because sigma decides whether a placement *scores*, not
whether it *fits*. Two tests pin that reasoning to the artefact, so a future
reader can see the ban lift rather than find it quietly gone.

The subtler guard is :func:`test_accounting_for_accuracy_changes_the_subset`. Raw
points rank a note above an instrument by a third; expected points stop doing so
at sigma = 20.4 mm, because `backstage` is 20x a note target and the instruments'
``p_full`` is still 1.0 at 30 mm. If that crossover ever disappears, the artefact
is claiming something the data no longer supports.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest

from sim import frontier, travel

ROOT = Path(__file__).resolve().parents[1]
FRONTIER = ROOT / "data" / "feasibility_frontier.json"

TRUCK = {"mic", "instrument_guitar", "instrument_keyboard", "instrument_congas"}
NOTES = {"note_black", "note_white", "note_yellow", "note_blue",
         "note_green", "note_red"}


@pytest.fixture(scope="module")
def spec() -> dict:
    return json.loads(FRONTIER.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def field() -> travel.FullField:
    from sim.scoring import Scorer
    field_spec = json.loads((ROOT / "data" / "field_spec.json").read_text(encoding="utf-8"))
    nominal = Scorer.load().nominal_placements()
    members = field_spec["start_groups"]["truck"]["members"]
    return travel.FullField(
        field_spec, travel.NoteField(field_spec),
        {m: (nominal[m][1], nominal[m][2]) for m in members})


@pytest.fixture(scope="module")
def value() -> dict[str, float]:
    model = json.loads((ROOT / "data" / "scoring_model.json").read_text(encoding="utf-8"))
    return {oid: float(m["each"]) for m in model["missions"]
            if m["id"] != "m4_bonus" for oid in m["objects"]}


@pytest.fixture(scope="module")
def tours(field) -> dict[int, float]:
    assign = field.assignments()[0]
    return frontier.subset_tours([assign[o] for o in field.objects],
                                 [field.targets[o] for o in field.objects],
                                 field.start, 2)


# --------------------------------------------------------------------------- #
# The subset tours
# --------------------------------------------------------------------------- #


def test_subset_tours_agree_with_an_independent_tour(field, tours):
    """One DP answers every subset — check it against solving each alone."""
    assign = field.assignments()[0]
    sources = [assign[o] for o in field.objects]
    targets = [field.targets[o] for o in field.objects]
    for subset in (0b1, 0b11, 0b1010101, 0b111111, 0b1111111111):
        members = [i for i in range(len(field.objects)) if subset >> i & 1]
        expected = travel.tour_points([sources[i] for i in members],
                                      [targets[i] for i in members], field.start, 2)
        assert tours[subset] == pytest.approx(expected, abs=1e-9), bin(subset)


def test_every_subset_is_present_and_the_empty_one_is_free(field, tours):
    assert len(tours) == 2 ** len(field.objects) == 1024
    assert tours[0] == 0.0, "doing nothing travels nothing"
    assert all(t >= 0 for t in tours.values())


def test_adding_a_mission_never_shortens_the_tour(field, tours):
    """Monotone in the subset — a superset visits everything the subset did."""
    n = len(field.objects)
    for subset in (0b1, 0b101, 0b11110000, 0b111111111):
        for bit in range(n):
            if subset >> bit & 1:
                continue
            assert tours[subset | (1 << bit)] >= tours[subset] - 1e-9, (subset, bit)


def test_subset_tours_rejects_a_bad_capacity(field, tours):
    assign = field.assignments()[0]
    with pytest.raises(ValueError):
        frontier.subset_tours([assign[o] for o in field.objects],
                              [field.targets[o] for o in field.objects], field.start, 0)


def test_the_profile_is_independent_of_where_anything_starts(field, value):
    """The hoist that makes sweeping 384 states cheap must actually be valid."""
    counts, points = frontier.subset_profile(field.objects, value)
    assert len(counts) == len(points) == 1024
    assert counts[0] == 0 and points[0] == 0.0
    assert counts[1023] == 10 and points[1023] == 185.0
    for subset in (0b1, 0b1011, 0b111111):
        members = [o for i, o in enumerate(field.objects) if subset >> i & 1]
        assert counts[subset] == len(members)
        assert points[subset] == pytest.approx(sum(value[o] for o in members))


# --------------------------------------------------------------------------- #
# The frontier itself
# --------------------------------------------------------------------------- #


def test_the_full_set_appears_exactly_when_it_fits(field, value, tours):
    """Checked against the time inequality directly, not against itself."""
    full = (1 << len(field.objects)) - 1
    for speed, pick in itertools.product((100, 150, 250), (0.0, 4.0, 8.0)):
        fits = tours[full] / speed + 10 * pick <= 120.0
        best = frontier.best_reachable(tours, field.objects, value, speed, pick)
        assert (best.points == 185.0) == fits, (speed, pick)


def test_more_speed_never_loses_points(field, value, tours):
    for pick in frontier.DEFAULT_PICK_PLACE:
        scores = [frontier.best_reachable(tours, field.objects, value, v, pick).points
                  for v in frontier.DEFAULT_SPEEDS]
        assert scores == sorted(scores), pick


def test_slower_handling_never_gains_points(field, value, tours):
    for speed in frontier.DEFAULT_SPEEDS:
        scores = [frontier.best_reachable(tours, field.objects, value, speed, t).points
                  for t in frontier.DEFAULT_PICK_PLACE]
        assert scores == sorted(scores, reverse=True), speed


def test_the_reported_subset_actually_fits(field, value, tours):
    for speed, pick in itertools.product((75, 150, 400), (0.0, 5.0, 10.0)):
        best = frontier.best_reachable(tours, field.objects, value, speed, pick)
        assert best.seconds <= 120.0 + 1e-9
        assert best.travel_mm == pytest.approx(tours[best.subset], abs=1e-9)
        assert best.points == pytest.approx(sum(value[o] for o in best.objects))
        assert set(best.objects) <= NOTES | TRUCK


def test_best_points_matches_best_reachable(field, value, tours):
    """The fast path and the detailed path must agree."""
    counts, points = frontier.subset_profile(field.objects, value)
    for speed, pick in itertools.product(frontier.DEFAULT_SPEEDS[:4],
                                         frontier.DEFAULT_PICK_PLACE[:4]):
        assert frontier.best_points(tours, counts, points, speed, pick) == pytest.approx(
            frontier.best_reachable(tours, field.objects, value, speed, pick).points)


def test_a_zero_speed_is_rejected(field, value, tours):
    with pytest.raises(ValueError):
        frontier.best_reachable(tours, field.objects, value, 0, 0.0)


# --------------------------------------------------------------------------- #
# Saturation — where field test P6 stops mattering
# --------------------------------------------------------------------------- #


def test_saturation_speed_is_exactly_what_the_ceiling_needs(field, value, tours):
    for pick in (0.0, 2.0, 4.0, 6.0):
        speed = frontier.saturation_speed(tours, field.objects, value, pick)
        target = frontier.ceiling(tours, field.objects, value, pick)
        assert speed is not None
        assert frontier.best_reachable(
            tours, field.objects, value, speed * 1.0001, pick).points >= target
        assert frontier.best_reachable(
            tours, field.objects, value, speed * 0.999, pick).points < target


def test_slower_handling_demands_more_speed(field, value, tours):
    speeds = [frontier.saturation_speed(tours, field.objects, value, t)
              for t in (0.0, 1.0, 2.0, 4.0, 6.0, 8.0)]
    assert all(s is not None for s in speeds)
    assert speeds == sorted(speeds)


def test_no_speed_saturates_past_the_cliff(field, value, tours):
    """ADR-030: ten objects x 12 s is the whole attempt, so nothing finite works."""
    assert frontier.saturation_speed(tours, field.objects, value, 12.0) is None


def test_the_ceiling_ignores_driving_entirely(field, value, tours):
    """It is the unlimited-speed bound, so only pick-and-place can reduce it."""
    assert frontier.ceiling(tours, field.objects, value, 0.0) == 185.0
    assert frontier.ceiling(tours, field.objects, value, 12.0) == 185.0
    assert frontier.ceiling(tours, field.objects, value, 13.0) < 185.0


# --------------------------------------------------------------------------- #
# Bonus exposure is a max, not a sum (ADR-024)
# --------------------------------------------------------------------------- #


def test_a_subset_risks_its_worst_cluster_once(spec):
    exposure = {o: 10 for o in NOTES} | {o: 30 for o in TRUCK}
    assert frontier.exposed_bonus([], exposure) == 0
    assert frontier.exposed_bonus(sorted(NOTES), exposure) == 10
    assert frontier.exposed_bonus(["note_red", "mic"], exposure) == 30
    assert frontier.exposed_bonus(sorted(TRUCK), exposure) == 30, \
        "four truck missions expose the stage cluster once, not four times"


def test_the_drop_order_records_what_each_subset_risks(spec):
    for block in spec["capacity_blocks"]:
        for row in block["drop_order"]:
            assert row["bonus_points_exposed"] in (0, 10, 30)
            if not set(row["dropped"]) >= TRUCK:
                assert row["bonus_points_exposed"] == 30, row


# --------------------------------------------------------------------------- #
# The artefact
# --------------------------------------------------------------------------- #


def test_the_grid_is_complete(spec):
    for block in spec["capacity_blocks"]:
        cells = {(c["speed_mm_s"], c["pick_place_s"]) for c in block["attemptable"]}
        assert cells == {(v, t) for v in frontier.DEFAULT_SPEEDS
                         for t in frontier.DEFAULT_PICK_PLACE}
    assert [b["capacity"] for b in spec["capacity_blocks"]] == [1, 2]


def test_the_worst_case_never_beats_the_best_case(spec):
    for block in spec["capacity_blocks"]:
        for cell in block["attemptable"]:
            assert cell["worst_case_points"] <= cell["best_case_points"], cell
            assert 0 <= cell["worst_case_points"] <= 185


def test_the_published_frontier_is_monotone(spec):
    for block in spec["capacity_blocks"]:
        cells = {(c["speed_mm_s"], c["pick_place_s"]): c for c in block["attemptable"]}
        for pick in frontier.DEFAULT_PICK_PLACE:
            row = [cells[(v, pick)]["worst_case_points"] for v in frontier.DEFAULT_SPEEDS]
            assert row == sorted(row), pick
        for speed in frontier.DEFAULT_SPEEDS:
            col = [cells[(speed, t)]["worst_case_points"]
                   for t in frontier.DEFAULT_PICK_PLACE]
            assert col == sorted(col, reverse=True), speed


def test_more_capacity_never_reaches_fewer_points(spec):
    at = {b["capacity"]: {(c["speed_mm_s"], c["pick_place_s"]): c["worst_case_points"]
                          for c in b["attemptable"]}
          for b in spec["capacity_blocks"]}
    for key, one in at[1].items():
        assert at[2][key] >= one, key


def test_the_instruments_go_before_the_notes(spec):
    """ADR-030's 5.2x points-per-metre gap, showing up as a decision."""
    block = next(b for b in spec["capacity_blocks"] if b["capacity"] == 2)
    first = next(r for r in block["drop_order"] if r["dropped"])
    assert set(first["dropped"]) <= TRUCK, first
    assert all(d.startswith("instrument_") for d in first["dropped"])


def test_the_microphone_is_dropped_ahead_of_a_cheaper_instrument(spec):
    """The inversion a points-per-metre table gets wrong.

    `mic` is worth 20 against an instrument's 15, yet it is shed first at some
    handling times because it costs more travel than the instrument it displaces.
    """
    for block in spec["capacity_blocks"]:
        for row in block["drop_order"]:
            if "mic" in row["dropped"] and not set(row["dropped"]) >= {
                    "instrument_congas", "instrument_guitar", "instrument_keyboard"}:
                return
    pytest.fail("expected at least one cell where mic is dropped before all instruments")


# --------------------------------------------------------------------------- #
# Robustness — the crossover
# --------------------------------------------------------------------------- #


def test_the_instruments_are_effectively_immune_to_placement_error(spec):
    rob = spec["robustness"]
    for cell in rob["instrument_keyboard"]:
        if cell["sigma_mm"] <= 30.0:
            assert cell["p_full"] == 1.0, cell
    assert rob["target_area_mm2"]["ratio_backstage_to_note"] > 15


def test_the_note_and_the_instrument_cross(spec):
    rob = spec["robustness"]
    crossover = rob["crossover_sigma_mm"]
    assert crossover is not None
    assert 15.0 < crossover < 30.0
    below = [(n, i) for n, i in zip(rob["note_blue"], rob["instrument_keyboard"])
             if n["sigma_mm"] < crossover]
    above = [(n, i) for n, i in zip(rob["note_blue"], rob["instrument_keyboard"])
             if n["sigma_mm"] > crossover]
    assert all(n["expected_points"] >= i["expected_points"] for n, i in below)
    assert all(n["expected_points"] < i["expected_points"] for n, i in above)


def test_raw_points_and_expected_points_disagree(spec):
    """If they ever agreed everywhere, the expected view would be dead weight."""
    total = 0
    for block in spec["capacity_blocks"]:
        diff = block["expected_value_changes_the_subset"]
        assert diff["cells_compared"] == 270
        assert len(diff["differences"]) == diff["cells_that_differ"]
        total += diff["cells_that_differ"]
        for cell in diff["differences"]:
            assert set(cell["attemptable_subset"]) != set(cell["expected_subset"])
    assert total > 0, "accuracy must change the answer somewhere, or ADR-031 is wrong"


def test_accounting_for_accuracy_favours_the_instruments(spec):
    """The direction is the finding, and it is the opposite of the raw ranking."""
    added: dict[str, int] = {}
    for block in spec["capacity_blocks"]:
        for cell in block["expected_value_changes_the_subset"]["differences"]:
            for object_id in set(cell["expected_subset"]) - set(cell["attemptable_subset"]):
                added[object_id] = added.get(object_id, 0) + 1
    assert added, "no substitutions recorded"
    winner = max(added, key=added.get)
    assert winner.startswith("instrument_"), added


# --------------------------------------------------------------------------- #
# Honesty guards
# --------------------------------------------------------------------------- #


def test_the_artefact_says_why_the_ban_lifted(spec):
    why = spec["scope"]["why_this_is_allowed_now"]
    assert "anti-pattern #3" in why
    assert "ADR-029 and ADR-030" in why
    assert "does not need sigma" in why


def test_neither_free_parameter_is_asserted(spec):
    scope = spec["scope"]
    assert scope["speed_is_not_measured"] is True and "P6" in scope["speed_source"]
    assert scope["pick_place_is_not_measured"] is True
    # MEAS-3, not A3: ADR-033 renamed the bench-work block off the ambiguity
    # namespace, where A3 is a *resolved* entry about robot overlap.
    assert "MEAS-3" in scope["pick_place_source"]
    assert "fits" in scope["feasibility_is_not_success"]
    assert scope["excludes_the_bonus_floor"] == 40


def test_the_artefact_states_it_is_a_lower_bound(spec):
    assert "LOWER BOUND" in spec["scope"]["does_not_cover"]
    assert "cable" in spec["scope"]["does_not_cover"]
    assert "185 of the 215" in spec["scope"]["covers"]


def _adr_031() -> str:
    text = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    return text.split("## ADR-031")[1].split("\n## ")[0]


def test_the_adr_saturation_table_matches_the_artefact(spec):
    """Same guard as ADR-029's and ADR-030's, turned on the saturation row."""
    body = _adr_031()

    def row(prefix: str) -> list[str]:
        """Table rows carry bold markers, so strip markup before matching."""
        for line in body.splitlines():
            cells = [c.strip().replace("*", "") for c in line.strip().strip("|").split("|")]
            if cells and cells[0] == prefix:
                return cells[1:]
        raise AssertionError(f"ADR-031 has no row labelled {prefix!r}")

    ticks = [float(c) for c in row("t (s per object)")]
    printed = [float(c) for c in row("needs (mm/s)")]
    block = next(b for b in spec["capacity_blocks"] if b["capacity"] == 2)
    sat = {s["pick_place_s"]: s for s in block["saturation"]}
    for pick, value in zip(ticks, printed):
        assert sat[pick]["speed_mm_s"] == pytest.approx(value, abs=0.05), pick


def test_the_adr_crossover_table_matches_the_artefact(spec):
    body = _adr_031()
    rob = spec["robustness"]
    note = {c["sigma_mm"]: c["expected_points"] for c in rob["note_blue"]}
    inst = {c["sigma_mm"]: c["expected_points"] for c in rob["instrument_keyboard"]}
    for line in body.splitlines():
        cells = [c.strip().replace("*", "") for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0].replace(".", "").isdigit():
            sigma = float(cells[0])
            if sigma not in note:
                continue
            assert float(cells[1]) == pytest.approx(note[sigma], abs=0.01), sigma
            assert float(cells[2]) == pytest.approx(inst[sigma], abs=0.01), sigma
    assert f"{rob['crossover_sigma_mm']:.1f} mm" in body
    assert f"{rob['target_area_mm2']['backstage']:,.0f}".replace(",", " ") in body


def test_the_adr_quotes_the_substitution_counts(spec):
    body = _adr_031()
    for block in spec["capacity_blocks"]:
        differ = block["expected_value_changes_the_subset"]
        assert f"{differ['cells_that_differ']} of {differ['cells_compared']}" in body

    # The per-instrument tallies the ADR names are capacity 2's, and it says so.
    block = next(b for b in spec["capacity_blocks"] if b["capacity"] == 2)
    added: dict[str, int] = {}
    for cell in block["expected_value_changes_the_subset"]["differences"]:
        for object_id in set(cell["expected_subset"]) - set(cell["attemptable_subset"]):
            added[object_id] = added.get(object_id, 0) + 1
    for object_id in ("instrument_keyboard", "instrument_guitar", "instrument_congas"):
        assert f"`{object_id}`" in body
        assert f"**{added[object_id]}**" in body, (object_id, added[object_id])


def test_provenance_pins_every_input(spec):
    inputs = spec["provenance"]["inputs"]
    assert set(inputs) == {"field_spec", "scoring_model", "expected_score", "travel_budget"}
    assert all(len(v) == 64 for v in inputs.values())
    assert spec["provenance"]["joint_start_states"] == 384
