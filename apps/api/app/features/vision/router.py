from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile

from apps.api.app.core.dependencies import get_vision_service
from apps.api.app.features.vision.schemas import VisionAnalysis
from apps.api.app.features.vision.service import VisionService
from apps.api.app.schemas.responses import ApiResponse

router = APIRouter(prefix="/vision", tags=["vision"])


@router.post("/analyze", response_model=ApiResponse[VisionAnalysis])
async def analyze_question_image(
    request: Request,
    service: Annotated[VisionService, Depends(get_vision_service)],
    image: Annotated[UploadFile | None, File()] = None,
) -> ApiResponse[VisionAnalysis]:
    analysis = await service.analyze(image, request.state.request_id)
    return ApiResponse(data=analysis)
