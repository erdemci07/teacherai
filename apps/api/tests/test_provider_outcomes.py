"""B paketi: Vision, Lesson ve Interaction için yedi sağlayıcı sonucu (3 x 7).

Her durum gerçek HTTP yolundan, Firestore emülatörüne bağlı depolarla ve sahte
OpenAI istemcisiyle koşar. Kontrol edilenler: HTTP durumu ve hata kodu, kalıcı
kayıt oluşmaması, çıktı rezervasyonunun sonuç kuralı ve tek ai_usage satırı.
"""

import io
import json
import logging
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from google.cloud.firestore_v1.base_query import FieldFilter
from openai import APITimeoutError, InternalServerError
from PIL import Image

import apps.api.app.features.interactions.openai_provider as interaction_module
import apps.api.app.features.lessons.openai_provider as lesson_module
import apps.api.app.features.vision.openai_provider as vision_module
from apps.api.app.core.settings import Settings
from apps.api.app.core.usage import UsageTracker
from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.interactions.openai_provider import OpenAIInteractionProvider
from apps.api.app.features.interactions.schemas import AdaptiveDraft
from apps.api.app.features.interactions.service import InteractionService
from apps.api.app.features.interactions.store import FirestorePracticeStore
from apps.api.app.features.lessons.openai_provider import OpenAILessonProvider
from apps.api.app.features.lessons.schemas import LessonDraftResponse
from apps.api.app.features.lessons.service import LessonService
from apps.api.app.features.mathai.isolated import IsolatedMathAI
from apps.api.app.features.memory.engine import MemoryEngine
from apps.api.app.features.shares.firestore_repository import FirestoreShareRepository
from apps.api.app.features.shares.service import ShareService
from apps.api.app.features.students.firestore_repository import FirestoreStudentRepository
from apps.api.app.features.students.service import StudentService
from apps.api.app.features.vision.openai_provider import OpenAIVisionProvider
from apps.api.app.features.vision.schemas import VisionProviderAnalysis, VisualElements
from apps.api.app.features.vision.service import VisionService
from apps.api.app.features.vision.storage import LocalTemporaryImageStorage
from apps.api.app.main import create_app
from apps.api.tests.fake_openai import FakeRaw, body, usage
from apps.api.tests.test_feedback import generated_result
from apps.api.tests.test_firestore_integration import databases as databases_fixture
from apps.api.tests.test_lesson_provider_errors import lesson_payload

databases = databases_fixture
PREFIX = "/api/v1"
REPORTED_OUTPUT = 321
OUTCOMES = [
    "completed",
    "incomplete_max_tokens",
    "incomplete_other",
    "refusal",
    "invalid_output",
    "timeout",
    "provider_error",
]
# Sonuç -> (HTTP, hata kodu); provider_error mevcut işlem kodlarını korur.
EXPECTED = {
    "incomplete_max_tokens": (502, "ai_output_truncated"),
    "incomplete_other": (422, "ai_output_filtered"),
    "refusal": (422, "ai_refused"),
    "invalid_output": (502, "ai_invalid_output"),
    "timeout": (504, "ai_timeout"),
}
PROVIDER_ERROR = {"vision": "provider_unavailable", "lessons": "lesson_provider_unavailable", "interaction": "interaction_provider_unavailable"}
LIMITS = {"vision": 4096, "lessons": 16384, "interaction": 4096}


class AnyTokenVerifier:
    def verify(self, token):
        return AuthenticatedUser(uid=token)


def vision_output():
    return VisionProviderAnalysis(
        image_status="valid_math_question", is_valid_question=True, rejection_reason=None,
        subject="mathematics", exam_context="TYT", topic="Cebir", subtopic="Denklemler",
        question_type="open", language="tr", difficulty="easy", question_text="3x + 7 = 19",
        mathematical_expressions=["3x + 7 = 19"], answer_choices=[],
        visual_elements=VisualElements(has_diagram=False, has_graph=False, has_table=False, has_geometry_figure=False, description=None),
        ocr_uncertainties=[], confidence=0.97,
    )


VALID = {
    "vision": vision_output,
    "lessons": lambda: LessonDraftResponse.model_validate(lesson_payload()),
    "interaction": lambda: AdaptiveDraft(title="Daha sade", text="Önce iki taraftan 7 çıkaralım."),
}


def scripted(outcome, operation):
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    tokens = usage(output_tokens=REPORTED_OUTPUT)
    if outcome == "timeout":
        return APITimeoutError(request=request)
    if outcome == "provider_error":
        return InternalServerError("upstream", response=httpx.Response(500, request=request), body=None)
    if outcome == "completed":
        return body(VALID[operation](), tokens=tokens)
    if outcome == "incomplete_max_tokens":
        return body(text='{"learning_objectives":["yar', status="incomplete", reason="max_output_tokens", tokens=tokens)
    if outcome == "incomplete_other":
        return body(text=None, status="incomplete", reason="content_filter", tokens=tokens)
    if outcome == "refusal":
        return body(refusal=True, tokens=tokens)
    return body(text='{"unexpected": true}', tokens=tokens)


class ScriptedClient:
    def __init__(self, script):
        self.script, self.calls = script, []

        async def parse(**kwargs):
            self.calls.append(kwargs)
            item = self.script
            if isinstance(item, Exception):
                raise item
            return FakeRaw(item)

        self.responses = SimpleNamespace(with_raw_response=SimpleNamespace(parse=parse))

    async def close(self):
        pass


@pytest.fixture
def stack(databases, monkeypatch, tmp_path):
    db = databases[0]
    settings = Settings(environment="test")
    app = create_app(settings)
    holder = {}

    def factory(**kwargs):
        return holder["client"]

    for module in (vision_module, lesson_module, interaction_module):
        monkeypatch.setattr(module, "AsyncOpenAI", factory)
    students = StudentService(FirestoreStudentRepository(db), MemoryEngine())
    app.state.container = replace(
        app.state.container,
        token_verifier=AnyTokenVerifier(),
        student_service=students,
        share_service=ShareService(FirestoreShareRepository(db), settings),
        usage_tracker=UsageTracker(settings, db),
        vision_service=VisionService(OpenAIVisionProvider("fixture-key", "fixture", 5), LocalTemporaryImageStorage(tmp_path), 10 * 1024 * 1024, False),
        lesson_service=LessonService(OpenAILessonProvider("fixture-key", "fixture", 5), IsolatedMathAI(), BoardPlanner()),
        interaction_service=InteractionService(OpenAIInteractionProvider("fixture-key", "fixture", 5), IsolatedMathAI(), FirestorePracticeStore(db)),
    )
    return app, db, students, holder


def owned_counts(db, uid):
    def count(collection, field):
        return db.collection(collection).where(filter=FieldFilter(field, "==", uid)).count().get()[0][0].value

    return {
        "lessons": count("lessons", "student_id"),
        "lesson_analyses": count("lesson_analyses", "owner"),
        "interaction_events": count("interaction_events", "student_id"),
        "practice_questions": db.collection("practice_questions").count().get()[0][0].value,
        "shared_solutions": db.collection("shared_solutions").count().get()[0][0].value,
    }


def png():
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def prepare(operation, uid, students):
    """Önkoşul kaydı yazar ve (yol, istek argümanları) döndürür."""
    user = AuthenticatedUser(uid=uid)
    if operation == "vision":
        return PREFIX + "/vision/analyze", {"files": {"image": ("q.png", png(), "image/png")}}
    if operation == "lessons":
        analysis = generated_result().lesson.source_analysis.model_copy(update={"request_id": "analysis_" + uuid4().hex})
        students.save_analysis(user, analysis)
        return PREFIX + "/lessons/generate", {"json": {"analysis_id": analysis.request_id}}
    result = generated_result()
    result.lesson.lesson_plan_id = "lesson_" + uuid4().hex
    students.save_lesson(user, result)
    return f"{PREFIX}/lessons/{result.lesson.lesson_plan_id}/interact", {"json": {"action": "simplify"}}


def run(app, db, students, operation, uid):
    path, kwargs = prepare(operation, uid, students)
    baseline = owned_counts(db, uid)
    records = []
    handler = logging.Handler(logging.INFO)
    handler.emit = records.append
    usage_logger = logging.getLogger("teacherai.ai_usage")
    level = usage_logger.level
    usage_logger.addHandler(handler)
    usage_logger.setLevel(logging.INFO)
    try:
        response = TestClient(app).post(path, headers={"Authorization": f"Bearer {uid}"}, **kwargs)
    finally:
        usage_logger.removeHandler(handler)
        usage_logger.setLevel(level)
    lines = [json.loads(record.getMessage()) for record in records]
    return response, baseline, owned_counts(db, uid), lines


def output_counter(db, uid):
    key = f"{datetime.now(UTC).date()}_{sha256(uid.encode()).hexdigest()}"
    return db.collection("ai_output_usage").document(key).get().get("output_tokens")


@pytest.mark.parametrize("operation", ["vision", "lessons", "interaction"])
@pytest.mark.parametrize("outcome", OUTCOMES)
def test_provider_outcome_matrix(stack, operation, outcome):
    app, db, students, holder = stack
    uid = "u_" + uuid4().hex
    holder["client"] = ScriptedClient(scripted(outcome, operation))
    response, baseline, after, lines = run(app, db, students, operation, uid)

    assert len(holder["client"].calls) == 1
    assert len(lines) == 1 and lines[0]["outcome"] == outcome
    assert holder["client"].calls[0]["max_output_tokens"] == LIMITS[operation]
    if outcome in ("timeout", "provider_error"):
        assert output_counter(db, uid) == LIMITS[operation], "tüketimi bilinmeyen sonuçta rezervasyon korunur"
    else:
        assert output_counter(db, uid) == REPORTED_OUTPUT, "bildirilen çıktıya göre iade edilir"

    if outcome == "completed":
        assert response.status_code == 200, response.text
        return
    status, code = EXPECTED.get(outcome, (503, PROVIDER_ERROR[operation]))
    assert (response.status_code, response.json()["error"]) == (status, code)
    assert "data" not in response.json()
    assert after == baseline, "başarısız sonuçta hiçbir kayıt kalıcı hale gelmez"


@pytest.mark.parametrize("reason", ["unknown_reason", None])
def test_unknown_incomplete_reason_is_not_content_filter(stack, reason):
    app, db, students, holder = stack
    uid = "u_" + uuid4().hex
    holder["client"] = ScriptedClient(body(text="{}", status="incomplete", reason=reason, tokens=usage(output_tokens=5)))
    response, baseline, after, lines = run(app, db, students, "interaction", uid)
    assert (response.status_code, response.json()["error"]) == (502, "ai_output_incomplete")
    assert lines[0]["outcome"] == "incomplete_other" and lines[0]["outcome_reason"] == (reason or "unknown")
    assert after == baseline


def test_lesson_normalization_failure_is_invalid_output_not_success(stack):
    """Sağlayıcı completed dese de anlamsal doğrulama başarısızsa başarı gösterilmez."""
    app, db, students, holder = stack
    uid = "u_" + uuid4().hex
    broken = lesson_payload()
    broken["content"]["steps"][0]["explanation"] = "Önce {metin buraya} sonra işlemi yap."
    holder["client"] = ScriptedClient(body(text=json.dumps(broken), tokens=usage(output_tokens=7)))
    response, baseline, after, lines = run(app, db, students, "lessons", uid)
    assert (response.status_code, response.json()["error"]) == (502, "ai_invalid_output")
    assert [line["outcome"] for line in lines] == ["invalid_output"]
    assert after == baseline and output_counter(db, uid) == 7
