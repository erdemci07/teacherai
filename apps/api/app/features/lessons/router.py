from typing import Annotated
from fastapi import APIRouter,Depends
from apps.api.app.core.dependencies import get_lesson_service,get_student_service
from apps.api.app.features.auth.dependencies import optional_user
from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.features.students.service import StudentService
from apps.api.app.schemas.responses import ApiResponse
from .schemas import GenerateLessonRequest
from .service import GeneratedLesson,LessonService
router=APIRouter(prefix="/lessons",tags=["lessons"])
@router.post("/generate",response_model=ApiResponse[GeneratedLesson])
async def generate(body:GenerateLessonRequest,service:Annotated[LessonService,Depends(get_lesson_service)],students:Annotated[StudentService,Depends(get_student_service)],user:Annotated[AuthenticatedUser|None,Depends(optional_user)]):
    context=students.context(user,body.analysis.topic) if user else None
    return ApiResponse(data=await service.generate(body.analysis,context))
