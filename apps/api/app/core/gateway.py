"""Shared boundary for structured Responses calls. Only allow-listed metadata leaves here."""

import json
import logging
from contextvars import ContextVar
from dataclasses import dataclass
from time import perf_counter

from starlette.concurrency import run_in_threadpool

from .operations import Operation, validate_effort
from .settings import get_settings


@dataclass
class Accounting:
    request_id: str
    settings: object
    tracker: object
    uid: str
    calls: int = 0


_current = ContextVar("provider_accounting", default=None)


def begin_accounting(request_id, settings, tracker, uid):
    return _current.set(Accounting(request_id, settings, tracker, uid))


def end_accounting(token):
    _current.reset(token)


async def parse_response(client, operation, **params):
    scope = _current.get()
    settings = scope.settings if scope else get_settings()
    operation = Operation(operation)
    limit = settings.max_output_tokens_by_operation[operation]
    effort = settings.reasoning_effort_by_operation.get(operation)
    if effort:
        validate_effort(params["model"], effort)
        params["reasoning"] = {"effort": effort}
    started = perf_counter()
    attempt = scope.calls if scope else 0
    reservation = None
    if scope:
        reservation = await run_in_threadpool(
            scope.tracker.reserve_output, scope.uid, limit
        )
        scope.calls += 1
    event = {
        "event": "ai_usage",
        "request_id": scope.request_id if scope else None,
        "operation": operation,
        "provider": "openai",
        "model": params["model"],
        "retry_count": attempt,
        "reserved_output_tokens": limit,
        "status": "error",
    }
    try:
        response = await client.responses.parse(
            **params, max_output_tokens=limit, store=False
        )
        usage = getattr(response, "usage", None)
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            event[key] = getattr(usage, key, None)
        event["cached_tokens"] = getattr(
            getattr(usage, "input_tokens_details", None), "cached_tokens", None
        )
        event["reasoning_tokens"] = getattr(
            getattr(usage, "output_tokens_details", None), "reasoning_tokens", None
        )
        event["provider_request_id"] = getattr(response, "_request_id", None)
        event["model"] = getattr(response, "model", None) or params["model"]
        event["status"] = getattr(response, "status", None) or "completed"
        rates = settings.model_prices.get(event["model"])
        if (
            rates
            and settings.pricing_version
            and all(
                event[k] is not None
                for k in ("input_tokens", "cached_tokens", "output_tokens")
            )
        ):
            cached = event["cached_tokens"]
            event["estimated_usd"] = (
                (event["input_tokens"] - cached) * rates[0]
                + cached * rates[1]
                + event["output_tokens"] * rates[2]
            ) / 1_000_000
            event["pricing_version"] = settings.pricing_version
        if reservation and event["output_tokens"] is not None:
            await run_in_threadpool(
                scope.tracker.release_output,
                reservation,
                max(0, limit - event["output_tokens"]),
            )
        return response
    except BaseException as exc:
        event["error_type"] = type(exc).__name__
        event["http_status"] = getattr(exc, "status_code", None)
        event["provider_request_id"] = getattr(exc, "request_id", None)
        raise
    finally:
        event["duration_ms"] = round((perf_counter() - started) * 1000)
        logging.getLogger("teacherai.ai_usage").info(
            json.dumps(event, separators=(",", ":"))
        )
