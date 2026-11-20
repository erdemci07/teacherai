"""Yapılandırılmış Responses çağrıları için ortak sınır.

Buradan yalnızca izin verilen üst veri çıkar. Her sağlayıcı çağrısı:
1. işleme özel sınırla çıktı rezervasyonu yapar,
2. SDK'nın ham yanıtını alır; durum ve refusal kontrolü yapılandırılmış
   ayrıştırmadan önce yapılır (kesilen JSON böylece doğru sınıflanır),
3. tam olarak bir sonuca (ai_outcomes.Outcome) düşer ve tek ai_usage satırı yazar,
4. rezervasyonu en fazla bir kez, sonuç kuralına göre iade eder.
"""

import asyncio
import json
import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable

from openai import APIError, APITimeoutError
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
from .operations import Operation, validate_effort
from .settings import get_settings

logger = logging.getLogger("teacherai.ai_usage")


@dataclass
class Accounting:
    request_id: str
    settings: object
    tracker: object
    uid: str
    calls: int = 0


@dataclass
class ProviderReply:
    """Doğrulanmış sağlayıcı yanıtı. Sağlayıcılar yalnızca bu alanları okur."""

    output_parsed: Any
    id: str | None = None
    model: str | None = None
    status: str = "completed"
    usage: dict = field(default_factory=dict)


_current = ContextVar("provider_accounting", default=None)


def begin_accounting(request_id, settings, tracker, uid):
    return _current.set(Accounting(request_id, settings, tracker, uid))


def end_accounting(token):
    _current.reset(token)


def _classify(body: dict, text_format, validate: Callable | None):
    """Ham Responses gövdesini tek bir sonuca indirger; başarıda ayrıştırılmış çıktıyı döndürür."""
    status = body.get("status")
    if status == "incomplete":
        reason = (body.get("incomplete_details") or {}).get("reason")
        if reason == "max_output_tokens":
            raise AIOutputTruncatedError(reason)
        if reason == "content_filter":
            raise AIOutputFilteredError(reason)
        raise AIOutputIncompleteError(reason or "unknown")
    texts, refused = [], False
    for item in body.get("output") or []:
        if item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if part.get("type") == "refusal":
                refused = True
            elif part.get("type") == "output_text":
                texts.append(part.get("text") or "")
    if refused:
        raise AIRefusalError("refusal")
    if status != "completed":
        raise AIOutcomeError(str(status or "missing_status"))
    if not texts:
        raise AIInvalidOutputError("missing_output")
    try:
        parsed = text_format.model_validate_json(texts[-1]) if text_format else texts[-1]
        return validate(parsed) if validate else parsed
    except Exception as exc:
        raise AIInvalidOutputError(type(exc).__name__) from exc


def _usage_fields(usage: dict) -> dict:
    return {
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "cached_tokens": (usage.get("input_tokens_details") or {}).get("cached_tokens"),
        "reasoning_tokens": (usage.get("output_tokens_details") or {}).get("reasoning_tokens"),
    }


def _price(event, settings):
    rates = settings.model_prices.get(event["model"])
    if not (rates and settings.pricing_version):
        return
    if any(event[k] is None for k in ("input_tokens", "cached_tokens", "output_tokens")):
        return
    cached = event["cached_tokens"]
    event["estimated_usd"] = (
        (event["input_tokens"] - cached) * rates[0] + cached * rates[1] + event["output_tokens"] * rates[2]
    ) / 1_000_000
    event["pricing_version"] = settings.pricing_version


async def parse_response(client, operation, *, timeout: float | None = None, validate: Callable | None = None, **params):
    scope = _current.get()
    settings = scope.settings if scope else get_settings()
    operation = Operation(operation)
    limit = settings.max_output_tokens_by_operation[operation]
    effort = settings.reasoning_effort_by_operation.get(operation)
    if effort:
        validate_effort(params["model"], effort)
        params["reasoning"] = {"effort": effort}
    text_format = params.get("text_format")
    attempt = scope.calls if scope else 0
    reservation = None
    if scope:
        reservation = await run_in_threadpool(scope.tracker.reserve_output, scope.uid, limit)
        scope.calls += 1
    started = perf_counter()
    event = {
        "event": "ai_usage",
        "request_id": scope.request_id if scope else None,
        "operation": operation,
        "provider": "openai",
        "model": params["model"],
        "retry_count": attempt,
        "reserved_output_tokens": limit,
        "status": "error",
        "outcome": Outcome.PROVIDER_ERROR,
    }
    usage: dict = {}
    try:
        try:
            call = client.responses.with_raw_response.parse(**params, max_output_tokens=limit, store=False)
            raw = await (asyncio.wait_for(call, timeout) if timeout else call)
        except (APITimeoutError, TimeoutError) as exc:
            raise AITimeoutError(type(exc).__name__) from exc
        body = raw.http_response.json()
        usage = body.get("usage") or {}
        event.update(_usage_fields(usage))
        event["provider_request_id"] = raw.request_id
        event["model"] = body.get("model") or params["model"]
        event["status"] = body.get("status") or "unknown"
        _price(event, settings)
        parsed = _classify(body, text_format, validate)
        event["outcome"] = Outcome.COMPLETED
        reply = ProviderReply(parsed, body.get("id"), event["model"], event["status"], usage)
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
        if isinstance(exc, APIError):
            event["http_status"] = getattr(exc, "status_code", None)
            event["provider_request_id"] = getattr(exc, "request_id", None)
        await _settle(scope, reservation, limit, Outcome.PROVIDER_ERROR, usage, event)
        _emit(event, started)
        raise
    try:
        # Uzlaştırma başarısızsa başarı gösterilmez; hata yukarı taşınır.
        await _settle(scope, reservation, limit, Outcome.COMPLETED, usage, event, strict=True)
    finally:
        _emit(event, started)
    return reply


async def _settle(scope, reservation, limit, outcome, usage, event, strict=False):
    """Kullanılmayan rezervasyonu bir kez iade eder; tüketimi bilinmeyen sonuçta korur."""
    output = usage.get("output_tokens")
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
