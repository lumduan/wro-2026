"""Guards on the three documents the operator actually works from.

`docs/QUESTIONS.md`, `docs/MEASUREMENT_PROTOCOL.md` and `docs/B1_PROCEDURE.md` are
the only artefacts in this repo that leave it — they are read at a bench, at a
competition table, and in an email to an organizer. Everything else is checked
against a source; these are checked against **completeness**, because a question
missing its fallback or a measurement missing its destination is discovered at
the worst possible moment.

The specific failure this file exists to prevent: a question that states an
ambiguity without stating **what to do if nobody answers it**. There are five
open ambiguities and two unasked organizer questions, and the competition does
not wait for replies.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "docs" / "QUESTIONS.md"
PROTOCOL = ROOT / "docs" / "MEASUREMENT_PROTOCOL.md"
B1 = ROOT / "docs" / "B1_PROCEDURE.md"

#: Every open ambiguity routed to S6, plus the two organizer questions.
EXPECTED_ASKS = 7


@pytest.fixture(scope="module")
def questions() -> str:
    return QUESTIONS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sections(questions: str) -> list[str]:
    return re.split(r"^## \d+ · ", questions, flags=re.M)[1:]


# --------------------------------------------------------------------------- #
# The seven questions
# --------------------------------------------------------------------------- #


def test_there_are_seven_questions(sections: list[str]):
    assert len(sections) == EXPECTED_ASKS


def test_every_question_carries_all_five_fields(sections: list[str]):
    """Quote, readings, what changes, magnitude, fallback — no exceptions.

    "Readings" for a rule the Q&A interprets; "answers" for a fact the organizer
    simply knows. Both are the same field: *enumerate the possibilities, do not
    force it to two*.
    """
    for section in sections:
        title = section.splitlines()[0]
        assert "**Quote" in section, title
        assert "plausible readings" in section or "plausible answers" in section, title
        assert "changes with the answer" in section, title
        assert "**Magnitude" in section, title
        assert "**Fallback" in section, title
        assert "Consequence if wrong" in section, title


def _enumeration_rows(section: str) -> list[str]:
    """Table rows under the "All plausible …" heading of one question.

    Split on the **bolded** marker, not the bare word: "plausible" also appears
    inside a table header cell, and splitting on it lands mid-row.
    """
    if "**All plausible" not in section:
        return []
    block = section.split("**All plausible", 1)[1]
    return [ln for ln in block.splitlines() if ln.startswith("|")]


def test_no_question_is_forced_to_two_options(sections: list[str]):
    """The brief's instruction, asserted: enumerate, do not dichotomise."""
    for section in sections:
        title = section.splitlines()[0]
        rows = _enumeration_rows(section)
        # header + separator + at least two options
        assert len(rows) >= 4, title
    wide = [s for s in sections if len(_enumeration_rows(s)) >= 5]
    assert len(wide) >= 4, "at least four questions should enumerate 3+ options"


def test_every_open_ambiguity_is_asked(questions: str):
    """Nothing routed to S6 may be missing from the outgoing set."""
    register = (ROOT / "docs" / "AMBIGUITIES.md").read_text(encoding="utf-8")
    open_ids = set(re.findall(r"^\| (A\d+) \| \*\*OPEN\*\*", register, re.M))
    assert open_ids, "the register should still have open items"
    for ambiguity in open_ids:
        assert re.search(rf"\*\*{ambiguity}\*\*", questions), \
            f"{ambiguity} is open but is not in the outgoing question set"


def test_both_organizer_questions_are_present(questions: str):
    assert "NO-TH (a)" in questions and "NO-TH (b)" in questions


def test_the_questions_are_ordered_by_magnitude(questions: str):
    """A partial reply should still be useful, so the order has to be real."""
    assert "descending" in questions
    first = re.split(r"^## \d+ · ", questions, flags=re.M)[1]
    assert "A7" in first.splitlines()[0], "A7 is the largest and must lead"


def test_a_fallback_is_never_left_as_an_exercise(sections: list[str]):
    for section in sections:
        fallback = section.split("**Fallback")[1]
        assert len(fallback.split("Consequence if wrong")[1].strip()) > 40, \
            section.splitlines()[0]


# --------------------------------------------------------------------------- #
# The measurement protocol
# --------------------------------------------------------------------------- #


def test_the_protocol_covers_every_meas_item():
    text = PROTOCOL.read_text(encoding="utf-8")
    for item in ("MEAS-1", "MEAS-2", "MEAS-3", "MEAS-4", "MEAS-5"):
        assert f"## {item}" in text, item


def test_every_measured_field_has_a_destination():
    text = PROTOCOL.read_text(encoding="utf-8")
    assert text.count("**Destination:**") >= 5
    for field in ("mass_g", "grip_face", "cog_height_mm", "tilt_angle_deg",
                  "measured_contact_mm"):
        assert field in text, field


def test_repeat_counts_are_justified_not_asserted():
    """A repeat count without arithmetic behind it is a guess in a table."""
    text = PROTOCOL.read_text(encoding="utf-8")
    assert "1 / √(2(n−1))" in text or "1 / √(2(n−1))" in text
    assert "n = 11" in text or "**11**" in text
    assert "not enough for a σ" in text, "the protocol must say where n is too small"


def test_proxies_are_decided_in_advance():
    text = PROTOCOL.read_text(encoding="utf-8")
    assert "Proxies, stated in advance" in text
    assert "h = w/tan θ + c" in text, "the CoG proxy needs the CLEAT-CORRECTED formula"
    assert "leave it `null`" in text, "ADR-014 discipline must survive the protocol"


# --------------------------------------------------------------------------- #
# ADR-034 — the tilt proxy measured friction
# --------------------------------------------------------------------------- #


def test_the_cleat_is_mandatory_and_corrected():
    """Without a cleat every object slides; without the `+ c` the answer is 7% low."""
    text = PROTOCOL.read_text(encoding="utf-8")
    assert "cleat is mandatory" in text.lower() or "mandatory, not an option" in text
    assert "h = w/tan θ + c" in text
    # 3.5, not 3: ADR-035 widened the bound so a LEGO tile (3.2 mm, flat,
    # dimensionally standard) is legal in place of a fabricated shim.
    assert "≤ 3.5 mm" in text, "cleat height must be bounded — a tall cleat makes c dominate"
    assert "LEGO tile" in text, "a standard part beats a shim, because c enters h at 1:1"
    assert "w/μ_s" in text, "the protocol must name what a slide actually returns"


def test_the_cleat_contact_point_is_recorded_per_object():
    """The pivot is at (0, c) only for a flat face square to the base."""
    text = PROTOCOL.read_text(encoding="utf-8")
    assert "cleat_contact_height_mm" in text
    assert "cleat_contact_note" in text
    assert "1 : 1" in text, "c's undamped propagation into h must be stated"
    assert "in situ" in text and "adhesive" in text
    assert "CoG-underivable" in text, "a shaped face must be allowed to yield no CoG"


def test_the_friction_validation_rule_is_present_with_a_number():
    text = PROTOCOL.read_text(encoding="utf-8")
    assert "19.3" in text, "arctan(mu_s) must be given, or the rule cannot be applied"
    assert "1.5×" in text, "the base-width ratio that triggers the check"
    assert "fail the block" in text.lower()
    assert "translation before rotation" in text.lower() or \
        "before it rotates" in text, "the physical check, not only the data check"


def test_the_angular_resolution_is_specified_with_its_amplification():
    text = PROTOCOL.read_text(encoding="utf-8")
    assert "±0.5°" in text
    assert "2·dθ / sin 2θ" in text or "2·dθ/sin 2θ" in text
    assert "3.11×" in text, "the amplification at 20 deg must be stated"
    assert "reaction-board" in text.lower(), "an alternative is required when 0.5 deg is not achievable"
    assert "h = L (R₀ − R₁) / (W · tan θ)" in text


def test_the_instruments_are_excluded_from_tilt():
    """No predicate consumes their tilt angle — scoring_model says so verbatim."""
    text = PROTOCOL.read_text(encoding="utf-8")
    assert "13 objects, not 16" in text
    assert "No uprightness requirement" in text, "the justification must be quoted, not asserted"
    model = json.loads((ROOT / "data" / "scoring_model.json").read_text(encoding="utf-8"))
    instruments = next(m for m in model["missions"]
                       if m["id"] == "m2_prepare_show_instruments")
    assert "upright" not in instruments["full_condition"]
    assert instruments["partial"] is None
    for other in ("m1_connect_amplifier", "m2_prepare_show_microphone", "m3_play_the_song"):
        mission = next(m for m in model["missions"] if m["id"] == other)
        assert "upright" in mission["full_condition"].lower(), other


def test_the_cleat_correction_recovers_a_known_height():
    """Re-derive the physics here rather than trusting the prose."""
    import math
    w, h_true, cleat = 16.0, 27.0, 2.0
    theta = math.degrees(math.atan(w / (h_true - cleat)))
    assert theta == pytest.approx(32.62, abs=0.01)
    corrected = w / math.tan(math.radians(theta)) + cleat
    assert corrected == pytest.approx(h_true, abs=1e-9)
    uncorrected = w / math.tan(math.radians(theta))
    assert (uncorrected - h_true) / h_true == pytest.approx(-0.074, abs=0.001)


def test_every_object_really_would_have_slid():
    """The premise of ADR-034, computed rather than quoted."""
    import math
    mu_s = 0.35
    shapes = {"note": (16, 27), "cable": (8, 10), "mic": (16, 45),
              "amp": (30, 35), "speaker": (20, 30), "clef": (16, 40)}
    for name, (w, h) in shapes.items():
        assert w / h > mu_s, f"{name} would have tipped — ADR-034's table needs revisiting"


# --------------------------------------------------------------------------- #
# The session budget
# --------------------------------------------------------------------------- #


def test_every_block_carries_a_time_estimate():
    text = PROTOCOL.read_text(encoding="utf-8")
    assert "Session budget" in text
    for block in ("MEAS-1", "MEAS-2", "MEAS-3", "MEAS-4", "MEAS-5a"):
        assert re.search(rf"\*\*{block}\*\*.*min", text), block
    assert "four hours" in text.lower(), "the honest total must be stated"
    assert "1:25" in text, "the milestone where the manipulator decision closes"


def test_the_screen_then_characterise_design_is_justified():
    """ADR-035: tiers are not assigned in advance; the screen decides."""
    text = PROTOCOL.read_text(encoding="utf-8")
    assert "Screen, then characterise" in text
    assert "3°" in text, "the promotion threshold must be stated"
    assert "55–71" in text, "the revised trial count"
    assert "Nothing is below a line in advance" in text


def test_the_notes_are_not_one_shape_class():
    """Computed from object_spec, not quoted — the premise that failed."""
    spec = json.loads((ROOT / "data" / "object_spec.json").read_text(encoding="utf-8"))
    objects = spec["objects"]
    notes = [k for k in objects if k.startswith("note_")]
    boms = {k: json.dumps(objects[k]["bom_steps"], sort_keys=True) for k in notes}
    assert len(set(boms.values())) > 1, (
        "if the notes ever become identical builds, the screen design can be "
        "simplified — and MEASUREMENT_PROTOCOL's justification needs rewriting")
    # …while the duplicate PAIRS genuinely are identical.
    for a, b in (("cable_upper", "cable_lower"), ("speaker_a", "speaker_b")):
        assert objects[a]["bom_steps"] == objects[b]["bom_steps"], (a, b)


def test_the_tilt_consumer_is_a_single_scalar():
    """Why per-object characterisation is over-specified."""
    source = (ROOT / "sim" / "scoring.py").read_text(encoding="utf-8")
    assert re.search(r"upright_tolerance_deg:\s*float\s*=", source), \
        "if this becomes per-object, the screen design needs revisiting"


# --------------------------------------------------------------------------- #
# ADR-035 — the two ceilings
# --------------------------------------------------------------------------- #


def test_the_rule_maximum_is_255_everywhere():
    """255 is not stale and nothing may correct it."""
    model = json.loads((ROOT / "data" / "scoring_model.json").read_text(encoding="utf-8"))
    assert model["max_score"] == 255
    total = 0
    for mission in model["missions"]:
        total += sum(e["max"] for e in mission["entries"]) if mission.get("entries") \
            else mission["max"]
    assert total == 255, "the sheet must sum to its stated maximum"


def test_no_document_proposes_correcting_255_to_225():
    """BRIEF_SYNC must never be the vector for a wrong number."""
    brief = (ROOT / "docs" / "BRIEF_SYNC.md").read_text(encoding="utf-8")
    drift = brief.split("### Not drift")[0]
    assert "maximum score is **255**" not in drift, \
        "255 is correct and must not appear in the drift table"
    assert "255 is the maximum score and nothing corrects it" in brief
    assert "rule maximum" in brief and "model coverage ceiling" in brief


def test_claude_md_names_225_as_the_models_ceiling():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "225, not 255" not in text, "that phrasing reads as correcting the rule"
    assert "model coverage ceiling" in text
    assert "255 is not stale and nothing corrects it" in text


def test_the_dq_is_priced_at_the_rule_maximum(questions: str):
    section = re.split(r"^## \d+ · ", questions, flags=re.M)[3]
    assert "NO-TH (a)" in section.splitlines()[0]
    assert "the full 255" in section
    assert "denominator here is 255, not 225" in section


def test_the_protocol_does_not_promise_that_calipers_close_a7():
    """The one thing measurement cannot do, said in the measurement document."""
    text = PROTOCOL.read_text(encoding="utf-8")
    assert "Calipers do not close A7" in text


# --------------------------------------------------------------------------- #
# B1
# --------------------------------------------------------------------------- #


def test_b1_names_its_single_question():
    text = B1.read_text(encoding="utf-8")
    assert "one** implementation or **two" in text or "one implementation or two" in text
    assert "decision rule" in text.lower()


def test_b1_marks_what_is_throwaway():
    text = B1.read_text(encoding="utf-8")
    assert "throwaway" in text.lower()
    assert "Build no manipulator" in text
    for part in ("wheelbase", "wheel diameter", "sensor mounting"):
        assert part in text, part


def test_b1_pass_fail_needs_no_interpretation():
    text = B1.read_text(encoding="utf-8")
    assert "recorded, not graded" in text or "Judge only what the table says" in text
    assert "counter-clockwise" in text, "the sign convention is the sharp criterion"


def test_b1_stays_inside_any_plausible_national_limit():
    """A6 is open at national scope, so B1 must not depend on the answer."""
    text = B1.read_text(encoding="utf-8")
    assert "2 motors" in text or "**2**" in text
    assert "A6" in text and "national" in text


def test_b1_gives_a_log_schema():
    text = B1.read_text(encoding="utf-8")
    assert "docs/b1_results.json" in text
    assert "semantic_differences" in text
    assert "implementations_needed" in text
