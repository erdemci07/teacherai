import asyncio

import httpx
import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError, BadRequestError

import apps.api.app.features.lessons.openai_provider as provider_module
from apps.api.app.features.lessons.exceptions import (
    InvalidLessonPlanError,
    LessonProviderTimeoutError,
    LessonProviderUnavailableError,
)
from apps.api.app.features.lessons.openai_provider import OpenAILessonProvider
from apps.api.app.features.lessons.schemas import LessonDraft, LessonDraftResponse
from apps.api.tests.test_mathai import plan


class ParsedResponse:
    def __init__(self, output_parsed):
        self.output_parsed = output_parsed


class Responses:
    def __init__(self, output=None, error: Exception | None = None, delay: float | None = None) -> None:
        self.output = output
        self.error = error
        self.delay = delay

    async def parse(self, **kwargs):
        if self.delay is not None:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return ParsedResponse(self.output)


class Client:
    def __init__(self, responses: Responses) -> None:
        self.responses = responses


def lesson_payload(step_ids: list[str] | None = None) -> dict:
    ids = step_ids or ["step_1", "step_2"]
    return {
        "learning_objectives": ["denklem çözmek"],
        "concept_id": "concept_linear_equation",
        "content": {
            "question_understanding": "x'i yalnız bırakacağız.",
            "known_values": ["3x + 7 = 19"],
            "unknown": "x",
            "prerequisite_reminder": None,
            "key_rule": "Eşitliğin iki tarafına aynı işlem uygulanır.",
            "strategy": "Sabit terimi temizleyip katsayıya bölelim.",
            "strategy_id": "strategy_isolate",
            "steps": [
                {
                    "id": ids[0],
                    "type": "transformation",
                    "title": "Sabit terimi çıkar",
                    "explanation": "İki taraftan 7 çıkar.",
                    "expressions": [{"type": "equation", "latex": "3x = 12"}],
                    "visual_reference": None,
                },
                {
                    "id": ids[1],
                    "type": "result",
                    "title": "Katsayıya böl",
                    "explanation": "İki tarafı 3'e böl.",
                    "expressions": [{"type": "equation", "latex": "x = 4"}],
                    "visual_reference": None,
                },
            ],
            "common_mistake": "Yalnızca bir taraftan işlem yapma.",
            "mistake_type": "equality_balance",
            "shortcut": None,
            "mini_example": [],
            "teacher_tip": "Her adımda dengeyi koru.",
            "final_answer": "x = 4",
            "final_answer_expressions": [{"type": "equation", "latex": "x = 4"}],
            "takeaway": "Denklem çözerken aynı işlemi iki tarafa da uygularız.",
        },
    }


def status_error(error_class, status: int, body: dict):
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    response = httpx.Response(status, request=request)
    return error_class("sensitive upstream lesson message", response=response, body=body)


def raw_status_error(status: int, body: dict):
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    response = httpx.Response(status, request=request)
    return APIStatusError("sensitive upstream lesson message", response=response, body=body)


def provider_with_responses(monkeypatch, responses: Responses) -> OpenAILessonProvider:
    monkeypatch.setattr(provider_module, "AsyncOpenAI", lambda **kwargs: Client(responses))
    return OpenAILessonProvider(api_key="secret-test-key", model="gpt-test-lesson", timeout_seconds=0.01)


@pytest.mark.asyncio
async def test_valid_structured_response_produces_lesson(monkeypatch) -> None:
    output = LessonDraftResponse.model_validate(lesson_payload())
    provider = provider_with_responses(monkeypatch, Responses(output=output))

    result = await provider.generate_lesson_plan(plan().source_analysis)

    assert result.provider == "openai"
    assert result.model == "gpt-test-lesson"
    assert result.draft.content.steps[0].id == "step_1"
    assert result.draft.content.final_answer_expressions[0].latex == "x = 4"


@pytest.mark.asyncio
async def test_openai_bad_request_is_not_mislabeled_as_provider_unavailable(monkeypatch) -> None:
    upstream = status_error(BadRequestError, 400, {"error": {"type": "invalid_request_error", "code": "bad_schema"}})
    provider = provider_with_responses(monkeypatch, Responses(error=upstream))

    with pytest.raises(InvalidLessonPlanError):
        await provider.generate_lesson_plan(plan().source_analysis)


@pytest.mark.asyncio
async def test_malformed_lesson_draft_maps_to_invalid_lesson(monkeypatch) -> None:
    output = LessonDraftResponse.model_validate(lesson_payload(step_ids=["step_1", "step_3"]))
    provider = provider_with_responses(monkeypatch, Responses(output=output))

    with pytest.raises(InvalidLessonPlanError):
        await provider.generate_lesson_plan(plan().source_analysis)


@pytest.mark.asyncio
async def test_api_connection_error_maps_to_provider_unavailable(monkeypatch) -> None:
    upstream = APIConnectionError(request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
    provider = provider_with_responses(monkeypatch, Responses(error=upstream))

    with pytest.raises(LessonProviderUnavailableError):
        await provider.generate_lesson_plan(plan().source_analysis)


@pytest.mark.asyncio
async def test_timeout_maps_to_lesson_timeout(monkeypatch) -> None:
    upstream = APITimeoutError(request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
    provider = provider_with_responses(monkeypatch, Responses(error=upstream))

    with pytest.raises(LessonProviderTimeoutError):
        await provider.generate_lesson_plan(plan().source_analysis)


@pytest.mark.asyncio
async def test_api_status_server_error_maps_to_provider_unavailable(monkeypatch) -> None:
    provider = provider_with_responses(monkeypatch, Responses(error=raw_status_error(500, {"error": {"type": "server_error"}})))

    with pytest.raises(LessonProviderUnavailableError):
        await provider.generate_lesson_plan(plan().source_analysis)


def test_valid_lesson_draft_with_sequential_steps_succeeds() -> None:
    draft = LessonDraft.model_validate(lesson_payload())

    assert [step.id for step in draft.content.steps] == ["step_1", "step_2"]


def test_invalid_step_sequence_still_fails_application_validation() -> None:
    with pytest.raises(ValueError):
        LessonDraft.model_validate(lesson_payload(step_ids=["step_1", "step_3"]))
