from apps.api.app.core.ai_outcomes import AIOutcomeError, ProviderFailure
from apps.api.app.core.ai_port import ProviderRequest
from apps.api.app.core.gateway import calls_remaining, invoke
from apps.api.app.core.openai_adapter import OpenAIAdapter
from apps.api.app.core.operations import Operation
import asyncio, json
from pathlib import Path
from openai import (
    AsyncOpenAI,
    APIConnectionError,
    APITimeoutError,
    BadRequestError,
    APIStatusError,
)
from pydantic import ValidationError
from .context import build_interaction_context, fits_context_budget
from .exceptions import (
    InteractionContextTooLargeError,
    InteractionProviderError,
    InvalidInteractionResponseError,
)
from .schemas import Action, AdaptiveDraft
from apps.api.app.features.lessons.schemas import LessonPlan


class OpenAIInteractionProvider:
    def __init__(
        self,
        api_key: str | None,
        model: str,
        timeout: float,
        context_budget_bytes: int = 12000,
        client_factory=None,
    ):
        self._client_factory = client_factory
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.context_budget_bytes = context_budget_bytes
        self.prompt = (Path(__file__).parent / "prompts" / "interaction.txt").read_text(
            encoding="utf-8"
        )

    async def adapt(
        self, action: Action, lesson: LessonPlan, hint_level: int, teaching_context=None
    ) -> AdaptiveDraft:
        if not self.api_key:
            raise InteractionProviderError
        client = (self._client_factory or AsyncOpenAI)(api_key=self.api_key, timeout=self.timeout, max_retries=0)
        try:
            return await self._adapt_with_context(
                client, action, lesson, hint_level, teaching_context, "normal"
            )
        except BadRequestError as exc:
            if not _is_context_limit(exc):
                raise InvalidInteractionResponseError from exc
            try:
                return await self._adapt_with_context(
                    client, action, lesson, hint_level, teaching_context, "emergency"
                )
            except BadRequestError as retry_exc:
                if _is_context_limit(retry_exc):
                    raise InteractionContextTooLargeError from retry_exc
                raise InvalidInteractionResponseError from retry_exc
            except (
                APIConnectionError,
                APITimeoutError,
                asyncio.TimeoutError,
            ) as retry_exc:
                raise InteractionProviderError from retry_exc
            except APIStatusError as retry_exc:
                raise InteractionProviderError from retry_exc
            except ValidationError as retry_exc:
                raise InvalidInteractionResponseError from retry_exc
        except (APIConnectionError, APITimeoutError, asyncio.TimeoutError) as exc:
            raise InteractionProviderError from exc
        except APIStatusError as exc:
            raise InteractionProviderError from exc
        except ValidationError as exc:
            raise InvalidInteractionResponseError from exc

        finally:
            await client.close()

    async def _adapt_with_context(
        self, client, action, lesson, hint_level, teaching_context, compact_level
    ):
        context = build_interaction_context(lesson, action, hint_level, compact_level)
        payload = {
            "interaction_context": context,
            "teaching_context": teaching_context.model_dump(mode="json")
            if teaching_context
            else None,
        }
        if compact_level == "normal" and not fits_context_budget(
            payload, self.context_budget_bytes
        ):
            payload = {
                "interaction_context": build_interaction_context(
                    lesson, action, hint_level, "emergency"
                ),
                "teaching_context": payload["teaching_context"],
            }
        if not fits_context_budget(payload, self.context_budget_bytes):
            raise InteractionContextTooLargeError
        request = ProviderRequest(Operation.INTERACTION, self.model,
                                  user=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                                  system=self.prompt, schema=AdaptiveDraft, timeout=self.timeout + 2)
        r = await invoke(self._adapter(client), request)
        return r.output_parsed

    def _adapter(self, client):
        return OpenAIAdapter(client)


class _NoClient:
    async def close(self):
        return None


class AnthropicInteractionProvider(OpenAIInteractionProvider):
    """TA-005C §1: aynı bağlam, istem, şema (onaylı izdüşüm) ve geçit; yalnız adaptör farklıdır.

    Bağlam aşımında (400 "prompt is too long") OpenAI yoluyla aynı tek acil bağlam denemesi yapılır;
    deneme yalnız mantıksal istek tavanında hak kaldıysa yapılır ve geçitte sayılır.
    """

    name = "anthropic"

    def __init__(self, api_key, model, timeout, context_budget_bytes: int = 12000, transport=None):
        super().__init__(api_key, model, timeout, context_budget_bytes)
        self.transport = transport

    def _adapter(self, client):
        from apps.api.app.core.anthropic_adapter import AnthropicAdapter

        return AnthropicAdapter(self.api_key, transport=self.transport)

    async def adapt(self, action: Action, lesson: LessonPlan, hint_level: int, teaching_context=None) -> AdaptiveDraft:
        if not self.api_key:
            raise InteractionProviderError
        client = _NoClient()
        try:
            return await self._adapt_with_context(client, action, lesson, hint_level, teaching_context, "normal")
        except AIOutcomeError as exc:
            reason = exc.reason if type(exc) is AIOutcomeError else None
            if reason is None:
                raise
            if reason != ProviderFailure.CONTEXT_WINDOW_EXCEEDED:
                raise _interaction_error(reason) from exc
            if calls_remaining() == 0:
                raise InteractionContextTooLargeError from exc
            try:
                return await self._adapt_with_context(client, action, lesson, hint_level, teaching_context, "emergency")
            except AIOutcomeError as retry:
                retry_reason = retry.reason if type(retry) is AIOutcomeError else None
                if retry_reason is None:
                    raise
                if retry_reason == ProviderFailure.CONTEXT_WINDOW_EXCEEDED:
                    raise InteractionContextTooLargeError from retry
                raise _interaction_error(retry_reason) from retry


def _interaction_error(reason):
    if reason in {ProviderFailure.INVALID_REQUEST, ProviderFailure.REQUEST_TOO_LARGE}:
        return InvalidInteractionResponseError()
    return InteractionProviderError()


def _is_context_limit(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        "context_length_exceeded" in text
        or "maximum context length" in text
        or "context length" in text
    )
