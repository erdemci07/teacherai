import json

import httpx
import pytest
from openai import BadRequestError

import apps.api.app.features.lessons.openai_provider as provider_module
from apps.api.app.features.lessons.context import build_lesson_generation_context
from apps.api.app.features.lessons.exceptions import LessonContextTooLargeError
from apps.api.app.features.lessons.openai_provider import OpenAILessonProvider
from apps.api.app.features.lessons.schemas import LessonDraftResponse
from apps.api.app.features.memory.schemas import EvidenceSignal, TeachingContext
from apps.api.tests.test_lesson_provider_errors import lesson_payload
from apps.api.tests.test_mathai import plan


class ParsedResponse:
    def __init__(self, output_parsed):
        self.output_parsed = output_parsed


class CapturingResponses:
    def __init__(self, output, errors=None):
        self.output = output
        self.errors = list(errors or [])
        self.payloads: list[dict] = []
        self.serialized_payloads: list[str] = []

    async def parse(self, **kwargs):
        user_message = kwargs["input"][1]["content"]
        self.serialized_payloads.append(user_message)
        self.payloads.append(json.loads(user_message))
        if self.errors:
            raise self.errors.pop(0)
        return ParsedResponse(self.output)


class Client:
    def __init__(self, responses):
        self.responses = responses


def context_length_error():
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    response = httpx.Response(400, request=request)
    return BadRequestError(
        "context too large",
        response=response,
        body={"error": {"type": "invalid_request_error", "code": "context_length_exceeded"}},
    )


def provider_with_capture(monkeypatch, responses: CapturingResponses, max_context_bytes=24_000):
    monkeypatch.setattr(provider_module, "AsyncOpenAI", lambda **kwargs: Client(responses))
    return OpenAILessonProvider("secret", "gpt-test", 0.5, max_context_bytes=max_context_bytes)


def visual_heavy_analysis():
    analysis = plan().source_analysis.model_copy(deep=True, update={"answer_choices": ["A) 1", "B) 2", "C) 3", "D) 4"]})
    analysis.visual_elements.visual_relevance = "essential"
    analysis.visual_elements.has_graph = True
    analysis.visual_elements.description = " ".join(["Grafikte uzun sahne açıklaması var."] * 120)
    analysis.visual_elements.relevant_visual_facts = [f"ilgili görsel bilgi {i}: x ve y ilişkisi korunmalı" for i in range(20)]
    analysis.visual_elements.relationships = [f"ilişki {i}: eğri y={i} çizgisiyle kesişiyor" for i in range(20)]
    analysis.ocr_uncertainties = [f"belirsizlik {i}" for i in range(10)]
    return analysis


def long_teaching_context():
    return TeachingContext(
        exam_goal=" ".join(["TYT hazırlığı ve temel anlatım ihtiyacı"] * 40),
        topic_experience=8,
        recurring_mistakes=[EvidenceSignal(signal=f"mistake_{i}", count=i + 2, confidence=0.7) for i in range(8)],
        support_need="high",
        preferred_explanation_depth="foundation",
        recent_topics=[f"konu_{i}" for i in range(8)],
    )


def test_compact_lesson_context_excludes_provider_debug_and_image_metadata():
    analysis = visual_heavy_analysis().model_copy(update={"normalized_preview_url": "data:image/jpeg;base64,SECRETIMAGE", "debug": {"provider_response_id": "resp_1"}})

    built = build_lesson_generation_context(analysis, teaching_context=long_teaching_context())
    serialized = built.serialized

    assert "problem" in built.payload
    assert "request_id" not in serialized
    assert "provider" not in serialized
    assert '"model"' not in serialized
    assert "processing_time_ms" not in serialized
    assert "normalized_preview_url" not in serialized
    assert "SECRETIMAGE" not in serialized
    assert "provider_response_id" not in serialized


def test_compact_lesson_context_retains_essential_math_and_visual_information():
    analysis = visual_heavy_analysis()

    built = build_lesson_generation_context(analysis)
    problem = built.payload["problem"]

    assert problem["question_text"] == analysis.question_text
    assert problem["answer_choices"] == analysis.answer_choices
    assert problem["mathematical_expressions"] == analysis.mathematical_expressions
    assert problem["visual_context"]["visual_relevance"] == "essential"
    assert problem["visual_context"]["relationships"]
    assert len(problem["visual_context"]["relationships"]) == 10
    assert len(problem["visual_context"]["relevant_visual_facts"]) == 8


def test_teaching_context_is_bounded_and_emergency_is_smaller():
    normal = build_lesson_generation_context(visual_heavy_analysis(), teaching_context=long_teaching_context())
    emergency = build_lesson_generation_context(visual_heavy_analysis(), teaching_context=long_teaching_context(), level="emergency")

    assert normal.metrics.size_bytes > emergency.metrics.size_bytes
    assert len(normal.payload["teaching_context"]["recurring_mistakes"]) == 3
    assert len(emergency.payload["teaching_context"]["recurring_mistakes"]) == 1
    assert "recent_topics" not in emergency.payload["teaching_context"]


def test_payload_size_is_materially_smaller_than_full_analysis_dump():
    analysis = visual_heavy_analysis().model_copy(update={"normalized_preview_url": "data:image/jpeg;base64," + ("A" * 20_000)})

    full = json.dumps({"analysis": analysis.model_dump(mode="json")}, ensure_ascii=False)
    compact = build_lesson_generation_context(analysis)

    assert compact.metrics.size_bytes < len(full.encode("utf-8")) * 0.35
    assert compact.metrics.size_bytes <= 24_000


@pytest.mark.asyncio
async def test_normal_question_uses_one_lesson_request(monkeypatch):
    responses = CapturingResponses(LessonDraftResponse.model_validate(lesson_payload()))
    provider = provider_with_capture(monkeypatch, responses)

    await provider.generate_lesson_plan(plan().source_analysis)

    assert len(responses.payloads) == 1
    assert "analysis" not in responses.payloads[0]
    assert "problem" in responses.payloads[0]


@pytest.mark.asyncio
async def test_context_length_exceeded_triggers_one_smaller_retry(monkeypatch):
    responses = CapturingResponses(LessonDraftResponse.model_validate(lesson_payload()), errors=[context_length_error()])
    provider = provider_with_capture(monkeypatch, responses)

    await provider.generate_lesson_plan(visual_heavy_analysis(), teaching_context=long_teaching_context())

    assert len(responses.payloads) == 2
    assert len(responses.serialized_payloads[1].encode("utf-8")) < len(responses.serialized_payloads[0].encode("utf-8"))


@pytest.mark.asyncio
async def test_second_context_length_failure_maps_to_controlled_error(monkeypatch):
    responses = CapturingResponses(LessonDraftResponse.model_validate(lesson_payload()), errors=[context_length_error(), context_length_error()])
    provider = provider_with_capture(monkeypatch, responses)

    with pytest.raises(LessonContextTooLargeError):
        await provider.generate_lesson_plan(visual_heavy_analysis(), teaching_context=long_teaching_context())

    assert len(responses.payloads) == 2


def test_large_visual_and_story_contexts_stay_within_budget():
    analysis = visual_heavy_analysis()
    analysis.question_text = " ".join(["Uzun hikaye sorusunda verilen koşullar dikkatli okunmalıdır."] * 300)

    normal = build_lesson_generation_context(analysis, teaching_context=long_teaching_context())
    emergency = build_lesson_generation_context(analysis, teaching_context=long_teaching_context(), level="emergency")

    assert normal.metrics.size_bytes <= 24_000
    assert emergency.metrics.size_bytes <= normal.metrics.size_bytes
