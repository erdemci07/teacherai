from typing import Annotated

from fastapi import APIRouter, Depends

from apps.api.app.core.dependencies import get_feedback_service
from apps.api.app.core.admission import admitted
from apps.api.app.core.dependencies import get_student_service
from apps.api.app.features.students.service import StudentService
from apps.api.app.features.lessons.service import GeneratedLesson
from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.schemas.responses import ApiResponse

from .schemas import SubmitFeedbackRequest, SubmitFeedbackResponse
from .service import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=ApiResponse[SubmitFeedbackResponse])
def submit_feedback(
    body: SubmitFeedbackRequest,
    service: Annotated[FeedbackService, Depends(get_feedback_service)],
    students: Annotated[StudentService, Depends(get_student_service)],
    user: Annotated[AuthenticatedUser, Depends(admitted("feedback"))],
):
    record = students.owned(user, body.source_id())
    body = body.model_copy(update={'result': GeneratedLesson.model_validate(record.lesson_data)})
    return ApiResponse(data=service.submit(body, user))
