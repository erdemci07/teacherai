import json
from dataclasses import dataclass
from typing import Any, Literal

from apps.api.app.features.vision.schemas import VisionAnalysis

from ..education.policy import TeachingPolicy
from ..integrity.engine import symbols_of
from ..reasoning.target import target_for
from ..memory.schemas import TeachingContext

CompactionLevel = Literal["normal", "emergency"]

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
    policy = teaching_context if isinstance(teaching_context, TeachingPolicy) else TeachingPolicy(
        learner=teaching_context if isinstance(teaching_context, TeachingContext) else None
    )
    if isinstance(teaching_context, TeachingPolicy):
        teaching_context = policy.learner
    learner_summary = _compact_teaching_context(teaching_context, level)
    exam = policy.exam_context(
        learner_summary.get("exam_goal") if learner_summary else None,
        _limit_text(analysis.exam_context, TEACHING_TEXT_LIMIT),
    )
    visual = analysis.visual_elements
    essential = visual.visual_relevance == "essential"
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
            # TA-003: Görsel çözüm için zorunluysa olgu ve ilişkiler cevabı belirler; sayıları veya metinleri
            # kırpılmaz. Sığmazsa sağlayıcı bütçesi kontrollü bir kurtarma hatası üretir.
            "relevant_visual_facts": list(visual.relevant_visual_facts) if essential else _bounded_items(visual.relevant_visual_facts, visual_fact_limit, VISUAL_TEXT_LIMIT),
            "relationships": list(visual.relationships) if essential else _bounded_items(visual.relationships, relationship_limit, VISUAL_TEXT_LIMIT),
            "description": _limit_text(visual.description, VISUAL_TEXT_LIMIT) if level == "normal" and visual.visual_relevance == "essential" and not visual.relationships else None,
            # TA-004: zorunlu görselin olguları yoksa sağlayıcıya şekil bilgisi uydurmaması açıkça bildirilir.
            "visual_evidence": "missing" if essential and not (visual.relevant_visual_facts or visual.relationships or visual.description) else None,
        }
    )

    strategy = answer_strategy(analysis)
    hidden = strategy == "solve_first_hidden"
    # TA-003: Soru metni, ifadeler, seçenekler ve öncüller karakter dilimlemeyle kısaltılmaz; yalnızca
    # boşluk normalleşir. İsteğe bağlı açıklamalar (belirsizlik notları, görsel betimleme) sıkıştırılabilir.
    problem = _without_empty(
        {
            "question_text": " ".join((analysis.question_text or "").split()),
            "topic": analysis.topic,
            "subtopic": analysis.subtopic,
            "exam_context": analysis.exam_context,
            "question_type": analysis.question_type,
            "difficulty": analysis.difficulty,
            "answer_choices": None if hidden else list(analysis.answer_choices),
            "answer_choice_count": len(analysis.answer_choices) if hidden else None,
            "statements": list(getattr(getattr(analysis, "source", None), "statements", []) or []),
            "mathematical_expressions": list(analysis.mathematical_expressions),
            "ocr_uncertainties": _bounded_items(analysis.ocr_uncertainties, uncertainty_limit, 240),
            "visual_context": visual_payload,
            "question_integrity": _integrity_payload(analysis, strategy),
        }
    )

    payload = _without_empty(
        {
            "problem": problem,
            "verification_feedback": _limit_text(verification_feedback, 1200 if level == "normal" else 600),
            "teaching_context": learner_summary,
            "student_exam": exam.model_dump() if exam and exam.origin == "profile" else None,
            "required_teaching_rules": [rule.model_dump() for rule in policy.rules] or None,
            "student_grade": policy.grade.model_dump() if policy.grade else None,
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


def answer_strategy(analysis: VisionAnalysis) -> str | None:
    """Seçeneklerin ders bağlamına nasıl gireceği.

    ``solve_first_hidden`` yalnızca amaç bir değer bulmaksa, seçenekler sayı/ifadeyse ve kaynakta tek
    değişkenli tek bir denklem varsa uygulanır; böylece MathAI sonucu bağımsız hesaplayıp etiketi
    sonradan belirleyebilir. Diğer durumlarda seçenekler korunur.
    """
    integrity = analysis.integrity
    if integrity is None:
        return None
    strategy = integrity.intent.answer_strategy
    if strategy != "solve_first_hidden":
        return strategy
    equations = [
        item for item in integrity.expressions
        if item.role == "given" and item.status == "parsed" and item.canonical and item.canonical.count(" = ") == 1
        and not any(op in item.canonical for op in ("<", ">", "!="))
    ]
    if len(equations) == 1 and len(symbols_of(equations[0])) == 1:
        return strategy
    return "derive_then_select"


def _integrity_payload(analysis: VisionAnalysis, strategy: str | None) -> dict[str, Any] | None:
    integrity = analysis.integrity
    if integrity is None:
        return None
    target = target_for(analysis, integrity)
    return _without_empty({
        "source_revision": analysis.revision,
        # TA-004: istenen hedef aynı ders çağrısında bildirilir; ek sağlayıcı çağrısı yoktur.
        "answer_target": _without_empty({"kind": target.kind, "expression": target.expression,
                                         "integer_only": target.integer_only or None}) if target.origin == "deterministic" else None,
        "intent": integrity.intent.kind,
        "answer_strategy": strategy,
        "intent_markers": [marker.marker for marker in integrity.intent.markers],
        "statement_labels": list(integrity.intent.statement_labels),
        "confirmed_corrections": [
            {"element": item.element, "original": item.original, "corrected": item.corrected} for item in integrity.corrections
        ],
    })


def _compact_teaching_context(teaching_context: Any, level: CompactionLevel) -> dict[str, Any] | None:
    if not teaching_context:
        return None
    data = teaching_context.model_dump(mode="json") if hasattr(teaching_context, "model_dump") else dict(teaching_context)
    mistake_limit = 3 if level == "normal" else 1
    recent_limit = 3 if level == "normal" else 0
    compact = {
        "exam_goal": _limit_text(data.get("exam_goal"), TEACHING_TEXT_LIMIT),
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
