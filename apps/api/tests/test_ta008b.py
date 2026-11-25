"""TA-008B: matematik doğrulamasının sertleştirilmesi, kanıt bütünlüğü ve çalışma zamanı tamamlama.

Ağ ve ücretli çağrı yoktur: OpenAI yolu sahte istemci (``fake_openai``), Anthropic yolu ``httpx.MockTransport`` ile
çalışır. Her senaryo iki yapılandırılmış yolda da aynı sonucu vermelidir.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

import apps.api.app.features.lessons.openai_provider as lesson_module
from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.education.mathematics import MathCheck
from apps.api.app.features.lessons.exceptions import VerificationContradictionError
from apps.api.app.features.lessons.openai_provider import AnthropicLessonProvider, OpenAILessonProvider
from apps.api.app.features.lessons.schemas import Expression, Step
from apps.api.app.features.lessons.service import LessonService, correction_feedback, correction_resolved
from apps.api.app.features.mathai.service import MathAIService
from apps.api.app.features.mathematics import domain, functions, sets, specialist, transforms
from apps.api.tests.fake_openai import FakeRaw, body, fake_client
from apps.api.tests.test_anthropic_adapter import message
from apps.api.tests.test_lesson_provider_errors import lesson_payload
from apps.api.tests.test_mathai import plan
from apps.api.tests.test_question_integrity import analysis

GEO_TEXT = "ABC üçgeninde AB = 3 cm, BC = 4 cm ve B açısı diktir. AC kaç cm'dir?"


def fact(id_, kind, points, value=None, evidence=None, origin="stated", other=None, premises=None, rule=None):
    return {"id": id_, "kind": kind, "points": points, "other": other or [], "value": value, "origin": origin,
            "evidence": evidence, "premises": premises or [], "rule": rule}


def geometry_model(with_evidence=True):
    ev = (lambda text: text) if with_evidence else (lambda text: None)
    return {"kind": "geometry", "word_problem": None, "geometry": {
        "points": ["A", "B", "C"], "facts": [
            fact("t", "triangle", ["A", "B", "C"], evidence=ev("ABC üçgeninde")),
            fact("r", "right_angle", ["A", "B", "C"], evidence=ev("B açısı diktir")),
            fact("ab", "segment_length", ["A", "B"], "3", ev("AB = 3 cm")),
            fact("bc", "segment_length", ["B", "C"], "4", ev("BC = 4 cm"))],
        "constructions": [], "target": {"kind": "length", "points": ["A", "C"]}, "schematic": True}}


def lesson_text(final: str, model=None, steps=None) -> str:
    payload = lesson_payload()
    payload["content"].update(known_values=[], unknown="istenen değer", final_answer=final,
                              final_answer_expressions=[{"type": "equation", "latex": final}],
                              steps=steps or [{"id": "step_1", "type": "result", "title": "Sonuç", "explanation": "Hesaplanır.",
                                               "expressions": [], "visual_reference": None}])
    payload["content"]["mathematical_model"] = model
    return json.dumps(payload, ensure_ascii=False)


def equation_steps(*latexes, kind="transformation"):
    return [{"id": f"step_{i + 1}", "type": kind, "title": "Adım", "explanation": "Dönüştür.",
             "expressions": [{"type": "equation", "latex": latex}], "visual_reference": None} for i, latex in enumerate(latexes)]


def provider(name, texts, monkeypatch, calls):
    queue = list(texts)

    def next_text():
        calls.append(1)
        return queue.pop(0) if len(queue) > 1 else queue[0]

    if name == "openai":
        async def parse(**kwargs):
            return FakeRaw(body(text=next_text()))

        monkeypatch.setattr(lesson_module, "AsyncOpenAI",
                            lambda **kw: SimpleNamespace(responses=fake_client(parse).responses, close=AsyncMock()))
        return OpenAILessonProvider("key", "test-model", 5)
    return AnthropicLessonProvider("key", "claude-sonnet-5-5", 5,
                                   transport=httpx.MockTransport(lambda request: message(text=next_text())))


async def run(name, source, texts, monkeypatch):
    calls: list = []
    service = LessonService(provider(name, texts, monkeypatch, calls), MathAIService(), BoardPlanner())
    try:
        return await service.generate(source), len(calls)
    except VerificationContradictionError:
        return "contradiction", len(calls)


PATHS = pytest.mark.parametrize("path", ["openai", "anthropic"])


# --- §24 hizmet düzeyi uçtan uca --------------------------------------------------------------------------------

@pytest.mark.asyncio
@PATHS
async def test_wrong_geometry_answer_is_detected_corrected_once_rechecked_and_drawn(path, monkeypatch):
    source = analysis(question_text=GEO_TEXT, mathematical_expressions=[], answer_choices=[])
    result, calls = await run(path, source, [lesson_text("AC = 7", geometry_model()), lesson_text("AC = 5", geometry_model())],
                              monkeypatch)
    assert calls == 2 and result.correction_attempted
    report = result.verification.mathematics
    assert result.verification.status != "failed" and report.material_count == 0
    assert any(c.id == "geometry_answer" and c.status == "passed" for c in report.checks)
    facts = next(e for e in result.board.elements if e.type == "geometry_facts").facts
    assert all("metinde verilen" in item for item in facts)
    assert result.board.elements[-1].type == "final_answer"


@pytest.mark.asyncio
@PATHS
async def test_unresolved_geometry_contradiction_is_rejected_after_one_correction(path, monkeypatch):
    source = analysis(question_text=GEO_TEXT, mathematical_expressions=[], answer_choices=[])
    result, calls = await run(path, source, [lesson_text("AC = 7", geometry_model())], monkeypatch)
    assert result == "contradiction" and calls == 2


@pytest.mark.asyncio
@PATHS
async def test_unsupported_model_stays_unsupported_without_extra_call(path, monkeypatch):
    source = analysis(question_text=GEO_TEXT, mathematical_expressions=[], answer_choices=[])
    result, calls = await run(path, source, [lesson_text("AC = 7", geometry_model(with_evidence=False))], monkeypatch)
    assert calls == 1 and not result.correction_attempted
    assert result.verification.status != "verified" and not result.verification.final_answer_verified
    report = result.verification.mathematics
    assert report.model_status == "rejected" and report.material_count == 0
    facts = next(e for e in result.board.elements if e.type == "geometry_facts").facts
    assert all("kullanılmadı" in item for item in facts)  # reddedilen olgu tahtada "verilen" görünmez
    assert result.board.elements[-1].mark == "warning"


@pytest.mark.asyncio
@PATHS
async def test_valid_lesson_makes_exactly_one_provider_call(path, monkeypatch):
    source = analysis(question_text="x^2 = 4 denkleminin çözüm kümesi nedir?", mathematical_expressions=["x^2 = 4"],
                      answer_choices=[])
    steps = [{"id": "step_1", "type": "case", "title": "İki durum", "explanation": "Karekök al.",
              "expressions": [{"type": "equation", "latex": "x = 2"}, {"type": "equation", "latex": "x = -2"}],
              "visual_reference": None}]
    text = lesson_text("x = 2", steps=steps)
    payload = json.loads(text)
    payload["content"]["final_answer"] = "x = -2 veya x = 2"
    payload["content"]["final_answer_expressions"] = [{"type": "equation", "latex": "x = -2"}, {"type": "equation", "latex": "x = 2"}]
    result, calls = await run(path, source, [json.dumps(payload, ensure_ascii=False)], monkeypatch)
    assert calls == 1 and not result.correction_attempted
    assert result.verification.status == "verified" and result.verification.mathematics.material_count == 0


@pytest.mark.asyncio
@PATHS
async def test_missing_root_is_material_and_feedback_is_structured(path, monkeypatch):
    source = analysis(question_text="x^2 = 4 denkleminin çözüm kümesi nedir?", mathematical_expressions=["x^2 = 4"],
                      answer_choices=[])
    wrong = lesson_text("x = 2", steps=equation_steps("x = 2"))
    result, calls = await run(path, source, [wrong], monkeypatch)
    assert result == "contradiction" and calls == 2
    verification = MathAIService().verify(plan("x^2 = 4", "x = 2", [Step(id="step_1", type="result", title="t",
                                                                          explanation="e", expressions=[])]))
    assert verification.status == "failed" and not verification.final_answer_verified
    feedback = correction_feedback(verification)
    assert "missing_solutions" in feedback and len(feedback) <= 1200


# --- §13–14 çelişki sınıfları ve hata yayılımı -----------------------------------------------------------------

def test_specialist_crash_is_reported_as_unavailable_not_hidden(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("beklenmedik")

    monkeypatch.setattr(specialist, "analyze", boom)
    result = MathAIService().verify(plan())
    assert result.mathematics is not None and result.mathematics.specialist_status == "unavailable"
    assert any("çalıştırılamadı" in warning for warning in result.warnings)
    assert result.status == "verified"  # çekirdek kanıtı ayrıdır; eksik denetim açıkça işaretlidir


def test_material_failure_survives_check_truncation():
    steps = [Step(id=f"step_{i}", type="transformation", title="t", explanation="e",
                  expressions=[Expression(type="equation", latex="3x = 12")]) for i in range(1, 80)]
    report = MathAIService().verify(plan(final="x = 5", steps=steps)).mathematics
    assert len(report.checks) == specialist.MAX_CHECKS
    assert report.material_count >= 1 and report.checks[0].material
    assert any(c.reason == "extraneous_or_wrong_claim" for c in report.material_failures)


def test_noncontradictory_partial_checks_never_become_material():
    check = MathCheck(id="model_fidelity", area="model_fidelity", status="partially_checked", reason="value_meaning_unanchored")
    assert not check.material
    resolved = MathAIService().verify(plan())
    assert correction_resolved(resolved)


def test_word_answer_mismatch_without_bound_target_is_not_material():
    p = plan("x = 1", "a = 30", [Step(id="step_1", type="result", title="t", explanation="e", expressions=[])])
    p.source_analysis.question_text = "Ali ile babasının yaşları toplamı 48'dir ve baba Ali'nin 3 katı yaşındadır. Ali kaç yaşındadır?"
    p.source_analysis.mathematical_expressions = []
    from apps.api.app.features.education.mathematics import MathematicalModel

    p.content.mathematical_model = MathematicalModel.model_validate({"kind": "word_problem", "word_problem": {
        "problem_type": "age", "quantities": [{"symbol": "a", "name_tr": "Ali"}, {"symbol": "b", "name_tr": "Baba"},
                                              {"symbol": "s", "name_tr": "Toplam", "value": "48"}],
        "relations": ["a + b = s", "b = 3a"], "objective": "a"}})
    result = MathAIService().verify(p)
    report = result.mathematics
    assert any(c.reason == "model_answer_disagreement" and c.status == "failed" for c in report.checks)
    assert report.material_count == 0 and result.status != "verified"


# --- §4–6 tanım kümesi, küme bütünlüğü, dönüşümler -------------------------------------------------------------

@pytest.mark.parametrize(("latex", "excluded"), [
    (r"\frac{x}{x} = 1", "0"), (r"0 \cdot \frac{1}{x} = 0", "0"), (r"x^{-1} \cdot x = 1", "0"), ("x^0 = 1", "0")])
def test_simplification_never_widens_the_original_domain(latex, excluded):
    solved = sets.solve_equation(latex, "x")
    assert solved.status == "exact" and solved.view.kind == "intervals"
    assert excluded in solved.view.exclusions and solved.view.conditions


def test_complex_domain_has_no_real_restrictions():
    solved = sets.solve_equation(r"\frac{1}{x} = x", "x", domain="complex")
    assert solved.view.kind == "finite" and set(solved.view.elements) == {"-1", "1"}


def test_large_solution_lists_are_marked_truncated_not_silently_cut():
    import sympy as sp

    view = sets.view(sp.FiniteSet(*range(40)))
    assert view.truncated and not view.exact and len(view.elements) == sets.MAX_ELEMENTS


def test_domain_conditions_are_collected_from_the_unsimplified_tree():
    kinds = {(c.kind, c.latex) for c in domain.conditions_of(r"\frac{\sqrt{x}}{\ln(x - 1)} + \tan(x)")}
    assert ("nonnegative", "x") in kinds and any(k == "positive" for k, _ in kinds)
    assert any(k == "nonzero" for k, _ in kinds)


def test_extraneous_elimination_after_squaring_is_not_a_loss():
    verdict = transforms.compare("x^2 - x - 2 = 0", "x = 2", r"\sqrt{x + 2} = x", "x")
    assert verdict.relation == "eliminates"
    assert transforms.compare("x^2 = x", "x = 1", "x^2 = x", "x").relation == "loses"


@pytest.mark.parametrize(("source", "branches", "verdict"), [
    ("|x - 2| = 4", ["x - 2 = 4", "x - 2 = -4"], "verified"),
    ("|x - 2| = 4", ["x - 2 = 4"], "failed"),
])
def test_case_analysis_is_judged_by_branch_union(source, branches, verdict):
    steps = [Step(id=f"step_{i + 1}", type="case", title="Durum", explanation="e",
                  expressions=[Expression(type="equation", latex=latex)]) for i, latex in enumerate(branches)]
    final = "x = -2 veya x = 6" if verdict == "verified" else "x = 6"
    assert MathAIService().verify(plan(source, final, steps)).status == verdict


# --- §15 ve §18 fonksiyonlar ve grafik --------------------------------------------------------------------------

def test_function_evaluation_target_is_not_read_as_a_product():
    p = plan("x = 1", "f(3) = 8", [Step(id="step_1", type="result", title="t", explanation="e", expressions=[])])
    p.source_analysis.question_text = "f(x) = 2x + 1 ise f(3) kaçtır?"
    p.source_analysis.mathematical_expressions = ["f(x) = 2x + 1", "f(3)"]
    report = MathAIService().verify(p).mathematics
    assert any(c.reason == "function_value_mismatch" and c.material for c in report.checks)
    p.content.final_answer_expressions = [Expression(type="equation", latex="f(3) = 7")]
    assert any(c.reason == "answer_matches_target" for c in MathAIService().verify(p).mathematics.checks)


@pytest.mark.parametrize(("latex", "holes", "asymptotes", "first_closed"), [
    ("1/x", [], [0.0], True), ("(x^2-1)/(x-1)", [(1.0, 2.0)], [], True), ("sqrt(x)", [], [], True), ("ln(x)", [], [0.0], False)])
def test_discontinuities_are_classified_for_rendering(latex, holes, asymptotes, first_closed):
    facts = functions.analyze(latex)
    assert list(facts.holes) == holes and list(facts.asymptotes) == asymptotes
    assert facts.segments[0].start_closed is first_closed


def test_board_graph_uses_verified_segments_and_excludes_undefined_points():
    p = plan("y = \\frac{x^2 - 1}{x - 1}", "y = x + 1",
             [Step(id="step_1", type="result", title="t", explanation="e", expressions=[])])
    verification = MathAIService().verify(p)
    board = BoardPlanner().create(p, verification)
    graph = next(e for e in board.elements if e.type == "graph").graph
    assert graph.holes == [(1.0, 2.0)] and graph.segments
    assert all(abs(x - 1.0) > 1e-9 for x, _ in graph.sample_points)


def test_rational_equation_does_not_break_the_specialist_through_alternatives():
    from apps.api.app.features.mathematics import alternatives

    assert alternatives.quadratic(r"\frac{x^2 - 4}{x - 2} = 4") == []  # payda temizlenip tanım kümesi kaybedilmez
    steps = [Step(id="step_1", type="transformation", title="t", explanation="e",
                  expressions=[Expression(type="equation", latex="x + 2 = 4")])]
    report = MathAIService().verify(plan(r"\frac{x^2 - 4}{x - 2} = 4", "x = 2", steps)).mathematics
    assert report.specialist_status == "completed"
    assert any(c.reason == "extraneous_or_wrong_claim" and c.material for c in report.checks)


@pytest.mark.parametrize(("answer", "reason"), [(r"\frac{3}{2}", "answer_matches_target"), ("2", "constant_value_mismatch")])
def test_variable_free_trig_expression_is_computed_exactly(answer, reason):
    source = analysis(question_text=r"\sin(\frac{\pi}{6}) + \cos(0) işleminin sonucu kaçtır?",
                      mathematical_expressions=[r"\sin(\frac{\pi}{6}) + \cos(0)"], answer_choices=[])
    p = plan("x = 1", "x = 1", [Step(id="step_1", type="result", title="t", explanation="e", expressions=[])])
    p = p.model_copy(update={"source_analysis": source})
    p.content.final_answer_expressions = [Expression(type="expression", latex=answer)]
    checks = MathAIService().verify(p).mathematics.checks
    assert any(c.id == "constant_value_answer" and c.reason == reason for c in checks)
