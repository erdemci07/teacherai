from typing import Annotated

from apps.api.app.core.admission import admitted
from apps.api.app.core.dependencies import get_lesson_service, get_student_service
from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.features.students.service import StudentService
from apps.api.app.schemas.responses import ApiResponse
from fastapi import APIRouter, Depends, Request, Response
from starlette.concurrency import run_in_threadpool

from ..auth.dependencies import require_user
from ..education.math_adapter import validated_math_lesson
from ..education.presentation import LessonView, plan_panels
from .exceptions import StaleQuestionRevisionError
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
    if body.expected_revision is not None and body.expected_revision != analysis.revision:
        raise StaleQuestionRevisionError
    context = await run_in_threadpool(students.context, user, analysis.topic)
    result = await service.generate(analysis, context, request.state.request_id)
    await run_in_threadpool(students.save_lesson, user, result)
    return ApiResponse(data=result)


@router.get("/{lesson_id}/v2", response_model=ApiResponse[LessonView])
def read_v2(
    lesson_id: str,
    response: Response,
    user: Annotated[AuthenticatedUser, Depends(require_user)],
    students: Annotated[StudentService, Depends(get_student_service)],
):
    """Sahibin sunucuda üretilmiş v1 dersinin belirlenimci v2 görünümü. Salt okunur, kota ve sağlayıcı çağrısı yok."""
    record = students.owned(user, lesson_id)
    stored = GeneratedLesson.model_validate(record.lesson_data)
    artifact = validated_math_lesson(stored.lesson, stored.verification, stored.education_context)
    response.headers["Cache-Control"] = "private, no-store"
    return ApiResponse(data=LessonView(lesson=artifact, panels=plan_panels(artifact), created_at=record.created_at))
