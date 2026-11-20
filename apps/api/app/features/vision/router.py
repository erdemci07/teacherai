from typing import Annotated

from apps.api.app.core.admission import admitted
from apps.api.app.core.dependencies import get_student_service, get_vision_service
from apps.api.app.features.account.dependencies import active_user
from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.features.education.source import ClarificationRequest
from apps.api.app.features.students.service import StudentService
from apps.api.app.features.vision.schemas import (
    NormalizedImagePreview,
    VisionAnalysis,
    VisionProviderDiagnostics,
)
from apps.api.app.features.vision.service import VisionService
from apps.api.app.schemas.responses import ApiResponse
from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix="/vision", tags=["vision"])


@router.get("/diagnostics", response_model=ApiResponse[VisionProviderDiagnostics])
async def vision_diagnostics(
    service: Annotated[VisionService, Depends(get_vision_service)],
) -> ApiResponse[VisionProviderDiagnostics]:
    return ApiResponse(data=service.diagnostics())


@router.post("/analyze", response_model=ApiResponse[VisionAnalysis])
async def analyze_question_image(
    request: Request,
    user: Annotated[AuthenticatedUser, Depends(admitted('analyze'))],
    students: Annotated[StudentService, Depends(get_student_service)],
    service: Annotated[VisionService, Depends(get_vision_service)],
    image: Annotated[UploadFile | None, File()] = None,
) -> ApiResponse[VisionAnalysis]:
    analysis = await service.analyze(image, request.state.request_id)
    if analysis.is_valid_question:
        await run_in_threadpool(students.save_analysis, user, analysis)
    return ApiResponse(data=analysis)


@router.post("/analyses/{analysis_id}/clarification", response_model=ApiResponse[VisionAnalysis])
async def clarify_question(
    analysis_id: str,
    body: ClarificationRequest,
    response: Response,
    user: Annotated[AuthenticatedUser, Depends(active_user)],
    students: Annotated[StudentService, Depends(get_student_service)],
) -> ApiResponse[VisionAnalysis]:
    """Öğrencinin tek bir belirsizlik için seçimi; yalnızca belirlenimci denetim yeniden çalışır.

    Sağlayıcı çağrılmaz; bu nedenle ücretli kabul/kota gerekmez. Yazma, sahiplik, beklenen revizyon ve
    hesap silme işaretini aynı Firestore işleminde denetler.
    """
    analysis = await run_in_threadpool(students.clarify, user, analysis_id, body)
    response.headers["Cache-Control"] = "private, no-store"
    return ApiResponse(data=analysis)


@router.post("/preview", dependencies=[Depends(admitted("preview"))], response_model=ApiResponse[NormalizedImagePreview])
async def preview_question_image(
    service: Annotated[VisionService, Depends(get_vision_service)],
    image: Annotated[UploadFile | None, File()] = None,
) -> ApiResponse[NormalizedImagePreview]:
    preview = await service.prepare(image)
    return ApiResponse(data=preview)
