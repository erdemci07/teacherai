from typing import Annotated
from fastapi import APIRouter,Depends
from apps.api.app.core.dependencies import get_interaction_service
from apps.api.app.schemas.responses import ApiResponse
from .schemas import InteractionRequest,InteractionResponse,PracticeAnswerRequest,PracticeFeedback
from .service import InteractionService
router=APIRouter(prefix="/lessons",tags=["interactions"])
@router.post("/{lesson_id}/interact",response_model=ApiResponse[InteractionResponse])
async def interact(lesson_id:str,body:InteractionRequest,service:Annotated[InteractionService,Depends(get_interaction_service)]):return ApiResponse(data=await service.interact(lesson_id,body))
@router.post("/{lesson_id}/practice/{practice_id}/answer",response_model=ApiResponse[PracticeFeedback])
async def answer(lesson_id:str,practice_id:str,body:PracticeAnswerRequest,service:Annotated[InteractionService,Depends(get_interaction_service)]):return ApiResponse(data=service.submit(lesson_id,practice_id,body))
