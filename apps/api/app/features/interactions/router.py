import logging
from typing import Annotated
from fastapi import APIRouter,Depends
from apps.api.app.core.dependencies import get_interaction_service,get_student_service
from apps.api.app.features.auth.dependencies import optional_user
from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.features.students.service import StudentService
from apps.api.app.schemas.responses import ApiResponse
from .schemas import InteractionRequest,InteractionResponse,PracticeAnswerRequest,PracticeFeedback
from .service import InteractionService
logger=logging.getLogger(__name__);router=APIRouter(prefix="/lessons",tags=["interactions"])
@router.post("/{lesson_id}/interact",response_model=ApiResponse[InteractionResponse])
async def interact(lesson_id:str,body:InteractionRequest,service:Annotated[InteractionService,Depends(get_interaction_service)],students:Annotated[StudentService,Depends(get_student_service)],user:Annotated[AuthenticatedUser|None,Depends(optional_user)]):
    context=students.context(user,body.lesson.source_analysis.topic) if user else None
    result=await service.interact(lesson_id,body,context)
    if user:
        try:students.record_event(user,result.event,result.practice.practice_question_id if result.practice else None)
        except Exception:logger.exception("Optional interaction persistence failed",extra={"student_id":user.uid,"lesson_id":lesson_id})
    return ApiResponse(data=result)
@router.post("/{lesson_id}/practice/{practice_id}/answer",response_model=ApiResponse[PracticeFeedback])
async def answer(lesson_id:str,practice_id:str,body:PracticeAnswerRequest,service:Annotated[InteractionService,Depends(get_interaction_service)],students:Annotated[StudentService,Depends(get_student_service)],user:Annotated[AuthenticatedUser|None,Depends(optional_user)]):
    result=service.submit(lesson_id,practice_id,body)
    if user:
        try:students.record_event(user,result.event,practice_id)
        except Exception:logger.exception("Optional practice persistence failed",extra={"student_id":user.uid,"lesson_id":lesson_id})
    return ApiResponse(data=result)
