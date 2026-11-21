"""TA-005 müfredat ve yöntem kaydı. Fikstür kaydı kullanılır; testler gerçek taslağa bağlı değildir.
Sahte ders sağlayıcısı kullanılır; ağ çağrısı yoktur."""

import pytest
from pydantic import ValidationError

from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.curriculum import registry as reg
from apps.api.app.features.education.curriculum import CurriculumRegistry
from apps.api.app.features.education.domain import Grade
from apps.api.app.features.education.math_adapter import validated_math_lesson
from apps.api.app.features.lessons.provider import LessonProviderResult
from apps.api.app.features.lessons.schemas import Expression, GenerateLessonRequest, LessonContent, LessonDraft, Step
from apps.api.app.features.lessons.service import LessonService
from apps.api.app.features.mathai.service import MathAIService
from apps.api.tests.test_question_integrity import analysis

SOURCE = {"document": "fikstür", "url": "https://example.invalid/program.pdf", "pages": "1"}


def fixture_registry(status="approved"):
    approval = {"status": status, "authored_by": "teacher", "approved_by": "test-ogretmen" if status == "approved" else None}
    return CurriculumRegistry.model_validate({
        "schema_name": "teacherai.curriculum_registry", "version": "1.0.0", "program_note": "fikstür",
        "outcomes": [{"subject": "mathematics", "grade": 8, "unit": "Doğrusal Denklemler", "topic": "dogrusal_denklemler",
                      "outcome_id": "T.8.1", "outcome_text_tr": "Birinci dereceden denklem çözer.", "source": SOURCE,
                      "source_status": "sourced"}],
        "policies": [
            {"id": "t.genel", "grade": 8, "topic": "genel", **approval,
             "forbidden_operations": [{"operation": "derivative", "reason": "Türev 8. sınıfta yoktur."}]},
            {"id": "t.lineer", "grade": 8, "topic": "dogrusal_denklemler", **approval, "outcome_ids": ["T.8.1"],
             "allowed_operations": ["subtract_both_sides", "divide_both_sides", "isolate_variable", "state_result", "explain"]},
        ]})


def linear_analysis():
    return analysis(question_text="3x + 7 = 19 ise x kaçtır?", mathematical_expressions=["3x + 7 = 19"],
                    answer_choices=["A) 2", "B) 3", "C) 4", "D) 5"])


CLEAN = [Step(id="step_1", type="transformation", title="Sabiti çıkar", explanation="İki taraftan 7 çıkar.",
              expressions=[Expression(type="equation", latex="3x = 12")]),
         Step(id="step_2", type="result", title="Böl", explanation="İki tarafı 3'e böl.",
              expressions=[Expression(type="equation", latex="x = 4")])]
# Türev adımı açıklama türündedir; hesap adımları aynı kalır, böylece yalnızca yöntem denetimi başarısız olur.
DERIVATIVE = [Step(id="step_1", type="explanation", title="Türev al",
                   explanation="Sol tarafın x'e göre türevini alırsak eğim 3 olur; buradan x'i bulalım.", expressions=[]),
              *[step.model_copy(update={"id": f"step_{i + 2}"}) for i, step in enumerate(CLEAN)]]


class Provider:
    name = "fixture"
    model = "fixture"

    def __init__(self, *responses):
        self.responses = list(responses)
        self.feedback = []

    async def generate_lesson_plan(self, analysis, correction_feedback=None, teaching_context=None, request_id=None):
        self.feedback.append(correction_feedback)
        steps = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        content = LessonContent(question_understanding="x'i bul", unknown="x", strategy="yalnız bırak", strategy_id="strategy_isolate",
                                steps=steps, final_answer="C) 4", final_answer_expressions=[Expression(type="equation", latex="x = 4")],
                                takeaway="İki tarafa aynı işlem")
        return LessonProviderResult(LessonDraft(learning_objectives=["denklem"], concept_id="concept_linear_equation", content=content),
                                    "fixture", "fixture")


@pytest.fixture
def approved(monkeypatch):
    monkeypatch.setattr(reg, "default_registry", fixture_registry)


async def generate(provider, grade=8):
    return await LessonService(provider, MathAIService(), BoardPlanner()).generate(
        linear_analysis(), grade=Grade(value=grade, origin="declared") if grade else None)


@pytest.mark.asyncio
async def test_derivative_for_grade_8_fails_then_one_targeted_correction(approved):
    provider = Provider(DERIVATIVE, CLEAN)
    result = await generate(provider)
    assert len(provider.feedback) == 2 and provider.feedback[0] is None
    assert "derivative" in provider.feedback[1] and "step_1" in provider.feedback[1]
    assert "subtract_both_sides" in provider.feedback[1]  # yalnızca izinli işlemler verilir
    assert result.correction_attempted and result.method_check.state == "passed"


@pytest.mark.asyncio
async def test_persistent_forbidden_method_is_flagged_not_hidden(approved):
    provider = Provider(DERIVATIVE)
    result = await generate(provider)
    assert len(provider.feedback) == 2  # tek düzeltme turu, sonra dur
    assert result.method_check.state == "failed" and result.method_check.step == "step_1"
    assert result.method_check.operations == ["derivative"]
    report = validated_math_lesson(result.lesson, result.verification, result.education_context,
                                   (result.method_check, result.curriculum_check)).verification
    assert report.method == "failed"
    assert any(c.id == "registry:method" and c.outcome == "failed" and c.target == "step_1" for c in report.block_checks)


@pytest.mark.asyncio
async def test_allowed_method_passes_and_curriculum_maps_to_sourced_outcome(approved):
    provider = Provider(CLEAN)
    result = await generate(provider)
    assert len(provider.feedback) == 1
    assert result.method_check.state == "passed" and result.method_check.topic == "dogrusal_denklemler"
    assert result.curriculum_check.state == "passed" and result.curriculum_check.outcome_ids == ["T.8.1"]
    report = validated_math_lesson(result.lesson, result.verification, result.education_context,
                                   (result.method_check, result.curriculum_check)).verification
    assert (report.method, report.curriculum) == ("passed", "passed")


@pytest.mark.asyncio
async def test_unknown_grade_is_not_checked_and_never_guessed(approved):
    provider = Provider(DERIVATIVE)
    result = await generate(provider, grade=None)
    assert len(provider.feedback) == 1
    assert (result.method_check.state, result.method_check.reason) == ("not_checked", "grade_unknown")
    assert result.curriculum_check.state == "not_checked" and result.education_context.grade is None


@pytest.mark.asyncio
async def test_draft_registry_never_restricts(monkeypatch):
    monkeypatch.setattr(reg, "default_registry", lambda: fixture_registry("draft"))
    provider = Provider(DERIVATIVE)
    result = await generate(provider)
    assert len(provider.feedback) == 1
    assert (result.method_check.state, result.method_check.reason) == ("not_checked", "no_approved_policy")
    assert result.curriculum_check.state == "not_checked"


def test_other_grades_and_topics_stay_not_checked():
    registry = fixture_registry()
    assert reg.approved_policies(registry, 9, "dogrusal_denklemler") == []
    quadratic = analysis(question_text="x² − 5x + 6 = 0 kökler toplamı kaçtır?", mathematical_expressions=["x^2-5x+6=0"],
                         answer_choices=["A) 5", "B) 6", "C) 1", "D) 2"])
    assert reg.topic_of(quadratic) is None
    assert reg.curriculum_check(quadratic, 8, registry).state == "not_checked"


@pytest.mark.parametrize(("expression", "topic"), [
    ("3x + 7 = 19", "dogrusal_denklemler"), ("2x - 3 < 7", "esitsizlikler"), ("\\sqrt{50}", "karekoklu_ifadeler"),
    ("2^{5}", "uslu_ifadeler"), ("x^2 = 9", None),
])
def test_topic_comes_from_source_structure_not_provider_label(expression, topic):
    item = analysis(question_text="Buna göre sonuç kaçtır?", mathematical_expressions=[expression],
                    answer_choices=["A) 1", "B) 2", "C) 3", "D) 4"])
    item = item.model_copy(update={"topic": "Türev"})  # sağlayıcı etiketi yok sayılır
    assert reg.topic_of(item) == topic


def test_registry_contract_rejects_unsourced_text_and_silent_approval():
    with pytest.raises(ValidationError):
        CurriculumRegistry.model_validate({**fixture_registry().model_dump(), "outcomes": [{
            **fixture_registry().outcomes[0].model_dump(), "source_status": "pending"}]})
    with pytest.raises(ValidationError):
        fixture_registry().policies[0].model_validate({**fixture_registry().policies[0].model_dump(), "approved_by": None})


def test_shipped_registry_is_valid_draft_with_sourced_outcomes():
    shipped = reg.default_registry()
    assert shipped.policies and all(p.status == "draft" and p.authored_by == "claude-draft" for p in shipped.policies)
    assert all(o.source_status == "sourced" and o.source.url.startswith("http://mufredat.meb.gov.tr/") for o in shipped.outcomes)


def test_request_and_profile_accept_optional_grade():
    assert GenerateLessonRequest(analysis_id="a1", grade=8).grade == 8
    assert GenerateLessonRequest(analysis_id="a1").grade is None
    with pytest.raises(ValidationError):
        GenerateLessonRequest(analysis_id="a1", grade=3)
