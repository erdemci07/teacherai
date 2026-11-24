"""Anthropic Messages API adaptörü (TA-005B §8, TA-005C §1–3). İnce ``httpx`` istemcisi; yeni bağımlılık yoktur.

Değerler resmî belgeden alındı (22 Kasım 2026; 24 Kasım 2026'da yeniden doğrulandı; docs.claude.com →
platform.claude.com):
- Messages API: ``POST https://api.anthropic.com/v1/messages``; ``x-api-key``, ``anthropic-version``;
  gövdede ``model``, ``max_tokens``, ``messages``; sistem istemi üst düzey ``system``
  (https://platform.claude.com/docs/en/api/messages).
- Yapılandırılmış çıktı: ``output_config.format = {type: json_schema, schema}``; JSON yanıtın metin
  bloğundadır (https://platform.claude.com/docs/en/build-with-claude/structured-outputs). Gönderilen
  şema ``schema_compat.anthropic_projection`` ile üretilir; doğrulama geçitte özgün Pydantic modeliyle yapılır.
- Görsel: image/jpeg, png, gif, webp; API'de görsel başına 10 MB (base64), en çok 8000×8000 px; istek
  başına 600 görsel (200k bağlamlı modellerde 100; burada daha küçük olan 100 uygulanır)
  (https://platform.claude.com/docs/en/build-with-claude/vision).
- ``stop_reason``: end_turn, max_tokens, stop_sequence, tool_use, pause_turn, refusal,
  model_context_window_exceeded (https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons).
  ``model_context_window_exceeded`` yanıtın bağlam penceresini doldurduğunu söyler; belge "yanıtı kesilmiş
  say" der, bu yüzden ``incomplete_max_tokens`` olur.
- Hatalar (https://platform.claude.com/docs/en/api/errors): gövde ``{"type":"error","error":{"type","message"},
  "request_id"}``; 400 invalid_request_error, 401 authentication_error, 402 billing_error, 403
  permission_error, 404 not_found_error, 413 request_too_large, 429 rate_limit_error, 500 api_error,
  504 timeout_error, 529 overloaded_error. Girdi tek başına bağlam penceresini aşarsa 400
  invalid_request_error "prompt is too long" döner
  (https://platform.claude.com/docs/en/build-with-claude/context-windows).
- usage: input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens.

Neden SDK değil: ``httpx`` kilit dosyasında zaten hash'li (openai bağımlılığı); bu adaptörün tek bir
uç noktaya tek bir POST'u var. Yeni kilitli paket eklenmedi. SDK'nın gizli yeniden deneme döngüsü de
(varsayılan 2 tekrar) bu yüzden yoktur: her gerçek HTTP isteği geçitte bir çağrı olarak sayılır.

Bu sürüm araç (tool), durdurma dizisi, önbellek ve düşünme parametresi göndermez. Bu yüzden
``stop_sequence``, ``tool_use`` ve ``pause_turn`` beklenmeyen değerlerdir ve ``provider_error`` olur.

Günlük/sonuç gizliliği: hata gövdesinin yalnız ``error.type`` alanı okunur. ``error.message`` yalnız
belgelenmiş "prompt is too long" ifadesi için okunur ve hiçbir yere yazılmaz. Anahtar, görsel ve
istem metni sonuçta veya günlükte yer almaz.
"""

from __future__ import annotations

import base64
import io

import httpx

from .ai_outcomes import Outcome, ProviderFailure
from .ai_port import AdapterResult, ImagePart, ProviderAdapter, ProviderRequest, Usage
from .operations import Operation
from .schema_compat import anthropic_projection

URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2026-10-21"  # belgedeki örnek istek başlığı
IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_IMAGE_BASE64_BYTES = 10 * 1024 * 1024
MAX_IMAGE_SIDE = 8000
MAX_IMAGES = 100
STOP_REASONS = {
    "end_turn": Outcome.COMPLETED,
    "max_tokens": Outcome.INCOMPLETE_MAX_TOKENS,
    "model_context_window_exceeded": Outcome.INCOMPLETE_MAX_TOKENS,
    "refusal": Outcome.REFUSAL,
}
# HTTP durumu → kanonik neden. ``error.type`` durumla çelişirse tür kazanır (ör. 500 + timeout_error).
STATUS_FAILURES = {
    400: ProviderFailure.INVALID_REQUEST, 401: ProviderFailure.AUTHENTICATION, 402: ProviderFailure.BILLING,
    403: ProviderFailure.PERMISSION, 404: ProviderFailure.MODEL_NOT_FOUND, 413: ProviderFailure.REQUEST_TOO_LARGE,
    429: ProviderFailure.RATE_LIMITED, 500: ProviderFailure.PROVIDER_INTERNAL, 504: ProviderFailure.PROVIDER_TIMEOUT,
    529: ProviderFailure.OVERLOADED,
}
TYPE_FAILURES = {
    "invalid_request_error": ProviderFailure.INVALID_REQUEST, "authentication_error": ProviderFailure.AUTHENTICATION,
    "billing_error": ProviderFailure.BILLING, "permission_error": ProviderFailure.PERMISSION,
    "not_found_error": ProviderFailure.MODEL_NOT_FOUND, "request_too_large": ProviderFailure.REQUEST_TOO_LARGE,
    "rate_limit_error": ProviderFailure.RATE_LIMITED, "api_error": ProviderFailure.PROVIDER_INTERNAL,
    "timeout_error": ProviderFailure.PROVIDER_TIMEOUT, "overloaded_error": ProviderFailure.OVERLOADED,
}
CONTEXT_MESSAGE = "prompt is too long"


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


def classify_http(status: int, body: object) -> ProviderFailure:
    """HTTP hata yanıtını kanonik nedene indirir. Mesaj metni yalnız bağlam aşımı için okunur."""
    error = body.get("error") if isinstance(body, dict) else None
    kind = error.get("type") if isinstance(error, dict) else None
    failure = TYPE_FAILURES.get(kind) or STATUS_FAILURES.get(status) or ProviderFailure.UNKNOWN
    if failure == ProviderFailure.INVALID_REQUEST and isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and CONTEXT_MESSAGE in message.lower():
            return ProviderFailure.CONTEXT_WINDOW_EXCEEDED
    return failure


def _dimensions(data: bytes) -> tuple[int, int] | None:
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as image:  # yalnız başlık okunur; piksel çözülmez
            return image.size
    except Exception:
        return None


class AnthropicAdapter(ProviderAdapter):
    name = "anthropic"
    # TA-005C: üç işlem de onaylı şema izdüşümüyle desteklenir (scripts/anthropic_schema_compat.py --check).
    operations = frozenset(Operation)

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
            body["output_config"] = {"format": {"type": "json_schema", "schema": anthropic_projection(request.schema).schema}}
        return body

    @staticmethod
    def _block(part):
        if isinstance(part, ImagePart):
            return {"type": "image", "source": {"type": "base64", "media_type": part.media_type,
                                                "data": base64.b64encode(part.data).decode("ascii")}}
        return {"type": "text", "text": part.text}

    def image_error(self, request: ProviderRequest) -> str | None:
        """Gönderilmeden önceki görsel denetimi; alan sağlayıcısı geçitten önce de çağırır (çağrı harcanmaz)."""
        return self._image_error(request)

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
            size = _dimensions(part.data)
            if size is None:
                return "image_unreadable"
            if max(size) > MAX_IMAGE_SIDE:
                return "image_dimension_limit"
        return None

    async def _send(self, request: ProviderRequest) -> AdapterResult:
        rejected = self._image_error(request)
        if rejected:  # gönderilmez; görsel gizliliği ve belge sınırları istemci tarafında uygulanır
            return AdapterResult(Outcome.PROVIDER_ERROR, reason=rejected)
        body = self.body(request)  # şema izdüşümü hatası burada, ağdan önce yükselir
        headers = {"x-api-key": self.api_key, "anthropic-version": API_VERSION, "content-type": "application/json"}
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=request.timeout) as client:
                response = await client.post(URL, json=body, headers=headers)
        except httpx.TimeoutException as exc:
            return AdapterResult(Outcome.TIMEOUT, reason=type(exc).__name__)
        except httpx.HTTPError:
            return AdapterResult(Outcome.PROVIDER_ERROR, reason=ProviderFailure.CONNECTION)
        request_id = response.headers.get("request-id")
        if response.status_code != 200:
            try:
                error_body = response.json()
            except ValueError:
                error_body = None
            failure = classify_http(response.status_code, error_body)
            return AdapterResult(Outcome.PROVIDER_ERROR, reason=failure, status=f"http_{response.status_code}",
                                 provider_request_id=request_id)
        try:
            data = response.json()
        except ValueError:
            return AdapterResult(Outcome.INVALID_OUTPUT, reason="body_not_json", provider_request_id=request_id)
        raw_usage = data.get("usage") or {}
        stop = data.get("stop_reason")
        outcome = STOP_REASONS.get(stop, Outcome.PROVIDER_ERROR)
        texts = [block.get("text") or "" for block in data.get("content") or [] if block.get("type") == "text"]
        if outcome == Outcome.COMPLETED:
            reason = None
        elif outcome == Outcome.PROVIDER_ERROR:
            reason = ProviderFailure.UNEXPECTED_STOP
        else:
            reason = str(stop)
        if outcome == Outcome.COMPLETED and not texts:
            outcome, reason = Outcome.INVALID_OUTPUT, "missing_output"
        return AdapterResult(outcome, text="".join(texts) if outcome == Outcome.COMPLETED else None, reason=reason,
                             usage=usage_of(raw_usage), model=data.get("model") or request.model,
                             status=str(stop or "missing_stop_reason"), response_id=data.get("id"),
                             provider_request_id=request_id, raw_usage=raw_usage)
