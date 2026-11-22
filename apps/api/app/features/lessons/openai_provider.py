import asyncio
import logging
from pathlib import Path
from time import perf_counter

from apps.api.app.core.ai_port import ProviderRequest
from apps.api.app.core.openai_adapter import OpenAIAdapter
from apps.api.app.core.operations import Operation
from apps.api.app.core.gateway import invoke
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

from ..vision.schemas import VisionAnalysis
from .context import BuiltLessonContext, build_lesson_generation_context
from .exceptions import (
    InvalidLessonPlanError,
    LessonContextTooLargeError,
    LessonProviderConfigurationError,
    LessonProviderTimeoutError,
    LessonProviderUnavailableError,
)
from .normalization import normalize_lesson_draft_response
from .provider import LessonProviderResult
from .schemas import LessonDraftResponse

logger = logging.getLogger(__name__)


class OpenAILessonProvider:
    name = "openai"

    def __init__(self, api_key: str | None, model: str, timeout_seconds: float, max_context_bytes: int = 24_000):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout_seconds
        self.max_context_bytes = max_context_bytes
        self.prompt = (Path(__file__).parent / "prompts" / "lesson_plan.txt").read_text(encoding="utf-8")

    def _client(self):
        return AsyncOpenAI(api_key=self.api_key, timeout=self.timeout, max_retries=0)

    def _adapter(self, client):
        return OpenAIAdapter(client)

    async def generate_lesson_plan(
        self,
        analysis: VisionAnalysis,
        correction_feedback: str | None = None,
        teaching_context=None,
        request_id: str | None = None,
    ) -> LessonProviderResult:
        started = perf_counter()
        if not self.api_key:
            error = LessonProviderConfigurationError()
            self._log_failure(error, started, request_id)
            raise error

        context = self._build_budgeted_context(analysis, correction_feedback, teaching_context, "normal")
        client = self._client()
        try:
            response = await self._request_lesson(client, context, "lessons.correction" if correction_feedback else "lessons.initial")
        except AuthenticationError as exc:
            self._log_failure(exc, started, request_id)
            raise LessonProviderConfigurationError from exc
        except RateLimitError as exc:
            self._log_failure(exc, started, request_id)
            raise LessonProviderUnavailableError from exc
        except BadRequestError as exc:
            self._log_failure(exc, started, request_id)
            if self._is_context_length_error(exc):
                emergency = self._build_budgeted_context(analysis, correction_feedback, teaching_context, "emergency")
                logger.warning(
                    "OpenAI Lesson context exceeded; retrying with emergency compact context request_id=%s first_size=%s retry_size=%s",
                    request_id or "unknown",
                    context.metrics.size_bytes,
                    emergency.metrics.size_bytes,
                )
                try:
                    response = await self._request_lesson(client, emergency, "lessons.context_retry")
                except BadRequestError as retry_exc:
                    self._log_failure(retry_exc, started, request_id)
                    if self._is_context_length_error(retry_exc):
                        raise LessonContextTooLargeError from retry_exc
                    raise InvalidLessonPlanError from retry_exc
                except (APITimeoutError, TimeoutError, asyncio.TimeoutError) as retry_exc:
                    self._log_failure(retry_exc, started, request_id)
                    raise LessonProviderTimeoutError from retry_exc
                except APIConnectionError as retry_exc:
                    self._log_failure(retry_exc, started, request_id)
                    raise LessonProviderUnavailableError from retry_exc
                except APIStatusError as retry_exc:
                    self._log_failure(retry_exc, started, request_id)
                    if retry_exc.status_code == 401:
                        raise LessonProviderConfigurationError from retry_exc
                    if retry_exc.status_code == 429 or retry_exc.status_code >= 500:
                        raise LessonProviderUnavailableError from retry_exc
                    raise InvalidLessonPlanError from retry_exc
            else:
                raise InvalidLessonPlanError from exc
        except (APITimeoutError, TimeoutError, asyncio.TimeoutError) as exc:
            self._log_failure(exc, started, request_id)
            raise LessonProviderTimeoutError from exc
        except APIConnectionError as exc:
            self._log_failure(exc, started, request_id)
            raise LessonProviderUnavailableError from exc
        except APIStatusError as exc:
            self._log_failure(exc, started, request_id)
            if exc.status_code == 401:
                raise LessonProviderConfigurationError from exc
            if exc.status_code == 429 or exc.status_code >= 500:
                raise LessonProviderUnavailableError from exc
            raise InvalidLessonPlanError from exc
        except ValidationError as exc:
            self._log_failure(exc, started, request_id)
            raise InvalidLessonPlanError from exc

        finally:
            await client.close()

        # Normalizasyon gateway içinde çalışır; başarısızlığı invalid_output olarak sınıflanır.
        return LessonProviderResult(response.output_parsed, self.name, self.model)

    async def _request_lesson(self, client: AsyncOpenAI, context: BuiltLessonContext, purpose: str = "lessons.initial"):
        logger.info(
            "Lesson compact context prepared",
            extra={
                "lesson_context_size_bytes": context.metrics.size_bytes,
                "lesson_context_estimated_tokens": context.metrics.estimated_tokens,
                "visual_fact_count": context.metrics.visual_fact_count,
                "visual_fact_count_after_compaction": context.metrics.visual_fact_count_after_compaction,
                "context_compaction_level": context.metrics.context_compaction_level,
                # TA-005: seçenek stratejisi ve nedeni (belirlenimci karar).
                "answer_strategy": context.metrics.answer_strategy,
                "answer_strategy_reason": context.metrics.answer_strategy_reason,
            },
        )
        request = ProviderRequest(Operation.LESSONS, self.model, user=context.serialized, system=self.prompt,
                                  schema=LessonDraftResponse, timeout=self.timeout + 2)
        return await invoke(self._adapter(client), request, validate=normalize_lesson_draft_response, purpose=purpose)

    def _build_budgeted_context(self, analysis: VisionAnalysis, correction_feedback: str | None, teaching_context, level: str) -> BuiltLessonContext:
        context = build_lesson_generation_context(analysis, correction_feedback, teaching_context, level)  # type: ignore[arg-type]
        if context.metrics.size_bytes <= self.max_context_bytes:
            return context
        if level == "normal":
            context = build_lesson_generation_context(analysis, correction_feedback, teaching_context, "emergency")
            if context.metrics.size_bytes <= self.max_context_bytes:
                return context
        raise LessonContextTooLargeError

    @staticmethod
    def _is_context_length_error(exc: Exception) -> bool:
        error_code = getattr(exc, "code", None)
        body = getattr(exc, "body", None)
        if isinstance(body, dict):
            error = body.get("error", body)
            if isinstance(error, dict):
                error_code = error_code or error.get("code")
        return error_code == "context_length_exceeded"

    def _log_failure(self, exc: Exception, started: float, request_id: str | None = None) -> None:
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
            "OpenAI Lesson request failed exception_type=%s provider=%s model=%s http_status=%s openai_error_code=%s openai_error_type=%s request_id=%s duration_ms=%s",
            type(exc).__name__,
            self.name,
            self.model,
            status,
            error_code,
            error_type,
            request_id or "unknown",
            round((perf_counter() - started) * 1000),
        )


class _NoClient:
    async def close(self):
        return None


class AnthropicLessonProvider(OpenAILessonProvider):
    """TA-005B §8: aynı ders bağlamı, istem ve doğrulama; yalnız adaptör farklıdır.

    OpenAI SDK hata eşlemesi burada devreye girmez; Anthropic aktarım hataları adaptörde sonuç sınıfına
    (``provider_error``, ``timeout``) indirgenir ve ortak katmanda AIOutcomeError olur.
    """

    name = "anthropic"

    def __init__(self, api_key, model, timeout_seconds, max_context_bytes=24_000, transport=None):
        super().__init__(api_key, model, timeout_seconds, max_context_bytes)
        self.transport = transport

    def _client(self):
        return _NoClient()

    def _adapter(self, client):
        from apps.api.app.core.anthropic_adapter import AnthropicAdapter

        return AnthropicAdapter(self.api_key, transport=self.transport)
