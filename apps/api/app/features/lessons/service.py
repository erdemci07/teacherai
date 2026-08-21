from time import perf_counter
from uuid import uuid4
from pydantic import BaseModel
from .exceptions import InvalidQuestionAnalysisError, VerificationContradictionError
from .provider import LessonProvider
from .schemas import LessonPlan
from ..vision.schemas import VisionAnalysis
from ..mathai.schemas import VerificationResult
from ..mathai.service import MathAIService
from ..board.schemas import BoardPlan
from ..board.planner import BoardPlanner
class GeneratedLesson(BaseModel):
    lesson:LessonPlan; verification:VerificationResult; board:BoardPlan; correction_attempted:bool=False; total_processing_ms:int
class LessonService:
    def __init__(self,provider:LessonProvider,mathai:MathAIService,board_planner:BoardPlanner): self.provider=provider;self.mathai=mathai;self.board_planner=board_planner
    async def generate(self,analysis:VisionAnalysis,teaching_context=None)->GeneratedLesson:
        if not analysis.is_valid_question or analysis.image_status != "valid_math_question":
            raise InvalidQuestionAnalysisError
        started=perf_counter(); correction=False
        plan=await self._plan(analysis,None,teaching_context)
        plan=self.mathai.reconcile_answer_choice(plan)
        verification=self.mathai.verify(plan)
        if verification.contradiction:
            correction=True
            feedback="MathAI çelişki buldu: "+"; ".join(x.detail or x.statement for x in verification.checks if x.status=="failed")
            plan=await self._plan(analysis,feedback,teaching_context); plan=self.mathai.reconcile_answer_choice(plan); verification=self.mathai.verify(plan)
            if verification.contradiction: raise VerificationContradictionError
        board=self.board_planner.create(plan,verification)
        return GeneratedLesson(lesson=plan,verification=verification,board=board,correction_attempted=correction,total_processing_ms=analysis.processing_time_ms+round((perf_counter()-started)*1000))
    async def _plan(self,analysis,feedback,teaching_context=None):
        started=perf_counter(); result=await self.provider.generate_lesson_plan(analysis,feedback,teaching_context)
        return LessonPlan(lesson_plan_id=f"lesson_{uuid4().hex}",source_analysis=analysis,learning_objectives=result.draft.learning_objectives,concept_id=result.draft.concept_id,content=result.draft.content,provider=result.provider,model=result.model,lesson_generation_ms=round((perf_counter()-started)*1000))
