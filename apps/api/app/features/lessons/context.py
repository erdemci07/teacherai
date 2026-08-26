import json
from dataclasses import dataclass
from typing import Any, Literal

from apps.api.app.features.vision.schemas import VisionAnalysis

CompactionLevel = Literal["normal", "emergency"]

CORE_TEXT_LIMIT = 3500
VISUAL_TEXT_LIMIT = 700
TEACHING_TEXT_LIMIT = 180


@dataclass(frozen=True)
class LessonContextMetrics:
    size_bytes: int
    estimated_tokens: int
    visual_fact_count: int
    visual_fact_count_after_compaction: int
    context_compaction_level: CompactionLevel
    teaching_context_included: bool


@dataclass(frozen=True)
class BuiltLessonContext:
    payload: dict[str, Any]
    serialized: str
    metrics: LessonContextMetrics


def build_lesson_generation_context(
    analysis: VisionAnalysis,
    verification_feedback: str | None = None,
    teaching_context: Any = None,
    level: CompactionLevel = "normal",
) -> BuiltLessonContext:
    visual = analysis.visual_elements
    original_visual_count = len(visual.relevant_visual_facts) + len(visual.relationships)
    visual_fact_limit = 8 if level == "normal" else 3
    relationship_limit = 10 if level == "normal" else 5
    uncertainty_limit = 6 if level == "normal" else 3

    visual_payload = _without_empty(
        {
            "visual_relevance": visual.visual_relevance,
            "visual_types": [
                name
                for name, present in (
                    ("diagram", visual.has_diagram),
                    ("graph", visual.has_graph),
                    ("table", visual.has_table),
                    ("geometry_figure", visual.has_geometry_figure),
                )
                if present
            ],
            "relevant_visual_facts": _bounded_items(visual.relevant_visual_facts, visual_fact_limit, VISUAL_TEXT_LIMIT),
            "relationships": _bounded_items(visual.relationships, relationship_limit, VISUAL_TEXT_LIMIT),
            "description": _limit_text(visual.description, VISUAL_TEXT_LIMIT) if level == "normal" and visual.visual_relevance == "essential" and not visual.relationships else None,
        }
    )

    problem = _without_empty(
        {
            "question_text": _limit_text(analysis.question_text, CORE_TEXT_LIMIT if level == "normal" else 2400),
            "topic": analysis.topic,
            "subtopic": analysis.subtopic,
            "exam_context": analysis.exam_context,
            "question_type": analysis.question_type,
            "difficulty": analysis.difficulty,
            "answer_choices": _bounded_items(analysis.answer_choices, 8, 240),
            "mathematical_expressions": _bounded_items(analysis.mathematical_expressions, 32, 300),
            "ocr_uncertainties": _bounded_items(analysis.ocr_uncertainties, uncertainty_limit, 240),
            "visual_context": visual_payload,
        }
    )

    payload = _without_empty(
        {
            "problem": problem,
            "verification_feedback": _limit_text(verification_feedback, 1200 if level == "normal" else 600),
            "teaching_context": _compact_teaching_context(teaching_context, level),
        }
    )
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    after_visual_count = len(visual_payload.get("relevant_visual_facts", [])) + len(visual_payload.get("relationships", []))
    return BuiltLessonContext(
        payload=payload,
        serialized=serialized,
        metrics=LessonContextMetrics(
            size_bytes=len(serialized.encode("utf-8")),
            estimated_tokens=max(1, len(serialized) // 4),
            visual_fact_count=original_visual_count,
            visual_fact_count_after_compaction=after_visual_count,
            context_compaction_level=level,
            teaching_context_included="teaching_context" in payload,
        ),
    )


def _compact_teaching_context(teaching_context: Any, level: CompactionLevel) -> dict[str, Any] | None:
    if not teaching_context:
        return None
    data = teaching_context.model_dump(mode="json") if hasattr(teaching_context, "model_dump") else dict(teaching_context)
    mistake_limit = 3 if level == "normal" else 1
    recent_limit = 3 if level == "normal" else 0
    compact = {
        "exam_goal": _limit_text(data.get("exam_goal"), TEACHING_TEXT_LIMIT) if level == "normal" else None,
        "topic_experience": data.get("topic_experience"),
        "recurring_mistakes": data.get("recurring_mistakes", [])[:mistake_limit],
        "support_need": data.get("support_need"),
        "preferred_explanation_depth": data.get("preferred_explanation_depth"),
        "recent_topics": data.get("recent_topics", [])[:recent_limit],
    }
    return _without_empty(compact)


def _limit_text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip() + "..."


def _bounded_items(items: list[str], limit: int, text_limit: int) -> list[str]:
    values = []
    for item in items[:limit]:
        text = _limit_text(item, text_limit)
        if text:
            values.append(text)
    return values


def _without_empty(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item not in (None, "", [], {})}
