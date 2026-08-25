from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from apps.api.app.core.dependencies import get_share_service
from apps.api.app.schemas.responses import ApiResponse

from .schemas import CreateShareRequest, CreateShareResponse, PublicShareResponse
from .service import ShareService

router = APIRouter(prefix="/shares", tags=["shares"])


@router.post("", response_model=ApiResponse[CreateShareResponse])
async def create_share(body: CreateShareRequest, service: Annotated[ShareService, Depends(get_share_service)]):
    return ApiResponse(data=service.create_or_reuse(body.result, body.existing_share_id))


@router.get("/{share_id}", response_model=ApiResponse[PublicShareResponse])
async def get_share(share_id: str, service: Annotated[ShareService, Depends(get_share_service)]):
    public = service.get_public(share_id)
    if not public:
        raise HTTPException(status_code=404, detail="Shared solution not found.")
    return ApiResponse(data=public)
