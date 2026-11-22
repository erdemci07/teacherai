"""Anthropic Messages API adaptörü (TA-005B §8). İnce ``httpx`` istemcisi; yeni bağımlılık yoktur.

Değerler resmî belgeden alındı (22 Kasım 2026; docs.claude.com → platform.claude.com):
- Messages API: ``POST https://api.anthropic.com/v1/messages``; ``x-api-key``, ``anthropic-version``;
  gövdede ``model``, ``max_tokens``, ``messages``; sistem istemi üst düzey ``system``
  (https://platform.claude.com/docs/en/api/messages).
- Yapılandırılmış çıktı: ``output_config.format = {type: json_schema, schema}``; JSON yanıtın metin
  bloğundadır (https://platform.claude.com/docs/en/build-with-claude/structured-outputs).
- Görsel: image/jpeg, png, gif, webp; API'de görsel başına 10 MB (base64); istek başına en çok 100
  görsel (200k bağlamlı modeller; diğerlerinde 600) (https://platform.claude.com/docs/en/build-with-claude/vision).
- ``stop_reason``: end_turn, max_tokens, stop_sequence, tool_use, pause_turn, refusal,
  model_context_window_exceeded (https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons).
- usage: input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens; düşünme
  tokenı ``output_tokens_details.thinking_tokens``.

Neden SDK değil: ``httpx`` kilit dosyasında zaten hash'li (openai bağımlılığı); bu adaptörün tek bir
uç noktaya tek bir POST'u var. Yeni bir kilitli paket ve geçişli bağımlılıkları eklenmedi.

Bu sürüm araç (tool), durdurma dizisi, önbellek ve düşünme parametresi göndermez. Bu yüzden
``stop_sequence``, ``tool_use`` ve ``pause_turn`` beklenmeyen değerlerdir ve ``provider_error`` olur.
"""

from __future__ import annotations

import base64

import httpx

from .ai_outcomes import Outcome
from .ai_port import AdapterResult, ImagePart, ProviderAdapter, ProviderRequest, Usage
from .operations import Operation
from .schema_compat import strict_schema

URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2026-10-21"  # belgedeki örnek istek başlığı
IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_IMAGE_BASE64_BYTES = 10 * 1024 * 1024
MAX_IMAGES = 100
STOP_REASONS = {
    "end_turn": Outcome.COMPLETED,
    "max_tokens": Outcome.INCOMPLETE_MAX_TOKENS,
    "model_context_window_exceeded": Outcome.INCOMPLETE_OTHER,
    "refusal": Outcome.REFUSAL,
}


def usage_of(raw: dict) -> Usage:
    """Anthropic ``input_tokens`` önbellek okumasını içermez; kanonik girdi toplamdır.

    Önbellek yazımı (1,25×/2× fiyat) tek fiyatla gösterilemediği için o durumda ``cached_input`` bilinmez
    sayılır ve maliyet hesaplanmaz.
    """
    plain, read, write = raw.get("input_tokens"), raw.get("cache_read_input_tokens"), raw.get("cache_creation_input_tokens")
    total = None if plain is None else plain + (read or 0) + (write or 0)
    cached = None if read is None or (write or 0) > 0 else read
    reasoning = (raw.get("output_tokens_details") or {}).get("thinking_tokens")
    return Usage(input=total, cached_input=cached, output=raw.get("output_tokens"), reasoning=reasoning)


class AnthropicAdapter(ProviderAdapter):
    name = "anthropic"
    # Yalnız şeması çevrimdışı denetimden geçen işlem (scripts/anthropic_schema_compat.py).
    operations = frozenset({Operation.LESSONS})

    def __init__(self, api_key: str, *, allow_images: bool = False, transport: httpx.AsyncBaseTransport | None = None):
        self.api_key, self.allow_images, self.transport = api_key, allow_images, transport

    def body(self, request: ProviderRequest) -> dict:
        if isinstance(request.user, str) or request.user is None:
            content: str | list = request.user or ""
        else:
            content = [self._block(part) for part in request.user]
        body = {"model": request.model, "max_tokens": request.max_output_tokens,
                "messages": [{"role": "user", "content": content}]}
        if request.system is not None:
            body["system"] = request.system
        if request.schema is not None:
            body["output_config"] = {"format": {"type": "json_schema", "schema": strict_schema(request.schema)}}
        return body

    @staticmethod
    def _block(part):
        if isinstance(part, ImagePart):
            return {"type": "image", "source": {"type": "base64", "media_type": part.media_type,
                                                "data": base64.b64encode(part.data).decode("ascii")}}
        return {"type": "text", "text": part.text}

    def _image_error(self, request: ProviderRequest) -> str | None:
        if not request.has_images:
            return None
        if not self.allow_images:
            return "student_images_not_allowed"
        images = [part for part in request.user if isinstance(part, ImagePart)]
        if len(images) > MAX_IMAGES:
            return "image_count_limit"
        for part in images:
            if part.media_type not in IMAGE_TYPES:
                return "image_media_type"
            if (len(part.data) + 2) // 3 * 4 > MAX_IMAGE_BASE64_BYTES:
                return "image_size_limit"
        return None

    async def _send(self, request: ProviderRequest) -> AdapterResult:
        rejected = self._image_error(request)
        if rejected:  # gönderilmez; görsel gizliliği ve belge sınırları istemci tarafında uygulanır
            return AdapterResult(Outcome.PROVIDER_ERROR, reason=rejected)
        headers = {"x-api-key": self.api_key, "anthropic-version": API_VERSION, "content-type": "application/json"}
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=request.timeout) as client:
                response = await client.post(URL, json=self.body(request), headers=headers)
        except httpx.TimeoutException as exc:
            return AdapterResult(Outcome.TIMEOUT, reason=type(exc).__name__)
        except httpx.HTTPError as exc:
            return AdapterResult(Outcome.PROVIDER_ERROR, reason=type(exc).__name__)
        request_id = response.headers.get("request-id")
        if response.status_code != 200:
            return AdapterResult(Outcome.PROVIDER_ERROR, reason=f"http_{response.status_code}", status="error",
                                 provider_request_id=request_id)
        try:
            data = response.json()
        except ValueError:
            return AdapterResult(Outcome.INVALID_OUTPUT, reason="body_not_json", provider_request_id=request_id)
        raw_usage = data.get("usage") or {}
        stop = data.get("stop_reason")
        outcome = STOP_REASONS.get(stop, Outcome.PROVIDER_ERROR)
        texts = [block.get("text") or "" for block in data.get("content") or [] if block.get("type") == "text"]
        reason = None if outcome == Outcome.COMPLETED else str(stop or "missing_stop_reason")
        if outcome == Outcome.COMPLETED and not texts:
            outcome, reason = Outcome.INVALID_OUTPUT, "missing_output"
        return AdapterResult(outcome, text="".join(texts) if outcome == Outcome.COMPLETED else None, reason=reason,
                             usage=usage_of(raw_usage), model=data.get("model") or request.model,
                             status=str(stop or "unknown"), response_id=data.get("id"),
                             provider_request_id=request_id, raw_usage=raw_usage)
