"""TA-005 müfredat ve yöntem kaydı. Fikstür kaydı kullanılır; testler gerçek taslağa bağlı değildir.
Sahte ders sağlayıcısı kullanılır; ağ çağrısı yoktur.

TA-007: ders akışı MethodPolicy v2 çalışma zamanını kullanır. Onaylı fikstür politikası artık yalnız yetkili
inceleyen (sentetik, yalnız bu yalıtılmış testte), onay tarihi ve güncel içerik özetiyle etkindir."""

from datetime import date
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.curriculum import methods, registry_v2
from apps.api.app.features.curriculum import registry as reg
from apps.api.app.features.education.curriculum import CurriculumRegistry
from apps.api.app.features.education.knowledge import ReviewerAuthorization
from apps.api.app.features.knowledge import reviewers as reviewer_registry
from apps.api.app.features.education.domain import Grade
from apps.api.app.features.education.math_adapter import validated_math_lesson
from apps.api.app.features.lessons.provider import LessonProviderResult
from apps.api.app.features.lessons.schemas import Expression, GenerateLessonRequest, LessonContent, LessonDraft, Step
from apps.api.app.features.lessons.service import LessonService
from apps.api.app.features.mathai.service import MathAIService
from apps.api.tests.test_question_integrity import analysis

SOURCE = {"document": "fikstür", "url": "https://example.invalid/program.pdf", "pages": "1"}


# Sentetik yetki: yalnız yalıtılmış testlerde. Üretim kaydı (knowledge/data/reviewers.json) boştur.
REVIEWER = ReviewerAuthorization(reviewer="teacher:test-ogretmen", roles=["teacher"], subjects=["mathematics"],
                                 stages=["pedagogical"], valid_from=date(2020, 1, 1), authorized_by="owner:test-sahip",
                                 authorized_on=date(2020, 1, 1), evidence_note_tr="Yalnız yalıtılmış test fikstürü.")


def fixture_registry(status="approved", *, digest=True):
    approval = {"status": status, "authored_by": "teacher",
                "approved_by": "teacher:test-ogretmen" if status == "approved" else None,
                "approved_on": "2026-01-15" if status == "approved" else None}
    registry = _fixture(approval)
    if status != "approved" or not digest:
        return registry
    digests = {p.legacy_id: methods.policy_digest(p) for p in registry_v2.migrate_v1_policies(registry)}
    return registry.model_copy(update={"policies": [p.model_copy(update={"approval_digest": digests[p.id]})
                                                    for p in registry.policies]})


def _fixture(approval):
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
# TA-005B: türev ifadenin AST'sinde (f'(x)) bulunur; düz metindeki "türev" sözü tek başına güçlü kanıt değildir.
DERIVATIVE = [Step(id="step_1", type="explanation", title="Türev al",
                   explanation="Sol tarafın x'e göre türevini alırsak eğim 3 olur; buradan x'i bulalım.",
                   expressions=[Expression(type="equation", latex="f'(x) = 3")]),
              *[step.model_copy(update={"id": f"step_{i + 2}"}) for i, step in enumerate(CLEAN)]]
# Aynı söz yalnız düz metinde: zayıf kanıt, düzeltme turu yok.
PROSE_ONLY = [DERIVATIVE[0].model_copy(update={"expressions": []}), *DERIVATIVE[1:]]


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


def authorize(monkeypatch, registry=fixture_registry, reviewers=(REVIEWER,)):
    registry_v2.default_registry()  # v2 kaydı gerçek v1 kayıtla bir kez kurulur; fikstür yalnız politikaları değiştirir
    monkeypatch.setattr(reg, "default_registry", registry)
    monkeypatch.setattr(reviewer_registry, "default_reviewers", lambda: tuple(reviewers))


@pytest.fixture
def approved(monkeypatch):
    authorize(monkeypatch)


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
    # TA-007: müfredat boyutu v2 kaydından; kazanım küresel kimlikli ve çözümlenen programın 8. sınıfındadır.
    assert result.curriculum_check.state == "passed" and result.curriculum_check.reason == "program_outcome_matched"
    assert result.curriculum_check.outcome_ids and all(
        ref.startswith("meb-2018.matematik.1-8::M.8.") for ref in result.curriculum_check.outcome_ids)
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
    authorize(monkeypatch, lambda: fixture_registry("draft"))
    provider = Provider(DERIVATIVE)
    result = await generate(provider)
    assert len(provider.feedback) == 1
    assert (result.method_check.state, result.method_check.reason) == ("not_checked", "no_approved_policy")
    assert result.method_check.inactive_policy_ids  # taslaklar sayılır ama kısıtlamaz
    # TA-007: müfredat boyutu yöntem politikasından bağımsızdır; resmî programdaki kazanımla eşleşir.
    assert result.curriculum_check.state == "passed" and result.curriculum_check.policy_ids == []


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


# --- TA-005B: kanıt düzeyleri ---

def plan_with(*steps):
    """method_check yalnız adımları ve kaynak analizi okur."""
    return SimpleNamespace(content=SimpleNamespace(steps=list(steps)), source_analysis=linear_analysis())


class NoChecks:
    checks = []


def prose_step(text):
    return Step(id="step_1", type="explanation", title="Açıklama", explanation=text, expressions=[])


def latex_step(latex):
    return Step(id="step_1", type="transformation", title="Adım", explanation="Devam edelim.",
                expressions=[Expression(type="equation", latex=latex)])


@pytest.mark.parametrize("step", [
    prose_step("Türev kullanmadan çözelim."),
    prose_step("Aracın hız limiti 90 km/sa."),
    latex_step(r"A^{\prime}(3,-2)"),
    prose_step(r"A^{\prime}(3,-2) noktası A'nın görüntüsüdür."),
    latex_step(r"\Delta ABC"),
    prose_step(r"\Delta ABC üçgeninde açıları toplayalım."),
    prose_step("Bu bir sinüs eğrisi değil."),
    prose_step("Hiçbir integral ya da logaritma gerekmez."),
])
def test_known_false_alarms_are_not_forbidden_operations(step):
    rows = reg.step_operations(plan_with(step), NoChecks())
    assert rows[0][1] == ["explain"] or not set(rows[0][1]) & set(reg.PROSE)
    assert rows[0][2] == []  # olumsuzlanan veya ilgisiz söz zayıf kanıt da değildir
    check = reg.method_check(plan_with(step), NoChecks(), 8, fixture_registry_all())
    assert check.state != "failed" and check.reason != "prose_mention_unverified"


@pytest.mark.parametrize(("latex", "construct"), [
    ("f'(x)=2x", "derivative"), (r"\log_2 8", "logarithm"), (r"\sin 30^\circ", "trigonometry"),
    (r"x=\frac{-b\pm\sqrt{b^2-4ac}}{2a}", "quadratic_formula"), (r"\frac{dy}{dx} = 3x^2", "derivative"),
    (r"\int_0^1 2x\,dx", "integral"), (r"\lim_{x \to 2} \frac{x^2-4}{x-2}", "limit"), (r"\ln e", "logarithm"),
    (r"\Delta = (-5)^2 - 4 \cdot 1 \cdot 6", "quadratic_formula"), (r"\sqrt{-4}", "complex_number"),
    (r"i^2 = -1", "complex_number"), (r"\frac{d}{dx}(x^2) = 2x", "derivative"),
])
def test_real_uses_are_strong_evidence_and_fail(latex, construct):
    assert construct in reg.ast_constructs(latex)
    check = reg.method_check(plan_with(latex_step(latex)), NoChecks(), 8, fixture_registry_all())
    assert (check.state, check.reason, check.operations) == ("failed", "forbidden_operation", [construct])


@pytest.mark.parametrize("latex", [
    "A'(2, 5)", r"A^{\prime}", "B''", r"\Delta ABC", "x^2 - 4xy + 4y^2", "(a-b)^2 = a^2 - 2ab + b^2",
    r"|AB| = \sqrt{3^2 + 4^2}", r"\frac{d}{2}", "y' = 2", r"A^{\prime}(3,-2)", r"\Delta = 12",
    r"\sqrt{-x}", "x^2 = 9",
])
def test_geometry_and_transformation_expressions_are_not_strong_evidence(latex):
    assert reg.ast_constructs(latex) == set()


def test_prose_only_mention_is_partially_checked_with_reason():
    check = reg.method_check(plan_with(prose_step("Burada sol tarafın türevini alırız.")), NoChecks(), 8, fixture_registry_all())
    assert (check.state, check.reason, check.operations, check.step) == (
        "partially_checked", "prose_mention_unverified", ["derivative"], "step_1")
    before = reg.prose_constructs("Türev almadan önce sadeleştir.")
    assert before == {"derivative"}  # "…madan önce" olumsuzlama değildir


@pytest.mark.asyncio
async def test_prose_mention_never_triggers_paid_correction(approved):
    provider = Provider(PROSE_ONLY)
    result = await generate(provider)
    assert len(provider.feedback) == 1 and not result.correction_attempted  # ek çağrı yok
    assert (result.method_check.state, result.method_check.reason) == ("partially_checked", "prose_mention_unverified")


def fixture_registry_all():
    """Bütün yapıları yasaklayan onaylı fikstür ``genel`` politikası (taslak politikalar onaylanmaz)."""
    registry = fixture_registry()
    general = registry.policies[0].model_copy(update={"forbidden_operations": [
        type(registry.policies[0].forbidden_operations[0])(operation=name, reason="fikstür") for name in reg.PROSE]})
    return registry.model_copy(update={"policies": [general, *registry.policies[1:]]})
