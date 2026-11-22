"""OpenAI Responses adaptörü (TA-005B §7). Davranış TA-005 geçidiyle birebir aynıdır.

İstek gövdesinin bayt bayt aynı kaldığı ``tests/test_gateway_golden.py`` ile sınanır. SDK aktarım
hataları (kimlik, hız sınırı, 4xx/5xx) değiştirilmeden yukarı taşınır; sağlayıcı sınıfları bunları kendi
alan hatalarına çevirir.
"""

from __future__ import annotations

import asyncio
import base64

from openai import APIError, APITimeoutError

from .ai_outcomes import Outcome
from .ai_port import AdapterResult, ImagePart, ProviderAdapter, ProviderRequest, Usage
from .operations import Operation


def openai_input(request: ProviderRequest) -> list[dict]:
    messages = []
    if request.system is not None:
        messages.append({"role": "system", "content": request.system})
    if isinstance(request.user, str):
        messages.append({"role": "user", "content": request.user})
    elif request.user:
        messages.append({"role": "user", "content": [
            {"type": "input_image", "image_url": f"data:{part.media_type};base64,{base64.b64encode(part.data).decode('ascii')}",
             "detail": part.detail} if isinstance(part, ImagePart) else {"type": "input_text", "text": part.text}
            for part in request.user]})
    return messages


def classify(body: dict) -> tuple[Outcome, str | None, str | None]:
    """(sonuç, neden, metin). Durum ve refusal, yapılandırılmış ayrıştırmadan önce denetlenir."""
    status = body.get("status")
    if status == "incomplete":
        reason = (body.get("incomplete_details") or {}).get("reason")
        if reason == "max_output_tokens":
            return Outcome.INCOMPLETE_MAX_TOKENS, reason, None
        return Outcome.INCOMPLETE_OTHER, reason or "unknown", None
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
        return Outcome.REFUSAL, "refusal", None
    if status != "completed":
        return Outcome.PROVIDER_ERROR, str(status or "missing_status"), None
    if not texts:
        return Outcome.INVALID_OUTPUT, "missing_output", None
    return Outcome.COMPLETED, None, texts[-1]


def usage_of(raw: dict) -> Usage:
    return Usage(input=raw.get("input_tokens"), cached_input=(raw.get("input_tokens_details") or {}).get("cached_tokens"),
                 output=raw.get("output_tokens"), reasoning=(raw.get("output_tokens_details") or {}).get("reasoning_tokens"))


class OpenAIAdapter(ProviderAdapter):
    name = "openai"
    operations = frozenset(Operation)

    _NO_INPUT = object()

    def __init__(self, client, raw_input=_NO_INPUT):
        """``raw_input`` yalnız ``gateway.parse_response`` uyumluluk girişi içindir (Responses ``input``)."""
        self.client = client
        self.raw_input = raw_input

    def params(self, request: ProviderRequest) -> dict:
        params: dict = {"model": request.model}
        if self.raw_input is not self._NO_INPUT:
            params["input"] = self.raw_input
        elif request.user is not None or request.system is not None:
            params["input"] = openai_input(request)
        if request.schema is not None:
            params["text_format"] = request.schema
        if request.reasoning:
            params["reasoning"] = {"effort": request.reasoning}
        return {**params, "max_output_tokens": request.max_output_tokens, "store": False}

    async def _send(self, request: ProviderRequest) -> AdapterResult:
        try:
            call = self.client.responses.with_raw_response.parse(**self.params(request))
            raw = await (asyncio.wait_for(call, request.timeout) if request.timeout else call)
        except (APITimeoutError, TimeoutError) as exc:
            return AdapterResult(Outcome.TIMEOUT, reason=type(exc).__name__)
        body = raw.http_response.json()
        outcome, reason, text = classify(body)
        raw_usage = body.get("usage") or {}
        return AdapterResult(outcome, text=text, reason=reason, usage=usage_of(raw_usage),
                             model=body.get("model") or request.model, status=body.get("status") or "unknown",
                             response_id=body.get("id"), provider_request_id=raw.request_id, raw_usage=raw_usage)

    @staticmethod
    def error_details(exc: BaseException) -> dict:
        if isinstance(exc, APIError):
            return {"http_status": getattr(exc, "status_code", None), "provider_request_id": getattr(exc, "request_id", None)}
        return {}
