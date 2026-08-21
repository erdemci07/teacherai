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
from apps.api.app.features.lessons.normalization import normalize_lesson_draft_response
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


def provider_with_responses(monkeypatch, responses: Responses, model: str = "gpt-test-lesson") -> OpenAILessonProvider:
    monkeypatch.setattr(provider_module, "AsyncOpenAI", lambda **kwargs: Client(responses))
    return OpenAILessonProvider(api_key="secret-test-key", model=model, timeout_seconds=0.01)


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
async def test_malformed_step_ids_are_normalized_to_sequential_steps(monkeypatch) -> None:
    output = LessonDraftResponse.model_validate(lesson_payload(step_ids=["step_1", "step_3"]))
    provider = provider_with_responses(monkeypatch, Responses(output=output))

    result = await provider.generate_lesson_plan(plan().source_analysis)

    assert [step.id for step in result.draft.content.steps] == ["step_1", "step_2"]


def test_already_correct_step_ids_remain_semantically_equivalent() -> None:
    response = LessonDraftResponse.model_validate(lesson_payload())
    draft = normalize_lesson_draft_response(response)

    assert [step.id for step in draft.content.steps] == ["step_1", "step_2"]
    assert [step.title for step in draft.content.steps] == ["Sabit terimi çıkar", "Katsayıya böl"]


def test_concept_id_with_spaces_and_case_becomes_valid_slug() -> None:
    payload = lesson_payload()
    payload["concept_id"] = "concept_Linear Equations"

    draft = normalize_lesson_draft_response(LessonDraftResponse.model_validate(payload))

    assert draft.concept_id == "concept_linear_equations"


def test_turkish_concept_id_becomes_ascii_safe_slug() -> None:
    payload = lesson_payload()
    payload["concept_id"] = "Doğrusal Denklemler"

    draft = normalize_lesson_draft_response(LessonDraftResponse.model_validate(payload))

    assert draft.concept_id == "concept_dogrusal_denklemler"


def test_strategy_id_is_normalized_safely() -> None:
    payload = lesson_payload()
    payload["content"]["strategy_id"] = "strategy_Cross Multiplication"

    draft = normalize_lesson_draft_response(LessonDraftResponse.model_validate(payload))

    assert draft.content.strategy_id == "strategy_cross_multiplication"


def test_text_whitespace_is_trimmed_without_rewriting_content() -> None:
    payload = lesson_payload()
    payload["content"]["question_understanding"] = "  x'i yalnız bırakacağız.  "
    payload["content"]["steps"][0]["title"] = "  Sabit terimi çıkar  "

    draft = normalize_lesson_draft_response(LessonDraftResponse.model_validate(payload))

    assert draft.content.question_understanding == "x'i yalnız bırakacağız."
    assert draft.content.steps[0].title == "Sabit terimi çıkar"


def test_valid_final_answer_expressions_remain_unchanged() -> None:
    response = LessonDraftResponse.model_validate(lesson_payload())
    draft = normalize_lesson_draft_response(response)

    assert [item.latex for item in draft.content.final_answer_expressions] == ["x = 4"]


def test_empty_final_answer_expression_can_be_extracted_from_exact_equation() -> None:
    payload = lesson_payload()
    payload["content"]["final_answer"] = "k = 3"
    payload["content"]["final_answer_expressions"] = []

    draft = normalize_lesson_draft_response(LessonDraftResponse.model_validate(payload))

    assert draft.content.final_answer_expressions[0].latex == "k = 3"


def test_missing_mathematically_essential_content_is_not_invented() -> None:
    payload = lesson_payload()
    payload["content"]["final_answer"] = "Cevap C seçeneğidir."
    payload["content"]["final_answer_expressions"] = []

    with pytest.raises(InvalidLessonPlanError):
        normalize_lesson_draft_response(LessonDraftResponse.model_validate(payload))


def test_normalized_response_passes_strict_lesson_draft_validation() -> None:
    payload = lesson_payload(step_ids=["anything", "later"])
    payload["concept_id"] = "Doğrusal Denklemler"
    payload["content"]["strategy_id"] = "strategy_Cross Multiplication"

    draft = normalize_lesson_draft_response(LessonDraftResponse.model_validate(payload))

    assert LessonDraft.model_validate(draft.model_dump()) == draft


def test_truly_invalid_mathematical_response_still_fails_cleanly() -> None:
    payload = lesson_payload()
    payload["concept_id"] = "!!!"

    with pytest.raises(InvalidLessonPlanError):
        normalize_lesson_draft_response(LessonDraftResponse.model_validate(payload))


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["gpt-5.6-terra", "gpt-4.1-mini"])
async def test_normalization_behavior_is_independent_of_configured_lesson_model(monkeypatch, model) -> None:
    output = LessonDraftResponse.model_validate(lesson_payload(step_ids=["first", "second"]))
    provider = provider_with_responses(monkeypatch, Responses(output=output), model=model)

    result = await provider.generate_lesson_plan(plan().source_analysis)

    assert result.model == model
    assert [step.id for step in result.draft.content.steps] == ["step_1", "step_2"]


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
