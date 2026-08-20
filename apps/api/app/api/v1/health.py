from typing import Annotated

from fastapi import APIRouter, Depends, Request

from apps.api.app.core.dependencies import get_health_service
from apps.api.app.schemas.responses import ApiResponse, HealthData
from apps.api.app.services.health_service import HealthService

router = APIRouter(tags=["system"])


@router.get("/health", response_model=ApiResponse[HealthData])
def health(request: Request, service: Annotated[HealthService, Depends(get_health_service)]) -> ApiResponse[HealthData]:
    return ApiResponse(data=service.get_health(), request_id=request.headers.get("x-request-id"))
