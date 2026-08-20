import asyncio
import base64
import logging
from pathlib import Path
from time import perf_counter

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

from apps.api.app.features.vision.exceptions import (
    InvalidProviderResponseError,
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from apps.api.app.features.vision.provider import ProviderResult
from apps.api.app.features.vision.schemas import VisionProviderAnalysis

logger = logging.getLogger(__name__)


class OpenAIVisionProvider:
    name = "openai"

    def __init__(self, api_key: str | None, model: str, timeout_seconds: float) -> None:
        self._api_key = api_key
        self._model = model
        self.model = model
        self._timeout_seconds = timeout_seconds
        self._prompt = (Path(__file__).parent / "prompts" / "question_analysis.txt").read_text(encoding="utf-8")

    async def analyze_image(self, image: bytes, media_type: str, request_id: str | None = None) -> ProviderResult:
        started = perf_counter()
        if not self._api_key:
            error = ProviderConfigurationError()
            self._log_failure(error, request_id, started)
            raise error

        image_url = f"data:{media_type};base64,{base64.b64encode(image).decode('ascii')}"
        client = AsyncOpenAI(api_key=self._api_key, timeout=self._timeout_seconds, max_retries=1)
        try:
            response = await asyncio.wait_for(
                client.responses.parse(
                    model=self._model,
                    input=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "input_text", "text": self._prompt},
                                {"type": "input_image", "image_url": image_url, "detail": "high"},
                            ],
                        }
                    ],
                    text_format=VisionProviderAnalysis,
                ),
                timeout=self._timeout_seconds + 2,
            )
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
        except Exception as exc:
            self._log_failure(exc, request_id, started)
            raise ProviderUnavailableError from exc

        parsed = response.output_parsed
        if parsed is None:
            self._log_failure(InvalidProviderResponseError(), request_id, started)
            raise InvalidProviderResponseError
        try:
            analysis = VisionProviderAnalysis.model_validate(parsed)
        except (ValidationError, ValueError) as exc:
            self._log_failure(exc, request_id, started)
            raise InvalidProviderResponseError from exc
        return ProviderResult(analysis=analysis, provider=self.name, model=self._model, response_id=response.id)

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
