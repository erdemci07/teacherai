"""TA-004 istenen hedef, adım/blok doğrulaması ve v2 projeksiyonu. Sağlayıcı çağrısı yoktur; sahte sağlayıcı kullanılır."""

from dataclasses import replace

import pytest
from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.education.lesson import BlockCheck, LessonPlanV2
from apps.api.app.features.education.math_adapter import validated_math_lesson, with_integrity
from apps.api.app.features.education.presentation import LessonView, plan_panels
from apps.api.app.features.education.reasoning import AnswerTarget, NarrationSegment, TargetResolution
from apps.api.app.features.integrity.engine import EvaluationState, evaluate
from apps.api.app.features.lessons.context import build_lesson_generation_context
from apps.api.app.features.lessons.provider import LessonProviderResult
from apps.api.app.features.lessons.schemas import Expression, LessonContent, LessonDraft, LessonPlan, Step
from apps.api.app.features.lessons.service import GeneratedLesson, LessonService
from apps.api.app.features.mathai.service import MathAIService
from apps.api.app.features.reasoning.target import detect_target
from apps.api.app.features.vision.schemas import VisionAnalysis, VisualElements
from apps.api.app.main import create_app
from apps.api.tests.client import authenticated_client
from apps.api.tests.test_mathai import choice_plan
from pydantic import ValidationError


def source(question, expressions, choices=(), request_id="analysis_ta004"):
    raw = VisionAnalysis(
        request_id=request_id, image_status="valid_math_question", is_valid_question=True, rejection_reason=None,
        subject="Matematik", exam_context=None, topic="Cebir", subtopic=None, question_type="multiple_choice" if choices else "open",
        language="tr", difficulty="easy", question_text=question, mathematical_expressions=list(expressions),
        answer_choices=list(choices), visual_elements=VisualElements(has_diagram=False, has_graph=False, has_table=False,
                                                                     has_geometry_figure=False, description=None),
        ocr_uncertainties=[], confidence=0.9, provider="fixture", model="fixture", processing_time_ms=1,
    )
    return raw.model_copy(update={"integrity": evaluate(raw, EvaluationState())})


def content(final, finals, steps=()):
    built = [Step(id=f"step_{i}", type=kind, title=f"Adım {i}", explanation="Açıklama.",
                  expressions=[Expression(type=etype, latex=latex) for etype, latex in items])
             for i, (kind, items) in enumerate(steps, start=1)] or [
        Step(id="step_1", type="result", title="Sonuç", explanation="Sonucu yaz.", expressions=[])]
    return LessonContent(question_understanding="Soruyu anla.", strategy="Hesapla.", strategy_id="strategy_compute", steps=built,
                         final_answer=final, final_answer_expressions=[Expression(type="equation", latex=x) for x in finals],
                         takeaway="İstenen hedefe dikkat et.")


def plan(analysis, lesson_content):
    return LessonPlan(lesson_plan_id="lesson_ta004", source_analysis=analysis, learning_objectives=["hedef"],
                      concept_id="concept_target", content=lesson_content, provider="mock", model="mock", lesson_generation_ms=1)


X3 = source("x = 3 olduğuna göre x + 2 kaçtır?", ["x = 3", "x + 2"], ["A) 3", "B) 4", "C) 5", "D) 6"])


# --------------------------------------------------------------------------- hedef tespiti


@pytest.mark.parametrize(("question", "expressions", "kind", "expression"), [
    ("x = 3 olduğuna göre x + 2 kaçtır?", ["x = 3", "x + 2"], "sum", "x + 2"),
    ("x = 4 ise x^2 kaçtır?", ["x = 4", "x^2"], "expression_value", "x^2"),
    ("x² - 5x + 6 = 0 denkleminin kökleri toplamı kaçtır?", ["x^2 - 5x + 6 = 0"], "root_sum", None),
    ("x² - 5x + 6 = 0 denkleminin köklerinin çarpımı kaçtır?", ["x^2 - 5x + 6 = 0"], "root_product", None),
    ("x² = 9 denkleminin kaç tane gerçel çözümü vardır?", ["x^2 = 9"], "solution_count", None),
    ("2x - 3 < 7 olduğuna göre x'in alabileceği en büyük tam sayı değeri kaçtır?", ["2x - 3 < 7"], "maximum", None),
    ("2x = 3y olduğuna göre x/y oranı kaçtır?", ["2x = 3y", "x/y"], "ratio", "x/y"),
    ("3x + 7 = 19 denkleminde x kaçtır?", ["3x + 7 = 19"], "variable_value", None),
    ("|x - 3| = 5 denklemini sağlayan x değerlerinin toplamı kaçtır?", ["|x - 3| = 5"], "root_sum", None),
])
def test_target_is_what_the_question_asks(question, expressions, kind, expression):
    analysis = source(question, expressions)
    target = detect_target(question, analysis.integrity)
    assert target.kind == kind and target.origin == "deterministic"
    assert target.expression == expression


def test_asked_symbol_absent_from_model_is_unresolved_not_anchored():
    p = choice_plan("B) 2", "x = 3")
    p.source_analysis.question_text = "k kaçtır?"
    service = MathAIService()
    assert service.target(p).kind == "unresolved"
    assert service.reconcile_answer_choice(p).content.final_answer == "B) 2"
    result = service.verify(p)
    assert result.choice_match.status == "unsupported" and result.target.target.kind == "unresolved"
    assert not any(check.id == "answer_choice" and check.status == "passed" for check in result.checks)


# --------------------------------------------------------------------------- MathAI hedef doğrulaması


def test_requested_expression_not_variable_value_is_verified_and_selected():
    result = MathAIService().verify(plan(X3, content("C) 5", ["x + 2 = 5"], [("result", [("equation", "x + 2 = 5")])])))
    assert result.status == "verified" and result.final_answer_verified
    target = result.target
    assert target.target.kind == "sum" and target.given == ["x = 3"]
    assert target.intermediate == ["x = 3"] and target.requested == ["5"] and target.provider_claim == ["5"]
    assert target.outcome == "passed" and target.selected_option == "C" and target.option_origin == "independent"
    final = next(check for check in result.checks if check.id == "final_answer")
    assert final.kind == "answer_target" and "x + 2" in final.statement


def test_intermediate_answer_with_wrong_choice_is_reconciled_to_requested_target():
    """TA-003 hatası: x = 3 çözümü 'A) 3' seçeneğine bağlanıyordu. İstenen x + 2 = 5'tir."""
    wrong = plan(X3, content("A) 3", ["x = 3"]))
    fixed = MathAIService().reconcile_answer_choice(wrong)
    assert fixed.content.final_answer == "C) 5"
    result = MathAIService().verify(fixed)
    final = next(check for check in result.checks if check.id == "final_answer")
    assert final.status == "failed" and final.reason == "intermediate_not_requested" and "5" in final.detail
    assert result.status == "failed" and result.target.claim_role == "intermediate"


def test_correct_intermediate_but_wrong_final_choice_is_a_target_failure():
    result = MathAIService().verify(plan(X3, content("A) 3", ["x + 2 = 5"])))
    choice = next(check for check in result.checks if check.id == "answer_choice")
    assert choice.status == "failed" and "C" in choice.detail
    assert result.choice_match.value == "5" and result.choice_match.matched_labels == ["C"]


def test_square_root_sum_product_count_and_ratio_targets():
    service = MathAIService()
    cases = [
        (source("x = 4 ise x^2 kaçtır?", ["x = 4", "x^2"]), ["16"], "passed"),
        (source("x² - 5x + 6 = 0 denkleminin kökleri toplamı kaçtır?", ["x^2 - 5x + 6 = 0"]), ["5"], "passed"),
        (source("x² - 5x + 6 = 0 denkleminin köklerinin çarpımı kaçtır?", ["x^2 - 5x + 6 = 0"]), ["6"], "passed"),
        (source("x² = 9 denkleminin kaç tane gerçel çözümü vardır?", ["x^2 = 9"]), ["2"], "passed"),
        (source("x = 4 ise x^2 kaçtır?", ["x = 4", "x^2"]), ["8"], "failed"),
    ]
    for analysis, claim, outcome in cases:
        result = service.verify(plan(analysis, content(claim[0], claim)))
        assert result.target.outcome == outcome, (analysis.question_text, result.target)
    ratio = service.verify(plan(source("2x = 3y olduğuna göre x/y oranı kaçtır?", ["2x = 3y", "x/y"]),
                                content("3/2", [r"\frac{3}{2}"])))
    assert ratio.target.requested == ["3/2"] and ratio.target.outcome == "passed" and ratio.status == "partially_verified"


def test_repeated_root_sum_is_not_guessed():
    analysis = source("x² - 4x + 4 = 0 denkleminin kökleri toplamı kaçtır?", ["x^2 - 4x + 4 = 0"])
    result = MathAIService().verify(plan(analysis, content("4", ["4"])))
    assert result.target.outcome == "unsupported" and result.target.reason == "multiplicity_or_complex_roots"
    assert not result.final_answer_verified and result.status != "failed"


def test_maximum_permitted_integer_from_inequality_and_open_bound():
    service = MathAIService()
    integer = source("2x - 3 < 7 olduğuna göre x'in alabileceği en büyük tam sayı değeri kaçtır?", ["2x - 3 < 7"])
    assert service.verify(plan(integer, content("x = 4", ["x = 4"]))).target.requested == ["4"]
    assert service.verify(plan(integer, content("x = 5", ["x = 5"]))).status == "failed"
    real = source("x < 5 olduğuna göre x en çok kaçtır?", ["x < 5"])
    result = service.verify(plan(real, content("x = 5", ["x = 5"])))
    assert result.target.reason == "unbounded_extremum" and result.status == "unsupported"


def test_inequality_direction_error_after_negative_division_is_detected():
    analysis = source("-2x > 6 olduğuna göre x'in alabileceği en büyük tam sayı değeri kaçtır?", ["-2x > 6"])
    wrong = content("x = -4", ["x = -4"], [("transformation", [("inequality", "x > -3")])])
    result = MathAIService().verify(plan(analysis, wrong))
    step = next(check for check in result.checks if check.id == "step_1_0")
    assert step.status == "failed" and step.reason == "inequality_direction"
    right = content("x = -4", ["x = -4"], [("transformation", [("inequality", "x < -3")])])
    assert MathAIService().verify(plan(analysis, right)).target.outcome == "passed"


def test_squaring_step_is_nonreversible_and_extraneous_root_is_named():
    analysis = source(r"\sqrt{x + 2} = x denkleminin çözüm kümesi nedir?", [r"\sqrt{x + 2} = x"])
    steps = [("transformation", [("equation", "x + 2 = x^2")])]
    good = MathAIService().verify(plan(analysis, content("x = 2", ["x = 2"], steps)))
    square = next(check for check in good.checks if check.id == "step_1_0")
    assert square.status == "passed" and square.reason == "nonreversible_superset" and square.operation == "square_both_sides"
    assert good.final_answer_verified
    bad = MathAIService().verify(plan(analysis, content("x = -1, x = 2", ["x = -1", "x = 2"], steps)))
    final = next(check for check in bad.checks if check.id == "final_answer")
    assert final.status == "failed" and final.reason == "extraneous_root"


def test_division_by_variable_losing_a_root_is_detected():
    analysis = source("x² = 2x denkleminin çözüm kümesi nedir?", ["x^2 = 2x"])
    steps = [("transformation", [("equation", "x = 2")])]
    result = MathAIService().verify(plan(analysis, content("x = 2", ["x = 2"], steps)))
    assert next(check for check in result.checks if check.id == "step_1_0").reason == "solution_lost"
    assert result.status == "failed"


def test_denominator_zero_root_is_excluded_by_substitution():
    analysis = source(r"\frac{x^2 - 4}{x - 2} = 0 denkleminin kökü kaçtır?", [r"\frac{x^2 - 4}{x - 2} = 0"])
    result = MathAIService().verify(plan(analysis, content("x = -2", ["x = -2"])))
    assert result.final_answer_verified and result.target.requested == ["-2"]
    assert MathAIService().verify(plan(analysis, content("x = 2", ["x = 2"]))).status == "failed"


def test_multiple_equivalent_options_are_not_silently_chosen():
    analysis = source("x = 3 olduğuna göre x + 2 kaçtır?", ["x = 3", "x + 2"], ["A) 5", "B) 10/2", "C) 6"])
    result = MathAIService().verify(plan(analysis, content("5", ["5"])))
    assert result.choice_match.status == "multiple_equivalent" and result.target.selected_option is None
    assert MathAIService().reconcile_answer_choice(plan(analysis, content("5", ["5"]))).content.final_answer == "5"


def test_unsupported_notation_is_not_rejected_or_marked_verified():
    analysis = source(r"\int_0^1 x\,dx integralinin değeri kaçtır?", [r"\int_0^1 x\,dx"])
    result = MathAIService().verify(plan(analysis, content("1/2", ["1/2"])))
    assert result.status == "unsupported" and result.target.outcome == "unsupported"
    lesson = validated_math_lesson(plan(analysis, content("1/2", ["1/2"])), result)
    assert lesson.verification.calculation == "unsupported" and lesson.verification.target.outcome == "unsupported"


def test_target_resolution_cannot_claim_success_without_independent_value():
    target = AnswerTarget(kind="sum", origin="deterministic", expression="x + 2")
    with pytest.raises(ValidationError):
        TargetResolution(target=target, claim_role="target", outcome="passed", reason="target_value_matched")
    with pytest.raises(ValidationError):
        TargetResolution(target=AnswerTarget(kind="unresolved", origin="unresolved"), requested=["5"], claim_role="target",
                         outcome="passed", reason="target_value_matched")


# --------------------------------------------------------------------------- v2 adım ve blok kontrolleri


def _verified_lesson():
    p = plan(source("3x + 7 = 19 denkleminde x kaçtır?", ["3x + 7 = 19"]),
             content("x = 4", ["x = 4"], [("transformation", [("equation", "3x = 12")]), ("result", [("equation", "x = 4")]),
                                          ("explanation", [])]))
    return p, MathAIService().verify(p)


def test_v2_derivation_steps_carry_deterministic_operations_and_block_checks():
    p, result = _verified_lesson()
    lesson = validated_math_lesson(p, result)
    assert lesson.schema_identity.version == "2.2.0" and result.status == "verified"
    steps = [block for block in lesson.content.blocks if block.kind == "derivation_step"]
    assert [step.operation for step in steps] == ["subtract_both_sides", "isolate_variable", "explain"]
    assert [step.operation_origin for step in steps] == ["deterministic", "deterministic", "v1_step_type"]
    assert steps[0].inputs[0].kind == "source_expression" and steps[1].inputs[0].id == "step_1_0"
    checks = {check.id: check for check in lesson.verification.block_checks}
    assert checks["mathai:step_1_0"].target == "step_1_0" and checks["mathai:step_1_0"].outcome == "passed"
    assert checks["mathai:final_answer"].scope == "answer" and checks["mathai:final_answer"].dimension == "answer_target"
    assert checks["mathai:original_equation"].mapping == "unmapped" and checks["mathai:original_equation"].scope == "lesson"
    # Kontrolü olmayan açıklama adımı dürüstçe "kontrol edilmedi" görünür.
    assert checks["none:step_3"].outcome == "not_checked" and checks["none:step_3"].verifier == "none"
    assert lesson.verification.target.outcome == "passed"
    assert lesson.problem.candidate_models == ["3 * x + 7 = 19"] and lesson.problem.target.kind == "variable_value"
    LessonView(lesson=lesson, panels=plan_panels(lesson), created_at="2026-01-01T00:00:00Z")


def test_old_v1_record_without_target_projects_honestly():
    p, result = _verified_lesson()
    legacy = result.model_copy(update={"target": None, "checks": [check.model_copy(update={"reason": None, "operation": None})
                                                                  for check in result.checks]})
    stored = GeneratedLesson.model_validate({"lesson": p.model_dump(by_alias=True), "verification": legacy.model_dump(exclude={"target"}),
                                             "board": BoardPlanner().create(p, legacy, None).model_dump(), "total_processing_ms": 1})
    lesson = validated_math_lesson(stored.lesson, stored.verification)
    assert lesson.verification.target is None
    steps = [block for block in lesson.content.blocks if block.kind == "derivation_step"]
    assert steps[0].operation == "unknown" and steps[0].operation_origin == "unknown"  # v1'de işlem kanıtı yok
    assert steps[1].operation == "state_result" and steps[1].operation_origin == "v1_step_type"


def test_block_check_contract_rejects_forged_or_untrusted_verification():
    with pytest.raises(ValidationError):
        BlockCheck(id="x", scope="lesson", dimension="scientific", verifier="mathai", outcome="passed", reason="forged")
    with pytest.raises(ValidationError):
        BlockCheck(id="x", scope="lesson", dimension="pedagogy", verifier="mathai", outcome="passed", reason="forged")
    with pytest.raises(ValidationError):
        BlockCheck(id="x", scope="block", dimension="calculation", verifier="none", outcome="passed", reason="r", target="b")
    with pytest.raises(ValidationError):
        BlockCheck(id="x", scope="block", dimension="calculation", verifier="mathai", outcome="passed", reason="r")
    p, result = _verified_lesson()
    data = validated_math_lesson(p, result).model_dump(by_alias=True)
    data["verification"]["block_checks"].append({"id": "ghost", "scope": "block", "target": "missing_block", "dimension": "calculation",
                                                 "verifier": "mathai", "outcome": "passed", "reason": "forged"})
    with pytest.raises(ValidationError):
        LessonPlanV2.model_validate(data)
    data = validated_math_lesson(p, result).model_dump(by_alias=True)
    data["verification"]["block_checks"][0]["outcome"] = "failed"
    with pytest.raises(ValidationError):  # bilinen çelişki "passed" hesapla birlikte gösterilemez
        LessonPlanV2.model_validate(data)
    data = validated_math_lesson(p, result).model_dump(by_alias=True)
    data["schema"]["version"] = "2.1.0"
    with pytest.raises(ValidationError):  # 2.1.0 belge 2.2.0 alanlarını taşıyamaz
        LessonPlanV2.model_validate(data)


def test_provider_draft_cannot_carry_verification():
    good = content("x = 4", ["x = 4"]).model_dump()
    with pytest.raises(ValidationError):
        LessonDraft.model_validate({"learning_objectives": ["a"], "concept_id": "concept_x", "content": good,
                                    "verification": {"calculation": "passed"}})
    with pytest.raises(ValidationError):
        LessonContent.model_validate(good | {"block_checks": [{"outcome": "passed"}]})


def test_narration_contract_references_blocks_in_order_and_rejects_markup():
    p, result = _verified_lesson()
    data = validated_math_lesson(p, result).model_dump(by_alias=True)
    blocks = [block["id"] for block in data["content"]["blocks"]]
    data["content"]["narration"] = [{"id": "n1", "order": 0, "block": blocks[0], "text": "Önce soruyu okuyalım."},
                                    {"id": "n2", "order": 1, "block": blocks[-1], "text": "Sonuç."}]
    LessonPlanV2.model_validate(data)
    for bad in ([{"id": "n1", "order": 0, "block": "ghost", "text": "x"}],
                [{"id": "n1", "order": 0, "block": blocks[-1], "text": "a"}, {"id": "n2", "order": 1, "block": blocks[0], "text": "b"}],
                [{"id": "n1", "order": 1, "block": blocks[0], "text": "a"}, {"id": "n2", "order": 0, "block": blocks[1], "text": "b"}]):
        data["content"]["narration"] = bad
        with pytest.raises(ValidationError):
            LessonPlanV2.model_validate(data)
    for markup in ("<script>alert(1)</script>", "<svg onload=x>", "<img src=x>"):
        with pytest.raises(ValidationError):
            NarrationSegment(id="n", order=0, block="b", text=markup)


# --------------------------------------------------------------------------- gerçek ders hattı


class TargetProvider:
    name = model = "mock"

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    async def generate_lesson_plan(self, analysis, correction_feedback=None, teaching_context=None, request_id=None):
        self.calls.append(correction_feedback)
        final, finals = self.answers[min(len(self.calls) - 1, len(self.answers) - 1)]
        return LessonProviderResult(LessonDraft(learning_objectives=["hedef"], concept_id="concept_target",
                                                content=content(final, finals)), "mock", "mock")


@pytest.mark.asyncio
async def test_runtime_pipeline_uses_target_with_one_bounded_correction():
    provider = TargetProvider([("A) 3", ["x = 3"]), ("C) 5", ["x + 2 = 5"])])
    lesson = await LessonService(provider, MathAIService(), BoardPlanner()).generate(X3)
    assert len(provider.calls) == 2 and "5" in provider.calls[1]  # mevcut tek düzeltme turu, yeni döngü yok
    assert lesson.lesson.content.final_answer == "C) 5" and lesson.verification.target.selected_option == "C"


@pytest.mark.asyncio
async def test_clean_question_makes_exactly_one_lesson_call_and_sends_target_hint():
    provider = TargetProvider([("C) 5", ["x + 2 = 5"])])
    lesson = await LessonService(provider, MathAIService(), BoardPlanner()).generate(X3)
    assert provider.calls == [None] and lesson.verification.status == "verified"
    payload = build_lesson_generation_context(with_integrity(X3)).payload["problem"]["question_integrity"]
    assert payload["answer_target"] == {"kind": "sum", "expression": "x + 2"}
    assert "answer_choices" not in build_lesson_generation_context(X3).payload["problem"]  # önce çöz, seçenek gizli


def test_v2_endpoint_exposes_target_and_step_checks_only_to_owner():
    app = create_app()
    provider = TargetProvider([("C) 5", ["x + 2 = 5"])])
    app.state.container = replace(app.state.container, lesson_service=LessonService(provider, MathAIService(), BoardPlanner()))
    students = app.state.container.student_service
    user = AuthenticatedUser(uid="student-a")
    students.save_analysis(user, X3)
    with authenticated_client(app) as client:
        generated = client.post("/api/v1/lessons/generate", json={"analysis_id": X3.request_id, "expected_revision": 1})
        assert generated.status_code == 200, generated.text
        assert generated.json()["data"]["verification"]["target"]["requested"] == ["5"]
        path = "/api/v1/lessons/" + generated.json()["data"]["lesson"]["lesson_plan_id"] + "/v2"
        view = client.get(path).json()["data"]["lesson"]
        assert view["verification"]["target"]["selected_option"] == "C" and view["problem"]["source_revision"] == 1
        assert any(check["dimension"] == "answer_choice" for check in view["verification"]["block_checks"])
        assert client.get(path, headers={"Authorization": "Bearer student-b"}).status_code == 404
    assert len(provider.calls) == 1
