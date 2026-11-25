"""TA-009 §3 ve §21: TA-008B kalıntı düzeltmeleri ve paylaşılan MathAI sınırı. Ağ ve sağlayıcı çağrısı yoktur.

Her test önce kusuru yeniden üreten girdiyle yazıldı (TA-008B tabanında başarısızdı; rapor: docs/phase-reports/TA-009.md).
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from fractions import Fraction

import pytest

from apps.api.app.features.education.mathematics import GeometryModel, MathematicalModel, WordProblemModel
from apps.api.app.features.lessons.schemas import Expression, Step
from apps.api.app.features.mathai import isolated, priority
from apps.api.app.features.mathai.isolated import IsolatedMathAI, MathAIUnavailable
from apps.api.app.features.mathai.service import MathAIService
from apps.api.app.features.mathematics import domain, geometry, sets, transforms, word_problems
from apps.api.app.features.integrity import expression as tree
from apps.api.app.features.reasoning import quantities, quotes
from apps.api.tests.test_mathai import plan


def f(id_, kind, points, origin="stated", evidence=None, **kw):
    return {"id": id_, "kind": kind, "points": points, "origin": origin, "evidence": evidence, **kw}


def run(model, text="", figure=False, observations=(), confirmed=()):
    return geometry.analyze(GeometryModel.model_validate(model), geometry.Source(text, figure, tuple(observations),
                                                                                 tuple(confirmed)))


# --- §3.1 belirteç düzeyinde kanıt --------------------------------------------------------------------------------

def test_value_is_not_matched_inside_a_larger_number():
    assert not quotes.contains("AB = 15 cm", "AB = 5")
    assert quotes.contains("ABC üçgeninde AB = 5 cm'dir", "AB = 5 cm")
    result = run({"points": ["A", "B"], "facts": [f("ab", "segment_length", ["A", "B"], value="5", evidence="AB = 5")]},
                 "AB = 15 cm'dir.")
    assert result.rejected == {"ab": "provider_proposed"}


def test_segment_label_is_not_matched_inside_unrelated_notation():
    assert not quotes.has_label(quotes.tokens("ABC çevresi 6"), "AB", "BA")
    result = run({"points": ["A", "B", "C"], "facts": [f("ab", "segment_length", ["A", "B"], value="6",
                                                        evidence="ABC çevresi 6")]}, "ABC çevresi 6 cm'dir.")
    assert result.rejected["ab"] == "quote_does_not_assert_fact"


def test_quoted_mention_is_not_an_asserted_value():
    text = "AB = 3 cm, BC = 4 cm ise AC kaç cm'dir?"
    result = run({"points": ["A", "C"], "facts": [f("ac", "segment_length", ["A", "C"], value="5", evidence="AC kaç cm")]}, text)
    assert result.rejected["ac"] == "quote_does_not_assert_fact"
    asked = run({"points": ["A", "C"], "facts": [f("ac", "segment_length", ["A", "C"], value="5", evidence="AC = 5 midir?")]},
                "AC = 5 midir?")
    assert asked.rejected["ac"] == "quote_mentions_without_asserting"


@pytest.mark.parametrize(("text", "quote"), [("AB, AC'ye eşit değildir.", "AB, AC'ye eşit değildir"), ("AB ≠ AC", "AB ≠ AC")])
def test_negated_relationship_is_not_a_positive_fact(text, quote):
    result = run({"points": ["A", "B", "C"], "facts": [f("e", "equal_segments", ["A", "B"], other=["A", "C"], evidence=quote)]},
                 text)
    assert result.rejected["e"] == "negated_in_source"


def test_word_problem_value_anchor_is_token_aware():
    model = WordProblemModel.model_validate({
        "problem_type": "other", "quantities": [{"symbol": "a", "name_tr": "elma", "value": "5", "evidence": "5 elma"},
                                                {"symbol": "b", "name_tr": "toplam"}],
        "relations": ["b = 2a"], "objective": "b"})
    fidelity = next(c for c in word_problems.analyze(model, "Sepette 15 elma ve 5 armut var.").checks
                    if c.area == "model_fidelity")
    assert fidelity.reason == "value_meaning_unanchored"


# --- §3.2 şekil kanıtı --------------------------------------------------------------------------------------------

BASE = [f("t", "triangle", ["A", "B", "C"], evidence="ABC üçgeninde"),
        f("ab", "segment_length", ["A", "B"], value="3", evidence="AB = 3 cm"),
        f("bc", "segment_length", ["B", "C"], value="4", evidence="BC = 4 cm"),
        f("r", "right_angle", ["A", "B", "C"], origin="marked", evidence="B köşesinde dik açı işareti")]
TEXT = "Şekildeki ABC üçgeninde AB = 3 cm ve BC = 4 cm'dir. AC kaç cm'dir?"
MODEL = {"points": ["A", "B", "C"], "facts": BASE, "target": {"kind": "length", "points": ["A", "C"]}}


def test_figure_existence_does_not_authorize_every_marked_fact():
    result = run(MODEL, TEXT, figure=True, observations=["Şekilde bir üçgen var"])
    assert result.rejected["r"] == "diagram_marking_unlinked" and result.determinacy == "underdetermined"


def test_marked_fact_linked_to_visual_observation_or_student_confirmation():
    observed = run(MODEL, TEXT, figure=True, observations=["B köşesinde dik açı işareti var"])
    assert observed.accepted["r"] == "diagram_observation" and [str(v) for v in observed.target_values] == ["5"]
    confirmed = run(MODEL, TEXT, figure=True, confirmed=["B köşesinde dik açı işareti var"])
    assert confirmed.accepted["r"] == "student_confirmed"


def test_answer_depending_on_ai_read_marking_is_only_partially_checked():
    p = plan("x = 1", "AC = 5", [Step(id="step_1", type="result", title="t", explanation="e", expressions=[])])
    p.source_analysis.question_text = TEXT
    p.source_analysis.mathematical_expressions = []
    p.source_analysis.visual_elements.has_geometry_figure = True
    p.source_analysis.visual_elements.relevant_visual_facts = ["B köşesinde dik açı işareti var"]
    p.content.final_answer_expressions = [Expression(type="equation", latex="AC = 5")]
    p.content.mathematical_model = MathematicalModel.model_validate({"kind": "geometry", "geometry": MODEL})
    check = next(c for c in MathAIService().verify(p).mathematics.checks if c.id == "geometry_answer")
    assert (check.status, check.reason) == ("partially_checked", "answer_matches_target_visual_dependency")


# --- §3.3 türlü nicelik karşılaştırması ---------------------------------------------------------------------------

def claim(text, kinds=None):
    return quantities.parse_claim(text, kinds).typed


@pytest.mark.parametrize(("expected", "text", "status", "reason"), [
    (quantities.from_si(Fraction(5), "length"), "5 km", "mismatch", "value_mismatch"),
    (quantities.from_si(Fraction(5000), "length"), "5 km", "match", None),
    (quantities.from_si(Fraction(5), "speed"), "5 m/s^2", "mismatch", "dimension_mismatch"),
    (quantities.from_si(Fraction(5), "mass"), "5 N", "mismatch", "dimension_mismatch"),
    (quantities.from_si(Fraction(20), "speed"), "72 km/h", "match", None),
    (quantities.from_si(Fraction(5), "speed"), "-5 m/s", "mismatch", "negative_magnitude"),
    (quantities.from_si(Fraction(5), "length"), "5", "undecidable", "unit_missing"),
])
def test_equal_numbers_do_not_imply_equal_physical_answers(expected, text, status, reason):
    result = quantities.compare(expected, claim(text))
    assert result.status == status and (reason is None or reason in result.reasons)


def test_energy_is_not_torque_and_component_sign_matters():
    energy = quantities.from_si(Fraction(5), "energy")
    assert quantities.compare(energy, claim("M = 5 N·m", {"M": "torque"})).reasons == ("kind_mismatch",)
    assert quantities.compare(energy, claim("5 J")).matched
    component = quantities.Typed(Fraction(-3), quantities.KINDS["velocity"].dim, "velocity", representation="component")
    assert quantities.compare(component, claim("3 m/s")).reasons == ("sign_mismatch",)
    assert quantities.compare(component, claim("-3 m/s")).matched
    left = quantities.Typed(Fraction(-3), quantities.KINDS["velocity"].dim, "velocity", direction="-x")
    assert quantities.compare(left, claim("3 m/s sağa")).reasons == ("direction_mismatch",)


def geometry_plan(answer, text="ABC üçgeninde AB = 3 cm, BC = 4 cm ve B açısı diktir. AC kaç cm'dir?"):
    p = plan("x = 1", answer, [Step(id="step_1", type="result", title="t", explanation="e", expressions=[])])
    p.source_analysis.question_text = text
    p.source_analysis.mathematical_expressions = []
    p.content.final_answer_expressions = [Expression(type="equation", latex=answer)]
    facts = [f("t", "triangle", ["A", "B", "C"], evidence="ABC üçgeninde"),
             f("r", "right_angle", ["A", "B", "C"], evidence="B açısı diktir"),
             f("ab", "segment_length", ["A", "B"], value="3", evidence="AB = 3 cm"),
             f("bc", "segment_length", ["B", "C"], value="4", evidence="BC = 4 cm")]
    p.content.mathematical_model = MathematicalModel.model_validate({"kind": "geometry", "geometry": {
        "points": ["A", "B", "C"], "facts": facts, "target": {"kind": "length", "points": ["A", "C"]}}})
    return p


@pytest.mark.parametrize(("answer", "status", "reason"), [
    ("AC = 5 cm", "passed", "answer_matches_target"),
    ("AC = 5", "passed", "answer_matches_target"),
    ("AC = 50 mm", "passed", "answer_matches_target"),
    ("AC = 5 km", "failed", "geometry_answer_mismatch"),
    ("BC = 5", "failed", "target_identity_mismatch"),
])
def test_geometry_answer_is_bound_to_target_identity_and_source_unit(answer, status, reason):
    check = next(c for c in MathAIService().verify(geometry_plan(answer)).mathematics.checks if c.id == "geometry_answer")
    assert (check.status, check.reason) == (status, reason)


# --- §3.4 tanım koşulu taşması ------------------------------------------------------------------------------------

def test_domain_condition_overflow_fails_closed():
    latex = " + ".join(f"\\sqrt{{\\ln(x-{k})}}" for k in range(1, 14)) + " = 1"  # 26 ayrı koşul, bütçe içinde
    assert tree.parse(latex).parsed
    with pytest.raises(domain.DomainOverflow):
        domain.conditions_of(latex)
    with pytest.raises(domain.DomainOverflow):
        sets.solve_equation(latex, "x")
    assert transforms.compare(latex, "x = 1", latex, "x").relation == "unsupported"
    with pytest.raises(domain.DomainOverflow):
        domain.conditions_of(r"\frac{1}{x" + "+" * 3)  # ayrıştırılamayan ifade "koşul yok" sayılmaz
    # Ders akışında kaynak ifade bütünlük motorunun görüntüleme bütçesine daha önce takılır (mevcut koruma).
    report = MathAIService().verify(plan(latex, "x = 1", [Step(id="step_1", type="result", title="t", explanation="e",
                                                                expressions=[])])).mathematics
    assert not any(c.id == "solution_set" and c.status == "passed" for c in report.checks)


# --- §3.5 durum ayrımından sonraki adımlar ------------------------------------------------------------------------

def case_steps(*groups):
    out = []
    for index, (kind, latexes) in enumerate(groups, 1):
        out.append(Step(id=f"step_{index}", type=kind, title="t", explanation="e",
                        expressions=[Expression(type="equation", latex=x) for x in latexes]))
    return out


def test_steps_after_a_case_split_are_checked_inside_their_branch():
    good = case_steps(("case", ["x - 2 = 4"]), ("case", ["x - 2 = -4"]), ("transformation", ["x = 6"]),
                      ("transformation", ["x = -2"]))
    checks = MathAIService().verify(plan("|x - 2| = 4", "x = -2 veya x = 6", good)).mathematics.checks
    branch = [c for c in checks if c.id.endswith("_branch")]
    assert len(branch) == 2 and all(c.status == "passed" for c in branch)
    bad = case_steps(("case", ["x - 2 = 4"]), ("case", ["x - 2 = -4"]), ("transformation", ["x = 5"]))
    checks = MathAIService().verify(plan("|x - 2| = 4", "x = -2 veya x = 6", bad)).mathematics.checks
    assert any(c.id.endswith("_branch") and c.status == "failed" and c.material for c in checks)


def test_invalid_split_leaves_later_steps_explicitly_unchecked():
    steps = case_steps(("case", ["x - 2 = 4"]), ("transformation", ["x = 6"]))
    checks = MathAIService().verify(plan("|x - 2| = 4", "x = 6", steps)).mathematics.checks
    assert any(c.reason == "case_branch_invalid" for c in checks)
    assert any(c.reason == "branch_steps_unchecked" and c.status == "not_checked" for c in checks)


# --- §21 paylaşılan MathAI sınırı ve ücretli sonuç kaybı ---------------------------------------------------------

def fake_worker(monkeypatch, delay=0.05):
    state = {"running": 0, "peak": 0, "calls": 0}
    lock = threading.Lock()

    def run_process(*args, **kwargs):
        with lock:
            state["running"] += 1
            state["calls"] += 1
            state["peak"] = max(state["peak"], state["running"])
        time.sleep(delay)
        with lock:
            state["running"] -= 1
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps({"value": [True, None], "timing": {"compute_ms": 1}}))

    monkeypatch.setattr(isolated.subprocess, "run", run_process)
    return state


def test_container_services_share_one_mathai_limiter():
    from apps.api.app.core.container import build_container
    from apps.api.app.core.settings import Settings

    container = build_container(Settings(environment="test"))
    lesson, interaction = container.lesson_service.mathai, container.interaction_service.mathai
    assert lesson is interaction and lesson.limiter is isolated.shared_limiter()


def test_global_process_count_never_exceeds_the_configured_maximum(monkeypatch):
    monkeypatch.setenv("TEACHERAI_MATHAI_MAX_PROCESSES", "2")
    monkeypatch.setenv("TEACHERAI_MATHAI_MAX_WAITING", "32")
    isolated.reset_shared_limiter()
    try:
        state = fake_worker(monkeypatch)
        services = [IsolatedMathAI(), IsolatedMathAI()]  # ders ve etkileşim hizmetleri gibi iki ayrı örnek
        for item in services:
            item.queue_timeout_seconds = 10
        threads = [threading.Thread(target=services[i % 2].check_answer, args=("2x=8", "4", "x")) for i in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(30)
        assert state["calls"] == 10 and state["peak"] <= 2
    finally:
        isolated.reset_shared_limiter()


def test_verification_after_a_paid_call_waits_longer_instead_of_discarding_the_result(monkeypatch):
    fake_worker(monkeypatch, delay=0.0)
    math = IsolatedMathAI(max_processes=1, max_waiting=0)
    math.queue_timeout_seconds = 0.01
    math.post_provider_queue_timeout_seconds = 2.0
    math._slots.acquire()
    with pytest.raises(MathAIUnavailable) as caught:
        math.check_answer("2x=8", "4", "x")  # ücretli çağrı öncesi: kuyruk dolu → hemen mathai_busy
    assert caught.value.code == "mathai_busy"
    releaser = threading.Timer(0.2, math._slots.release)
    releaser.start()
    assert priority.after_paid_call(math.check_answer)("2x=8", "4", "x")[0]  # sonra: sınırlı bekleme, sonuç korunur
    releaser.join()


def test_post_provider_wait_is_bounded(monkeypatch):
    fake_worker(monkeypatch, delay=0.0)
    math = IsolatedMathAI(max_processes=1, max_waiting=0)
    math.post_provider_queue_timeout_seconds = 0.05
    math._slots.acquire()
    try:
        with pytest.raises(MathAIUnavailable):
            priority.after_paid_call(math.check_answer)("2x=8", "4", "x")
    finally:
        math._slots.release()
