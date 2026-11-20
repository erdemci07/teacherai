"""Yetkili v1 matematik dersinin salt okunur, belirlenimci eğitim görünümü."""

from pydantic import ValidationError

from ..integrity.engine import EvaluationState, evaluate
from ..lessons.exceptions import (
    InvalidLessonPlanError,
    InvalidQuestionAnalysisError,
    LessonError,
    QuestionClarificationRequiredError,
    VerificationContradictionError,
)
from ..lessons.schemas import LessonPlan
from ..mathai.schemas import VerificationResult
from ..vision.schemas import VisionAnalysis
from .domain import (
    ContextValue,
    EducationContext,
    QuestionUnderstanding,
    Reference,
    Subject,
    canonical_subject,
    capabilities,
)
from .lesson import (
    EducationalDraft,
    ExpressionBlock,
    LessonPlanV2,
    MathAnswer,
    ProseBlock,
    Provenance,
    VerificationReport,
    VisualBlock,
)


class UnsupportedSubjectError(LessonError):
    code = "subject_generation_unavailable"
    status_code = 422
    public_message = "Bu alanda ders üretimi henüz kullanılamıyor."


def understand(analysis: VisionAnalysis) -> QuestionUnderstanding:
    """Mevcut v1 görsel analizini ortak soru sözleşmesine çevirir.

    Mevcut görsel istemi yalnızca matematik sorularını ``valid_math_question`` olarak kabul eder ve
    ``subject`` alanını serbest Türkçe etiket olarak döndürür ("Cebir", "Temel Matematik" gibi). Etiket
    kanonik listede yoksa alan bilgisinin kanıtı bu matematik kapısıdır. Kanonik olarak başka bir alana
    eşlenen etiket (ör. "Fizik") matematik sayılmaz ve desteklenmeyen alan olarak işaretlenir.
    """
    subject = canonical_subject(analysis.subject)
    if subject == Subject.UNKNOWN and analysis.is_valid_question and analysis.image_status == "valid_math_question":
        subject = Subject.MATHEMATICS
    status = {"unreadable": "unreadable", "incomplete_question": "incomplete",
              "not_math_question": "unresolved_subject"}.get(analysis.image_status, "educational")
    if status == "educational" and not capabilities(subject).generation:
        status = "unresolved_subject" if subject == Subject.UNKNOWN else "unsupported_subject"
    visual = analysis.visual_elements
    descriptions = [visual.description] if visual.description else []
    return QuestionUnderstanding(
        source_id=analysis.request_id, status=status, question=analysis.question_text or None,
        context=EducationContext(subject=subject, language=analysis.language or "und",
            source_exam=ContextValue(value=analysis.exam_context, origin="inferred") if analysis.exam_context else None),
        facts=visual.relevant_visual_facts + visual.relationships, choices=analysis.answer_choices,
        expressions=analysis.mathematical_expressions, visuals=descriptions, uncertainties=analysis.ocr_uncertainties,
        revision=analysis.revision if analysis.integrity is not None else None, integrity=analysis.integrity,
    )


def with_integrity(analysis: VisionAnalysis) -> VisionAnalysis:
    """TA-003 öncesi kaydedilmiş analizlere bütünlük kararını sağlayıcı çağırmadan ekler.

    Eski serbest metin belirsizlikleri önemsiz sayılır; böylece eski kayıtlar yeni engellere takılmaz.
    """
    if analysis.integrity is not None:
        return analysis
    report = evaluate(analysis, EvaluationState(revision=analysis.revision, origin="legacy"))
    return analysis.model_copy(update={"integrity": report})


def require_math_question(analysis: VisionAnalysis) -> QuestionUnderstanding:
    if not analysis.is_valid_question:
        raise InvalidQuestionAnalysisError
    question = understand(analysis)
    if question.status != "educational":
        raise UnsupportedSubjectError
    if analysis.integrity is not None and not analysis.integrity.solvable:
        raise QuestionClarificationRequiredError
    return question


def verification_report(result: VerificationResult, integrity=None) -> VerificationReport:
    if result.status == "failed" or result.contradiction:
        raise VerificationContradictionError
    state = {"verified": "passed", "partially_verified": "partially_checked", "unsupported": "unsupported"}[result.status]
    return VerificationReport(
        structural="passed", scientific="partially_checked" if state != "unsupported" else "unsupported",
        calculation=state,
        # TA-003: yapısal kaynak tutarlılığı denetlendi; görselin doğru okunduğu kanıtlanmadı.
        source_consistency="partially_checked" if integrity is not None and integrity.solvable else "not_checked", curriculum="not_checked", method="not_checked",
        pedagogy="not_checked", engine=result.engine,
        checked_claims=[check.statement for check in result.checks if check.status == "passed"],
    )


def project_math(plan: LessonPlan, result: VerificationResult, education_context: EducationContext | None = None) -> LessonPlanV2:
    if plan.schema_.get("version") != "1.0.0" or plan.schema_.get("name") != "teacherai.lesson_plan":
        raise InvalidLessonPlanError
    question = require_math_question(plan.source_analysis)
    c = plan.content
    blocks = []
    def prose(block_id, kind, text):
        if text:
            blocks.append(ProseBlock(id=block_id, kind=kind, text=text))

    prose("understanding", "explanation", c.question_understanding)
    for i, fact in enumerate(c.known_values):
        prose(f"fact_{i}", "explanation", fact)
    prose("unknown", "checkpoint", c.unknown)
    prose("prerequisite", "hint", c.prerequisite_reminder)
    prose("rule", "definition", c.key_rule)
    prose("strategy", "explanation", c.strategy)
    for i, expression in enumerate(c.mini_example):
        blocks.append(ExpressionBlock(id=f"example_{i}", kind="expression", latex=expression.latex))
    for step in c.steps:
        blocks.append(ProseBlock(id=step.id, kind="warning" if step.type == "warning" else "explanation",
                                 title=step.title or None, text=step.explanation))
        for i, expr in enumerate(step.expressions):
            blocks.append(ExpressionBlock(id=f"{step.id}_{i}", kind="expression", latex=expr.latex, relates_to=[step.id]))
        if step.visual_reference:
            blocks.append(VisualBlock(id=f"{step.id}_figure", kind="visual", visual_type="source_figure",
                                      description=step.visual_reference, relates_to=[step.id]))
    prose("mistake", "warning", c.common_mistake)
    prose("shortcut", "hint", c.shortcut)
    prose("teacher_tip", "hint", c.teacher_tip)
    return LessonPlanV2(
        schema={"name": "teacherai.lesson_plan", "version": "2.1.0"},
        lesson_id=plan.lesson_plan_id, source_id=question.source_id, context=education_context or question.context,
        source_revision=plan.source_analysis.revision if plan.source_analysis.integrity is not None else None,
        source_decision=plan.source_analysis.integrity.decision if plan.source_analysis.integrity is not None else None,
        content=EducationalDraft(activity="question_solution",
            objectives=[objective for objective in plan.learning_objectives if objective.strip()],
            references=[Reference(kind="concept", key=plan.concept_id), Reference(kind="method", key=c.strategy_id)],
            blocks=blocks, answer=MathAnswer(kind="math", description=c.final_answer,
                expressions=[expr.latex for expr in c.final_answer_expressions]), takeaway=c.takeaway),
        provenance=Provenance(provider=plan.provider, model=plan.model),
        verification=verification_report(result, plan.source_analysis.integrity),
    )


def resolved_context(question: QuestionUnderstanding, teaching_context=None) -> EducationContext:
    """Ders için tek bağlam: sorudan çıkarılan sınav türü ile öğrencinin profil hedefi ayrı alanlarda kalır."""
    goal = getattr(teaching_context, "exam_goal", None)
    if goal is None and teaching_context is not None and hasattr(teaching_context, "learner"):
        goal = getattr(teaching_context.learner, "exam_goal", None)
    exam = ContextValue(value=goal.strip()[:256], origin="profile") if isinstance(goal, str) and goal.strip() else None
    return question.context.model_copy(update={"exam": exam})


def validated_math_lesson(plan: LessonPlan, result: VerificationResult, education_context: EducationContext | None = None) -> LessonPlanV2:
    try:
        return project_math(plan, result, education_context)
    except ValidationError as exc:
        raise InvalidLessonPlanError from exc
