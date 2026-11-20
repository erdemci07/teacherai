"""TA-003 soru bütünlüğü davranış testleri. Sağlayıcı çağrısı yapılmaz; sahte istemci ve fikstür kullanılır."""

import copy
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from apps.api.app.core.gateway import (
    ProviderCallBudgetExhausted,
    begin_accounting,
    end_accounting,
    parse_response,
)
from apps.api.app.core.settings import Settings
from apps.api.app.core.usage import UsageTracker
from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.education.lesson import LessonPlanV2
from apps.api.app.features.education.math_adapter import (
    validated_math_lesson,
    with_integrity,
)
from apps.api.app.features.education.source import IntegrityReport
from apps.api.app.features.integrity.engine import (
    EvaluationState,
    apply_clarification,
    evaluate,
)
from apps.api.app.features.integrity.expression import (
    canonical,
    equivalent_readings,
    exact_value,
    parse,
    same_structure,
    shape,
    to_latex,
)
from apps.api.app.features.integrity.language import detect_intent, parse_choices
from apps.api.app.features.lessons.context import build_lesson_generation_context
from apps.api.app.features.lessons.service import LessonService
from apps.api.app.features.mathai.parser import MathParseError, equation, expression
from apps.api.app.features.mathai.service import MathAIService
from apps.api.app.features.memory.schemas import TeachingContext
from apps.api.app.features.vision.schemas import VisionAnalysis, VisionProviderAnalysis
from apps.api.app.main import create_app
from apps.api.tests.client import authenticated_client
from apps.api.tests.test_lesson_pipeline import AlgebraLessonProvider
from fastapi.testclient import TestClient
from scripts import integrity_matrix

FIXTURES = json.loads((Path(__file__).parent / "fixtures/integrity/scenarios.json").read_text(encoding="utf-8"))


def wire(**overrides) -> VisionProviderAnalysis:
    return VisionProviderAnalysis.model_validate(integrity_matrix._merge(FIXTURES["base"], overrides))


def analysis(request_id="analysis_1", recheck_limit=0, **overrides) -> VisionAnalysis:
    source = wire(**overrides)
    report = evaluate(source, EvaluationState(recheck_limit=recheck_limit))
    return VisionAnalysis(**source.model_dump(), request_id=request_id, provider="fixture", model="fixture",
                          processing_time_ms=1, integrity=report)


SIGN = {"source": {"uncertainties": [{"category": "sign", "element": "expression:0", "recognized": "+ 7",
                                      "alternatives": ["- 7"], "affects_answer": True, "region_index": None}]}}


# --------------------------------------------------------------------------- yapı ve ayrıştırma


@pytest.mark.parametrize(("left", "right"), [
    (r"\sqrt{5+\sqrt{9}}", r"\sqrt{5}+\sqrt{9}"),
    ("(2+4)/3", "2+4/3"),
    ("-(2^2)", "(-2)^2"),
    (r"\sin(x^2)", r"(\sin(x))^2"),
    ("2(x+1)", "2x+1"),
    ("|x-2|", "|x|-2"),
])
def test_distinct_source_structures_stay_distinct(left, right):
    a, b = parse(left), parse(right)
    assert a.parsed and b.parsed
    assert not same_structure(a.tree, b.tree)
    assert canonical(a.tree) != canonical(b.tree)


@pytest.mark.parametrize(("left", "right"), [
    ("(2+4)/3", r"\frac{2+4}{3}"), ("-2^2", "-(2^2)"), (r"\sin^2 x", r"(\sin(x))^2"), ("3·4−2", r"3\cdot 4-2"),
    (r"2\frac{1}{3}", "2+1/3"), ("√(5+√9)", r"\sqrt{5+\sqrt{9}}"), ("x²", "x^{2}"), ("0,5", "0.5"),
])
def test_equivalent_notations_share_structure(left, right):
    assert same_structure(parse(left).tree, parse(right).tree)


@pytest.mark.parametrize("source", [
    r"\sqrt{5+\sqrt{9}}", r"\frac{\frac{1}{2}}{3}", "-2^2+(-2)^2=x", r"\sin^2 x+\cos(x^2)", r"\left|x-3\right|\le 5",
    r"x = -2 \pm \sqrt{3}", r"2\frac{1}{3}", "3,5x=7", r"\sqrt[3]{-8}", "x_1+x_{2}=10", r"\log_{2}(x)^2", "a/(b c)",
    r"2\frac{x}{3}", "1<x<=4",
])
def test_display_and_canonical_round_trip_preserve_structure(source):
    result = parse(source)
    assert result.parsed, result.reason
    for rendered in (to_latex(result.tree), canonical(result.tree)):
        again = parse(rendered)
        assert again.parsed and shape(again.tree) == shape(result.tree), rendered


def test_display_keeps_fraction_and_radical_notation():
    assert to_latex(parse(r"\frac{2+4}{3}").tree) == r"\frac{2 + 4}{3}"
    assert to_latex(parse(r"\sqrt{8}").tree) == r"\sqrt{8}"
    assert to_latex(parse("3,5").tree) == "3{,}5"


@pytest.mark.parametrize(("source", "status", "reason"), [
    (r"\frac{1}{}", "invalid", "fraction_operand_missing"), ("(2+3", "invalid", "unbalanced_delimiter"),
    (r"\sqrt{}", "invalid", "radicand_missing"), ("2 3", "invalid", "adjacent_numbers"), ("2+", "invalid", "operand_missing"),
    (r"\int x dx", "unsupported", "latex_command"), ("30°", "unsupported", "unsupported_symbol"), ("AB=5", "unsupported", "multi_letter_identifier"),
    ("x!", "unsupported", "factorial"), ("(1, 2)", "unsupported", "list_or_tuple"),
    ("__import__('os').system('x')", "unsupported", None), ("eval(1)", "unsupported", "multi_letter_identifier"),
])
def test_invalid_and_unsupported_are_distinct_and_never_executed(source, status, reason):
    result = parse(source)
    assert result.status == status and result.tree is None
    assert reason is None or result.reason == reason


def test_parser_budgets_are_enforced_without_recursion_errors():
    assert parse("(" * 40 + "x" + ")" * 40).reason == "depth_budget"
    assert parse("x" + "+x" * 200).reason in {"token_budget", "length_budget"}
    assert parse("1" * 16).reason == "numeric_literal_budget"
    assert parse("a+b+c+d+e+f+g+h+k").reason == "symbol_budget"
    assert parse("x" * 401).reason == "length_budget"


def test_contextual_decimal_comma_and_ambiguity():
    assert exact_value(parse("0,125").tree) == exact_value(parse("0.125").tree)
    ambiguous = parse("1,250+1")
    assert ambiguous.ambiguity is not None and ambiguous.ambiguity.readings == ("1.250", "1250")
    assert parse("(2,3)").status == "unsupported"


def test_equivalent_readings_require_same_structure_or_exact_value():
    assert equivalent_readings(parse("2/4"), parse(r"\frac{2}{4}"))
    assert equivalent_readings(parse(r"\sqrt{16}"), parse("4"))
    assert not equivalent_readings(parse(r"\sqrt{5}+9"), parse(r"\sqrt{5+9}"))
    assert not equivalent_readings(parse("x+1"), parse("1+x"))


def test_mathai_uses_balanced_parser_with_existing_compute_budgets():
    assert equation(r"\sqrt{5+\sqrt{9}} = x").rhs.name == "x"
    assert expression(r"\frac{1}{1+\frac{1}{2}}").equals(expression("2/3"))
    for unsafe in ("x^11", "a+b+c+d+e", "__import__('os')", "1234567890123"):
        with pytest.raises(MathParseError):
            expression(unsafe)


# --------------------------------------------------------------------------- amaç ve seçenekler


@pytest.mark.parametrize(("text", "kind", "markers"), [
    ("Aşağıdakilerden hangisi YANLIŞTIR?", "identify_false", {"yanlıştır"}),
    ("Buna göre aşağıdakilerden hangisi doğru değildir?", "identify_false", {"doğru değildir"}),
    ("2x + 1 aşağıdakilerden hangisi olamaz?", "determine_impossible", {"olamaz"}),
    ("x·y en az kaçtır?", "find_minimum", {"en az"}),
    ("Kaç tane farklı çözüm vardır? Kaç tanedir?", "count", {"kaç tanedir", "farklı"}),
])
def test_turkish_intent_markers_and_negation_are_preserved(text, kind, markers):
    evidence = detect_intent(text, [])
    assert evidence.intent.kind == kind
    assert markers <= {item.marker for item in evidence.intent.markers}


def test_choice_labels_keep_their_printed_content_and_are_never_relabelled():
    evidence = parse_choices(["B) 8", "A) 4", "C) 12", "D) 16"])
    assert [(item.label, item.content, item.order) for item in evidence.choices] == [("B", "8", 0), ("A", "4", 1), ("C", "12", 2), ("D", "16", 3)]
    unlabeled = parse_choices(["4", "8"])
    assert all(item.label is None and item.label_origin == "none" for item in unlabeled.choices)
    combination = parse_choices(["A) Yalnız I", "B) I ve III", "C) I, II ve III"]).choices
    assert [item.statement_refs for item in combination] == [["I"], ["I", "III"], ["I", "II", "III"]]


def test_duplicate_values_are_not_treated_as_extraction_errors():
    evidence = parse_choices(["A) 1/2", "B) 0,5", "C) 2", "D) 3"])
    assert evidence.equivalent_values and not evidence.duplicate_labels
    report = evaluate(wire(question_text="2x = 1 ise x kaçtır?", mathematical_expressions=["2x = 1"], answer_choices=["A) 1/2", "B) 0,5", "C) 2", "D) 3"]))
    assert report.solvable and not report.pending()


# --------------------------------------------------------------------------- karar zekâsı


def test_behavior_matrix_meets_fixture_acceptance():
    result = integrity_matrix.evaluate(FIXTURES)
    assert integrity_matrix.failures(result) == []
    metrics = result["metrics"]
    assert metrics["false_blocking"] == metrics["unresolved_critical_allowed"] == metrics["wrong_automatic_source_correction"] == 0
    assert metrics["max_calls_per_scenario"] <= 2 and not metrics["wrong_choice_reconciliation"]


def test_confidence_alone_never_decides():
    low = evaluate(wire(confidence=0.05))
    high = evaluate(wire(confidence=1.0, **SIGN))
    assert low.decision == "ready" and high.decision == "clarification_required"


def test_image_advisories_are_evidence_not_verdicts():
    report = evaluate(wire(), EvaluationState(image=("possible_blur", "underexposed", "low_contrast")))
    assert report.decision == "ready" and report.image == ["possible_blur", "underexposed", "low_contrast"]


def test_provider_cannot_mark_a_question_ready_with_pending_material_uncertainty():
    report = evaluate(wire(**SIGN))
    with pytest.raises(ValueError):
        IntegrityReport.model_validate(report.model_dump() | {"decision": "ready"})


# --------------------------------------------------------------------------- açıklama ve revizyon


def test_student_clarification_creates_a_new_revision_without_rewriting_history():
    current = analysis(**SIGN)
    assert current.integrity.decision == "clarification_required" and current.integrity.recovery == "choose_alternative"
    pending = current.integrity.pending()[0]
    updated = apply_clarification(current, pending.id, pending.alternatives[0].id)
    assert updated.revision == 2 and updated.integrity.revision == 2
    assert updated.integrity.revision_origin == "student_clarification"
    assert updated.mathematical_expressions == ["3x - 7 = 19"] and updated.question_text.startswith("3x - 7 = 19")
    assert updated.integrity.solvable
    correction = updated.integrity.corrections[0]
    assert (correction.original, correction.corrected, correction.from_revision) == ("+ 7", "- 7", 1)
    assert updated.integrity.uncertainties[0].resolution == "resolved_by_student"
    rejected = apply_clarification(current, pending.id, "none")
    assert rejected.integrity.decision == "retake_required" and rejected.integrity.recovery == "retake"


def make_app():
    app = create_app()
    provider = AlgebraLessonProvider()
    app.state.container = replace(app.state.container, lesson_service=LessonService(provider, MathAIService(), BoardPlanner()))
    return app, provider


def test_clarification_api_is_owned_revision_checked_and_idempotent():
    app, provider = make_app()
    students = app.state.container.student_service
    user = AuthenticatedUser(uid="student-a")
    current = analysis(request_id="analysis_clarify", **SIGN)
    students.save_analysis(user, current)
    path = "/api/v1/vision/analyses/analysis_clarify/clarification"
    pending = current.integrity.pending()[0]
    choice = {"expected_revision": 1, "uncertainty_id": pending.id, "selection": "recognized"}
    with authenticated_client(app) as client:
        blocked = client.post("/api/v1/lessons/generate", json={"analysis_id": "analysis_clarify"})
        assert blocked.status_code == 409 and blocked.json()["error"] == "question_clarification_required"
        assert provider.analysis_payloads == []
        assert client.post(path, json=choice, headers={"Authorization": "Bearer student-b"}).status_code == 404
        assert client.post(path, json=choice | {"expected_revision": 2}).json()["error"] == "stale_question_revision"
        assert client.post(path, json=choice | {"selection": "u9_9"}).json()["error"] == "invalid_clarification"
        assert client.post(path, json=choice | {"verified": True}).status_code == 422
        first = client.post(path, json=choice)
        assert first.status_code == 200 and first.headers["cache-control"] == "private, no-store"
        assert first.json()["data"]["revision"] == 2 and first.json()["data"]["integrity"]["decision"] == "ready_with_noncritical_uncertainty"
        retry = client.post(path, json=choice)
        assert retry.status_code == 200 and retry.json()["data"]["revision"] == 2
        conflicting = client.post(path, json=choice | {"selection": pending.alternatives[0].id})
        assert conflicting.status_code == 409 and conflicting.json()["error"] == "stale_question_revision"
        stale = client.post("/api/v1/lessons/generate", json={"analysis_id": "analysis_clarify", "expected_revision": 1})
        assert stale.status_code == 409 and stale.json()["error"] == "stale_question_revision"
        assert provider.analysis_payloads == []
        generated = client.post("/api/v1/lessons/generate", json={"analysis_id": "analysis_clarify", "expected_revision": 2})
        assert generated.status_code == 200, generated.text
        assert len(provider.analysis_payloads) == 1
        lesson = generated.json()["data"]["lesson"]
        assert lesson["source_analysis"]["revision"] == 2
        stored = students.owned(user, lesson["lesson_plan_id"])
        assert stored.lesson_data["lesson"]["source_analysis"]["integrity"]["revision"] == 2
        view = client.get(f"/api/v1/lessons/{lesson['lesson_plan_id']}/v2").json()["data"]["lesson"]
        assert view["schema"]["version"] == "2.1.0" and view["source_revision"] == 2
        assert view["verification"]["source_consistency"] == "partially_checked"
        assert view["verification"]["scientific"] != "passed"
    with TestClient(app) as anonymous:
        assert anonymous.post(path, json=choice).status_code == 401


def test_legacy_analysis_without_integrity_stays_solvable_and_readable():
    legacy = VisionAnalysis.model_validate_json(
        analysis(ocr_uncertainties=["Kök işaretinin sonu biraz silik."]).model_dump_json(exclude={"integrity", "revision", "source"})
    )
    assert legacy.integrity is None and legacy.revision == 1
    upgraded = with_integrity(legacy)
    assert upgraded.integrity.revision_origin == "legacy" and upgraded.integrity.solvable
    assert upgraded.integrity.uncertainties[0].origin == "legacy_text" and upgraded.integrity.uncertainties[0].impact == "noncritical"


@pytest.mark.asyncio
async def test_unsupported_subject_is_not_routed_to_mathai_or_provider():
    provider = AlgebraLessonProvider()

    class NoMath:
        def __getattr__(self, name):
            raise AssertionError("MathAI çağrılmamalı")

    from apps.api.app.features.education.math_adapter import UnsupportedSubjectError

    with pytest.raises(UnsupportedSubjectError):
        await LessonService(provider, NoMath(), BoardPlanner()).generate(analysis(subject="Biyoloji"))
    assert provider.analysis_payloads == []


# --------------------------------------------------------------------------- maliyet sınırı


def _fake_client(calls):
    async def parse(**kwargs):
        calls.append(kwargs)
        body = {"id": "r", "model": "m", "status": "completed",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": '{"readings": []}'}]}],
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}
        return SimpleNamespace(http_response=SimpleNamespace(json=lambda: body), request_id="req")

    return SimpleNamespace(responses=SimpleNamespace(with_raw_response=SimpleNamespace(parse=parse)))


@pytest.mark.asyncio
async def test_call_budget_stops_before_reservation_and_provider():
    from apps.api.app.features.vision.schemas import RecheckResponse

    settings = Settings(environment="test")
    tracker = UsageTracker(settings)
    calls: list = []
    token = begin_accounting("req", settings, tracker, "budget-user", max_calls=1)
    try:
        await parse_response(_fake_client(calls), "vision", model="gpt-4.1-mini", input=[], text_format=RecheckResponse)
        with pytest.raises(ProviderCallBudgetExhausted):
            await parse_response(_fake_client(calls), "vision", purpose="vision.recheck", model="gpt-4.1-mini", input=[], text_format=RecheckResponse)
    finally:
        end_accounting(token)
    assert len(calls) == 1
    day = next(iter(tracker.globals))
    assert tracker.globals[day]["provider_calls"] == 1


def test_call_budgets_are_bounded_and_configurable():
    settings = Settings(environment="test")
    assert [settings.provider_call_budget(op) for op in ("analyze", "generate", "interact", "understood")] == [2, 3, 1, None]
    assert Settings(environment="test", vision_max_rechecks=0).provider_call_budget("analyze") == 1
    with pytest.raises(ValueError):
        Settings(environment="test", vision_max_rechecks=5)


def test_admission_applies_the_logical_request_budget(monkeypatch):
    from apps.api.app.core import admission

    seen = []
    original = admission.begin_accounting

    def capture(*args, **kwargs):
        seen.append(kwargs.get("max_calls"))
        return original(*args, **kwargs)

    monkeypatch.setattr(admission, "begin_accounting", capture)
    app, _ = make_app()
    students = app.state.container.student_service
    students.save_analysis(AuthenticatedUser(uid="student-a"), analysis(request_id="analysis_budget"))
    with authenticated_client(app) as client:
        assert client.post("/api/v1/lessons/generate", json={"analysis_id": "analysis_budget"}).status_code == 200
    assert seen == [3]


# --------------------------------------------------------------------------- bağlam koruma ve bağlam tutarlılığı


def test_solve_first_hides_choices_only_when_safe():
    hidden = build_lesson_generation_context(analysis()).payload["problem"]
    assert "answer_choices" not in hidden and hidden["answer_choice_count"] == 4
    assert hidden["question_integrity"]["answer_strategy"] == "solve_first_hidden"
    dependent = analysis(question_text="Aşağıdakilerden hangisi yanlıştır?", mathematical_expressions=[],
                         answer_choices=["A) 2 asaldır.", "B) 4 asaldır.", "C) 6 çifttir.", "D) 9 tektir."])
    kept = build_lesson_generation_context(dependent).payload["problem"]
    assert kept["answer_choices"] == dependent.answer_choices and kept["question_integrity"]["answer_strategy"] == "choice_dependent"
    assert "yanlıştır" in kept["question_integrity"]["intent_markers"]
    two_unknowns = analysis(question_text="x + y = 10 ise x·y en çok kaçtır?", mathematical_expressions=["x + y = 10"])
    assert build_lesson_generation_context(two_unknowns).payload["problem"]["question_integrity"]["answer_strategy"] == "derive_then_select"


def test_answer_critical_content_is_never_sliced():
    long_expression = "x = " + " + ".join(["1"] * 160)
    choices = [f"{chr(65 + i)}) {i}" for i in range(10)]
    statements = ["I. 4 bir çift sayıdır.", "II. 9 bir asal sayıdır."]
    item = analysis(question_text=("Uzun soru " * 500) + "kaçtır?", mathematical_expressions=[long_expression], answer_choices=choices,
                    source={"statements": statements})
    for level in ("normal", "emergency"):
        problem = build_lesson_generation_context(item, level=level).payload["problem"]
        assert problem["mathematical_expressions"] == [long_expression]
        assert problem.get("answer_choices", choices) == choices
        assert problem["statements"] == statements
        assert problem["question_text"].endswith("kaçtır?") and "..." not in problem["question_text"]


def test_confirmed_corrections_and_revision_reach_lesson_context():
    current = analysis(**SIGN)
    pending = current.integrity.pending()[0]
    updated = apply_clarification(current, pending.id, pending.alternatives[0].id)
    payload = build_lesson_generation_context(updated).payload["problem"]["question_integrity"]
    assert payload["source_revision"] == 2
    assert payload["confirmed_corrections"] == [{"element": "expression:0", "original": "+ 7", "corrected": "- 7"}]


@pytest.mark.asyncio
async def test_profile_exam_and_source_exam_are_kept_apart():
    provider = AlgebraLessonProvider()
    learner = TeachingContext(exam_goal="AYT", topic_experience=1, recurring_mistakes=[], support_need="normal",
                              preferred_explanation_depth="normal", recent_topics=[])
    result = await LessonService(provider, MathAIService(), BoardPlanner()).generate(analysis(exam_context="TYT"), learner)
    context = result.education_context
    assert (context.exam.value, context.exam.origin) == ("AYT", "profile")
    assert (context.source_exam.value, context.source_exam.origin) == ("TYT", "inferred")
    view = validated_math_lesson(result.lesson, result.verification, result.education_context)
    assert view.context.exam.value == "AYT" and view.context.source_exam.value == "TYT"
    historical = validated_math_lesson(result.lesson, result.verification)
    assert historical.context.exam is None


def test_v2_source_linkage_is_versioned_and_cannot_reference_unsolvable_questions():
    fixture = json.loads((Path(__file__).parent / "fixtures/education/synthetic.json").read_text(encoding="utf-8"))[0]["lesson"]
    assert LessonPlanV2.model_validate(fixture).schema_identity.version == "2.0.0"
    upgraded = copy.deepcopy(fixture) | {"schema": {"name": "teacherai.lesson_plan", "version": "2.1.0"}, "source_revision": 3, "source_decision": "ready"}
    assert LessonPlanV2.model_validate(upgraded).source_revision == 3
    with pytest.raises(ValueError):
        LessonPlanV2.model_validate(upgraded | {"source_decision": "clarification_required"})
