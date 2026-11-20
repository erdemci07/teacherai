import json
from dataclasses import replace
from pathlib import Path

import pytest
from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.education.domain import (
    Grade,
    Subject,
    canonical_subject,
    capabilities,
)
from apps.api.app.features.education.lesson import EducationalDraft, LessonPlanV2
from apps.api.app.features.education.math_adapter import (
    UnsupportedSubjectError,
    understand,
    validated_math_lesson,
)
from apps.api.app.features.education.policy import TeachingPolicy, TeachingRule
from apps.api.app.features.education.presentation import LessonView, plan_panels
from apps.api.app.features.lessons.context import build_lesson_generation_context
from apps.api.app.features.lessons.exceptions import VerificationContradictionError
from apps.api.app.features.lessons.service import LessonService
from apps.api.app.features.mathai.service import MathAIService
from apps.api.app.features.memory.schemas import TeachingContext
from apps.api.app.main import create_app
from apps.api.tests.client import authenticated_client
from apps.api.tests.test_lesson_pipeline import AlgebraLessonProvider
from apps.api.tests.test_mathai import plan
from fastapi.testclient import TestClient
from pydantic import ValidationError

FIXTURES = json.loads((Path(__file__).parent / "fixtures/education/synthetic.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("example", FIXTURES, ids=lambda item: item["lesson"]["lesson_id"])
def test_synthetic_architecture_cases(example):
    view = LessonView.model_validate(example)
    assert view.panels == plan_panels(view.lesson)
    lesson = view.lesson
    assert lesson.provenance.provider == "synthetic"
    # Yapısal geçerlilik bilimsel doğrulama sayılmaz; motoru olmayan alanlar "unsupported" kalır.
    engine = capabilities(lesson.context.subject).verification
    expected = "not_checked" if engine == "bounded_math" else "unsupported"
    assert lesson.verification.scientific == expected
    assert lesson.verification.calculation in {"not_checked", "unsupported", "not_applicable"}
    assert {lesson.verification.curriculum, lesson.verification.method, lesson.verification.pedagogy} == {"not_checked"}
    assert all(ref.review == "unreviewed" for ref in lesson.content.references + lesson.context.references)


def test_fixtures_cover_every_subject_and_answer_free_topic_lessons():
    lessons = [LessonView.model_validate(item).lesson for item in FIXTURES]
    assert {lesson.context.subject for lesson in lessons} == set(Subject) - {Subject.UNKNOWN}
    topics = [lesson for lesson in lessons if lesson.content.activity == "topic_lesson"]
    assert topics and all(lesson.content.answer is None for lesson in topics)
    assert any(
        lesson.context.subject in {Subject.BIOLOGY, Subject.SCIENCE}
        and not any(block.kind in {"expression", "calculation"} for block in lesson.content.blocks)
        for lesson in topics
    )


@pytest.mark.parametrize("answer", [
    {"kind": "choice", "choices": ["A) 3", "B) 4"], "selected": 1},
    {"kind": "number", "value": 4},
    {"kind": "text", "text": "Doğal seçilim kalıtsal çeşitlilik üzerinden işler."},
    {"kind": "quantity", "quantity": {"value": 12.0, "unit": "m/s", "label": "Hız"}},
    {"kind": "table", "table": {"headers": ["Hal", "Şekil"], "rows": [["Katı", "Belirli"]]}},
])
def test_answer_forms_are_not_restricted_to_latex(answer):
    assert EducationalDraft.model_validate(FIXTURES[0]["lesson"]["content"] | {"answer": answer}).answer.kind == answer["kind"]


def test_generated_contracts_are_current():
    from scripts.education_contracts import outputs

    for path, contents in outputs().items():
        assert path.read_text(encoding="utf-8") == contents, f"{path.name}: python -m scripts.education_contracts"


@pytest.mark.parametrize(("label", "subject"), [
    (" Matematik ", "mathematics"), ("GEOMETRİ", "geometry"), ("Fizik", "physics"), ("KİMYA", "chemistry"),
    ("Biyoloji", "biology"), ("Fen Bilimleri", "science"), ("Sanat", "unknown"),
])
def test_subject_mapping_and_capabilities(label, subject):
    assert canonical_subject(label) == canonical_subject(subject) == subject
    cap = capabilities(Subject(subject))
    assert cap.generation == (subject in {"mathematics", "geometry"})
    assert cap.rendering == (subject != "unknown")


@pytest.mark.parametrize("subject", ["Biyoloji", "Fizik", "KİMYA", "Fen Bilimleri"])
@pytest.mark.asyncio
async def test_recognition_does_not_authorize_generation(subject):
    analysis = plan().source_analysis.model_copy(update={"subject": subject, "exam_context": None})
    question = understand(analysis)
    assert question.status == "unsupported_subject" and question.question
    assert question.context.exam is None and question.context.source_exam is None and question.context.grade is None
    provider = AlgebraLessonProvider()
    with pytest.raises(UnsupportedSubjectError):
        await LessonService(provider, None, BoardPlanner()).generate(analysis)
    assert not provider.analysis_payloads


@pytest.mark.parametrize("label", ["Cebir", "Temel Matematik", "Analitik Geometri", "Olasılık"])
@pytest.mark.asyncio
async def test_free_text_math_labels_keep_the_working_pipeline(label):
    """Mevcut görsel istemi yalnızca matematik sorusunu kabul eder; serbest etiket akışı kırmamalı."""
    analysis = plan().source_analysis.model_copy(update={"subject": label})
    question = understand(analysis)
    assert question.status == "educational" and question.context.subject == Subject.MATHEMATICS
    # TA-003: sorunun benzediği sınav türü AI çıkarımıdır ve öğrencinin hedefinden ayrı alanda durur.
    assert question.context.source_exam.origin == "inferred" and question.context.exam is None
    provider = AlgebraLessonProvider()
    result = await LessonService(provider, MathAIService(), BoardPlanner()).generate(analysis)
    assert len(provider.analysis_payloads) == 1
    assert result.board.elements[-1].type == "final_answer" and result.board.elements[-1].mark == "check"


def test_current_vision_cannot_establish_non_educational():
    analysis = plan().source_analysis.model_copy(update={"image_status": "not_math_question", "is_valid_question": False,
                                                         "subject": "", "question_text": ""})
    assert understand(analysis).status == "unresolved_subject"


def test_profile_priority_and_required_rules_survive_compaction():
    learner = TeachingContext(exam_goal="AYT", topic_experience=3, recurring_mistakes=[],
                              support_need="destek", preferred_explanation_depth="kısa", recent_topics=["Denklem"])
    policy = TeachingPolicy(learner=learner, grade=Grade(value=11, origin="profile"),
                            rules=[TeachingRule(source="platform_policy", forbidden_methods=["derivative"])])
    for level in ("normal", "emergency"):
        payload = build_lesson_generation_context(plan().source_analysis, teaching_context=policy, level=level).payload
        assert payload["student_exam"] == {"value": "AYT", "origin": "profile"}
        assert payload["student_grade"]["value"] == 11
        assert payload["required_teaching_rules"][0]["forbidden_methods"] == ["derivative"]
    with pytest.raises(ValidationError):
        Grade(value=11, origin="inferred")


@pytest.mark.parametrize("change", [
    {"blocks": [{"kind": "html", "id": "a", "html": "<script>"}]},
    {"blocks": [{"kind": "warning", "id": "a", "text": "a", "javascript": "run()"}]},
    {"blocks": [{"kind": "warning", "id": "a", "text": "x" * 8193}]},
    {"blocks": [{"kind": "hint", "id": "a", "text": "x"}] * 2},
    {"blocks": [{"kind": "hint", "id": "a", "text": "x", "relates_to": ["b"]}]},
    {"blocks": [{"kind": "table", "id": "a", "table": {"headers": ["A"], "rows": [["a", "b"]]}}]},
    {"blocks": [{"kind": "table", "id": "a", "table": {"headers": ["A"], "rows": [["a"]] * 41}}]},
    {"blocks": [{"kind": "visual", "id": "a", "visual_type": "svg", "description": "x"}]},
    {"answer": None}, {"answer": {"kind": "quantity", "quantity": {"value": float("nan"), "unit": "m"}}},
    {"answer": {"kind": "choice", "choices": ["a", "b"], "selected": 2}},
    {"verification": {"curriculum": "passed"}}, {"owner": "student"}, {"teacher_approved": True},
])
def test_draft_rejects_invalid_or_privileged_content(change):
    with pytest.raises(ValidationError):
        EducationalDraft.model_validate(FIXTURES[0]["lesson"]["content"] | change)


def test_version_and_verification_authority():
    bio = FIXTURES[7]["lesson"]
    assert bio["content"]["answer"] is None
    for changes in [
        # 2.1.0 (TA-003) yalnızca isteğe bağlı kaynak revizyonu alanlarını ekler; bilinmeyen sürüm reddedilir.
        {"schema": {"name": "teacherai.lesson_plan", "version": "2.2.0"}},
        {"source_revision": 1},
        {"context": {"subject": "unknown", "language": "tr"}},
        {"verification": bio["verification"] | {"calculation": "passed"}},
        {"verification": bio["verification"] | {"method": "passed"}},
    ]:
        with pytest.raises(ValidationError):
            LessonPlanV2.model_validate(bio | changes)
    broken = plan(final="x = 5")
    with pytest.raises(VerificationContradictionError):
        validated_math_lesson(broken, MathAIService().verify(broken))


def test_private_views_share_one_math_lesson():
    app = create_app()
    provider = AlgebraLessonProvider()
    service = LessonService(provider, MathAIService(), BoardPlanner())
    app.state.container = replace(app.state.container, lesson_service=service)
    students = app.state.container.student_service
    user = AuthenticatedUser(uid="student-a")
    analysis = plan().source_analysis
    students.save_analysis(user, analysis)
    with authenticated_client(app) as client:
        generated = client.post("/api/v1/lessons/generate", json={"analysis_id": analysis.request_id})
        assert generated.status_code == 200, generated.text
        v1 = generated.json()["data"]
        path = "/api/v1/lessons/" + v1["lesson"]["lesson_plan_id"] + "/v2"
        before = students.dashboard(user)
        first = client.get(path)
        assert first.status_code == 200, first.text
        assert first.headers["cache-control"] == "private, no-store"
        view = LessonView.model_validate(first.json()["data"])
        assert view.lesson.lesson_id == v1["lesson"]["lesson_plan_id"]
        assert view.lesson.verification.calculation == "passed"
        assert view.lesson.verification.scientific == "partially_checked"
        assert view.lesson.verification.curriculum == "not_checked"
        assert client.get(path).json()["data"] == first.json()["data"]
        assert len(provider.analysis_payloads) == 1 and students.dashboard(user) == before
        assert before.questions_solved == 1
        assert client.get(path, headers={"Authorization": "Bearer student-b"}).status_code == 404
        assert client.post(path, json={"verification": {"scientific": "passed"}}).status_code == 405
        historical = students.owned(user, view.lesson.lesson_id).model_copy(update={"server_generated": False})
        students.repository.save_lesson(historical)
        assert client.get(path).status_code == 404
        assert students.history(user)[0].verification_status == "legacy_unverified"
    with TestClient(app) as client:
        assert client.get(path).status_code == 401
