from starlette.concurrency import run_in_threadpool
from typing import Annotated
from fastapi import APIRouter, Depends, Request
from apps.api.app.core.dependencies import get_lesson_service, get_student_service
from apps.api.app.core.admission import admitted
from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.features.students.service import StudentService
from apps.api.app.schemas.responses import ApiResponse
from .schemas import GenerateLessonRequest
from .service import GeneratedLesson, LessonService

router = APIRouter(prefix="/lessons", tags=["lessons"])


@router.post("/generate", response_model=ApiResponse[GeneratedLesson])
async def generate(
    body: GenerateLessonRequest,
    request: Request,
    service: Annotated[LessonService, Depends(get_lesson_service)],
    students: Annotated[StudentService, Depends(get_student_service)],
    user: Annotated[AuthenticatedUser, Depends(admitted("generate"))],
):
    analysis = await run_in_threadpool(
        students.source_analysis,
        user,
        body.analysis_id or (body.analysis.request_id if body.analysis else None),
    )
    context = await run_in_threadpool(students.context, user, analysis.topic)
    result = await service.generate(analysis, context, request.state.request_id)
    await run_in_threadpool(students.save_lesson, user, result)
    return ApiResponse(data=result)
