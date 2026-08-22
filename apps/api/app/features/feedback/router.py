from typing import Annotated

from fastapi import APIRouter, Depends

from apps.api.app.core.dependencies import get_feedback_service
from apps.api.app.features.auth.dependencies import optional_user
from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.schemas.responses import ApiResponse

from .schemas import SubmitFeedbackRequest, SubmitFeedbackResponse
from .service import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=ApiResponse[SubmitFeedbackResponse])
def submit_feedback(
    body: SubmitFeedbackRequest,
    service: Annotated[FeedbackService, Depends(get_feedback_service)],
    user: Annotated[AuthenticatedUser | None, Depends(optional_user)],
):
    return ApiResponse(data=service.submit(body, user))
