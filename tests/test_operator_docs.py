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
import math
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "docs" / "QUESTIONS.md"
PROTOCOL = ROOT / "docs" / "MEASUREMENT_PROTOCOL.md"
B1 = ROOT / "docs" / "B1_PROCEDURE.md"

#: Every open ambiguity routed to S6, plus the four organizer questions, plus
#: the three added on 2026-07-27 (Thailand's game rules, the technical summary,
#: the tie-break-within-a-tie). The round-count question retired: confirmed.
EXPECTED_ASKS = 10


@pytest.fixture(scope="module")
def questions() -> str:
    return QUESTIONS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sections(questions: str) -> list[str]:
    return re.split(r"^## \d+ · ", questions, flags=re.M)[1:]


# --------------------------------------------------------------------------- #
# The seven questions
# --------------------------------------------------------------------------- #


def test_the_question_count_is_pinned(sections: list[str]):
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


def test_the_operating_point_is_the_tipping_angle_not_the_friction_angle():
    """The 20° row must never read as the expected reading.

    `arctan(0.35) ≈ 19.3°` is the *friction* angle — what a sliding object
    reports when the cleat fails. Budgeting error there is planning against the
    measurement the method exists to avoid, and it is pessimistic by ~2.6×.
    A cleated object reads at 30–35°.
    """
    text = PROTOCOL.read_text(encoding="utf-8")
    assert "not your operating point" in text
    assert "30–35°" in text, "the real operating point must be named"
    assert "Evaluate sensitivity at the TIPPING angle" in text
    assert "32.6°" in text, "the worked tipping angle anchors it"
    assert "the cleat is not working, fail the block" in text, \
        "the 20-degree row must tie back to the validation rule"


def test_the_sensitivity_figures_are_arithmetically_right():
    """Re-derive both ends rather than trusting the table."""
    import math
    w, h, c = 16.0, 27.0, 2.0
    tip = math.degrees(math.atan(w / (h - c)))
    assert tip == pytest.approx(32.62, abs=0.01)
    # |dh/dtheta| = w / sin^2(theta), in mm per radian
    at_tip = w / math.sin(math.radians(tip)) ** 2
    at_slide = w / math.sin(math.radians(19.3)) ** 2
    assert at_tip == pytest.approx(55.1, abs=0.2)
    assert at_slide == pytest.approx(146.5, abs=0.5)
    # +-0.5 deg on h = 27
    assert at_tip * math.radians(0.5) / h == pytest.approx(0.018, abs=0.001)
    assert at_slide / at_tip == pytest.approx(2.66, abs=0.05), \
        "the friction angle overstates the error budget by ~2.6x"


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


# --------------------------------------------------------------------------- #
# ADR-037 — best-of-2 confirmed. These guards exist to stop the two mistakes
# the rework was made to fix: the wrong quantity in sigma/sqrt(pi), and rho
# silently defaulting to zero.
# --------------------------------------------------------------------------- #

ROUND_STRATEGY = ROOT / "data" / "round_strategy.json"
AMBIGUITIES = ROOT / "docs" / "AMBIGUITIES.md"


@pytest.fixture(scope="module")
def round_strategy() -> dict:
    return json.loads(ROUND_STRATEGY.read_text(encoding="utf-8"))


def _row(strategy: dict, reading: str, block: str, sigma: float = 20.0) -> dict:
    return next(r for r in strategy["readings"][reading][block] if r["sigma_mm"] == sigma)


def test_the_premium_uses_the_score_sd_not_the_placement_sigma(round_strategy):
    """The exact figure and sd/sqrt(pi) must agree; sigma_mm/sqrt(pi) does not.

    At placement sigma = 20 mm the score sd is ~15.1 points. Feeding 20 into the
    closed form gives +11.28 against an exact +8.41 — a third too high. This is
    the arithmetic error ADR-037 exists to prevent recurring.
    """
    dist = _row(round_strategy, "contact", "distribution")
    best = _row(round_strategy, "contact", "best_of")
    exact = next(c for c in best["at_n"] if c["n"] == 2)["premium_over_single_attempt"]
    closed = next(c for c in best["premium_at_rho"] if c["rho"] == 0.0)["premium"]
    assert abs(closed - exact) / exact < 0.02, (closed, exact)

    wrong = dist["sigma_mm"] / math.sqrt(math.pi)
    assert abs(wrong - exact) / exact > 0.25, \
        "the placement sigma must NOT reproduce the premium — that is the bug"


def test_correlation_collapses_the_premium(round_strategy):
    """Systematic variance is pure cost. rho = 0.9 must leave almost nothing."""
    best = _row(round_strategy, "contact", "best_of")
    at = {c["rho"]: c["premium"] for c in best["premium_at_rho"]}
    assert at[0.9] < 3.0, at
    assert at[0.0] / at[0.9] > 3.0, "the rho = 0 default must be visibly optimistic"
    assert at[0.0] > at[0.5] > at[0.9], "the premium must fall monotonically in rho"


def test_round_two_is_priced_as_an_option(round_strategy):
    """E[(X - S1)+] must fall as the realised round-1 score rises."""
    for reading in round_strategy["readings"]:
        best = _row(round_strategy, reading, "best_of")
        worth = [c["round_2_worth"] for c in best["conditional_round_2"]]
        assert worth == sorted(worth, reverse=True), (reading, worth)
        assert worth[0] > worth[-1], reading


def test_survival_is_emitted_and_monotone(round_strategy):
    for reading, block in round_strategy["readings"].items():
        for row in block["distribution"]:
            ps = [c["p"] for c in row["survival"]]
            assert ps == sorted(ps, reverse=True), (reading, row["sigma_mm"])
            assert all(0.0 <= x <= 1.0 for x in ps)


def test_the_round_count_is_recorded_as_confirmed(round_strategy):
    scope = round_strategy["scope"]
    assert scope["n"] == 2 and scope["n_is_not_known"] is False
    assert "operator" in scope["n_source"].lower()
    assert scope["rho_is_not_measured"] is True, "rho is NOT measured and must say so"


def test_the_safe_default_for_rho_is_high_not_zero(round_strategy):
    """The one default whose safe direction inverts under best-of-2."""
    register = AMBIGUITIES.read_text(encoding="utf-8")
    assert "safe default for ρ is HIGH" in register
    assert "overstates the premium" in register
    assert "overstates" in round_strategy["scope"]["rho_source"].lower()


def test_the_sigma_direction_audit_covers_every_open_default():
    """Each open ambiguity must be classified as touching sd or not."""
    register = AMBIGUITIES.read_text(encoding="utf-8")
    audit = register.split("σ-direction audit", 1)[1].split("## Detail", 1)[0]
    open_ids = set(re.findall(r"^\| (A\d+) \| \*\*OPEN\*\*", register, re.M))
    for ambiguity in open_ids:
        assert f"**{ambiguity}**" in audit or f"| {ambiguity} " in audit, \
            f"{ambiguity} is open but was not audited for sigma-direction"


def test_the_variance_claim_is_narrowed_to_independent_variance(round_strategy):
    """ADR-027 said 'extra rounds reward variance'. Only INDEPENDENT variance."""
    why = round_strategy["formula"]["why_variance_matters"]
    assert "INDEPENDENT" in why
    assert "Systematic variance is pure cost" in why


# --------------------------------------------------------------------------- #
# S4 rules that do not exist, and rules that now have consumers
# --------------------------------------------------------------------------- #

#: Extraction defect ADR-038: page 9 of S4 lost 75% of its text to a spurious
#: table, chapter 5's rules 5.5-5.13 went with it, and the absence was written
#: up as a finding AND enforced by a test. The replacement guards the METHOD:
#: no page may lose text between the spans and the markdown. It would have
#: caught the defect on the day it appeared, and it encodes no conclusion.
EXTRACTED = ROOT / "docs" / "extracted"

#: Markdown re-flows and adds table pipes, so exact equality is not the test.
#: The observed floor across 224 good pages is 0.94; the defect page sat at 0.25.
PAGE_TEXT_FLOOR = 0.94


def _tokens(text: str) -> list[str]:
    return re.findall(r"[0-9a-z]+", text.lower())


def _span_text(page: dict) -> str:
    out: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get("text"), str):
                out.append(node["text"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(page)
    return " ".join(out)


def _extracted_docs() -> list[Path]:
    if not EXTRACTED.exists():
        return []
    return [d for d in sorted(EXTRACTED.iterdir()) if (d / "text" / "spans.json").exists()]


@pytest.mark.skipif(not _extracted_docs(), reason="extraction output is gitignored")
def test_no_extracted_page_loses_text():
    """Every page's markdown must retain the text the same run put in spans.json.

    This is the precondition of every "the rules do not say X" claim in this
    repo. Grepping the markdown cannot establish an absence unless the markdown
    is known to be complete — see ADR-038, where it was not.
    """
    for doc in _extracted_docs():
        spans = json.loads((doc / "text" / "spans.json").read_text(encoding="utf-8"))
        for page in spans["pages"]:
            number = page["page"]
            md_path = doc / "text" / f"page_{number:03d}.md"
            if not md_path.exists():
                continue
            want = _tokens(_span_text(page))
            if not want:
                continue
            have: dict[str, int] = {}
            for token in _tokens(md_path.read_text(encoding="utf-8")):
                have[token] = have.get(token, 0) + 1
            kept = 0
            for token in want:
                if have.get(token, 0) > 0:
                    have[token] -= 1
                    kept += 1
            coverage = kept / len(want)
            assert coverage >= PAGE_TEXT_FLOOR, (
                f"{doc.name} page {number} lost {100 * (1 - coverage):.0f}% of its text "
                f"between spans.json and the markdown — see ADR-038"
            )


@pytest.mark.skipif(not _extracted_docs(), reason="extraction output is gitignored")
def test_every_rule_number_survives_into_the_markdown():
    """The sharper form of the same precondition, for rule numbers specifically."""
    rule = re.compile(r"\b(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\.")
    for doc in _extracted_docs():
        spans = json.loads((doc / "text" / "spans.json").read_text(encoding="utf-8"))
        md = " ".join(
            (doc / "text" / f"page_{p['page']:03d}.md").read_text(encoding="utf-8")
            for p in spans["pages"]
            if (doc / "text" / f"page_{p['page']:03d}.md").exists()
        )
        in_spans = set(rule.findall(" ".join(_span_text(p) for p in spans["pages"])))
        missing = sorted(in_spans - set(rule.findall(md)))
        assert not missing, f"{doc.name}: rule numbers lost by the markdown: {missing}"


def test_the_retracted_absence_claim_is_not_restated():
    """ADR-038 retracts it. Nothing may re-assert that chapter 5 ends at 5.4."""
    for path in sorted((ROOT / "docs").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for claim in ("ends at 5.4", "ends at **5.4**", "do not exist", "absent document-wide"):
            if claim not in text:
                continue
            window = text[max(0, text.index(claim) - 400):text.index(claim) + 400]
            assert "ADR-038" in window or "retract" in window.lower(), (
                f"{path.name} restates the retracted absence claim without naming ADR-038"
            )


def test_the_button_rule_reached_the_chassis_constraints():
    text = (ROOT / "docs" / "PHASE7_CONSTRAINTS.md").read_text(encoding="utf-8")
    assert "5.2.6" in text and "outer side" in text
    assert "separate stop button of the EV3" in text, "the platform asymmetry must be named"
    assert "5.2.9" in text and "sticky material" in text
    assert "omni" in text.lower(), "omni wheels are explicitly permitted and worth knowing"


def test_the_mass_limit_has_a_measurement_and_is_a_gate():
    text = (ROOT / "docs" / "HARDWARE_SESSION.md").read_text(encoding="utf-8")
    assert "MEAS-6" in text and "1500 g" in text
    assert "robot_mass_g" in text
    assert "gate" in text.lower(), "mass is checked repeatedly, not once"


def test_chapter_6_is_tracked_outside_the_255():
    text = (ROOT / "docs" / "HARDWARE_SESSION.md").read_text(encoding="utf-8")
    assert "technical summary" in text.lower()
    assert "two (2) DIN A4 page" in text, "two pages, not one"
    assert "Attachment B" in text
    assert "not folded into" in text or "outside the 255" in text


def test_b1_separates_the_contract_question_from_the_platform_decision():
    text = B1.read_text(encoding="utf-8")
    assert "5.4" in text and "one full robot" in text
    assert "Which platform competes?" in text
    assert "before the twelve mission programs are written" in text


# --------------------------------------------------------------------------- #
# ADR-039 — the closed form is an upper bound, and latent rho is not measured rho
# --------------------------------------------------------------------------- #


def test_the_closed_form_is_an_upper_bound_at_every_rho(round_strategy):
    """If the analytic premium ever came in BELOW the exact one, the claim that
    it is a safe upper bound would be false and the safe default would flip."""
    for reading, block in round_strategy["readings"].items():
        for row in block["best_of"]:
            for cell in row["premium_at_rho"]:
                assert cell["premium"] >= cell["premium_exact"], (reading, row["sigma_mm"], cell)
                assert cell["analytic_overstates_by"] >= 0.0, cell


def test_latent_rho_is_reported_separately_from_realised(round_strategy):
    """The trap ADR-039 exists to stop: measured rho fed into the closed form."""
    row = _row(round_strategy, "contact", "best_of")
    high = next(c for c in row["premium_at_rho"] if c["rho"] == 0.9)
    assert high["rho_realised"] < high["rho"], "attenuation must be visible, not hidden"
    note = round_strategy["formula"]["correlation_is_latent_not_measured"]
    assert "24%" in note, "the overstatement at a measured rho must be stated as a number"
    assert "correlated_best_of_two" in note, "the note must name the function that fixes it"


def test_the_inverted_assumption_is_registered():
    """AS-13 — the only assumption whose safe direction is the opposite of the rest."""
    text = (ROOT / "docs" / "ASSUMPTIONS.md").read_text(encoding="utf-8")
    assert "AS-13" in text
    assert "Consequence if wrong" in text.split("## AS-13", 1)[1]
    assert "3.2" in text.split("## AS-13", 1)[1], "the asymmetry needs its number"


def test_the_conditional_round_two_rule_is_gated():
    """ADR-027's tactic needs a practice block between rounds; say so in the ADR."""
    adr = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    body = adr.split("## ADR-027", 1)[1].split("## ADR-028", 1)[0]
    assert "GATED" in body and "9.3" in body
    assert "QUESTIONS.md` #2" in body or "QUESTIONS.md #2" in body


# --------------------------------------------------------------------------- #
# The recovered rules must reach a consumer, not just a quote
# --------------------------------------------------------------------------- #


def test_the_recovered_rules_have_design_consumers():
    text = (ROOT / "docs" / "PHASE7_CONSTRAINTS.md").read_text(encoding="utf-8")
    for rule in ("5.5", "5.6", "5.7", "5.8", "5.9", "5.10", "5.11", "5.12", "5.13"):
        assert f"**{rule}**" in text or f"§{rule}" in text, f"S4 {rule} has no consumer"
    assert "offline version" in text, "5.8 must reach the toolchain decision"
    assert "boot from an SD card" in text or "boot card" in text, "5.10 must reach the EV3 path"
    assert "abort card" in text, "5.13 must reach the printed-material decision"


def test_the_two_ceilings_are_distinguished_wherever_both_appear():
    """255 is the rule maximum; 225 is model coverage. Neither corrects the other."""
    for name in ("README.md", "CLAUDE.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        if "225" not in text:
            continue
        assert "rule maximum" in text, f"{name} names 225 without naming what 255 is"
        assert "coverage" in text.lower(), f"{name} names 225 without saying it is coverage"


def test_s1_and_s4_carry_the_same_version_date():
    citations = json.loads((ROOT / "docs" / "citations.json").read_text(encoding="utf-8"))
    s1 = citations["sources"]["S1"]["version_line"]
    s4 = citations["sources"]["S4"]["version_line"]
    assert "January 15th 2026" in s1 and "JANUARY 15TH 2026" in s4

