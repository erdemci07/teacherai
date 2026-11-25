import logging
from datetime import date, datetime, timezone
from time import perf_counter
from typing import Callable
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from ..board.planner import BoardPlanner
from ..board.schemas import BoardPlan
from ...core.ai_outcomes import AIOutcomeError
from ...core.gateway import ProviderCallBudgetExhausted, calls_remaining
from ..curriculum import context as curriculum_context
from ..curriculum import methods
from ..mathematics import guidance as mathematics_guidance
from ..mathematics import strategies as mathematics_strategies
from ..education.curriculum import PolicyCheck
from ..education.curriculum_v2 import EducationalProvenance
from ..education.domain import EducationContext, Grade, Reference
from ..education.policy import TeachingPolicy
from ..education.math_adapter import (
    require_math_question,
    resolved_context,
    validated_math_lesson,
    with_integrity,
)
from ..mathai.schemas import VerificationResult
from ..mathai.service import MathAIService
from ..vision.schemas import VisionAnalysis
from .exceptions import LessonError, MathVerificationError, VerificationContradictionError
from .provider import LessonProvider
from .schemas import LessonPlan

logger = logging.getLogger(__name__)


class GeneratedLesson(BaseModel):
    lesson: LessonPlan
    verification: VerificationResult
    board: BoardPlan
    correction_attempted: bool = False
    total_processing_ms: int
    # TA-003: üretim anındaki tek çözümlenmiş eğitim bağlamı. Eski kayıtlarda yoktur ve geriye dönük
    # olarak öğrencinin bugünkü profilinden doldurulmaz.
    education_context: EducationContext | None = None
    # TA-005: sunucunun sınıf düzeyi yöntem ve müfredat denetimi. Sınıf bilinmiyorsa not_checked.
    # TA-007: MethodPolicy v2 ve Müfredat Kaydı v2 ile üretilir (v1 denetimleri ders akışında kullanılmaz).
    method_check: PolicyCheck | None = None
    curriculum_check: PolicyCheck | None = None
    # TA-006: üretim anındaki müfredat/bilgi kaydı sürümü, program çözümlemesi ve seçilen kayıtlar. Eski
    # derslerde yoktur; kayıt veya profil sonradan değişse de bu ders yeniden hesaplanmaz.
    educational_provenance: EducationalProvenance | None = None


def _today() -> date:
    return datetime.now(timezone.utc).date()


def with_curriculum(teaching_context, grade: Grade | None, payload):
    """Seçilmiş müfredat bağlamı varsa sağlayıcıya TeachingPolicy olarak verilir; yoksa bağlam aynen kalır."""
    if payload is None:
        return teaching_context
    if isinstance(teaching_context, TeachingPolicy):
        return teaching_context.model_copy(update={"curriculum_context": payload, "grade": teaching_context.grade or grade})
    return TeachingPolicy(learner=teaching_context, grade=grade, curriculum_context=payload)


def with_strategies(verification, analysis, grade, policy_set):
    """TA-008: yapısal özelliklere uyan strateji önerileri (taslak; kısıt değil). Onaylı politikanın yasakladığı
    yapıya dayanan strateji uygun değil olarak işaretlenir. Ek çağrı yoktur."""
    report = getattr(verification, "mathematics", None)
    if report is None:
        return verification
    features, _ = mathematics_guidance.analyze_sources(analysis)
    if report.model_kind == "word_problem":
        features.add("word_problem")
    if report.model_kind == "geometry":
        features.add("geometry")
    forbidden = set(policy_set.forbidden) if policy_set is not None else set()
    refs = mathematics_strategies.recommend(features, grade, forbidden)
    return verification.model_copy(update={"mathematics": report.model_copy(update={"strategies": refs})})


class LessonService:
    def __init__(self, provider: LessonProvider, mathai: MathAIService, board_planner: BoardPlanner,
                 clock: Callable[[], date] = _today):
        self.provider = provider
        self.mathai = mathai
        self.board_planner = board_planner
        self.clock = clock

    async def generate(self, analysis: VisionAnalysis, teaching_context=None, request_id: str | None = None,
                       grade: Grade | None = None, learner_status: str | None = None,
                       exam_goal: str | None = None, school_track: str | None = None,
                       advanced_method_requested: bool = False) -> GeneratedLesson:
        resolved_request_id = request_id or analysis.request_id
        analysis = with_integrity(analysis)
        question = require_math_question(analysis)
        education_context = resolved_context(question, teaching_context).model_copy(update={"grade": grade})
        # TA-006: belirlenimci ve sınırlı bağlam; ek sağlayıcı çağrısı veya Firestore okuması yoktur.
        selected = curriculum_context.select(analysis, education_context.subject, grade.value if grade else None,
                                             today=self.clock(), learner_status=learner_status, exam_goal=exam_goal,
                                             track=school_track, advanced_requested=advanced_method_requested)
        attempts: list[dict] = []  # TA-008: her sağlayıcı çağrısı; kabul edilen plan sonda işaretlenir
        if selected.outcome_ids:
            references = [*education_context.references, Reference(kind="curriculum", key=selected.program_id),
                          *(Reference(kind="outcome", key=item) for item in selected.outcome_ids)]
            education_context = education_context.model_copy(update={"references": references[:64]})
        teaching_context = with_curriculum(teaching_context, grade, selected.payload)

        started = perf_counter()
        correction = False
        logger.info(
            "Lesson generation started",
            extra={
                "request_id": resolved_request_id,
                "stage": "lesson_start",
                "vision_provider": analysis.provider,
                "vision_model": analysis.model,
                "lesson_provider": getattr(self.provider, "name", self.provider.__class__.__name__),
                "lesson_model": self.provider.model,
                "topic": analysis.topic,
                "question_type": analysis.question_type,
            },
        )

        plan = await self._plan(analysis, None, teaching_context, resolved_request_id, attempts, "initial")
        plan = await self._reconcile(plan)
        verification = await run_in_threadpool(self._verify, plan, resolved_request_id, "math_verification")
        if verification.status == "failed":
            correction = True
            feedback = "MathAI çelişki buldu: " + "; ".join(
                check.detail or check.statement for check in verification.checks if check.status == "failed"
            )
            logger.info(
                "Lesson correction requested",
                extra={"request_id": resolved_request_id, "stage": "correction", "failed_checks": len([x for x in verification.checks if x.status == "failed"])},
            )
            plan = await self._plan(analysis, feedback, teaching_context, resolved_request_id, attempts,
                                    "verification_correction")
            plan = await self._reconcile(plan)
            verification = await run_in_threadpool(self._verify, plan, resolved_request_id, "math_verification_retry")
            if verification.status == "failed" or not verification.final_answer_verified:
                logger.warning("Lesson verification contradiction remained", extra={"request_id": resolved_request_id, "stage": "math_verification_retry"})
                raise VerificationContradictionError

        grade_value = grade.value if grade is not None else None
        policy_set = selected.policy_set

        def check(candidate, candidate_verification):
            return methods.method_check(candidate, candidate_verification, grade_value, policy_set,
                                        advanced_requested=advanced_method_requested)

        method = check(plan, verification)
        if method.state == "failed" and not correction and calls_remaining() != 0:
            # Tek hedefli düzeltme turu; mevcut lesson_max_provider_calls tavanı içinde kalır.
            correction = True
            logger.info("Lesson method correction requested", extra={"request_id": resolved_request_id, "stage": "method_correction",
                                                                       "operation": ",".join(method.operations)})
            try:
                retry = await self._reconcile(await self._plan(analysis, methods.correction_feedback(method, policy_set),
                                                                teaching_context, resolved_request_id, attempts,
                                                                "method_correction"))
                retry_verification = await run_in_threadpool(self._verify, retry, resolved_request_id, "math_verification_method")
            except (LessonError, AIOutcomeError, ProviderCallBudgetExhausted):
                retry_verification = None  # doğrulanmış özgün ders korunur; yöntem işareti failed kalır
            if retry_verification is not None and retry_verification.status != "failed" and (
                    retry_verification.final_answer_verified or not verification.final_answer_verified):
                plan, verification = retry, retry_verification
                method = check(plan, verification)
        if method.state == "failed":
            logger.warning("Lesson method not verified for grade", extra={"request_id": resolved_request_id, "stage": "method_check"})
        curriculum = methods.curriculum_check(selected.resolution, selected.mapping, grade_value, list(selected.matched))
        verification = with_strategies(verification, analysis, grade_value, policy_set)

        board_started = perf_counter()
        artifact = validated_math_lesson(plan, verification, education_context, (method, curriculum))
        board = self.board_planner.create(plan, verification, artifact)
        logger.info(
            "Lesson board created",
            extra={
                "request_id": resolved_request_id,
                "stage": "board",
                "duration_ms": round((perf_counter() - board_started) * 1000),
                "element_count": len(board.elements),
            },
        )
        duration = round((perf_counter() - started) * 1000)
        logger.info(
            "Lesson generation succeeded",
            extra={
                "request_id": resolved_request_id,
                "stage": "lesson_complete",
                "duration_ms": duration,
                "verification_status": verification.status,
                "correction_attempted": correction,
            },
        )
        return GeneratedLesson(
            lesson=plan,
            verification=verification,
            board=board,
            correction_attempted=correction,
            total_processing_ms=analysis.processing_time_ms + duration,
            education_context=education_context,
            method_check=method,
            curriculum_check=curriculum,
            educational_provenance=curriculum_context.with_attempts(selected.provenance, [
                {"purpose": item["purpose"], "levels": item["levels"], "accepted": item["plan_id"] == plan.lesson_plan_id}
                for item in attempts]),
        )

    async def _plan(self, analysis, feedback, teaching_context=None, request_id: str | None = None,
                    attempts: list | None = None, purpose: str = "initial"):
        started = perf_counter()
        logger.info(
            "Lesson provider planning started",
            extra={
                "request_id": request_id or analysis.request_id,
                "stage": "lesson_provider",
                "provider": getattr(self.provider, "name", self.provider.__class__.__name__),
                "model": self.provider.model,
                "correction": feedback is not None,
            },
        )
        result = await self.provider.generate_lesson_plan(analysis, feedback, teaching_context, request_id=request_id)
        duration = round((perf_counter() - started) * 1000)
        logger.info(
            "Lesson provider planning succeeded",
            extra={
                "request_id": request_id or analysis.request_id,
                "stage": "lesson_provider",
                "provider": result.provider,
                "model": result.model,
                "duration_ms": duration,
            },
        )
        plan_id = f"lesson_{uuid4().hex}"
        if attempts is not None:
            sent = list(getattr(result, "context_levels", ()) or ())
            if not sent:
                level = getattr(result, "context_level", None)
                sent = [level] if level else []
            attempts.append({"purpose": purpose, "levels": [item if item in {"normal", "emergency"} else "unknown"
                                                             for item in sent] or ["unknown"], "plan_id": plan_id})
        return LessonPlan(
            lesson_plan_id=plan_id,
            source_analysis=analysis,
            learning_objectives=result.draft.learning_objectives,
            concept_id=result.draft.concept_id,
            content=result.draft.content,
            provider=result.provider,
            model=result.model,
            lesson_generation_ms=duration,
        )

    async def _reconcile(self, plan):
        try:
            return await run_in_threadpool(self.mathai.reconcile_answer_choice, plan)
        except HTTPException:
            raise
        except Exception as exc:
            raise MathVerificationError from exc

    def _verify(self, plan: LessonPlan, request_id: str | None, stage: str) -> VerificationResult:
        started = perf_counter()
        logger.info("MathAI verification started", extra={"request_id": request_id, "stage": stage, "expression_count": len(plan.source_analysis.mathematical_expressions)})
        try:
            verification = self.mathai.verify(plan)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(
                "MathAI verification failed",
                extra={"request_id": request_id, "stage": stage, "exception_type": type(exc).__name__},
            )
            raise MathVerificationError from exc
        logger.info(
            "MathAI verification completed",
            extra={
                "request_id": request_id,
                "stage": stage,
                "duration_ms": round((perf_counter() - started) * 1000),
                "verification_status": verification.status,
                "contradiction": verification.contradiction,
            },
        )
        return verification
