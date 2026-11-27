"""Yapılandırılmış sağlayıcı çağrıları için ortak sınır (TA-001B; TA-005B'de sağlayıcıdan bağımsız).

Buradan yalnızca izin verilen üst veri çıkar. Her sağlayıcı çağrısı:
1. mantıksal istek tavanını denetler ve işleme özel sınırla çıktı rezervasyonu yapar,
2. adaptöre (``core/ai_port.py``) yalnız bu çağrı için geçerli bir geçiş belgesiyle gider; adaptör ham
   yanıtı tek sonuca indirir (kesilen JSON böylece şema doğrulamasından önce doğru sınıflanır),
3. başarıda çıktıyı hedef şemaya ve isteğe bağlı doğrulayıcıya göre burada doğrular,
4. tam olarak bir sonuca (ai_outcomes.Outcome) düşer ve tek ai_usage satırı yazar,
5. rezervasyonu en fazla bir kez, sonuç kuralına göre iade eder.
Kota, idempotency ve hesap silme denetimi ``core/admission.py`` ve ``core/usage.py`` ile bu katmandadır;
adaptör bunları atlayamaz.

TA-005C: muhasebe kapsamı zorunludur. İki tür vardır ve ikisi de açıkça açılır:
- ``begin_accounting`` (production): ``core/admission.py`` açar (kimlik, kota, idempotency, hesap silme
  denetiminden sonra). Her çağrı kullanıcı ve küresel çıktı rezervasyonu yapar. Çağrı tavanı her zaman
  tanımlıdır: ``max_calls`` verilmezse işlemin mantıksal istek tavanı (``Settings.provider_call_budget``).
- ``begin_offline_accounting`` (değerlendirme/test): kendi çağrı tavanı ve isteğe bağlı USD tavanı vardır,
  kullanıcı kotasına yazmaz. Production/staging ortamında veya Cloud Run'da (``K_SERVICE``) açılamaz.
Kapsam yoksa çağrı ``AccountingScopeRequired`` ile reddedilir; adaptöre hiç gidilmez.
"""

import json
import logging
import os
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable, Literal

from starlette.concurrency import run_in_threadpool

from .ai_outcomes import (
    KEEP_RESERVATION,
    AIInvalidOutputError,
    AIOutcomeError,
    AIOutputFilteredError,
    AIOutputIncompleteError,
    AIOutputTruncatedError,
    AIRefusalError,
    AITimeoutError,
    Outcome,
)
from . import model_catalog
from .ai_port import ProviderAdapter, ProviderRequest, Usage, issue
from .operations import Operation, validate_effort

logger = logging.getLogger("teacherai.ai_usage")


@dataclass
class Accounting:
    request_id: str
    settings: object
    tracker: object
    uid: str
    calls: int = 0
    # TA-003: mantıksal istek başına çağrı tavanı. TA-005C: None sınırsız demek değildir; production
    # kapsamında işlemin mantıksal istek tavanı (Settings.provider_call_budget) uygulanır.
    max_calls: int | None = None
    kind: Literal["production", "offline"] = "production"
    max_usd: float | None = None  # yalnız offline: tahmini USD tavanı (kesin harcama sınırı değildir)
    spent_usd: float = 0.0
    unpriced_calls: int = 0  # maliyeti bilinmeyen çağrı; USD tavanı varken sonraki çağrıyı durdurur


class ProviderCallBudgetExhausted(Exception):
    """İstek başına sağlayıcı çağrısı tavanı doldu; yeni ücretli çağrı yapılmaz (503 / ai_call_budget_exhausted)."""


class AccountingScopeRequired(RuntimeError):
    """Sağlayıcı çağrısı açık bir muhasebe kapsamı olmadan denendi; adaptör çağrılmadı."""


class OfflineAccountingNotAllowed(RuntimeError):
    """Offline (değerlendirme/test) kapsamı production, staging veya Cloud Run'da açılamaz."""


@dataclass
class ProviderReply:
    """Doğrulanmış sağlayıcı yanıtı. Sağlayıcılar yalnızca bu alanları okur."""

    output_parsed: Any
    id: str | None = None
    model: str | None = None
    status: str = "completed"
    usage: dict = field(default_factory=dict)


_current = ContextVar("provider_accounting", default=None)
# İşlem → ``Settings.provider_call_budget`` etkinliği (tavanı verilmemiş production kapsamı için).
_ACTIVITY = {Operation.VISION: "analyze", Operation.LESSONS: "generate", Operation.INTERACTION: "interact"}


def begin_accounting(request_id, settings, tracker, uid, max_calls=None):
    """Production kapsamı: kullanıcıya bağlı rezervasyon ve çağrı tavanı."""
    if tracker is None or not uid:
        raise AccountingScopeRequired("Production kapsamı kullanım izleyicisi ve kullanıcı ister.")
    return _current.set(Accounting(request_id, settings, tracker, uid, max_calls=max_calls))


def begin_offline_accounting(label: str, settings, *, max_calls: int, max_usd: float | None = None):
    """Değerlendirme veya test kapsamı: kendi çağrı/USD tavanı; kullanıcı kotası ve rezervasyon yoktur."""
    if getattr(settings, "environment", None) in {"production", "staging"} or os.getenv("K_SERVICE"):
        raise OfflineAccountingNotAllowed("Offline muhasebe production/staging veya Cloud Run'da açılamaz.")
    if not isinstance(max_calls, int) or isinstance(max_calls, bool) or max_calls < 1:
        raise ValueError("Offline kapsam pozitif bir çağrı tavanı ister.")
    if max_usd is not None and not max_usd > 0:
        raise ValueError("Offline USD tavanı pozitif olmalı.")
    return _current.set(Accounting(label, settings, None, "offline", max_calls=max_calls, kind="offline",
                                   max_usd=max_usd))


def current_scope() -> Accounting | None:
    return _current.get()


def calls_remaining() -> int | None:
    """Bu istekte kalan sağlayıcı çağrısı hakkı; kapsam yoksa veya tavan işleme bağlıysa None."""
    scope = _current.get()
    if scope is None or scope.max_calls is None:
        return None
    return max(0, scope.max_calls - scope.calls)


def end_accounting(token):
    _current.reset(token)


def _ceiling(scope: Accounting, operation: Operation) -> int:
    if scope.max_calls is not None:
        return scope.max_calls
    budget = scope.settings.provider_call_budget(_ACTIVITY[operation])
    return budget if budget is not None else 1


def _raise_for(outcome: Outcome, reason: str | None):
    if outcome == Outcome.INCOMPLETE_MAX_TOKENS:
        raise AIOutputTruncatedError(reason)
    if outcome == Outcome.INCOMPLETE_OTHER:
        raise (AIOutputFilteredError if reason == "content_filter" else AIOutputIncompleteError)(reason or "unknown")
    if outcome == Outcome.REFUSAL:
        raise AIRefusalError(reason or "refusal")
    if outcome == Outcome.INVALID_OUTPUT:
        raise AIInvalidOutputError(reason)
    if outcome == Outcome.TIMEOUT:
        raise AITimeoutError(reason)
    raise AIOutcomeError(reason)


def _validated(text: str, schema, validate: Callable | None):
    try:
        parsed = schema.model_validate_json(text) if schema else text
        return validate(parsed) if validate else parsed
    except Exception as exc:
        raise AIInvalidOutputError(type(exc).__name__) from exc


def _usage_fields(usage: Usage) -> dict:
    total = usage.input + usage.output if usage.input is not None and usage.output is not None else None
    return {"input_tokens": usage.input, "output_tokens": usage.output, "total_tokens": total,
            "cached_tokens": usage.cached_input, "reasoning_tokens": usage.reasoning}


def _price(event, settings):
    rates = model_catalog.rates_for(event["model"], event.get("input_tokens"), settings.model_prices,
                                    settings.model_price_tiers)
    if not (rates and settings.pricing_version):
        return
    if any(event[k] is None for k in ("input_tokens", "cached_tokens", "output_tokens")):
        return  # bilinmeyen kullanımın maliyeti uydurulmaz
    cached = event["cached_tokens"]
    event["estimated_usd"] = (
        (event["input_tokens"] - cached) * rates[0] + cached * rates[1] + event["output_tokens"] * rates[2]
    ) / 1_000_000
    event["pricing_version"] = settings.pricing_version


def _refuse(scope, operation, purpose, reason, **extra):
    logger.info(json.dumps({"event": "ai_call_refused", "reason": reason, "operation": operation, "purpose": purpose,
                            "request_id": scope.request_id if scope else None,
                            "accounting": scope.kind if scope else None, **extra},
                           separators=(",", ":"), default=str))


async def invoke(adapter: ProviderAdapter, request: ProviderRequest, *, validate: Callable | None = None,
                 purpose: str = "primary") -> ProviderReply:
    """Ortak katman: kapsam, tavan, rezervasyon, reasoning, geçiş belgesi, şema doğrulaması, günlük ve iade."""
    scope = _current.get()
    operation = Operation(request.operation)
    if scope is None:
        _refuse(None, operation, purpose, "no_accounting_scope")
        raise AccountingScopeRequired("Sağlayıcı çağrısı muhasebe kapsamı olmadan yapılamaz.")
    settings = scope.settings
    ceiling = _ceiling(scope, operation)
    if scope.calls >= ceiling:
        logger.info(json.dumps({"event": "ai_call_budget_exhausted", "request_id": scope.request_id,
                                "operation": operation, "purpose": purpose, "calls": scope.calls,
                                "max_calls": ceiling, "accounting": scope.kind}, separators=(",", ":"), default=str))
        raise ProviderCallBudgetExhausted
    if scope.max_usd is not None and (scope.unpriced_calls or scope.spent_usd >= scope.max_usd):
        _refuse(scope, operation, purpose, "offline_usd_budget", spent_usd=round(scope.spent_usd, 6),
                unpriced_calls=scope.unpriced_calls)
        raise ProviderCallBudgetExhausted
    limit = settings.max_output_tokens_by_operation[operation]
    effort = settings.reasoning_effort_by_operation.get(operation)
    if effort:
        validate_effort(request.model, effort)
    request = ProviderRequest(operation, request.model, request.user, request.system, request.schema,
                              request.timeout, limit, effort or None)
    attempt = scope.calls
    reservation = None
    if scope.kind == "production":
        reservation = await run_in_threadpool(scope.tracker.reserve_output, scope.uid, limit)
    scope.calls += 1
    started = perf_counter()
    event = {
        "event": "ai_usage",
        "request_id": scope.request_id,
        "accounting": scope.kind,
        "operation": operation,
        "purpose": purpose,
        "provider": adapter.name,
        "model": request.model,
        "retry_count": attempt,
        "reserved_output_tokens": limit,
        "status": "error",
        "outcome": Outcome.PROVIDER_ERROR,
    }
    usage: Usage = Usage()
    try:
        result = await adapter.send(request, issue(request))
        if result.outcome != Outcome.TIMEOUT:
            usage = result.usage
            event.update(_usage_fields(usage))
            event["provider_request_id"] = result.provider_request_id
            event["model"] = result.model or request.model
            event["status"] = result.status or "unknown"
            _price(event, settings)
        if result.outcome != Outcome.COMPLETED:
            _raise_for(result.outcome, result.reason)
        parsed = _validated(result.text, request.schema, validate)
        event["outcome"] = Outcome.COMPLETED
        reply = ProviderReply(parsed, result.response_id, event["model"], event["status"], result.raw_usage)
    except AIOutcomeError as exc:
        event["outcome"] = exc.outcome
        event["error_type"] = type(exc).__name__
        if exc.reason:
            event["outcome_reason"] = exc.reason
        await _settle(scope, reservation, limit, exc.outcome, usage, event)
        _emit(event, started)
        raise
    except BaseException as exc:
        event["error_type"] = type(exc).__name__
        event.update(getattr(adapter, "error_details", lambda _: {})(exc))
        await _settle(scope, reservation, limit, Outcome.PROVIDER_ERROR, usage, event)
        _emit(event, started)
        raise
    try:
        # Uzlaştırma başarısızsa başarı gösterilmez; hata yukarı taşınır.
        await _settle(scope, reservation, limit, Outcome.COMPLETED, usage, event, strict=True)
    finally:
        _emit(event, started)
    return reply


async def parse_response(client, operation, *, timeout: float | None = None, validate: Callable | None = None,
                         purpose: str = "primary", **params):
    """TA-001B uyumluluk girişi: OpenAI istemcisi ve Responses parametreleri alır, ``invoke``'a çevirir."""
    from .openai_adapter import OpenAIAdapter

    adapter = OpenAIAdapter(client, raw_input=params["input"]) if "input" in params else OpenAIAdapter(client)
    request = ProviderRequest(Operation(operation), params["model"], schema=params.get("text_format"), timeout=timeout)
    return await invoke(adapter, request, validate=validate, purpose=purpose)


async def _settle(scope, reservation, limit, outcome, usage: Usage, event, strict=False):
    """Kullanılmayan rezervasyonu bir kez iade eder; tüketimi bilinmeyen sonuçta korur.

    Offline kapsamda rezervasyon yoktur; maliyet kapsamın USD sayacına yazılır, bilinmiyorsa sayılır.
    """
    if scope.kind == "offline":
        cost = event.get("estimated_usd")
        if cost is None:
            scope.unpriced_calls += 1
        else:
            scope.spent_usd += cost
        event["reservation"] = "offline"
        return
    output = usage.output
    if not reservation or outcome in KEEP_RESERVATION or output is None:
        event["reservation"] = "kept" if reservation else "none"
        return
    try:
        unused = max(0, limit - min(output, limit))
        await run_in_threadpool(scope.tracker.release_output, reservation, unused, event.get("estimated_usd"))
        event["reservation"] = "released"
    except Exception:
        event["reservation"] = "release_failed"
        if strict:
            raise


def _emit(event, started):
    event["duration_ms"] = round((perf_counter() - started) * 1000)
    logger.info(json.dumps(event, separators=(",", ":"), default=str))
