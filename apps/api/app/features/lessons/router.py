from typing import Annotated
from fastapi import APIRouter,Depends
from apps.api.app.core.dependencies import get_lesson_service
from apps.api.app.schemas.responses import ApiResponse
from .schemas import GenerateLessonRequest
from .service import GeneratedLesson,LessonService
router=APIRouter(prefix="/lessons",tags=["lessons"])
@router.post("/generate",response_model=ApiResponse[GeneratedLesson])
async def generate(body:GenerateLessonRequest,service:Annotated[LessonService,Depends(get_lesson_service)]): return ApiResponse(data=await service.generate(body.analysis))
