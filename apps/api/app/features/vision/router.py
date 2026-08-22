from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile

from apps.api.app.core.dependencies import get_vision_service
from apps.api.app.features.vision.schemas import NormalizedImagePreview, VisionAnalysis, VisionProviderDiagnostics
from apps.api.app.features.vision.service import VisionService
from apps.api.app.schemas.responses import ApiResponse

router = APIRouter(prefix="/vision", tags=["vision"])


@router.get("/diagnostics", response_model=ApiResponse[VisionProviderDiagnostics])
async def vision_diagnostics(
    service: Annotated[VisionService, Depends(get_vision_service)],
) -> ApiResponse[VisionProviderDiagnostics]:
    return ApiResponse(data=service.diagnostics())


@router.post("/analyze", response_model=ApiResponse[VisionAnalysis])
async def analyze_question_image(
    request: Request,
    service: Annotated[VisionService, Depends(get_vision_service)],
    image: Annotated[UploadFile | None, File()] = None,
) -> ApiResponse[VisionAnalysis]:
    analysis = await service.analyze(image, request.state.request_id)
    return ApiResponse(data=analysis)


@router.post("/preview", response_model=ApiResponse[NormalizedImagePreview])
async def preview_question_image(
    service: Annotated[VisionService, Depends(get_vision_service)],
    image: Annotated[UploadFile | None, File()] = None,
) -> ApiResponse[NormalizedImagePreview]:
    preview = await service.prepare(image)
    return ApiResponse(data=preview)
