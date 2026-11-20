"""C paketi: küresel AI bütçesi tek UTC gün belgesinde, kullanıcı sayacıyla aynı işlemde."""

import contextlib
import json
import random
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from google.api_core.exceptions import ServiceUnavailable

import apps.api.app.core.usage as usage_module
import apps.api.app.features.lessons.openai_provider as lesson_module
from apps.api.app.core.gateway import begin_accounting, end_accounting, parse_response
from apps.api.app.core.settings import Settings
from apps.api.app.core.usage import GlobalBudgetExhausted, UsageTracker
from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.lessons.openai_provider import OpenAILessonProvider
from apps.api.app.features.lessons.service import LessonService
from apps.api.app.features.mathai.isolated import IsolatedMathAI
from apps.api.app.main import create_app
from apps.api.tests.fake_openai import FakeRaw, body, fake_client, usage
from apps.api.tests.test_feedback import generated_result
from apps.api.tests.test_firestore_integration import databases as databases_fixture
from apps.api.tests.test_lesson_provider_errors import lesson_payload

databases = databases_fixture
PREFIX = "/api/v1"


class Clock:
    """Enjekte edilen UTC saati; her test kendi uzak gününü kullanır, emülatör verisiyle çakışmaz."""

    def __init__(self):
        self.now = datetime(2300, 1, 1, tzinfo=UTC) + timedelta(days=random.randrange(1, 200_000))

    def __call__(self):
        return self.now


def global_doc(db, clock):
    return db.collection("ai_global_usage").document(clock().date().isoformat()).get().to_dict() or {}


def admit(trackers):
    def run(index):
        try:
            trackers[index % len(trackers)].record("u_" + uuid4().hex, "generate")
            return "accepted"
        except GlobalBudgetExhausted:
            return "global"
        except HTTPException as exc:
            return f"http_{exc.status_code}"

    return run


def test_fifty_concurrent_admissions_never_exceed_twenty(databases):
    clock = Clock()
    settings = Settings(global_daily_paid_operations=20)
    trackers = [UsageTracker(settings, db, clock) for db in databases]
    with ThreadPoolExecutor(50) as pool:
        results = list(pool.map(admit(trackers), range(50)))
    assert results.count("accepted") == 20 and results.count("global") == 30
    assert global_doc(databases[0], clock)["http_operations"] == 20
    # Sınıra ulaşıldıktan sonraki ardışık isteklerin tamamı reddedilir.
    assert [admit(trackers)(i) for i in range(5)] == ["global"] * 5


def test_without_process_lock_firestore_alone_keeps_the_limit(databases, monkeypatch):
    """Yerel kilit yokken (farklı Cloud Run örnekleri gibi) yalnız Firestore işlemi sınırı korur."""
    monkeypatch.setattr(usage_module, "usage_lock", lambda key: contextlib.nullcontext())
    clock = Clock()
    settings = Settings(global_daily_paid_operations=20)
    trackers = [UsageTracker(settings, db, clock) for db in databases]
    with ThreadPoolExecutor(50) as pool:
        results = list(pool.map(admit(trackers), range(50)))
    accepted = results.count("accepted")
    # Güvenlik özelliği: sınır asla aşılmaz. Çakışan işlemler 503 ile reddedilir (fail closed);
    # tek belgedeki yoğun çakışmanın verim etkisi raporda ölçümüyle belgelenir.
    assert accepted <= 20
    assert set(results) <= {"accepted", "global", "http_503"}
    assert global_doc(databases[0], clock).get("http_operations", 0) == accepted


def test_fifty_concurrent_provider_calls_never_exceed_twenty(databases):
    clock = Clock()
    settings = Settings(global_daily_provider_calls=20)
    trackers = [UsageTracker(settings, db, clock) for db in databases]

    def reserve(index):
        try:
            return trackers[index % 2].reserve_output("u_" + uuid4().hex, 100)
        except GlobalBudgetExhausted:
            return None

    with ThreadPoolExecutor(50) as pool:
        accepted = [item for item in pool.map(reserve, range(50)) if item]
    doc = global_doc(databases[0], clock)
    assert len(accepted) == 20
    assert doc["provider_calls"] == 20 and doc["reserved_output_tokens"] == 2000


def test_global_output_tokens_are_reserved_and_released_once(databases):
    clock = Clock()
    settings = Settings(global_daily_output_tokens=3000)
    tracker = UsageTracker(settings, databases[0], clock)
    held = [tracker.reserve_output("u_" + uuid4().hex, 1000) for _ in range(3)]
    with pytest.raises(GlobalBudgetExhausted):
        tracker.reserve_output("u_" + uuid4().hex, 1000)
    assert tracker.release_output(held[0], 600, usd=0.25) is True
    assert tracker.release_output(held[0], 600, usd=0.25) is False, "aynı çağrının iadesi ikinci kez yapılmaz"
    doc = global_doc(databases[0], clock)
    assert doc["reserved_output_tokens"] == 2400 and doc["estimated_usd"] == pytest.approx(0.25)
    for item in held[1:]:
        tracker.release_output(item, 50_000)
    assert global_doc(databases[0], clock)["reserved_output_tokens"] == 400, "iade sayacı negatif yapmaz"


def test_counter_restarts_at_utc_day_boundary(databases):
    clock = Clock()
    clock.now = clock.now.replace(hour=23, minute=59, second=59)
    tracker = UsageTracker(Settings(global_daily_paid_operations=2), databases[0], clock)
    for _ in range(2):
        tracker.record("u_" + uuid4().hex, "analyze")
    with pytest.raises(GlobalBudgetExhausted):
        tracker.record("u_" + uuid4().hex, "analyze")
    first_day = clock().date().isoformat()
    clock.now += timedelta(seconds=2)
    tracker.record("u_" + uuid4().hex, "analyze")
    assert global_doc(databases[0], clock)["http_operations"] == 1
    day = databases[0].collection("ai_global_usage").document(first_day).get().to_dict()
    assert day["http_operations"] == 2
    assert day["expires_at"] - day["created_at"] == timedelta(days=30)


# HTTP yolları -------------------------------------------------------------


class AnyTokenVerifier:
    def verify(self, token):
        return AuthenticatedUser(uid=token)


def lesson_app(monkeypatch, settings, tracker, responses):
    calls = []

    async def parse(**kwargs):
        calls.append(kwargs)
        return FakeRaw(responses.pop(0))

    monkeypatch.setattr(lesson_module, "AsyncOpenAI", lambda **kwargs: SimpleNamespace(responses=fake_client(parse).responses, close=AsyncMock()))
    app = create_app(settings)
    app.state.container = replace(
        app.state.container,
        token_verifier=AnyTokenVerifier(),
        usage_tracker=tracker,
        lesson_service=LessonService(OpenAILessonProvider("fixture-key", "fixture", 5), IsolatedMathAI(), BoardPlanner()),
    )
    return app, calls


def generate(app, uid):
    analysis = generated_result().lesson.source_analysis.model_copy(update={"request_id": "analysis_" + uuid4().hex})
    app.state.container.student_service.save_analysis(AuthenticatedUser(uid=uid), analysis)
    return TestClient(app).post(PREFIX + "/lessons/generate", headers={"Authorization": f"Bearer {uid}"}, json={"analysis_id": analysis.request_id})


def lesson_body(final="x = 4"):
    payload = lesson_payload()
    payload["content"]["final_answer"] = final
    payload["content"]["final_answer_expressions"] = [{"type": "equation", "latex": final}]
    payload["content"]["steps"][-1]["expressions"] = [{"type": "equation", "latex": final}]
    return body(text=json.dumps(payload), tokens=usage(output_tokens=200))


def test_requests_after_global_limit_get_503_without_provider_call(monkeypatch):
    clock = Clock()
    settings = Settings(global_daily_paid_operations=1)
    tracker = UsageTracker(settings, None, clock)
    app, calls = lesson_app(monkeypatch, settings, tracker, [lesson_body()])
    assert generate(app, "u_" + uuid4().hex).status_code == 200
    for _ in range(3):
        response = generate(app, "u_" + uuid4().hex)
        assert (response.status_code, response.json()["error"]) == (503, "ai_global_budget_exhausted")
    assert len(calls) == 1


def test_math_correction_call_counts_as_separate_provider_call(monkeypatch):
    clock = Clock()
    settings = Settings()
    tracker = UsageTracker(settings, None, clock)
    app, calls = lesson_app(monkeypatch, settings, tracker, [lesson_body("x = 5"), lesson_body("x = 4")])
    response = generate(app, "u_" + uuid4().hex)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["correction_attempted"] is True
    day = tracker.globals[clock().date().isoformat()]
    assert len(calls) == 2
    assert day["http_operations"] == 1 and day["provider_calls"] == 2


class BrokenDb:
    def collection(self, name):
        raise ServiceUnavailable("firestore down")

    def transaction(self, **kwargs):
        raise ServiceUnavailable("firestore down")


def test_firestore_outage_fails_closed_before_provider(monkeypatch):
    settings = Settings()
    app, calls = lesson_app(monkeypatch, settings, UsageTracker(settings, BrokenDb()), [lesson_body()])
    response = generate(app, "u_" + uuid4().hex)
    assert response.status_code == 503
    assert calls == []


@pytest.mark.asyncio
async def test_reservation_outage_never_calls_provider():
    tracker = UsageTracker(Settings(), BrokenDb())
    parse = AsyncMock()
    token = begin_accounting("req", tracker.settings, tracker, "uid")
    try:
        with pytest.raises(HTTPException) as caught:
            await parse_response(fake_client(parse), "vision", model="fixture")
    finally:
        end_accounting(token)
    assert caught.value.status_code == 503
    parse.assert_not_called()


@pytest.mark.parametrize(
    ("ai_enabled", "global_operations", "expected"),
    [
        (False, 2000, "http_error"),
        (True, 0, "ai_global_budget_exhausted"),
    ],
)
def test_kill_switch_and_zero_budget_close_paid_paths_independently(monkeypatch, ai_enabled, global_operations, expected):
    settings = Settings(ai_enabled=ai_enabled, global_daily_paid_operations=global_operations)
    tracker = UsageTracker(settings, None, Clock())
    app, calls = lesson_app(monkeypatch, settings, tracker, [lesson_body()])
    response = generate(app, "u_" + uuid4().hex)
    assert (response.status_code, response.json()["error"]) == (503, expected)
    assert calls == []
    # Ücretsiz önizleme her iki durumda da çalışmaya devam eder.
    preview = TestClient(app).post(PREFIX + "/vision/preview", headers={"Authorization": "Bearer u_preview"}, files={"image": ("q.png", _png(), "image/png")})
    assert preview.status_code == 200


def test_zero_provider_call_budget_blocks_before_call():
    tracker = UsageTracker(Settings(global_daily_provider_calls=0), None, Clock())
    with pytest.raises(GlobalBudgetExhausted):
        tracker.reserve_output("uid", 100)


def _png():
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), "white").save(buffer, format="PNG")
    return buffer.getvalue()
