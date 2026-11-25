"""TA-006 çalışma zamanı eğitim bağlamı: seçim, boyut sınırı, çağrı sayısı, köken ve geçmiş dersin korunması.
Sahte ders sağlayıcısı ve yerel Firestore emülatörü kullanılır; ağ çağrısı yoktur."""

import json
from dataclasses import replace
from datetime import date
from time import perf_counter
from uuid import uuid4

import pytest

from apps.api.app.core.settings import Settings
from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.curriculum import context as selection
from apps.api.app.features.curriculum import registry_v2
from apps.api.app.features.education.base import Subject
from apps.api.app.features.education.domain import Grade
from apps.api.app.features.education.knowledge import KnowledgeEntry, ReviewerAuthorization, content_digest
from apps.api.tests.test_ta006_knowledge import seal_rights
from apps.api.app.features.education.policy import TeachingPolicy
from apps.api.app.features.knowledge import registry as knowledge
from apps.api.app.features.lessons.context import build_lesson_generation_context
from apps.api.app.features.lessons.service import GeneratedLesson, LessonService
from apps.api.app.features.mathai.service import MathAIService
from apps.api.app.main import create_app
from apps.api.tests.client import authenticated_client
from apps.api.tests.test_curriculum import CLEAN, Provider, linear_analysis

TODAY = date(2026, 11, 24)


class Capturing(Provider):
    def __init__(self, *responses):
        super().__init__(*responses)
        self.contexts = []

    async def generate_lesson_plan(self, analysis, correction_feedback=None, teaching_context=None, request_id=None):
        self.contexts.append(teaching_context)
        return await super().generate_lesson_plan(analysis, correction_feedback, teaching_context, request_id)


async def generate(grade=None, **kwargs):
    provider = Capturing(CLEAN)
    today = kwargs.pop("today", TODAY)
    service = LessonService(provider, MathAIService(), BoardPlanner(), clock=lambda: today)
    result = await service.generate(linear_analysis(), grade=Grade(value=grade, origin="declared") if grade else None, **kwargs)
    return result, provider


@pytest.mark.asyncio
async def test_grade_8_lesson_gets_bounded_official_codes_and_one_provider_call():
    result, provider = await generate(8)
    assert len(provider.feedback) == 1  # olağan ders: tek sağlayıcı çağrısı
    policy = provider.contexts[0]
    assert isinstance(policy, TeachingPolicy)
    payload = policy.curriculum_context
    assert payload.program == "MEB 2018 Matematik (1-8)" and payload.grade == 8 and payload.academic_year == "2026-2027"
    assert [item.code for item in payload.outcomes] == ["M.8.2.2.1", "M.8.2.2.2", "M.8.2.2.3", "M.8.2.2.4"]
    assert payload.knowledge == []  # bilgi girdileri taslak: isteme girmez
    serialized = json.dumps(payload.model_dump(), ensure_ascii=False)
    assert "Birinci dereceden bir bilinmeyenli denklemleri çözer" not in serialized  # resmî metin gönderilmez
    provenance = result.educational_provenance
    assert provenance.included_in_prompt and provenance.match == "topic_key" and provenance.payload_bytes <= selection.MAX_PAYLOAD_BYTES
    assert provenance.excluded_draft_knowledge >= 1 and provenance.knowledge_ids == []
    assert provenance.curriculum_version == registry_v2.default_registry().version
    keys = {(ref.kind, ref.key) for ref in result.education_context.references}
    assert ("curriculum", "meb-2018.matematik.1-8") in keys and ("outcome", "meb-2018.matematik.1-8::M.8.2.2.1") in keys


@pytest.mark.asyncio
async def test_lesson_context_stays_within_budget_and_emergency_drops_curriculum():
    _, provider = await generate(8)
    built = build_lesson_generation_context(linear_analysis(), None, provider.contexts[0])
    assert "curriculum_context" in built.payload and built.metrics.size_bytes <= Settings().lesson_context_max_bytes
    assert built.payload["student_grade"] == {"value": 8, "origin": "declared"}
    emergency = build_lesson_generation_context(linear_analysis(), None, provider.contexts[0], "emergency")
    assert "curriculum_context" not in emergency.payload


@pytest.mark.asyncio
async def test_without_grade_the_prompt_context_is_unchanged():
    result, provider = await generate(None)
    assert provider.contexts == [None]
    assert build_lesson_generation_context(linear_analysis(), None, None).serialized == \
        build_lesson_generation_context(linear_analysis(), None, provider.contexts[0]).serialized
    assert result.educational_provenance.resolution.reasons == ["grade_unknown"]
    assert not result.educational_provenance.included_in_prompt


@pytest.mark.asyncio
async def test_maarif_grade_7_matches_through_reviewable_alias():
    result, provider = await generate(7)
    assert [item.code for item in provider.contexts[0].curriculum_context.outcomes] == ["MAT.7.2.2"]
    assert result.educational_provenance.match == "alias"


@pytest.mark.asyncio
async def test_graduate_and_transition_contexts_do_not_reach_the_prompt():
    graduate, provider = await generate(12, learner_status="graduate", exam_goal="AYT hazırlık")
    assert provider.contexts == [None] and graduate.educational_provenance.resolution.status == "ambiguous"
    summer, provider = await generate(8, today=date(2027, 7, 15))
    assert provider.contexts == [None] and "academic_year_transition" in summer.educational_provenance.resolution.reasons


def test_approved_knowledge_enters_context_only_after_review():
    registry = knowledge.default_knowledge()
    base = registry.entries["math.equation-equivalence"]
    # TA-007: onay aynı sürümün içerik özetiyle, hak kararı proje sahibince; ikisi de yetki kaydında (yalnız test).
    review = {"reviewer": "teacher:matematik-01", "role": "teacher", "reviewed_on": "2026-12-01",
              "reviewed_version": base.version, "decision": "approve", "rationale_tr": "8. sınıfa uygun.",
              "stage": "scientific", "content_digest": content_digest(base)}
    rights = {"source_use": "independent_fact", "basis_tr": "Özgün anlatım.", "decision": "approved",
              "decided_by": "owner:test-sahip", "decided_on": "2026-12-02"}
    approved = seal_rights(KnowledgeEntry.model_validate({**base.model_dump(), "status": "approved", "reviews": [review],
                                                          "rights": rights}))
    reviewers = tuple(ReviewerAuthorization(reviewer=ref, roles=[role], subjects=["mathematics"], stages=[stage],
                                            valid_from=date(2026, 1, 1), authorized_by="owner:test-sahip",
                                            authorized_on=date(2026, 1, 1), evidence_note_tr="Yalnız test fikstürü.")
                      for ref, role, stage in (("teacher:matematik-01", "teacher", "scientific"),
                                               ("owner:test-sahip", "project_owner", "rights")))
    custom = knowledge.KnowledgeRegistry(sources=registry.sources, entries={**registry.entries, approved.id: approved},
                                         digest="t", reviewers=reviewers)
    chosen = selection.select(linear_analysis(), Subject.MATHEMATICS, 8, today=TODAY, knowledge=custom)
    assert [item.id for item in chosen.payload.knowledge] == ["math.equation-equivalence"]
    assert chosen.provenance.knowledge_ids == ["math.equation-equivalence"]
    assert chosen.provenance.payload_bytes <= selection.MAX_PAYLOAD_BYTES
    # Koşullar kırpılmadan bütün kayıt gider; sürüm ve içerik özeti köken kaydındadır.
    assert chosen.payload.knowledge[0].conditions_tr == list(approved.conditions_tr)
    assert chosen.provenance.knowledge_refs[0].content_digest == content_digest(approved)


def test_selection_is_deterministic_and_fast():
    analysis = linear_analysis()
    first = selection.select(analysis, Subject.MATHEMATICS, 8, today=TODAY)
    started = perf_counter()
    for _ in range(50):
        again = selection.select(analysis, Subject.MATHEMATICS, 8, today=TODAY)
    elapsed = (perf_counter() - started) / 50
    assert again == first
    assert elapsed < 0.05, f"seçim başına {elapsed * 1000:.1f} ms"


def test_exam_goal_parsing_does_not_guess():
    # TA-007: Türkçe ekli biçimler tanınır; birden çok hedef kaybolmaz ("YKS" = TYT + AYT).
    assert selection.canonical_exam("LGS'ye hazırlanıyorum") == "LGS"
    assert selection.canonical_exam("lgs") == "LGS" and selection.canonical_exam("AYT matematik") == "AYT"
    assert selection.canonical_exam("YKS") is None and selection.canonical_exam("TYT ve AYT") is None
    assert selection.exam_goals("TYT ve AYT") == ["TYT", "AYT"] and selection.exam_goals("YKS'ye hazırlanıyorum") == ["TYT", "AYT"]
    assert selection.exam_goals("Sınava hazırlanıyorum") == [] and selection.exam_goals(None) == []
    assert selection.declared_graduate("Mezunum, AYT'ye çalışıyorum") and not selection.declared_graduate("12. sınıfım")


@pytest.fixture
def app():
    app = create_app()
    provider = Capturing(CLEAN)
    service = LessonService(provider, MathAIService(), BoardPlanner(), clock=lambda: TODAY)
    app.state.container = replace(app.state.container, lesson_service=service)
    app.state.provider = provider
    return app


def _generate(app, client, **body):
    analysis = linear_analysis().model_copy(update={"request_id": f"an_{uuid4().hex}"})
    app.state.container.student_service.save_analysis(AuthenticatedUser(uid="student-a"), analysis)
    response = client.post("/api/v1/lessons/generate", json={"analysis_id": analysis.request_id, **body})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_historical_lesson_keeps_its_original_context_after_registry_and_profile_change(app, monkeypatch):
    with authenticated_client(app) as client:
        client.put("/api/v1/students/me/profile", json={"display_name": "Ada", "exam_goal": "LGS", "grade": 8})
        first = _generate(app, client)
        lesson_id = first["lesson"]["lesson_plan_id"]
        original = first["educational_provenance"]
        assert original["resolution"]["program_ids"] == ["meb-2018.matematik.1-8"]
        assert original["resolution"]["exam"] == "LGS" and original["resolution"]["exam_scope_id"] == "lgs-2027"
        client.put("/api/v1/students/me/profile", json={"display_name": "Ada", "grade": 9})
        changed = registry_v2.default_registry()
        monkeypatch.setattr(registry_v2, "default_registry", lambda: replace(changed, digest="0" * 64))
        second = _generate(app, client)
        assert second["educational_provenance"]["curriculum_version"] == "2.0.0+000000000000"
        assert second["educational_provenance"]["resolution"]["program_ids"] == ["tymm-2026.matematik.9-12"]
        record = app.state.container.student_service.owned(AuthenticatedUser(uid="student-a"), lesson_id)
        stored = GeneratedLesson.model_validate(record.lesson_data)
        assert stored.educational_provenance.model_dump(mode="json") == original
        view = client.get(f"/api/v1/lessons/{lesson_id}/v2").json()["data"]
        assert view["lesson"]["context"]["grade"] == {"value": 8, "origin": "profile"}


def test_learner_status_is_kept_when_old_clients_omit_it(app):
    with authenticated_client(app) as client:
        client.put("/api/v1/students/me/profile", json={"display_name": "Ada", "learner_status": "graduate", "exam_goal": "AYT"})
        kept = client.put("/api/v1/students/me/profile", json={"display_name": "Ada", "exam_goal": "AYT"}).json()["data"]
        assert kept["learner_status"] == "graduate"
        cleared = client.put("/api/v1/students/me/profile", json={"display_name": "Ada", "learner_status": None}).json()["data"]
        assert cleared["learner_status"] is None
        assert client.put("/api/v1/students/me/profile", json={"display_name": "Ada", "learner_status": "mezun"}).status_code == 422


def test_topic_explanation_intent_needs_no_fabricated_question_and_unsupported_modes_are_explicit():
    from pydantic import ValidationError

    from apps.api.app.features.education.lesson_intent import LessonIntent, mode_support

    topic = LessonIntent(mode="topic_explanation", subject=Subject.MATHEMATICS, topic_key="dogrusal_denklemler")
    assert topic.source_analysis_id is None
    for bad in ({"mode": "question_solving"}, {"mode": "topic_explanation", "topic_key": None},
                {"mode": "topic_explanation", "source_analysis_id": "an_1"}):
        with pytest.raises(ValidationError):
            LessonIntent.model_validate({"subject": "mathematics", "topic_key": "x", **bad})
    assert mode_support("question_solving", Subject.MATHEMATICS).available
    assert mode_support("topic_explanation", Subject.MATHEMATICS).planned_phase == "TA-013"
    physics = mode_support("question_solving", Subject.PHYSICS)
    assert not physics.available and physics.reason == "subject_generation_unavailable"
