from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import pytest

from apps.api.app.core.gateway import begin_accounting, end_accounting, parse_response
from apps.api.app.core.settings import Settings
from apps.api.app.core.usage import UsageLimitExceeded, UsageTracker
from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.features.interactions.openai_provider import OpenAIInteractionProvider
from apps.api.app.features.interactions.schemas import AdaptiveDraft
from apps.api.app.features.lessons.exceptions import VerificationContradictionError
from apps.api.app.features.lessons.service import LessonService
from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.mathai.parser import MathParseError, expression
from apps.api.app.features.mathai.isolated import IsolatedMathAI
from apps.api.app.features.mathai.service import MathAIService
from apps.api.app.main import create_app
from apps.api.tests.client import authenticated_client
from apps.api.tests.test_feedback import generated_result
from apps.api.tests.test_interactions import service as interaction_service
from apps.api.tests.test_lesson_pipeline import AlgebraLessonProvider
from apps.api.tests.test_mathai import plan
from apps.api.tests.fake_openai import raw_responses

PREFIX = "/api/v1"
OTHER = {"Authorization": "Bearer student-b"}


@pytest.mark.parametrize(
    "route",
    [
        "/vision/analyze",
        "/vision/preview",
        "/lessons/generate",
        "/lessons/id/interact",
        "/lessons/id/practice/p/answer",
        "/students/me/lessons",
        "/shares",
        "/feedback",
    ],
)
def test_post_requires_auth_before_reading_body(route):
    app = create_app()
    authenticated_client(app)
    client = TestClient(app)
    for headers in ({}, {"Authorization": "Bearer invalid"}):
        assert (
            client.post(PREFIX + route, content=b"{}", headers=headers).status_code
            == 401
        )


def test_admission_quotas_and_duplicate_key():
    app = create_app(
        Settings(
            operation_limits={"analyze": 1, "generate": 2, "preview": 1},
            authenticated_daily_ai_limit=1,
        )
    )
    client = authenticated_client(app)
    assert (
        client.post(
            PREFIX + "/vision/analyze", headers={"Idempotency-Key": "1"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            PREFIX + "/vision/analyze", headers={"Idempotency-Key": "1"}
        ).status_code
        == 409
    )
    assert client.post(PREFIX + "/vision/analyze").status_code == 429
    assert (
        client.post(
            PREFIX + "/lessons/generate", json={"analysis_id": "ref"}
        ).status_code
        == 429
    )
    assert client.post(PREFIX + "/vision/preview").status_code == 400
    assert client.post(PREFIX + "/vision/preview").status_code == 429
    assert client.post(PREFIX + "/vision/analyze", headers=OTHER).status_code == 400


def test_unavailable_quota_or_disabled_provider_fails_closed(monkeypatch):
    app = create_app()
    client = authenticated_client(app)

    def unavailable(*args):
        raise RuntimeError("private detail")

    monkeypatch.setattr(app.state.container.usage_tracker, "record", unavailable)
    response = client.post(PREFIX + "/vision/analyze")
    assert response.status_code == 503 and "private detail" not in response.text
    monkeypatch.setattr(app.state.container.settings, "ai_enabled", False)
    assert client.post(PREFIX + "/vision/analyze").status_code == 503


def test_atomic_memory_quota():
    tracker = UsageTracker(Settings(operation_limits={"generate": 3}))

    def attempt(i):
        try:
            tracker.record("u", "generate")
            return 1
        except UsageLimitExceeded:
            return 0

    with ThreadPoolExecutor(8) as pool:
        assert sum(pool.map(attempt, range(20))) == 3


def test_chunked_body_limit_and_appcheck(monkeypatch):
    app = create_app(Settings(max_json_bytes=1024, app_check_mode="enforce"))
    client = authenticated_client(app)
    assert client.get(PREFIX + "/students/me/history").status_code == 403
    monkeypatch.setattr(
        "firebase_admin.app_check.verify_token",
        lambda token, **kwargs: {"app_id": "test"},
    )
    headers = {"X-Firebase-AppCheck": "token"}
    assert (
        client.get(PREFIX + "/students/me/history", headers=headers).status_code == 200
    )
    response = client.post(
        PREFIX + "/lessons/generate",
        content=iter([b"x" * 600, b"x" * 600]),
        headers=headers,
    )
    assert response.status_code == 413


def test_owned_sources_and_legacy_tampering():
    app = create_app()
    provider = AlgebraLessonProvider()
    app.state.container = replace(
        app.state.container,
        lesson_service=LessonService(provider, MathAIService(), BoardPlanner()),
    )
    client = authenticated_client(app)
    source = plan().source_analysis
    app.state.container.student_service.save_analysis(
        AuthenticatedUser(uid="student-a"), source
    )
    altered = source.model_dump()
    altered["question_text"] = "untrusted"
    assert (
        client.post(
            PREFIX + "/lessons/generate", json={"analysis": altered}, headers=OTHER
        ).status_code
        == 404
    )
    response = client.post(PREFIX + "/lessons/generate", json={"analysis": altered})
    result = response.json()["data"]
    assert result["lesson"]["source_analysis"]["question_text"] == source.question_text
    lesson_id = result["lesson"]["lesson_plan_id"]
    result["verification"]["status"] = "failed"
    result["lesson"]["content"]["strategy"] = "untrusted"
    assert (
        client.post(PREFIX + "/students/me/lessons", json={"result": result}).json()[
            "data"
        ]["verification_status"]
        == "verified"
    )
    path = PREFIX + f"/lessons/{lesson_id}/interact"
    body = {"action": "understood", "lesson": result["lesson"]}
    assert "untrusted" not in client.post(path, json=body).json()["data"]["message"]
    for route, payload in [
        (path, body),
        (PREFIX + "/shares", {"lesson_id": lesson_id}),
        (PREFIX + "/students/me/lessons", {"result": result}),
    ]:
        assert client.post(route, json=payload, headers=OTHER).status_code == 404
    assert (
        client.post(PREFIX + "/shares", json={"lesson_id": "fabricated"}).status_code
        == 404
    )
    share = client.post(PREFIX + "/shares", json={"result": result}).json()["data"]
    public = TestClient(app).get(PREFIX + "/shares/" + share["share_id"]).text
    assert "untrusted" not in public and source.question_text not in public


def test_practice_flow_and_retries():
    app = create_app()
    app.state.container = replace(
        app.state.container, interaction_service=interaction_service()
    )
    client = authenticated_client(app, lesson=generated_result())
    base = PREFIX + "/lessons/lesson_1"
    response = client.post(
        base + "/interact", json={"action": "similar_example"}
    ).json()["data"]
    pid = response["practice"]["practice_question_id"]
    path = f"{base}/practice/{pid}/answer"
    assert client.post(path, json={"answer": "4"}, headers=OTHER).status_code == 404
    for answer, correct, attempt in [
        ("2", False, 1),
        ("2", False, 1),
        ("4", True, 2),
        ("4", True, 2),
    ]:
        feedback = client.post(path, json={"answer": answer}).json()["data"]
        assert (feedback["correct"], feedback["attempt_number"]) == (correct, attempt)
    assert client.post(path, json={"answer": "9"}).status_code == 409
    stats = client.get(PREFIX + "/students/me/dashboard").json()["data"]
    assert (stats["practice_attempts"], stats["practice_correct"]) == (2, 1)


@pytest.mark.parametrize("sign", ["±", r"\pm"])
def test_plus_minus_is_a_solution_set(sign):
    service = MathAIService()
    assert service.check_answer(f"x=1{sign}2", f"x=1{sign}2") == (True, "unknown")
    assert service.check_answer(f"x=1{sign}2", "3") == (False, "missing_case")
    p = plan(original="(x-1)^2=4")
    p.content.steps = p.content.steps[-1:]
    p.content.steps[0].expressions[0].latex = f"x=1{sign}2"
    p.content.final_answer_expressions[0].latex = r"x \in \{-1,3\}"
    p.content.final_answer = f"x=1{sign}2"
    assert service.verify(p).status == "verified"
    p.content.final_answer_expressions[0].latex = "sin 1,3"
    assert not service.verify(p).final_answer_verified


@pytest.mark.parametrize(
    "value", ["2^100000", "(x^10)^9", "1" * 401, "a+b+c+d+e", "x+" * 90 + "1", "sin(x)"]
)
def test_parser_budgets(value):
    with pytest.raises(MathParseError):
        expression(value)


def test_symbolic_worker_covers_normal_path_and_kills_timeout(monkeypatch):
    assert IsolatedMathAI().check_answer("2x=8", "4", "x")[0]
    monkeypatch.setattr(IsolatedMathAI, "timeout_seconds", 0.001)
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        IsolatedMathAI().verify(plan())
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_bad_transformation_is_never_delivered():
    class BadStep(AlgebraLessonProvider):
        async def generate_lesson_plan(self, *args, **kwargs):
            result = await super().generate_lesson_plan(*args, **kwargs)
            result.draft.content.steps[0].expressions[0].latex = "3x=14"
            return result

    provider = BadStep()
    with pytest.raises(VerificationContradictionError):
        await LessonService(provider, MathAIService(), BoardPlanner()).generate(
            plan().source_analysis
        )
    assert len(provider.analysis_payloads) == 2


@pytest.mark.asyncio
async def test_provider_accounting_and_budget(monkeypatch):
    settings = Settings(
        max_output_tokens=128,
        daily_output_tokens=150,
        pricing_version="fixture",
        model_prices={"model": (1, 0.5, 2)},
    )
    tracker = UsageTracker(settings)
    usage = SimpleNamespace(
        input_tokens=30,
        output_tokens=25,
        total_tokens=55,
        input_tokens_details=SimpleNamespace(cached_tokens=10),
        output_tokens_details=SimpleNamespace(reasoning_tokens=3),
    )
    parse = AsyncMock(
        return_value=SimpleNamespace(usage=usage, status="completed", model="model", output_parsed={"ok": True})
    )
    logs = []
    monkeypatch.setattr(
        "logging.Logger.info",
        lambda self, msg, *args, **kwargs: logs.append(json.loads(msg)),
    )
    scope = begin_accounting("request", settings, tracker, "student")
    try:
        client = SimpleNamespace(responses=raw_responses(parse))
        await parse_response(client, "vision", model="model", input=["private"])
        with pytest.raises(UsageLimitExceeded):
            await parse_response(client, "vision", model="model", input=["private"])
    finally:
        end_accounting(scope)
    assert list(tracker.output.values()) == [25]
    assert parse.call_count == 1 and parse.call_args.kwargs["max_output_tokens"] == 128
    assert logs[0]["estimated_usd"] == pytest.approx(0.000075)
    assert logs[0]["request_id"] == "request" and logs[0]["reasoning_tokens"] == 3
    assert "private" not in str(logs) and "student" not in str(logs)


@pytest.mark.asyncio
async def test_interaction_compaction_preserves_teaching_policy():
    provider = OpenAIInteractionProvider(
        "fixture", "model", 1, context_budget_bytes=4300
    )
    lesson = plan()
    lesson.content.question_understanding = "uzun " * 500
    lesson.content.strategy = "uzun " * 500
    lesson.content.steps[0].explanation = "uzun " * 500
    lesson.source_analysis.visual_elements.description = "uzun " * 500
    context = SimpleNamespace(
        model_dump=lambda **kwargs: {"grade_policy": "yalnız temel yöntem"}
    )
    parse = AsyncMock(
        return_value=SimpleNamespace(
            output_parsed=AdaptiveDraft(title="İpucu", text="İki taraftan çıkar.")
        )
    )
    await provider._adapt_with_context(
        SimpleNamespace(responses=raw_responses(parse)),
        "hint",
        lesson,
        1,
        context,
        "normal",
    )
    payload = json.loads(parse.call_args.kwargs["input"][1]["content"])
    assert payload["teaching_context"]["grade_policy"] == "yalnız temel yöntem"
    assert not payload["interaction_context"]["problem"]["visual_facts"]


def test_cached_identity_and_local_interaction_when_ai_is_off(monkeypatch):
    app = create_app(Settings(ai_enabled=False))
    client = authenticated_client(app, lesson=generated_result())
    verifier = app.state.container.token_verifier
    original = verifier.verify
    calls = []

    def verify(token):
        calls.append(token)
        return original(token)

    monkeypatch.setattr(verifier, "verify", verify)
    path = PREFIX + "/lessons/lesson_1/interact"
    assert client.post(path, json={"action": "understood"}).status_code == 200
    assert len(calls) == 1
    assert client.post(path, json={"action": "simplify"}).status_code == 503
    assert len(calls) == 2
