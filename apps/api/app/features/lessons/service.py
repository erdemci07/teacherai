import logging
from time import perf_counter
from uuid import uuid4

from pydantic import BaseModel

from .exceptions import InvalidQuestionAnalysisError, MathVerificationError, VerificationContradictionError
from .provider import LessonProvider
from .schemas import LessonPlan
from ..board.planner import BoardPlanner
from ..board.schemas import BoardPlan
from ..mathai.schemas import VerificationResult
from ..mathai.service import MathAIService
from ..vision.schemas import VisionAnalysis

logger = logging.getLogger(__name__)


class GeneratedLesson(BaseModel):
    lesson: LessonPlan
    verification: VerificationResult
    board: BoardPlan
    correction_attempted: bool = False
    total_processing_ms: int


class LessonService:
    def __init__(self, provider: LessonProvider, mathai: MathAIService, board_planner: BoardPlanner):
        self.provider = provider
        self.mathai = mathai
        self.board_planner = board_planner

    async def generate(self, analysis: VisionAnalysis, teaching_context=None, request_id: str | None = None) -> GeneratedLesson:
        resolved_request_id = request_id or analysis.request_id
        if not analysis.is_valid_question or analysis.image_status != "valid_math_question":
            raise InvalidQuestionAnalysisError

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

        plan = await self._plan(analysis, None, teaching_context, resolved_request_id)
        plan = self.mathai.reconcile_answer_choice(plan)
        verification = self._verify(plan, resolved_request_id, "math_verification")
        if verification.contradiction:
            correction = True
            feedback = "MathAI çelişki buldu: " + "; ".join(
                check.detail or check.statement for check in verification.checks if check.status == "failed"
            )
            logger.info(
                "Lesson correction requested",
                extra={"request_id": resolved_request_id, "stage": "correction", "failed_checks": len([x for x in verification.checks if x.status == "failed"])},
            )
            plan = await self._plan(analysis, feedback, teaching_context, resolved_request_id)
            plan = self.mathai.reconcile_answer_choice(plan)
            verification = self._verify(plan, resolved_request_id, "math_verification_retry")
            if verification.contradiction:
                logger.warning("Lesson verification contradiction remained", extra={"request_id": resolved_request_id, "stage": "math_verification_retry"})
                raise VerificationContradictionError

        board_started = perf_counter()
        board = self.board_planner.create(plan, verification)
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
        )

    async def _plan(self, analysis, feedback, teaching_context=None, request_id: str | None = None):
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
        return LessonPlan(
            lesson_plan_id=f"lesson_{uuid4().hex}",
            source_analysis=analysis,
            learning_objectives=result.draft.learning_objectives,
            concept_id=result.draft.concept_id,
            content=result.draft.content,
            provider=result.provider,
            model=result.model,
            lesson_generation_ms=duration,
        )

    def _verify(self, plan: LessonPlan, request_id: str | None, stage: str) -> VerificationResult:
        started = perf_counter()
        logger.info("MathAI verification started", extra={"request_id": request_id, "stage": stage, "expression_count": len(plan.source_analysis.mathematical_expressions)})
        try:
            verification = self.mathai.verify(plan)
        except Exception as exc:
            logger.exception(
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
