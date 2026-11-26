import json
from ..mathematics import guidance as mathematics_guidance
from dataclasses import dataclass
from typing import Any, Literal

from apps.api.app.features.vision.schemas import VisionAnalysis

from ..education.base import Subject
from ..education.policy import TeachingPolicy
from ..education.domain import canonical_subject
from ..integrity.engine import symbols_of
from ..integrity.expression import parse as parse_expression
from ..integrity.expression import symbols as expression_symbols
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
    answer_strategy: str | None = None
    answer_strategy_reason: str | None = None


# TA-009 §15, §17: fizik isteğine eklenen kısa yönerge. Sağlayıcının modeli yetkili değildir; sunucu denetler.
PHYSICS_INSTRUCTIONS = {
    "subject_mode": "physics",
    "model_tr": ("physics_model alanında fiziksel sistemi yapılandır: nicelikleri (soruda yazıldığı biçimiyle original "
                 "alanına birebir alıntı, birimle), cisimleri, yüzeyleri, kuvvetleri, ipleri, hareket evrelerini, "
                 "çarpışmaları veya devre bağlantı grafiğini ve istenen hedefi yaz. Sorunun verdiği uzlaşımları "
                 "(g = 10 m/s², sin 37° = 0,6) problem_convention olarak kullan; standart sabitle değiştirme. Soruda "
                 "yazmayan idealleştirmeyi varsayım olarak belirt. Seri/paralel kararını görsel yakınlıktan değil "
                 "bağlantılardan ver; emin olmadığın bağlantıda connection_certain=false yaz."),
    "explanation_tr": ("Açıklamada seçilen sistemi, eksenleri ve pozitif yönü, uygulanan yasayı ve neden uygulanabildiğini, "
                       "varsayımları ve kısa bir fiziksel anlamlılık denetimini yaz. Sürat/hız, kütle/ağırlık, yer "
                       "değiştirme/alınan yol terimlerini karıştırma. Öğrencinin sınıf düzeyinde türev/integral kullanma."),
}


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

    decision = strategy_decision(analysis)
    strategy = decision.strategy
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
            # TA-006: yalnız resmî kod/başlık ve onaylı bilgi; yoksa anahtar hiç eklenmez (istem değişmez).
            # Acil sıkıştırmada isteğe bağlı olduğu için düşer.
            "curriculum_context": policy.curriculum_context.model_dump(exclude_none=True)
            if policy.curriculum_context and level == "normal" else None,
            # TA-008: kaynak ifadelerden belirlenimci tanım kümesi koşulları (yoksa anahtar eklenmez).
            "mathematics_hints": mathematics_guidance.prompt_hints(analysis),
            # TA-009: yalnız fizik dersinde (bayrak açıkken bu hatta gelir); matematik isteği değişmez.
            "physics": PHYSICS_INSTRUCTIONS if canonical_subject(analysis.subject) == Subject.PHYSICS else None,
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
            answer_strategy=strategy,
            answer_strategy_reason=decision.reason,
        ),
    )


@dataclass(frozen=True)
class StrategyDecision:
    strategy: str | None
    reason: str


# Gizli stratejide MathAI'nin hedefi bağımsız hesaplayabildiği kaynak modelleri (TA-005).
_HIDDEN_MODELS = {
    "constant_expression": {"expression_value", "sum", "difference", "product", "ratio"},
    "single_equation": {"variable_value", "expression_value", "sum", "difference", "product", "ratio",
                        "solution_count", "root_sum", "root_product", "solution_set", "minimum", "maximum"},
    "single_inequality": {"minimum", "maximum", "solution_count"},
}


def strategy_decision(analysis: VisionAnalysis) -> StrategyDecision:
    """Seçeneklerin ders bağlamına nasıl gireceği ve nedeni. Belirlenimcidir, sağlayıcı çağırmaz.

    Seçenekler sorunun parçasıysa (doğru/yanlış, öncül, karşılaştırma, "olabilir/olamaz", grafik/tablo
    yorumu) ``choice_dependent`` korunur. Aksi halde, seçeneklerin hepsi sayı/ifadeyse ve istenen hedef
    belirlenimci olarak tespit edilip MathAI'nin desteklediği bir modelden bağımsız hesaplanabiliyorsa
    ``solve_first_hidden`` seçilir: model önce çözer, seçenek etiketi sonradan bağımsız değerle eşlenir;
    böylece yakın çeldirici şıklar çözümü yönlendiremez. Modeller: değişkensiz ifade (köklü, üslü, kesirli),
    tek değişkenli tek denklem, tek değişkenli tek eşitsizlikte uç değer/sayım. Değişken içeren ifade
    sadeleştirmesinde seçenekler sembolik eşlenemediği için seçenekler korunur.
    """
    integrity = analysis.integrity
    if integrity is None:
        return StrategyDecision(None, "no_integrity_report")
    intent = integrity.intent
    if intent.answer_strategy in {"choice_dependent", "open"}:
        return StrategyDecision(intent.answer_strategy, "choice_dependent_intent" if intent.choice_dependent else "no_choices")
    if not integrity.choices or any(choice.kind not in {"number", "expression"} for choice in integrity.choices):
        return StrategyDecision("derive_then_select", "non_numeric_choices")
    target = target_for(analysis, integrity)
    if target.origin != "deterministic" or not target.computable or target.kind == "statement_combination":
        return StrategyDecision("derive_then_select", "target_not_computable")
    given = [item for item in integrity.expressions if item.role == "given" and item.status == "parsed" and item.canonical]
    if any(item.role == "given" and item.status != "parsed" for item in integrity.expressions):
        return StrategyDecision("derive_then_select", "unparsed_source_expression")
    inequalities = [item for item in given if any(op in item.canonical for op in ("<", ">", "!="))]
    equations = [item for item in given if item not in inequalities and item.canonical.count(" = ") == 1]
    if not given:
        expression = parse_expression(target.expression or "")
        if expression.parsed and not expression_symbols(expression.tree):
            model = "constant_expression"
        else:
            return StrategyDecision("derive_then_select", "symbolic_expression")
    elif len(given) == 1 and len(equations) == 1 and len(symbols_of(equations[0])) == 1:
        model = "single_equation"
    elif len(given) == 1 and len(inequalities) == 1 and len(symbols_of(inequalities[0])) == 1:
        model = "single_inequality"
    else:
        return StrategyDecision("derive_then_select", "model_not_supported")
    if target.kind not in _HIDDEN_MODELS[model]:
        return StrategyDecision("derive_then_select", f"{model}_target_not_supported")
    return StrategyDecision("solve_first_hidden", f"{model}:{target.kind}")


def answer_strategy(analysis: VisionAnalysis) -> str | None:
    return strategy_decision(analysis).strategy


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
