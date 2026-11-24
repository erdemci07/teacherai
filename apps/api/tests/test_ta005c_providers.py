"""TA-005C: Anthropic Vision/etkileşim, şema izdüşümü, sunucu doğrulaması, gizlilik, fallback yokluğu,
muhasebe kapsamı, rezervasyon uzlaştırması ve sağlayıcı hata sınıflandırması.

Gerçek sağlayıcı çağrısı yoktur: yalnız ``httpx.MockTransport`` ve sahte adaptörler. Görseller bellekte
üretilen sentetik PNG'lerdir; öğrenci görseli kullanılmaz. Bu testler model kalitesini ölçmez.
"""

import copy
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from pydantic import BaseModel, ConfigDict, Field

from apps.api.app.core import gateway
from apps.api.app.core.ai_outcomes import (
    AIInvalidOutputError,
    AIOutcomeError,
    AIOutputTruncatedError,
    AIRefusalError,
    AITimeoutError,
    Outcome,
    ProviderFailure,
)
from apps.api.app.core.ai_port import AdapterResult, ImagePart, ProviderAdapter, ProviderRequest, TextPart, Usage
from apps.api.app.core.anthropic_adapter import AnthropicAdapter, classify_http
from apps.api.app.core.container import build_container
from apps.api.app.core.gateway import (
    AccountingScopeRequired,
    OfflineAccountingNotAllowed,
    ProviderCallBudgetExhausted,
    begin_accounting,
    begin_offline_accounting,
    end_accounting,
    invoke,
)
from apps.api.app.core.operations import Operation
from apps.api.app.core.schema_compat import (
    APPROVED_PROJECTIONS,
    SchemaProjectionError,
    anthropic_projection,
    incompatibilities,
    strict_schema,
)
from apps.api.app.core.settings import Settings
from apps.api.app.features.interactions.exceptions import (
    InteractionContextTooLargeError,
    InteractionProviderError,
)
from apps.api.app.features.interactions.openai_provider import AnthropicInteractionProvider, OpenAIInteractionProvider
from apps.api.app.features.interactions.schemas import AdaptiveDraft
from apps.api.app.features.lessons.exceptions import (
    LessonContextTooLargeError,
    LessonProviderConfigurationError,
    LessonProviderUnavailableError,
)
from apps.api.app.features.lessons.openai_provider import AnthropicLessonProvider
from apps.api.app.features.vision.exceptions import (
    ImageTooLargeError,
    InvalidProviderResponseError,
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from apps.api.app.features.vision.openai_provider import AnthropicVisionProvider, OpenAIVisionProvider
from apps.api.app.features.vision.schemas import RecheckResponse, VisionProviderAnalysis

BASE = json.loads(Path(__file__).with_name("fixtures").joinpath("integrity", "scenarios.json").read_text(encoding="utf-8"))["base"]


def png(size=(400, 200)):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, format="PNG")
    return buffer.getvalue()


def reply(payload, stop="end_turn", usage=None, status=200):
    text = payload if isinstance(payload, str) or payload is None else json.dumps(payload, ensure_ascii=False)
    usage = {"input_tokens": 100, "output_tokens": 40, "cache_read_input_tokens": 0,
             "cache_creation_input_tokens": 0} if usage is None else usage
    return httpx.Response(status, headers={"request-id": "req_fixture"},
                          json={"id": "msg_x", "type": "message", "model": "claude-sonnet-5-5", "stop_reason": stop,
                                "content": [] if text is None else [{"type": "text", "text": text}], "usage": usage})


def error(status, kind, message="ayrıntı"):
    return httpx.Response(status, headers={"request-id": "req_err"},
                          json={"type": "error", "error": {"type": kind, "message": message}, "request_id": "req_err"})


def transport(*responses, seen=None):
    queue = list(responses)

    def handler(request):
        if seen is not None:
            seen.append(request)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    return httpx.MockTransport(handler)


def vision(**overrides):
    payload = copy.deepcopy(BASE)
    payload.update(overrides)
    return payload


def logs(monkeypatch):
    lines = []

    def info(self, msg, *args, **kwargs):
        if self.name == "teacherai.ai_usage":
            lines.append(json.loads(msg))

    monkeypatch.setattr("logging.Logger.info", info)
    return lines


# --------------------------------------------------------------------------- 1. şema izdüşümü


def test_projection_removes_only_approved_constraints_and_documents_them():
    projected = anthropic_projection(VisionProviderAnalysis)
    assert {(path, key) for path, key, _ in projected.removed} == set(APPROVED_PROJECTIONS["VisionProviderAnalysis"])
    assert incompatibilities(projected.schema) == []
    confidence = projected.schema["properties"]["confidence"]
    assert "minimum" not in confidence and "maximum" not in confidence
    assert "{minimum: 0, maximum: 1}" in confidence["description"]  # SDK yardımcılarıyla aynı açıklama notu
    # Özgün şema ve Pydantic modeli değişmez.
    assert strict_schema(VisionProviderAnalysis)["properties"]["confidence"]["maximum"] == 1
    draft = anthropic_projection(AdaptiveDraft)
    latex = draft.schema["$defs"]["Expression"]["properties"]["latex"]
    assert "minLength" not in latex and latex["description"] == "{minLength: 1}" and incompatibilities(draft.schema) == []
    assert anthropic_projection(RecheckResponse).removed == ()


def test_unapproved_or_unprojectable_constraints_are_refused():
    class NewLimit(BaseModel):
        model_config = ConfigDict(extra="forbid")
        name: str = Field(max_length=5)

    with pytest.raises(SchemaProjectionError, match="onaysız"):
        anthropic_projection(NewLimit)

    class Pairs(BaseModel):
        model_config = ConfigDict(extra="forbid")
        items: list[int] = Field(min_length=2)

    with pytest.raises(SchemaProjectionError, match="uyumsuz alan kaldı"):
        anthropic_projection(Pairs)  # minItems=2 izdüşümle giderilmez


@pytest.mark.asyncio
async def test_unprojectable_schema_never_reaches_the_network():
    class Pairs(BaseModel):
        model_config = ConfigDict(extra="forbid")
        items: list[int] = Field(min_length=2)

    seen = []
    with pytest.raises(SchemaProjectionError):
        await invoke(AnthropicAdapter("k", transport=transport(reply({"items": [1, 2]}), seen=seen)),
                     ProviderRequest(Operation.LESSONS, "claude-sonnet-5-5", user="x", schema=Pairs))
    assert seen == []


def test_stale_approval_fails_the_check(monkeypatch):
    from apps.api.app.core import schema_compat

    monkeypatch.setitem(schema_compat.APPROVED_PROJECTIONS, "RecheckResponse", {("#/properties/readings", "minimum"): "yok"})
    with pytest.raises(SchemaProjectionError, match="eskimiş"):
        anthropic_projection(RecheckResponse)


# --------------------------------------------------------------------------- 2. sunucu doğrulaması


def anthropic_vision_provider(*responses, seen=None, allow=True):
    return AnthropicVisionProvider("key", "claude-sonnet-5-5", 5, allow_images=allow, transport=transport(*responses, seen=seen))


@pytest.mark.asyncio
async def test_valid_anthropic_vision_response_is_accepted_with_projected_schema_on_the_wire():
    seen = []
    result = await anthropic_vision_provider(reply(vision()), seen=seen).analyze_image(png(), "image/png", "req")
    assert result.analysis.confidence == 0.9 and result.provider == "anthropic"
    sent = json.loads(seen[0].content)
    schema = sent["output_config"]["format"]["schema"]
    assert incompatibilities(schema) == [] and "maximum" not in schema["properties"]["confidence"]
    assert sent["messages"][0]["content"][1]["type"] == "image"


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    vision(confidence=1.5),                                        # maximum (izdüşümle gönderilmedi)
    vision(confidence=-0.1),                                       # minimum
    vision(source={"question_count": -1}),                         # iç içe minimum
    {k: v for k, v in vision().items() if k != "question_text"},   # eksik alan
    vision(image_status="maybe_math"),                             # geçersiz enum
    vision(extra_field="uydurma"),                                 # ek alan
    vision(visual_elements="diyagram yok"),                        # bozuk iç içe nesne
    vision(revision=7),                                            # soru revizyonu sunucuya aittir
    vision(source={"regions": [{"kind": "triangle", "x0": 0, "y0": 0, "x1": 1, "y1": 1}]}),  # bölge türü enum dışı
    vision(is_valid_question=False),                               # alanlar arası kural
])
async def test_invalid_anthropic_vision_output_is_rejected_by_original_pydantic_schema(payload):
    with pytest.raises(AIInvalidOutputError):
        await anthropic_vision_provider(reply(payload)).analyze_image(png(), "image/png", "req")


@pytest.mark.asyncio
async def test_invalid_bounding_boxes_are_not_trusted_after_acceptance():
    from apps.api.app.features.integrity.engine import _region

    payload = vision(source={"regions": [{"kind": "expression", "x0": 0.8, "y0": 0.1, "x1": 0.2, "y1": 0.4},
                                         {"kind": "expression", "x0": -2, "y0": 0, "x1": 3, "y1": 1}]})
    result = await anthropic_vision_provider(reply(payload)).analyze_image(png(), "image/png", "req")
    assert _region(result.analysis.source, 0) is None and _region(result.analysis.source, 1) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("draft", [
    {"title": "İpucu", "text": "x", "expressions": [{"type": "expression", "latex": ""}]},  # minLength=1 sunucuda
    {"title": "İpucu"},                                                                    # eksik alan
    {"title": "İpucu", "text": "x", "expressions": [{"type": "matrix", "latex": "1"}]},   # geçersiz enum
    {"title": "İpucu", "text": "x", "secret": True},                                       # ek alan
])
async def test_invalid_anthropic_interaction_output_is_rejected(draft):
    from apps.api.tests.test_mathai import plan as lesson_plan

    provider = AnthropicInteractionProvider("key", "claude-sonnet-5-5", 5, transport=transport(reply(draft)))
    with pytest.raises(AIInvalidOutputError):
        await provider.adapt("hint", lesson_plan(), 1)


# --------------------------------------------------------------------------- 3. gizlilik ve fallback


@pytest.mark.asyncio
async def test_student_images_are_never_sent_without_privacy_permission():
    seen = []
    provider = anthropic_vision_provider(reply(vision()), seen=seen, allow=False)
    with pytest.raises(ProviderConfigurationError):
        await provider.analyze_image(png(), "image/png", "req")
    with pytest.raises(ProviderConfigurationError):
        await provider.recheck([(png(), "image/png")], "1. ifade", "req")
    assert seen == [] and not await provider.health()


@pytest.mark.asyncio
async def test_rejected_image_spends_no_call_and_no_reservation():
    seen, tracker = [], Mock()
    token = begin_accounting("req", Settings(_env_file=None), tracker, "uid", max_calls=2)
    try:
        with pytest.raises(ImageTooLargeError):
            await anthropic_vision_provider(reply(vision()), seen=seen).analyze_image(png((9000, 10)), "image/png", "req")
        assert gateway.current_scope().calls == 0
    finally:
        end_accounting(token)
    tracker.reserve_output.assert_not_called()
    assert seen == []


def test_capability_and_privacy_permission_are_separate_settings():
    with pytest.raises(Exception, match="ALLOW_STUDENT_IMAGES"):
        Settings(_env_file=None, provider_vision="anthropic", anthropic_api_key="k", anthropic_vision_model="claude-sonnet-5-5")
    only_flag = Settings(_env_file=None, allow_student_images_to_anthropic=True, anthropic_api_key="k")
    assert only_flag.provider_for(Operation.VISION) == "openai"  # izin tek başına sağlayıcıyı değiştirmez
    assert isinstance(build_container(only_flag).vision_service._provider, OpenAIVisionProvider)
    assert not isinstance(build_container(only_flag).vision_service._provider, AnthropicVisionProvider)
    both = Settings(_env_file=None, provider_vision="anthropic", allow_student_images_to_anthropic=True,
                    anthropic_api_key="k", anthropic_vision_model="claude-sonnet-5-5")
    assert isinstance(build_container(both).vision_service._provider, AnthropicVisionProvider)


def test_default_container_uses_openai_for_every_operation():
    container = build_container(Settings(_env_file=None))
    assert type(container.vision_service._provider) is OpenAIVisionProvider
    assert type(container.interaction_service.provider) is OpenAIInteractionProvider
    assert container.lesson_service.provider.name == "openai"


@pytest.mark.asyncio
async def test_anthropic_failure_never_falls_back_to_openai(monkeypatch):
    import apps.api.app.features.vision.openai_provider as vision_module

    opened = []
    monkeypatch.setattr(vision_module, "AsyncOpenAI", lambda **kwargs: opened.append(kwargs))
    seen = []
    with pytest.raises(ProviderRateLimitError):
        await anthropic_vision_provider(error(529, "overloaded_error"), seen=seen).analyze_image(png(), "image/png", "req")
    assert len(seen) == 1 and opened == []  # tek deneme; OpenAI istemcisi hiç açılmadı


@pytest.mark.asyncio
async def test_vision_service_runs_integrity_with_anthropic_provider(tmp_path):
    from starlette.datastructures import Headers, UploadFile

    from apps.api.app.features.vision.service import VisionService
    from apps.api.app.features.vision.storage import LocalTemporaryImageStorage

    seen = []
    service = VisionService(anthropic_vision_provider(reply(vision()), seen=seen), LocalTemporaryImageStorage(tmp_path),
                            10 * 1024 * 1024, False, recheck_limit=1)
    upload = UploadFile(file=io.BytesIO(png()), filename="sentetik.png", headers=Headers({"content-type": "image/png"}))
    result = await service.analyze(upload, "req_vision")
    assert result.integrity is not None and result.integrity.decision == "ready" and result.provider == "anthropic"
    assert result.revision == 1 and len(seen) == 1  # temiz soruda ikinci çağrı yok


# --------------------------------------------------------------------------- 4. muhasebe kapsamı


class CountingAdapter(ProviderAdapter):
    name = "counting"
    operations = frozenset(Operation)

    def __init__(self, result=None):
        self.calls, self.result = 0, result

    async def _send(self, request):
        self.calls += 1
        return self.result or AdapterResult(Outcome.COMPLETED, text="{}", usage=Usage(input=10, cached_input=0, output=5),
                                            model="gpt-4.1-mini", status="completed")


@pytest.mark.asyncio
async def test_calls_without_accounting_scope_are_refused(no_accounting_scope, monkeypatch):
    lines = logs(monkeypatch)
    adapter = CountingAdapter()
    with pytest.raises(AccountingScopeRequired):
        await invoke(adapter, ProviderRequest(Operation.VISION, "gpt-4.1-mini"))
    assert adapter.calls == 0 and lines[-1]["reason"] == "no_accounting_scope"
    with pytest.raises(AccountingScopeRequired):
        begin_accounting("req", Settings(_env_file=None), None, "uid")
    with pytest.raises(AccountingScopeRequired):
        begin_accounting("req", Settings(_env_file=None), Mock(), "")


@pytest.mark.asyncio
async def test_production_scope_without_explicit_ceiling_uses_the_operation_budget():
    adapter, tracker = CountingAdapter(), Mock()
    settings = Settings(_env_file=None)
    token = begin_accounting("req", settings, tracker, "uid")
    try:
        for _ in range(settings.provider_call_budget("analyze")):
            await invoke(adapter, ProviderRequest(Operation.VISION, "gpt-4.1-mini"))
        with pytest.raises(ProviderCallBudgetExhausted):
            await invoke(adapter, ProviderRequest(Operation.VISION, "gpt-4.1-mini"))
    finally:
        end_accounting(token)
    assert adapter.calls == 2 and tracker.reserve_output.call_count == 2


def test_offline_scope_cannot_be_opened_in_production_or_on_cloud_run(monkeypatch):
    production = SimpleNamespace(environment="production")
    with pytest.raises(OfflineAccountingNotAllowed):
        begin_offline_accounting("eval", production, max_calls=1)
    monkeypatch.setenv("K_SERVICE", "teacherai-api")
    with pytest.raises(OfflineAccountingNotAllowed):
        begin_offline_accounting("eval", Settings(_env_file=None), max_calls=1)
    monkeypatch.delenv("K_SERVICE")
    for bad in (0, -1, None, True):
        with pytest.raises(ValueError):
            begin_offline_accounting("eval", Settings(_env_file=None), max_calls=bad)


@pytest.mark.asyncio
async def test_offline_scope_has_its_own_call_and_usd_limits_and_never_reserves(monkeypatch):
    lines = logs(monkeypatch)
    adapter = CountingAdapter()
    token = begin_offline_accounting("eval", Settings(_env_file=None), max_calls=10, max_usd=0.000012)
    try:
        await invoke(adapter, ProviderRequest(Operation.VISION, "gpt-4.1-mini"))  # 10×0,4 + 5×1,6 = 12e-6 USD
        with pytest.raises(ProviderCallBudgetExhausted):
            await invoke(adapter, ProviderRequest(Operation.VISION, "gpt-4.1-mini"))
    finally:
        end_accounting(token)
    usage = [line for line in lines if line["event"] == "ai_usage"]
    assert adapter.calls == 1 and usage[0]["accounting"] == "offline" and usage[0]["reservation"] == "offline"
    assert lines[-1]["reason"] == "offline_usd_budget"


@pytest.mark.asyncio
async def test_unknown_cost_stops_an_offline_usd_budget_instead_of_counting_zero():
    adapter = CountingAdapter(AdapterResult(Outcome.COMPLETED, text="{}", usage=Usage(), model="gpt-4.1-mini"))
    token = begin_offline_accounting("eval", Settings(_env_file=None), max_calls=10, max_usd=5)
    try:
        await invoke(adapter, ProviderRequest(Operation.VISION, "gpt-4.1-mini"))
        scope = gateway.current_scope()
        assert scope.spent_usd == 0 and scope.unpriced_calls == 1
        with pytest.raises(ProviderCallBudgetExhausted):
            await invoke(adapter, ProviderRequest(Operation.VISION, "gpt-4.1-mini"))
    finally:
        end_accounting(token)


@pytest.mark.asyncio
@pytest.mark.parametrize(("response", "error", "released"), [
    (reply({}, usage={"input_tokens": 10, "output_tokens": 30}), None, True),                       # başarı
    (reply(None, stop="refusal", usage={"input_tokens": 10, "output_tokens": 3}), AIRefusalError, True),
    (reply('{"yar', stop="max_tokens", usage={"input_tokens": 10, "output_tokens": 4096}), AIOutputTruncatedError, True),
    (httpx.ReadTimeout("yavaş"), AITimeoutError, False),                                             # tüketim bilinmez
    (reply({}, usage={}), None, False),                                                              # bilinmeyen kullanım
    (error(529, "overloaded_error"), AIOutcomeError, False),                                         # hata gövdesinde kullanım yok
])
async def test_reservation_settlement_per_outcome(response, error, released, monkeypatch):
    class Empty(BaseModel):
        model_config = ConfigDict(extra="forbid")

    lines = logs(monkeypatch)
    tracker = Mock()
    tracker.reserve_output.return_value = "reservation"
    token = begin_accounting("req", Settings(_env_file=None), tracker, "uid", max_calls=1)
    try:
        call = invoke(AnthropicAdapter("k", transport=transport(response)),
                      ProviderRequest(Operation.VISION, "claude-sonnet-5-5", user="x", schema=Empty))
        if error:
            with pytest.raises(error):
                await call
        else:
            await call
    finally:
        end_accounting(token)
    event = [line for line in lines if line["event"] == "ai_usage"][-1]
    assert event["reservation"] == ("released" if released else "kept")
    assert tracker.release_output.called is released
    if released:
        output = event["output_tokens"]
        assert tracker.release_output.call_args.args[1] == max(0, 4096 - min(output, 4096))
    assert "estimated_usd" not in event or event["input_tokens"] is not None  # bilinmeyen kullanım fiyatlanmaz


# --------------------------------------------------------------------------- 5. hata sınıflandırması


@pytest.mark.parametrize(("status", "kind", "message", "expected"), [
    (401, "authentication_error", "invalid x-api-key", ProviderFailure.AUTHENTICATION),
    (403, "permission_error", "", ProviderFailure.PERMISSION),
    (402, "billing_error", "", ProviderFailure.BILLING),
    (404, "not_found_error", "model: claude-x", ProviderFailure.MODEL_NOT_FOUND),
    (400, "invalid_request_error", "messages: roles must alternate", ProviderFailure.INVALID_REQUEST),
    (400, "invalid_request_error", "prompt is too long: 1200000 tokens > 1000000 maximum", ProviderFailure.CONTEXT_WINDOW_EXCEEDED),
    (413, "request_too_large", "", ProviderFailure.REQUEST_TOO_LARGE),
    (429, "rate_limit_error", "", ProviderFailure.RATE_LIMITED),
    (500, "api_error", "", ProviderFailure.PROVIDER_INTERNAL),
    (500, "timeout_error", "", ProviderFailure.PROVIDER_TIMEOUT),  # tür durumdan önce gelir
    (504, "timeout_error", "", ProviderFailure.PROVIDER_TIMEOUT),
    (529, "overloaded_error", "", ProviderFailure.OVERLOADED),
    (418, "brand_new_error", "", ProviderFailure.UNKNOWN),
])
def test_http_errors_are_classified_from_status_and_error_type(status, kind, message, expected):
    assert classify_http(status, {"type": "error", "error": {"type": kind, "message": message}}) == expected


def test_unparseable_error_bodies_fall_back_to_status():
    assert classify_http(529, None) == ProviderFailure.OVERLOADED
    assert classify_http(400, {"error": "düz metin"}) == ProviderFailure.INVALID_REQUEST
    assert classify_http(599, "html") == ProviderFailure.UNKNOWN


@pytest.mark.asyncio
async def test_error_logs_carry_no_key_message_body_or_image(monkeypatch):
    lines = logs(monkeypatch)
    secret, image = "sk-ant-gizli-anahtar", png()
    body = error(401, "authentication_error", "öğrenci Ayşe'nin anahtarı geçersiz")
    adapter = AnthropicAdapter(secret, allow_images=True, transport=transport(body))
    with pytest.raises(AIOutcomeError) as caught:
        await invoke(adapter, ProviderRequest(Operation.VISION, "claude-sonnet-5-5",
                                              user=(TextPart("oku"), ImagePart(image, "image/png")), schema=RecheckResponse))
    assert caught.value.reason == ProviderFailure.AUTHENTICATION
    text = json.dumps(lines, ensure_ascii=False)
    assert secret not in text and "Ayşe" not in text and "iVBOR" not in text
    assert lines[-1]["outcome_reason"] == "authentication" and lines[-1]["status"] == "http_401"


@pytest.mark.asyncio
async def test_connection_failure_and_unexpected_stop_are_distinct():
    with pytest.raises(AIOutcomeError) as caught:
        await invoke(AnthropicAdapter("k", transport=transport(httpx.ConnectError("yok"))),
                     ProviderRequest(Operation.LESSONS, "claude-sonnet-5-5", user="x"))
    assert caught.value.reason == ProviderFailure.CONNECTION
    with pytest.raises(AIOutcomeError) as caught:
        await invoke(AnthropicAdapter("k", transport=transport(reply({}, stop="pause_turn"))),
                     ProviderRequest(Operation.LESSONS, "claude-sonnet-5-5", user="x"))
    assert caught.value.reason == ProviderFailure.UNEXPECTED_STOP


@pytest.mark.asyncio
@pytest.mark.parametrize(("response", "expected"), [
    (error(401, "authentication_error"), ProviderAuthenticationError),
    (error(404, "not_found_error"), ProviderAuthenticationError),
    (error(429, "rate_limit_error"), ProviderRateLimitError),
    (error(529, "overloaded_error"), ProviderRateLimitError),
    (error(500, "api_error"), ProviderUnavailableError),
    (httpx.ConnectError("yok"), ProviderUnavailableError),
    (error(504, "timeout_error"), ProviderTimeoutError),
    (error(400, "invalid_request_error"), InvalidProviderResponseError),
    (httpx.ReadTimeout("yavaş"), AITimeoutError),
    (reply(None, stop="refusal"), AIRefusalError),
])
async def test_vision_domain_errors_match_the_openai_contract(response, expected):
    with pytest.raises(expected):
        await anthropic_vision_provider(response).analyze_image(png(), "image/png", "req")


@pytest.mark.asyncio
@pytest.mark.parametrize(("response", "expected"), [
    (error(401, "authentication_error"), LessonProviderConfigurationError),
    (error(429, "rate_limit_error"), LessonProviderUnavailableError),
    (error(529, "overloaded_error"), LessonProviderUnavailableError),
])
async def test_lesson_domain_errors_match_the_openai_contract(response, expected):
    from apps.api.tests.test_question_integrity import analysis

    provider = AnthropicLessonProvider("key", "claude-sonnet-5-5", 5, transport=transport(response))
    with pytest.raises(expected):
        await provider.generate_lesson_plan(analysis())


# --------------------------------------------------------------------------- 6. bağlam aşımı yeniden denemesi


TOO_LONG = "prompt is too long: 1000001 tokens > 1000000 maximum"


@pytest.mark.asyncio
async def test_lesson_context_retry_is_single_bounded_and_counted(monkeypatch):
    from apps.api.tests.test_lesson_provider_errors import lesson_payload
    from apps.api.tests.test_question_integrity import analysis

    lines = logs(monkeypatch)
    seen = []
    provider = AnthropicLessonProvider("key", "claude-sonnet-5-5", 5,
                                       transport=transport(error(400, "invalid_request_error", TOO_LONG),
                                                           reply(lesson_payload()), seen=seen))
    token = begin_accounting("req", Settings(_env_file=None), Mock(), "uid", max_calls=3)
    try:
        result = await provider.generate_lesson_plan(analysis())
        assert gateway.current_scope().calls == 2
    finally:
        end_accounting(token)
    assert result.provider == "anthropic" and len(seen) == 2
    purposes = [line["purpose"] for line in lines if line["event"] == "ai_usage"]
    assert purposes == ["lessons.initial", "lessons.context_retry"]
    assert len(seen[1].content) <= len(seen[0].content)  # acil bağlam hiçbir zaman büyümez


@pytest.mark.asyncio
async def test_lesson_context_retry_stops_when_still_too_long_or_budget_is_spent():
    from apps.api.tests.test_question_integrity import analysis

    twice = transport(error(400, "invalid_request_error", TOO_LONG), error(400, "invalid_request_error", TOO_LONG))
    with pytest.raises(LessonContextTooLargeError):
        await AnthropicLessonProvider("key", "claude-sonnet-5-5", 5, transport=twice).generate_lesson_plan(analysis())
    seen = []
    once = AnthropicLessonProvider("key", "claude-sonnet-5-5", 5,
                                   transport=transport(error(400, "invalid_request_error", TOO_LONG), seen=seen))
    token = begin_accounting("req", Settings(_env_file=None), Mock(), "uid", max_calls=1)
    try:
        with pytest.raises(LessonContextTooLargeError):
            await once.generate_lesson_plan(analysis())
    finally:
        end_accounting(token)
    assert len(seen) == 1  # tavan doluyken ikinci istek yok


@pytest.mark.asyncio
async def test_plain_invalid_request_is_not_retried():
    from apps.api.app.features.lessons.exceptions import InvalidLessonPlanError
    from apps.api.tests.test_question_integrity import analysis

    seen = []
    provider = AnthropicLessonProvider("key", "claude-sonnet-5-5", 5,
                                       transport=transport(error(400, "invalid_request_error", "bad field"), seen=seen))
    with pytest.raises(InvalidLessonPlanError):
        await provider.generate_lesson_plan(analysis())
    assert len(seen) == 1


@pytest.mark.asyncio
async def test_interaction_context_retry_and_errors():
    from apps.api.tests.test_mathai import plan as lesson_plan

    good = {"title": "İpucu", "text": "Önce iki tarafı sadeleştir.", "steps": [], "expressions": []}
    seen = []
    provider = AnthropicInteractionProvider("key", "claude-sonnet-5-5", 5,
                                            transport=transport(error(400, "invalid_request_error", TOO_LONG), reply(good), seen=seen))
    draft = await provider.adapt("hint", lesson_plan(), 1)
    assert draft.title == "İpucu" and len(seen) == 2
    token = begin_accounting("req", Settings(_env_file=None), Mock(), "uid", max_calls=1)
    try:
        with pytest.raises(InteractionContextTooLargeError):
            await AnthropicInteractionProvider("key", "claude-sonnet-5-5", 5, transport=transport(
                error(400, "invalid_request_error", TOO_LONG))).adapt("hint", lesson_plan(), 1)
    finally:
        end_accounting(token)
    with pytest.raises(InteractionProviderError):
        await AnthropicInteractionProvider("key", "claude-sonnet-5-5", 5, transport=transport(
            error(529, "overloaded_error"))).adapt("hint", lesson_plan(), 1)
