"""TA-005B §7: sağlayıcı seçimi, tek fiyat kaynağı, geçiş belgesi ve sağlayıcıdan bağımsız doğrulama zinciri.

Gerçek sağlayıcı çağrısı yoktur; sahte adaptör ve sahte istemci kullanılır.
"""

import json
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
from pydantic import ValidationError

import apps.api.app.features.lessons.openai_provider as lesson_module
from apps.api.app.core import gateway, model_catalog
from apps.api.app.core.ai_outcomes import AIInvalidOutputError, Outcome
from apps.api.app.core.ai_port import AdapterResult, Admission, AdmissionRequired, ProviderAdapter, ProviderRequest, Usage, issue
from apps.api.app.core.gateway import ProviderCallBudgetExhausted, begin_accounting, end_accounting, invoke
from apps.api.app.core.operations import REASONING_LEVELS, Operation
from apps.api.app.core.providers import SUPPORTED_OPERATIONS, adapter_classes
from apps.api.app.core.settings import Settings
from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.lessons.exceptions import QuestionClarificationRequiredError
from apps.api.app.features.lessons.openai_provider import OpenAILessonProvider
from apps.api.app.features.lessons.service import LessonService
from apps.api.app.features.mathai.service import MathAIService
from apps.api.tests.fake_openai import FakeRaw, body
from apps.api.tests.test_lesson_provider_errors import lesson_payload
from apps.api.tests.test_question_integrity import SIGN, analysis

PRODUCTION = {"_env_file": None, "environment": "production", "firebase_project_id": "p", "firebase_auth_project_id": "p"}


# --- yapılandırma ---

@pytest.mark.parametrize(("field", "model_field", "env"), [
    ("provider_vision", "anthropic_vision_model", "TEACHERAI_ANTHROPIC_VISION_MODEL"),
    ("provider_interaction", "anthropic_interaction_model", "TEACHERAI_ANTHROPIC_INTERACTION_MODEL")])
def test_unsupported_or_incomplete_provider_assignment_stops_startup(field, model_field, env):
    # TA-005C: şema izdüşümüyle üç işlem de Anthropic'te desteklenir; eksik model/anahtar yine başlatmaz.
    assert SUPPORTED_OPERATIONS["anthropic"] == frozenset(Operation)
    base = {"_env_file": None, "allow_student_images_to_anthropic": True, field: "anthropic"}
    with pytest.raises(ValidationError, match=env):
        Settings(**base, anthropic_api_key="k")
    with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY"):
        Settings(**base, **{model_field: "claude-sonnet-5-5"})
    with pytest.raises(ValidationError, match="openai sağlayıcısına ait"):
        Settings(**base, anthropic_api_key="k", **{model_field: "gpt-4.1-mini"})  # model/sağlayıcı uyumsuzluğu
    ok = Settings(**base, anthropic_api_key="k", **{model_field: "claude-sonnet-5-5"})
    assert ok.model_for(field.removeprefix("provider_")) == "claude-sonnet-5-5"
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: "gemini"})


def test_anthropic_lesson_needs_explicit_model_key_and_price():
    base = {"_env_file": None, "provider_lesson": "anthropic"}
    with pytest.raises(ValidationError, match="model verilmedi"):
        Settings(**base, anthropic_api_key="k")
    with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY"):
        Settings(**base, anthropic_lesson_model="claude-sonnet-5-5")
    ok = Settings(**base, anthropic_api_key="k", anthropic_lesson_model="claude-sonnet-5-5")
    assert ok.model_for(Operation.LESSONS) == "claude-sonnet-5-5" and ok.provider_for(Operation.VISION) == "openai"
    with pytest.raises(ValidationError, match="Fiyatı tanımsız"):
        Settings(**PRODUCTION, openai_api_key="k", provider_lesson="anthropic", anthropic_api_key="k",
                 anthropic_lesson_model="claude-unpriced")  # TA-009B: Haiku 5.5 artık kademeli fiyatlı; fiyatsız örnek
    with pytest.raises(ValidationError, match="reasoning"):
        Settings(**base, anthropic_api_key="k", anthropic_lesson_model="claude-sonnet-5-5",
                 reasoning_effort_by_operation={"lessons": "low"})


def test_vision_to_anthropic_requires_student_image_flag():
    with pytest.raises(ValidationError, match="ALLOW_STUDENT_IMAGES_TO_ANTHROPIC"):
        Settings(_env_file=None, provider_vision="anthropic", anthropic_api_key="k")


def test_default_provider_is_openai_without_fallback():
    settings = Settings(_env_file=None)
    assert {settings.provider_for(op) for op in Operation} == {"openai"}


def test_production_requires_key_and_priced_models():
    with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
        Settings(**PRODUCTION, openai_api_key=None)
    with pytest.raises(ValidationError, match="Fiyatı tanımsız"):
        Settings(**PRODUCTION, openai_api_key="k", openai_lesson_model="gpt-unpriced")
    assert Settings(**PRODUCTION, openai_api_key="k").pricing_version == model_catalog.pricing_version()
    Settings(_env_file=None, openai_lesson_model="gpt-unpriced")  # geliştirmede başlar; maliyet hesaplanmaz


def test_unpriced_model_cost_is_not_invented():
    event = {"model": "gpt-unpriced", "input_tokens": 10, "cached_tokens": 0, "output_tokens": 5}
    gateway._price(event, Settings(_env_file=None))
    assert "estimated_usd" not in event
    priced = {**event, "model": "gpt-4.1-mini"}
    gateway._price(priced, Settings(_env_file=None))
    assert priced["estimated_usd"] == pytest.approx((10 * 0.4 + 5 * 1.6) / 1_000_000)
    unknown = {**priced, "cached_tokens": None}
    unknown.pop("estimated_usd")
    gateway._price(unknown, Settings(_env_file=None))
    assert "estimated_usd" not in unknown  # bilinmeyen kullanım tahmin edilmez


def test_price_and_capability_table_has_one_source():
    from scripts import eval_pack

    assert not Path("evals/config/models.json").exists()
    assert Settings(_env_file=None).model_prices == model_catalog.prices()
    version, prices = eval_pack.load_pricing()
    assert (version, prices) == (model_catalog.pricing_version(), model_catalog.prices())
    assert REASONING_LEVELS == model_catalog.reasoning_levels() and "gpt-4.1-mini" not in REASONING_LEVELS
    for name, entry in model_catalog.catalog()["models"].items():
        assert entry["provider"] in SUPPORTED_OPERATIONS, name


# --- geçiş belgesi: adaptör ortak katmanı atlayamaz ---

class RecordingClient:
    def __init__(self, order):
        async def parse(**kwargs):
            order.append("provider")
            return FakeRaw(body({"ok": True}))

        self.responses = type("R", (), {"with_raw_response": type("W", (), {"parse": staticmethod(parse)})()})()


def make_adapter(name, order):
    if name == "openai":
        return adapter_classes()[name](RecordingClient(order))

    def handler(request):
        order.append("provider")
        return httpx.Response(200, json={"id": "msg", "model": "m", "stop_reason": "end_turn",
                                         "content": [{"type": "text", "text": "{}"}], "usage": {}})

    return adapter_classes()[name]("k", transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
@pytest.mark.parametrize("name", sorted(adapter_classes()))
async def test_every_adapter_refuses_calls_that_bypass_the_gateway(name):
    order = []
    adapter = make_adapter(name, order)
    request = ProviderRequest(Operation.LESSONS, "fixture")
    with pytest.raises(AdmissionRequired):
        await adapter.send(request, None)
    with pytest.raises(AdmissionRequired):
        Admission(request, _issuer=object())
    other = issue(ProviderRequest(Operation.LESSONS, "fixture"))
    with pytest.raises(AdmissionRequired):
        await adapter.send(request, other)  # başka isteğin belgesi
    used = issue(request)
    await adapter.send(request, used)
    with pytest.raises(AdmissionRequired):
        await adapter.send(request, used)  # tek kullanımlık
    assert order == ["provider"]


@pytest.mark.asyncio
@pytest.mark.parametrize("name", sorted(adapter_classes()))
async def test_gateway_reserves_and_counts_before_any_adapter_call(name):
    order = []
    tracker = Mock()
    tracker.reserve_output.side_effect = lambda uid, limit: order.append("reserve") or "reservation"
    adapter = make_adapter(name, order)
    token = begin_accounting("req", Settings(_env_file=None), tracker, "uid", max_calls=1)
    try:
        await invoke(adapter, ProviderRequest(Operation.LESSONS, "fixture"))
        with pytest.raises(ProviderCallBudgetExhausted):
            await invoke(adapter, ProviderRequest(Operation.LESSONS, "fixture"))
    finally:
        end_accounting(token)
    assert order == ["reserve", "provider"]  # rezervasyon önce; tavan dolunca adaptöre gidilmez


# --- doğrulama zinciri sağlayıcıdan bağımsızdır ---

class FakeAdapter(ProviderAdapter):
    """OpenAI olmayan sahte adaptör: yalnız kanonik istek görür ve JSON metni döndürür."""

    name = "fake"
    operations = frozenset(Operation)
    replies: list = []
    seen: list = []

    def __init__(self, client=None):
        pass

    async def _send(self, request):
        FakeAdapter.seen.append(request)
        return AdapterResult(Outcome.COMPLETED, text=FakeAdapter.replies.pop(0), usage=Usage(input=10, output=20),
                             model="fake-model", status="completed")


def reply(final):
    payload = lesson_payload()
    payload["content"].update(
        known_values=[], unknown="istenen değer", final_answer=final,
        final_answer_expressions=[{"type": "expression", "latex": final}],
        steps=[{"id": "step_1", "type": "result", "title": "Hesapla", "explanation": "Kök alınır, 1 eklenir.",
                "expressions": [{"type": "expression", "latex": final}], "visual_reference": None}])
    return json.dumps(payload, ensure_ascii=False)


def fake_service(monkeypatch, *replies):
    FakeAdapter.replies, FakeAdapter.seen = list(replies), []
    monkeypatch.setattr(lesson_module, "OpenAIAdapter", FakeAdapter)
    monkeypatch.setattr(lesson_module, "AsyncOpenAI", lambda **kwargs: type("C", (), {"close": staticmethod(_noop)})())
    return LessonService(OpenAILessonProvider("fixture-key", "fixture", 5), MathAIService(), BoardPlanner())


async def _noop():
    return None


def constant_question():
    return analysis(question_text="√16 + 1 kaçtır?", mathematical_expressions=[r"\sqrt{16}+1"],
                    answer_choices=["A) 3", "B) 5", "C) 17", "D) 4"])


@pytest.mark.asyncio
async def test_math_verification_runs_after_a_non_openai_adapter(monkeypatch):
    service = fake_service(monkeypatch, reply("5"))
    result = await service.generate(constant_question())
    assert result.verification.final_answer_verified and len(FakeAdapter.seen) == 1
    assert FakeAdapter.seen[0].system and isinstance(FakeAdapter.seen[0].user, str)  # sağlayıcı gövdesi değil


@pytest.mark.asyncio
async def test_wrong_answer_from_any_adapter_is_caught_by_mathai(monkeypatch):
    service = fake_service(monkeypatch, reply("17"), reply("5"))
    result = await service.generate(constant_question())
    assert len(FakeAdapter.seen) == 2 and result.verification.final_answer_verified  # MathAI düzeltme istedi


@pytest.mark.asyncio
async def test_schema_violation_from_any_adapter_is_invalid_output(monkeypatch):
    service = fake_service(monkeypatch, '{"learning_objectives": "değil-liste"}')
    with pytest.raises(AIInvalidOutputError):
        await service.generate(constant_question())


@pytest.mark.asyncio
async def test_question_integrity_stops_before_any_adapter_call(monkeypatch):
    service = fake_service(monkeypatch, reply("5"))
    unclear = analysis(question_text="3x + 7 = 19 ise x kaçtır?", mathematical_expressions=["3x + 7 = 19"],
                       answer_choices=["A) 2", "B) 3", "C) 4", "D) 5"], confidence=1.0, **SIGN)
    with pytest.raises(QuestionClarificationRequiredError):
        await service.generate(unclear)
    assert FakeAdapter.seen == []
