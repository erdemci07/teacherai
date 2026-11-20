from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from apps.api.app.core.dependencies import get_share_service
from apps.api.app.schemas.responses import ApiResponse

from apps.api.app.features.account.dependencies import active_user
from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.features.students.service import StudentService
from apps.api.app.features.lessons.service import GeneratedLesson
from apps.api.app.core.dependencies import get_student_service

from .schemas import CreateShareRequest, CreateShareResponse, PublicShareResponse
from .service import ShareService

router = APIRouter(prefix="/shares", tags=["shares"])


@router.post("", response_model=ApiResponse[CreateShareResponse])
def create_share(request: Request, body: CreateShareRequest, user: Annotated[AuthenticatedUser, Depends(active_user)], students: Annotated[StudentService, Depends(get_student_service)], service: Annotated[ShareService, Depends(get_share_service)]):
    record = students.owned(user, body.source_id())
    result = GeneratedLesson.model_validate(record.lesson_data)
    return ApiResponse(data=service.create_or_reuse(result, body.existing_share_id, _request_origin(request), user.uid))


@router.get("/{share_id}", response_model=ApiResponse[PublicShareResponse])
def get_share(request: Request, share_id: str, service: Annotated[ShareService, Depends(get_share_service)]):
    public = service.get_public(share_id, _request_origin(request))
    if not public:
        raise HTTPException(status_code=404, detail="Shared solution not found.")
    return ApiResponse(data=public)


def _request_origin(request: Request) -> str:
    return f"{request.url.scheme}://{request.url.netloc}"
