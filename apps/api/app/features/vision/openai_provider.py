import asyncio
import logging
from pathlib import Path
from time import perf_counter

from apps.api.app.core.ai_outcomes import AIOutcomeError
from apps.api.app.core.ai_port import ImagePart, ProviderRequest, TextPart
from apps.api.app.core.gateway import ProviderCallBudgetExhausted, invoke
from apps.api.app.core.openai_adapter import OpenAIAdapter
from apps.api.app.core.operations import Operation
from apps.api.app.core.usage import UsageLimitExceeded
from apps.api.app.features.account.guard import AccountDeletionInProgress
from apps.api.app.features.vision.exceptions import (
    ImageTooLargeError,
    InvalidImageError,
    InvalidProviderResponseError,
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    UnsupportedImageError,
)
from apps.api.app.features.vision.provider import ProviderResult
from apps.api.app.features.vision.schemas import RecheckResponse, VisionProviderAnalysis
from fastapi import HTTPException
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class OpenAIVisionProvider:
    name = "openai"

    def __init__(self, api_key: str | None, model: str, timeout_seconds: float, client_factory=None) -> None:
        # Değerlendirme betiği sahte istemci verebilir; varsayılan çağrı anında AsyncOpenAI'dir.
        self._client_factory = client_factory
        self._api_key = api_key
        self._model = model
        self.model = model
        self._timeout_seconds = timeout_seconds
        self._prompt = (Path(__file__).parent / "prompts" / "question_analysis.txt").read_text(encoding="utf-8")
        self._recheck_prompt = (Path(__file__).parent / "prompts" / "targeted_recheck.txt").read_text(encoding="utf-8")

    async def analyze_image(self, image: bytes, media_type: str, request_id: str | None = None) -> ProviderResult:
        content = (TextPart(self._prompt), ImagePart(image, media_type, "high"))
        response = await self._call(content, VisionProviderAnalysis, "vision.initial", request_id)
        # Şema doğrulaması gateway'de yapılır; burada yalnız doğrulanmış çıktı vardır.
        return ProviderResult(analysis=response.output_parsed, provider=self.name, model=self._model, response_id=response.id)

    async def recheck(self, images: list[tuple[bytes, str]], items: str, request_id: str | None = None) -> RecheckResponse:
        """Belirsiz parçaları hedefli olarak yeniden okur. Aynı gateway, kota ve bütçe sınırından geçer."""
        content = (TextPart(f"{self._recheck_prompt}\n\n{items}"), *(ImagePart(data, kind, "high") for data, kind in images[:2]))
        response = await self._call(content, RecheckResponse, "vision.recheck", request_id)
        return response.output_parsed

    async def _call(self, content, text_format, purpose: str, request_id: str | None):
        started = perf_counter()
        if not self._api_key:
            error = ProviderConfigurationError()
            self._log_failure(error, request_id, started)
            raise error
        client = (self._client_factory or AsyncOpenAI)(api_key=self._api_key, timeout=self._timeout_seconds, max_retries=0)
        try:
            request = ProviderRequest(Operation.VISION, self._model, user=content, schema=text_format,
                                      timeout=self._timeout_seconds + 2)
            return await invoke(OpenAIAdapter(client), request, purpose=purpose)
        except AuthenticationError as exc:
            self._log_failure(exc, request_id, started)
            raise ProviderAuthenticationError from exc
        except RateLimitError as exc:
            self._log_failure(exc, request_id, started)
            raise ProviderRateLimitError from exc
        except BadRequestError as exc:
            self._log_failure(exc, request_id, started)
            raise InvalidProviderResponseError from exc
        except (APITimeoutError, TimeoutError, asyncio.TimeoutError) as exc:
            self._log_failure(exc, request_id, started)
            raise ProviderTimeoutError from exc
        except APIConnectionError as exc:
            self._log_failure(exc, request_id, started)
            raise ProviderUnavailableError from exc
        except APIStatusError as exc:
            self._log_failure(exc, request_id, started)
            if exc.status_code == 401:
                raise ProviderAuthenticationError from exc
            if exc.status_code == 429:
                raise ProviderRateLimitError from exc
            if 400 <= exc.status_code < 500:
                raise InvalidProviderResponseError from exc
            raise ProviderUnavailableError from exc
        except ValidationError as exc:
            self._log_failure(exc, request_id, started)
            raise InvalidProviderResponseError from exc
        except (UsageLimitExceeded, HTTPException, AIOutcomeError, AccountDeletionInProgress, ProviderCallBudgetExhausted):
            raise
        except Exception as exc:
            self._log_failure(exc, request_id, started)
            raise ProviderUnavailableError from exc
        finally:
            await client.close()

    def diagnostics(self) -> dict[str, str | bool]:
        return {"provider": self.name, "configured": bool(self._api_key), "model": self._model}

    async def health(self) -> bool:
        return bool(self._api_key)

    def _log_failure(self, exc: Exception, request_id: str | None, started: float) -> None:
        status = getattr(exc, "status_code", None)
        error_code = getattr(exc, "code", None)
        error_type = getattr(exc, "type", None)
        body = getattr(exc, "body", None)
        if isinstance(body, dict):
            error = body.get("error", body)
            if isinstance(error, dict):
                error_code = error_code or error.get("code")
                error_type = error_type or error.get("type")
        logger.warning(
            "OpenAI Vision request failed exception_type=%s provider=%s model=%s http_status=%s openai_error_code=%s openai_error_type=%s request_id=%s duration_ms=%s",
            type(exc).__name__,
            self.name,
            self._model,
            status,
            error_code,
            error_type,
            request_id or "unknown",
            round((perf_counter() - started) * 1000),
        )


class AnthropicVisionProvider(OpenAIVisionProvider):
    """TA-005C §1: aynı istem, aynı ön işlenmiş görsel, aynı şema ve aynı geçit; yalnız adaptör farklıdır.

    Gizlilik ve sağlayıcı yeteneği ayrı koşullardır: ``allow_images`` (TEACHERAI_ALLOW_STUDENT_IMAGES_TO_ANTHROPIC)
    yoksa hiçbir görsel gönderilmez. Görsel denetimi geçitten önce yapılır; reddedilen görsel çağrı hakkı
    veya rezervasyon harcamaz. Başka sağlayıcıya otomatik geçiş yoktur.
    """

    name = "anthropic"

    def __init__(self, api_key: str | None, model: str, timeout_seconds: float, *, allow_images: bool = False,
                 transport=None) -> None:
        super().__init__(api_key, model, timeout_seconds)
        self._allow_images, self._transport = allow_images, transport

    def diagnostics(self) -> dict[str, str | bool]:
        return {"provider": self.name, "configured": bool(self._api_key and self._allow_images), "model": self._model}

    async def health(self) -> bool:
        return bool(self._api_key and self._allow_images)

    async def _call(self, content, text_format, purpose: str, request_id: str | None):
        from apps.api.app.core.anthropic_adapter import AnthropicAdapter

        started = perf_counter()
        if not self._api_key or not self._allow_images:
            error = ProviderConfigurationError()
            self._log_anthropic(error.code if self._api_key else "missing_key", request_id, started)
            raise error
        adapter = AnthropicAdapter(self._api_key, allow_images=self._allow_images, transport=self._transport)
        request = ProviderRequest(Operation.VISION, self._model, user=content, schema=text_format,
                                  timeout=self._timeout_seconds + 2)
        rejected = adapter.image_error(request)
        if rejected:
            self._log_anthropic(rejected, request_id, started)
            raise _IMAGE_ERRORS.get(rejected, InvalidImageError)()
        try:
            return await invoke(adapter, request, purpose=purpose)
        except AIOutcomeError as exc:
            if type(exc) is not AIOutcomeError:
                raise  # ret, kesilme, geçersiz çıktı, zaman aşımı: OpenAI yoluyla aynı sonuç sınıfı
            self._log_anthropic(exc.reason, request_id, started)
            raise _vision_error(exc.reason) from exc

    def _log_anthropic(self, reason, request_id, started):
        logger.warning("Anthropic Vision request failed reason=%s provider=%s model=%s request_id=%s duration_ms=%s",
                       reason, self.name, self._model, request_id or "unknown", round((perf_counter() - started) * 1000))


_IMAGE_ERRORS = {"student_images_not_allowed": ProviderConfigurationError, "image_size_limit": ImageTooLargeError,
                 "image_dimension_limit": ImageTooLargeError, "image_media_type": UnsupportedImageError}


def _vision_error(reason):
    from apps.api.app.core.ai_outcomes import CONFIGURATION_FAILURES, ProviderFailure

    if reason in CONFIGURATION_FAILURES:
        return ProviderAuthenticationError()
    if reason in {ProviderFailure.RATE_LIMITED, ProviderFailure.OVERLOADED}:
        return ProviderRateLimitError()
    if reason == ProviderFailure.PROVIDER_TIMEOUT:
        return ProviderTimeoutError()
    if reason in {ProviderFailure.INVALID_REQUEST, ProviderFailure.REQUEST_TOO_LARGE,
                  ProviderFailure.CONTEXT_WINDOW_EXCEEDED}:
        return InvalidProviderResponseError()
    if reason in _IMAGE_ERRORS:
        return _IMAGE_ERRORS[reason]()
    return ProviderUnavailableError()
