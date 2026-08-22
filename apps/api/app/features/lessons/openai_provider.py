import asyncio
import json
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

from .exceptions import (
    InvalidLessonPlanError,
    LessonProviderConfigurationError,
    LessonProviderTimeoutError,
    LessonProviderUnavailableError,
)
from .normalization import normalize_lesson_draft_response
from .provider import LessonProviderResult
from .schemas import LessonDraftResponse
from ..vision.schemas import VisionAnalysis

logger = logging.getLogger(__name__)


class OpenAILessonProvider:
    name = "openai"

    def __init__(self, api_key: str | None, model: str, timeout_seconds: float):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout_seconds
        self.prompt = (Path(__file__).parent / "prompts" / "lesson_plan.txt").read_text(encoding="utf-8")

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

        payload = {
            "analysis": analysis.model_dump(exclude={"debug"}),
            "verification_feedback": correction_feedback,
            "teaching_context": teaching_context.model_dump(mode="json") if teaching_context else None,
        }
        client = AsyncOpenAI(api_key=self.api_key, timeout=self.timeout, max_retries=1)
        try:
            response = await asyncio.wait_for(
                client.responses.parse(
                    model=self.model,
                    input=[
                        {"role": "system", "content": self.prompt},
                        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                    ],
                    text_format=LessonDraftResponse,
                ),
                timeout=self.timeout + 2,
            )
        except AuthenticationError as exc:
            self._log_failure(exc, started, request_id)
            raise LessonProviderConfigurationError from exc
        except RateLimitError as exc:
            self._log_failure(exc, started, request_id)
            raise LessonProviderUnavailableError from exc
        except BadRequestError as exc:
            self._log_failure(exc, started, request_id)
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

        parsed = response.output_parsed
        if parsed is None:
            self._log_failure(InvalidLessonPlanError(), started, request_id)
            raise InvalidLessonPlanError
        try:
            draft = normalize_lesson_draft_response(parsed)
        except InvalidLessonPlanError as exc:
            self._log_failure(exc, started, request_id)
            raise
        return LessonProviderResult(draft, self.name, self.model)

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
