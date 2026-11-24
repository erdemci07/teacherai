"""TA-005B §8: Anthropic adaptörü. Yalnız sahte HTTP yanıtları (httpx.MockTransport); gerçek çağrı yoktur.

Uyum testi (iki adaptörden aynı kanonik nesne) bir kalite ölçümü değildir; yalnız dönüşümün
sağlayıcıdan bağımsız olduğunu gösterir.
"""

import base64
import io
import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

import apps.api.app.features.lessons.openai_provider as lesson_module
from apps.api.app.core.ai_outcomes import (
    AIInvalidOutputError,
    AIOutcomeError,
    AIOutputTruncatedError,
    AIRefusalError,
    AITimeoutError,
)
from apps.api.app.core.ai_port import ImagePart, ProviderRequest, TextPart
from apps.api.app.core.anthropic_adapter import API_VERSION, URL, AnthropicAdapter, usage_of
from apps.api.app.core.gateway import begin_accounting, end_accounting, invoke
from apps.api.app.core.operations import Operation
from apps.api.app.core.settings import Settings
from apps.api.app.core.usage import GlobalBudgetExhausted, UsageTracker
from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.lessons.normalization import normalize_lesson_draft_response
from apps.api.app.features.lessons.openai_provider import AnthropicLessonProvider, OpenAILessonProvider
from apps.api.app.features.lessons.schemas import LessonDraftResponse
from apps.api.app.features.lessons.service import LessonService
from apps.api.app.features.mathai.service import MathAIService
from apps.api.app.main import create_app
from apps.api.tests.fake_openai import FakeRaw, body, fake_client
from apps.api.tests.test_global_budget import AnyTokenVerifier, Clock, generated_result, lesson_body
from apps.api.tests.test_lesson_provider_errors import lesson_payload
from apps.api.tests.test_question_integrity import analysis

PAYLOAD = json.dumps(lesson_payload(), ensure_ascii=False)


def message(text=PAYLOAD, stop="end_turn", usage=None, status=200):
    usage = {"input_tokens": 40, "output_tokens": 30, "cache_read_input_tokens": 10,
             "cache_creation_input_tokens": 0} if usage is None else usage
    content = [{"type": "text", "text": text}] if text is not None else []
    return httpx.Response(status, headers={"request-id": "req_anthropic"},
                          json={"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-sonnet-5-5",
                                "content": content, "stop_reason": stop, "usage": usage})


def transport(*responses, seen=None):
    queue = list(responses)

    def handler(request):
        if seen is not None:
            seen.append(request)
        reply = queue.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    return httpx.MockTransport(handler)


def request(**kw):
    return ProviderRequest(Operation.LESSONS, "claude-sonnet-5-5", user="bağlam", system="istem",
                           schema=LessonDraftResponse, timeout=5, **kw)


async def call(adapter, req=None, settings=None, tracker=None):
    token = begin_accounting("req", settings or Settings(_env_file=None), tracker or Mock(), "uid")
    try:
        return await invoke(adapter, req or request(), validate=normalize_lesson_draft_response)
    finally:
        end_accounting(token)


@pytest.mark.asyncio
async def test_successful_canonical_conversion_and_request_shape():
    seen = []
    reply = await call(AnthropicAdapter("key", transport=transport(message(), seen=seen)))
    sent = seen[0]
    assert str(sent.url) == URL and sent.method == "POST"
    assert sent.headers["x-api-key"] == "key" and sent.headers["anthropic-version"] == API_VERSION
    data = json.loads(sent.content)
    assert data["model"] == "claude-sonnet-5-5" and data["max_tokens"] == 16384 and data["system"] == "istem"
    assert data["messages"] == [{"role": "user", "content": "bağlam"}]
    assert data["output_config"]["format"]["type"] == "json_schema"
    assert "reasoning" not in data and "thinking" not in data and "tools" not in data
    assert reply.output_parsed.content.final_answer == lesson_payload()["content"]["final_answer"]
    assert reply.id == "msg_1"


@pytest.mark.asyncio
@pytest.mark.parametrize(("response", "error"), [
    (message(stop="max_tokens", text='{"yarım'), AIOutputTruncatedError),
    (message(stop="refusal", text=None), AIRefusalError),
    # TA-005C: belge "yanıtı kesilmiş say" der (handling-stop-reasons); kesilme sınıfına düşer.
    (message(stop="model_context_window_exceeded", text=None), AIOutputTruncatedError),
    (message(stop="tool_use"), AIOutcomeError),  # eşlenemeyen değer: provider_error
    (message(stop="pause_turn"), AIOutcomeError),
    (message(stop=None), AIOutcomeError),
    (message(text="json değil"), AIInvalidOutputError),
    (message(text='{"learning_objectives": []}'), AIInvalidOutputError),  # şemaya uymayan çıktı
    (message(text=None), AIInvalidOutputError),
    (httpx.Response(529, json={"type": "error"}), AIOutcomeError),
    (httpx.Response(200, content=b"<html>"), AIInvalidOutputError),
])
async def test_stop_reasons_and_bad_output_map_to_outcome_classes(response, error):
    with pytest.raises(error) as caught:
        await call(AnthropicAdapter("key", transport=transport(response)))
    if error is AIOutcomeError:
        assert type(caught.value) is AIOutcomeError and caught.value.outcome == "provider_error"


@pytest.mark.asyncio
async def test_timeout_keeps_reservation():
    tracker = Mock()
    tracker.reserve_output.return_value = "r"
    with pytest.raises(AITimeoutError):
        await call(AnthropicAdapter("key", transport=transport(httpx.ReadTimeout("yavaş"))), tracker=tracker)
    tracker.release_output.assert_not_called()  # tüketim bilinmiyor


def capture_logs(monkeypatch):
    logs = []

    def info(self, msg, *args, **kwargs):
        if self.name == "teacherai.ai_usage":
            logs.append(json.loads(msg))

    monkeypatch.setattr("logging.Logger.info", info)
    return logs


@pytest.mark.asyncio
async def test_missing_usage_is_not_guessed_and_cost_is_not_invented(monkeypatch):
    tracker = Mock()
    tracker.reserve_output.return_value = "r"
    logs = capture_logs(monkeypatch)
    await call(AnthropicAdapter("key", transport=transport(message(usage={}))), tracker=tracker)
    event = logs[-1]
    assert event["input_tokens"] is None and event["output_tokens"] is None and "estimated_usd" not in event
    assert event["provider"] == "anthropic" and event["reservation"] == "kept"
    assert usage_of({"input_tokens": 5, "cache_read_input_tokens": 3, "cache_creation_input_tokens": 2,
                     "output_tokens": 1}).cached_input is None  # önbellek yazımı: maliyet hesaplanmaz


@pytest.mark.asyncio
async def test_priced_usage_counts_cache_reads_once(monkeypatch):
    logs = capture_logs(monkeypatch)
    await call(AnthropicAdapter("key", transport=transport(message())))
    event = logs[-1]
    assert (event["input_tokens"], event["cached_tokens"], event["output_tokens"]) == (50, 10, 30)
    assert event["estimated_usd"] == pytest.approx((40 * 2 + 10 * 0.10 + 30 * 10) / 1_000_000)


@pytest.mark.asyncio
async def test_global_budget_exhaustion_sends_nothing():
    seen = []
    tracker = Mock()
    tracker.reserve_output.side_effect = GlobalBudgetExhausted
    with pytest.raises(GlobalBudgetExhausted):
        await call(AnthropicAdapter("key", transport=transport(message(), seen=seen)), tracker=tracker)
    assert seen == []


@pytest.mark.asyncio
async def test_student_images_are_not_sent_without_flag_and_limits_apply():
    seen = []
    png = tiny_png()  # TA-005C: boyut denetimi için okunabilir (sentetik, 2×2) görsel gerekir
    image = request().__class__(Operation.LESSONS, "claude-sonnet-5-5", user=(TextPart("oku"), ImagePart(png, "image/png")),
                                schema=LessonDraftResponse)
    with pytest.raises(AIOutcomeError) as caught:
        await call(AnthropicAdapter("key", transport=transport(message(), seen=seen)), image)
    assert caught.value.reason == "student_images_not_allowed" and seen == []
    bmp = replace(image, user=(ImagePart(b"BM", "image/bmp"),))
    with pytest.raises(AIOutcomeError, match="ai_provider_error") as caught:
        await call(AnthropicAdapter("key", allow_images=True, transport=transport(message(), seen=seen)), bmp)
    assert caught.value.reason == "image_media_type" and seen == []
    await call(AnthropicAdapter("key", allow_images=True, transport=transport(message(), seen=seen)), image)
    block = json.loads(seen[0].content)["messages"][0]["content"][1]
    assert block == {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                 "data": base64.b64encode(png).decode("ascii")}}


def tiny_png(size=(2, 2)):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, format="PNG")
    return buffer.getvalue()


def anthropic_app(monkeypatch, responses, seen):
    settings = Settings(provider_lesson="anthropic", anthropic_api_key="key", anthropic_lesson_model="claude-sonnet-5-5")
    tracker = UsageTracker(settings, None, Clock())
    app = create_app(settings)
    provider = AnthropicLessonProvider("key", "claude-sonnet-5-5", 5, transport=transport(*responses, seen=seen))
    app.state.container = replace(app.state.container, token_verifier=AnyTokenVerifier(), usage_tracker=tracker,
                                  lesson_service=LessonService(provider, MathAIService(), BoardPlanner()))
    return app


def anthropic_lesson():
    data = json.loads(lesson_body()["output"][0]["content"][0]["text"])
    return message(text=json.dumps(data, ensure_ascii=False))


def test_same_idempotency_key_runs_the_paid_call_once(monkeypatch):
    seen = []
    app = anthropic_app(monkeypatch, [anthropic_lesson(), anthropic_lesson()], seen)
    uid = "u_" + uuid4().hex
    source = generated_result().lesson.source_analysis.model_copy(update={"request_id": "analysis_" + uuid4().hex})
    app.state.container.student_service.save_analysis(AuthenticatedUser(uid=uid), source)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {uid}", "Idempotency-Key": "anth-1"}
    first = client.post("/api/v1/lessons/generate", json={"analysis_id": source.request_id}, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["data"]["lesson"]["provider"] == "anthropic"
    again = client.post("/api/v1/lessons/generate", json={"analysis_id": source.request_id}, headers=headers)
    assert (again.status_code, again.json()["error"]) == (409, "duplicate_request") and len(seen) == 1


def test_account_deletion_in_progress_blocks_the_call(monkeypatch):
    seen = []
    app = anthropic_app(monkeypatch, [anthropic_lesson()], seen)
    uid = "u_" + uuid4().hex
    source = generated_result().lesson.source_analysis.model_copy(update={"request_id": "analysis_" + uuid4().hex})
    app.state.container.student_service.save_analysis(AuthenticatedUser(uid=uid), source)
    monkeypatch.setattr("apps.api.app.core.admission.deletion_started", lambda db, user: True)
    response = TestClient(app).post("/api/v1/lessons/generate", json={"analysis_id": source.request_id},
                                    headers={"Authorization": f"Bearer {uid}"})
    assert (response.status_code, response.json()["error"]) == (409, "account_deletion_in_progress") and seen == []


# --- uyum: iki adaptör aynı kanonik nesneyi ve doğrulama sonucunu üretir (kalite ölçümü değildir) ---

FIXTURES = {
    "ic_ice_kok": (r"\sqrt{5+\sqrt{16}}", "3", ["A) 3", "B) 9", "C) 1", "D) 5"]),
    "kesir_cizgisi": (r"\frac{1+2}{3}", "1", ["A) 1", "B) 3", "C) 7/3", "D) 2"]),
    "negatif_isaret": ("-2^2", "-4", ["A) 4", "B) -4", "C) -2", "D) 2"]),
    "gizli_sik": (r"\sqrt{16}+1", "5", ["A) 3", "B) 5", "C) 17", "D) 4"]),
    "istenen_hedef": ("2x = 8", "5", ["A) 4", "B) 5", "C) 8", "D) 9"]),
}
SUBJECTS = {"birimli_fizik": "physics", "kimyasal_formul": "chemistry"}


def fixture_analysis(name):
    if name in FIXTURES:
        expression, _, choices = FIXTURES[name]
        question = "2x = 8 ise x + 1 kaçtır?" if name == "istenen_hedef" else f"{expression} işleminin sonucu kaçtır?"
        return analysis(question_text=question, mathematical_expressions=[expression], answer_choices=choices)
    if name in SUBJECTS:
        return analysis(question_text="Hız 20 m/s ise 5 s'de kaç m gider?" if name == "birimli_fizik" else "H2O kaç atom içerir?",
                        mathematical_expressions=["v = 20"], answer_choices=["A) 100", "B) 4"]).model_copy(
            update={"subject": SUBJECTS[name]})
    if name == "eksik_bilgi":
        from apps.api.tests.test_question_integrity import SIGN

        return analysis(question_text="3x + 7 = 19 ise x kaçtır?", mathematical_expressions=["3x + 7 = 19"],
                        answer_choices=["A) 2", "B) 3", "C) 4", "D) 5"], confidence=1.0, **SIGN)
    return analysis(question_text="a = 2 ve b = a + 3 ise b kaçtır?", mathematical_expressions=["a = 2", "b = a + 3"],
                    answer_choices=["A) 5", "B) 2", "C) 3", "D) 6"])  # öncül


def fixture_payload(name):
    final = FIXTURES.get(name, (None, "5", None))[1]
    payload = lesson_payload()
    payload["content"].update(known_values=[], unknown="istenen değer", final_answer=final,
                              final_answer_expressions=[{"type": "expression", "latex": final}],
                              steps=[{"id": "step_1", "type": "result", "title": "Hesapla", "explanation": "Hesaplanır.",
                                      "expressions": [{"type": "expression", "latex": final}], "visual_reference": None}])
    return json.dumps(payload, ensure_ascii=False)


async def outcome(provider_name, name, monkeypatch):
    text = fixture_payload(name)
    if provider_name == "openai":
        async def parse(**kwargs):
            return FakeRaw(body(text=text))

        monkeypatch.setattr(lesson_module, "AsyncOpenAI",
                            lambda **kw: SimpleNamespace(responses=fake_client(parse).responses, close=AsyncMock()))
        provider = OpenAILessonProvider("key", "claude-sonnet-5-5", 5)
    else:
        repeat = httpx.MockTransport(lambda request: message(text=text))  # düzeltme turunda aynı yanıt
        provider = AnthropicLessonProvider("key", "claude-sonnet-5-5", 5, transport=repeat)
    try:
        result = await LessonService(provider, MathAIService(), BoardPlanner()).generate(fixture_analysis(name))
    except Exception as exc:  # aynı hata sınıfı beklenir
        return ("error", type(exc).__name__)
    lesson = result.lesson.model_dump(mode="json", exclude={"lesson_plan_id", "provider", "model", "generated_at",
                                                             "processing_time_ms", "lesson_generation_ms"})
    verification = result.verification.model_dump(mode="json", exclude={"processing_time_ms"})
    return ("ok", lesson, verification, result.method_check, result.correction_attempted)


@pytest.mark.asyncio
@pytest.mark.parametrize("name", [*FIXTURES, *SUBJECTS, "oncul", "eksik_bilgi"])
async def test_both_adapters_yield_same_canonical_lesson_and_verification(name, monkeypatch):
    first = await outcome("openai", name, monkeypatch)
    second = await outcome("anthropic", name, monkeypatch)
    assert first == second


def test_pack_command_wires_anthropic_lessons_without_any_call(capsys):
    from scripts import eval_pack, evaluate_models

    with pytest.raises(SystemExit):
        evaluate_models.main(["pack", "--provider", "anthropic", "--dry-run"], settings=Settings(_env_file=None))
    assert "--lesson-model zorunludur" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        evaluate_models.main(["pack", "--provider", "anthropic", "--lesson-model", "claude-sonnet-5-5", "--allow-paid",
                              "--max-usd", "1", "--max-calls", "5"], settings=Settings(_env_file=None, openai_api_key="k"))
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
    assert evaluate_models.main(["pack", "--provider", "anthropic", "--lesson-model", "claude-sonnet-5-5", "--dry-run"],
                                settings=Settings(_env_file=None)) == 0
    out = capsys.readouterr().out
    assert "ders Anthropic, Vision OpenAI" in out and "--provider anthropic" in out and "--model None" not in out
    services = eval_pack.Services(Settings(_env_file=None, anthropic_api_key="k"), "gpt-4.1-mini", "claude-sonnet-5-5",
                                  None, lesson_provider="anthropic")
    assert isinstance(services.lessons.provider, AnthropicLessonProvider) and services.vision._provider.name == "openai"


def test_schema_compat_flags_documented_unsupported_features():
    from apps.api.app.core.schema_compat import incompatibilities
    from scripts.anthropic_schema_compat import report

    bad = {"type": "object", "additionalProperties": True, "properties": {
        "n": {"type": "integer", "minimum": 0}, "s": {"type": "string", "maxLength": 3},
        "a": {"type": "array", "minItems": 2, "items": {"oneOf": [{"type": "string"}]}},
        "p": {"type": "string", "pattern": "(?=x)"}, "r": {"$ref": "https://example.invalid/s"}}}
    found = " ".join(incompatibilities(bad))
    for reason in ("minimum", "maxLength", "minItems=2", "oneOf", "pattern", "external_ref", "additionalProperties"):
        assert reason in found
    recursive = {"$defs": {"N": {"type": "object", "properties": {"c": {"$ref": "#/$defs/N"}}, "additionalProperties": False}}}
    assert incompatibilities(recursive) == ["$defs/N: recursive_schema"]
    assert incompatibilities({"type": "object", "properties": {}, "required": [], "additionalProperties": False}) == []
    allof = {"allOf": [{"$ref": "#/$defs/A"}, {"type": "object"}]}
    assert incompatibilities(allof) == ["#: allOf_with_ref_or_combinator"]
    result = report()
    # TA-005C: özgün şemalardaki uyumsuzluklar hâlâ görünür; onaylı izdüşümden sonra üç işlem uyumludur.
    assert result["vision"]["schemas"]["VisionProviderAnalysis"]["original_issues"]
    assert result["interaction"]["schemas"]["AdaptiveDraft"]["original_issues"]
    assert all(result[op]["compatible"] for op in ("vision", "lessons", "interaction"))
