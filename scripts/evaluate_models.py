"""Opt-in paid comparison using synthetic questions and the production adapters."""

import argparse
import asyncio
import io
import json
import logging
from pathlib import Path

from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageFont
from pydantic import ValidationError

from apps.api.app.core.settings import get_settings
from apps.api.app.features.interactions.exceptions import InteractionError
from apps.api.app.features.interactions.openai_provider import OpenAIInteractionProvider
from apps.api.app.features.lessons.exceptions import LessonError
from apps.api.app.features.lessons.openai_provider import OpenAILessonProvider
from apps.api.app.features.lessons.schemas import (
    Expression,
    LessonContent,
    LessonPlan,
    Step,
)
from apps.api.app.features.mathai.isolated import IsolatedMathAI
from apps.api.app.features.mathai.parser import MathParseError
from apps.api.app.features.vision.exceptions import VisionError
from apps.api.app.features.vision.openai_provider import OpenAIVisionProvider
from apps.api.app.features.vision.schemas import VisionAnalysis, VisualElements


def reference(case):
    eq = case["question"]
    final = "x = " + case["answer"]
    source = VisionAnalysis(
        request_id=case["id"],
        image_status="valid_math_question",
        is_valid_question=True,
        rejection_reason=None,
        subject="mathematics",
        exam_context=None,
        topic=case["topic"],
        subtopic=None,
        question_type="open",
        language="tr",
        difficulty="easy",
        question_text=eq + " için x değerlerini bul.",
        mathematical_expressions=[eq],
        answer_choices=[],
        visual_elements=VisualElements(
            has_diagram=False,
            has_graph=False,
            has_table=False,
            has_geometry_figure=False,
            description=None,
        ),
        ocr_uncertainties=[],
        confidence=1,
        provider="fixture",
        model="fixture",
        processing_time_ms=0,
    )
    expr = Expression(type="equation", latex=final)
    content = LessonContent(
        question_understanding="x değerlerini bul.",
        strategy="Denklemi düzenle.",
        strategy_id="strategy_solve",
        steps=[
            Step(
                id="step_1",
                type="result",
                title="Sonuç",
                explanation="İki tarafı karşılaştır.",
                expressions=[expr],
            )
        ],
        final_answer=final,
        final_answer_expressions=[expr],
        takeaway="Sonucu yerine koy.",
    )
    return LessonPlan(
        lesson_plan_id=case["id"],
        source_analysis=source,
        learning_objectives=["Denklem çözme"],
        concept_id="concept_equation",
        content=content,
        provider="fixture",
        model="fixture",
        lesson_generation_ms=0,
    )


async def evaluate(case, operation, model, settings):
    plan = reference(case)
    math = IsolatedMathAI()
    key = settings.openai_api_key
    if operation == "vision":
        image = Image.new("RGB", (540, 100), "white")
        ImageDraw.Draw(image).text(
            (20, 25),
            case["question"] + "    x = ?",
            fill="black",
            font=ImageFont.load_default(size=30),
        )
        data = io.BytesIO()
        image.save(data, format="PNG")
        result = await OpenAIVisionProvider(
            key, model, settings.vision_provider_timeout_seconds
        ).analyze_image(data.getvalue(), "image/png")
        equations = result.analysis.mathematical_expressions
        return {
            "expressions": equations,
            "expected_roots_match": len(equations) == 1
            and math.check_answer(equations[0], case["answer"], "x")[0],
        }
    if operation == "lesson":
        draft = (
            await OpenAILessonProvider(
                key, model, settings.lesson_provider_timeout_seconds
            ).generate_lesson_plan(plan.source_analysis)
        ).draft
        candidate = plan.model_copy(update={"content": draft.content})
        verified = math.verify(candidate)
        return {"verification": verified.status, "content": draft.content.model_dump()}
    draft = await OpenAIInteractionProvider(
        key, model, settings.interaction_provider_timeout_seconds
    ).adapt("hint", plan, 1)
    return {"hint": draft.text, "steps": draft.steps}


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("--candidate", default="gpt-6-luna")
    parser.add_argument(
        "--operations",
        nargs="+",
        choices=["vision", "lesson", "interaction"],
        default=["vision", "interaction"],
    )
    args = parser.parse_args()
    settings = get_settings()
    cases = json.loads(
        Path(__file__).with_name("eval-fixtures.json").read_text(encoding="utf-8")
    )
    if not args.allow_paid:
        for case in cases:
            reference(case)
        print(f"{len(cases)} fixtures validated; no API calls.")
        return
    if not settings.openai_api_key or not settings.ai_enabled:
        parser.error("Configured evaluation API key and enabled AI required.")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    incumbent = {
        "vision": settings.openai_vision_model,
        "lesson": settings.openai_lesson_model,
        "interaction": settings.openai_interaction_model,
    }
    failed = False
    for case in cases:
        for operation in args.operations:
            for model in dict.fromkeys([incumbent[operation], args.candidate]):
                row = {"fixture": case["id"], "operation": operation, "model": model}
                try:
                    row["result"] = await evaluate(case, operation, model, settings)
                except (
                    LessonError,
                    VisionError,
                    InteractionError,
                    MathParseError,
                    HTTPException,
                    ValidationError,
                ) as exc:
                    row["error"] = type(exc).__name__
                    failed = True
                print(json.dumps(row, ensure_ascii=True))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
