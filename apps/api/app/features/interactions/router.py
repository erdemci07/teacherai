from starlette.concurrency import run_in_threadpool
from typing import Annotated
from fastapi import APIRouter, Depends

from apps.api.app.core.admission import admitted
from apps.api.app.core.dependencies import get_interaction_service, get_student_service
from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.features.lessons.schemas import LessonPlan
from apps.api.app.features.students.service import StudentService
from apps.api.app.schemas.responses import ApiResponse
from .schemas import (
    InteractionRequest,
    InteractionResponse,
    PracticeAnswerRequest,
    PracticeFeedback,
)
from .service import InteractionService

router = APIRouter(prefix="/lessons", tags=["interactions"])
Students = Annotated[StudentService, Depends(get_student_service)]
Service = Annotated[InteractionService, Depends(get_interaction_service)]


@router.post("/{lesson_id}/interact", response_model=ApiResponse[InteractionResponse])
async def interact(
    lesson_id: str,
    body: InteractionRequest,
    service: Service,
    students: Students,
    user: Annotated[AuthenticatedUser, Depends(admitted("interact"))],
):
    record = await run_in_threadpool(students.owned, user, lesson_id)
    lesson = LessonPlan.model_validate(record.lesson_data["lesson"])
    result = await service.interact(
        lesson_id,
        body.model_copy(update={"lesson": lesson}),
        await run_in_threadpool(students.context, user, record.topic),
        user.uid,
    )
    await run_in_threadpool(students.record_event, user, result.event)
    return ApiResponse(data=result)


@router.post(
    "/{lesson_id}/practice/{practice_id}/answer",
    response_model=ApiResponse[PracticeFeedback],
)
def answer(
    lesson_id: str,
    practice_id: str,
    body: PracticeAnswerRequest,
    service: Service,
    students: Students,
    user: Annotated[AuthenticatedUser, Depends(admitted("answer"))],
):
    students.owned(user, lesson_id)
    result = service.submit(lesson_id, practice_id, body, user.uid)
    students.record_event(user, result.event, practice_id)
    return ApiResponse(data=result)
