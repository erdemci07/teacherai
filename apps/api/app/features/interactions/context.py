import json

from apps.api.app.features.lessons.schemas import Expression, LessonPlan, Step

MAX_NORMAL_STEPS = 8
MAX_EMERGENCY_STEPS = 4
MAX_EXPRESSIONS = 12
MAX_TEXT = 900
MAX_EMERGENCY_TEXT = 360


def build_interaction_context(lesson: LessonPlan, action: str, hint_level: int, compact_level: str = "normal") -> dict:
    emergency = compact_level == "emergency"
    text_limit = MAX_EMERGENCY_TEXT if emergency else MAX_TEXT
    step_limit = MAX_EMERGENCY_STEPS if emergency else MAX_NORMAL_STEPS
    source = lesson.source_analysis
    content = lesson.content
    return {
        "action": action,
        "hint_level": hint_level if action == "hint" else None,
        "problem": {
            "question_text": _text(source.question_text, text_limit),
            "topic": source.topic,
            "subtopic": source.subtopic,
            "question_type": source.question_type,
            "answer_choices": [_text(choice, 120) for choice in source.answer_choices[:8]],
            "mathematical_expressions": [_text(expr, 240) for expr in source.mathematical_expressions[:MAX_EXPRESSIONS]],
            "visual_facts": _visual_facts(lesson, text_limit, emergency),
        },
        "lesson": {
            "lesson_plan_id": lesson.lesson_plan_id,
            "question_understanding": _text(content.question_understanding, text_limit),
            "key_rule": _text(content.key_rule, text_limit) if content.key_rule else None,
            "strategy": _text(content.strategy, text_limit),
            "steps": [_step(step, text_limit) for step in content.steps[:step_limit]],
            "final_answer": _text(content.final_answer, text_limit),
            "final_answer_expressions": [_expr(expr) for expr in content.final_answer_expressions[:MAX_EXPRESSIONS]],
        },
    }


def fits_context_budget(payload: dict, budget_bytes: int) -> bool:
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) <= budget_bytes


def _step(step: Step, text_limit: int) -> dict:
    return {
        "id": step.id,
        "title": _text(step.title, 180),
        "explanation": _text(step.explanation, text_limit),
        "expressions": [_expr(expr) for expr in step.expressions[:6]],
        "visual_reference": _text(step.visual_reference, 180) if step.visual_reference else None,
    }


def _expr(expr: Expression) -> dict:
    return {"type": expr.type, "latex": expr.latex}


def _visual_facts(lesson: LessonPlan, text_limit: int, emergency: bool) -> list[str]:
    visual = lesson.source_analysis.visual_elements
    if emergency:
        return []
    facts = []
    if visual.description:
        facts.append(_text(visual.description, text_limit))
    facts.extend(_text(item, 220) for item in visual.relevant_visual_facts[:6])
    facts.extend(_text(item, 220) for item in visual.relationships[:6])
    return [item for item in facts if item]


def _text(value: str | None, limit: int) -> str:
    if not value:
        return ""
    clean = " ".join(value.split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 1)].rstrip() + "…"
