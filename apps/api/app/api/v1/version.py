from typing import Annotated

from fastapi import APIRouter, Depends, Request

from apps.api.app.core.dependencies import get_version_service
from apps.api.app.schemas.responses import ApiResponse, VersionData
from apps.api.app.services.version_service import VersionService

router = APIRouter(tags=["system"])


@router.get("/version", response_model=ApiResponse[VersionData])
def version(request: Request, service: Annotated[VersionService, Depends(get_version_service)]) -> ApiResponse[VersionData]:
    return ApiResponse(data=service.get_version(), request_id=request.headers.get("x-request-id"))
