import logging
from uuid import uuid4

from apps.api.app.core.ai_outcomes import AIOutcomeError
from apps.api.app.core.gateway import ProviderCallBudgetExhausted
from apps.api.app.core.usage import (
    DuplicateRequest,
    GlobalBudgetExhausted,
    UsageLimitExceeded,
)
from apps.api.app.features.account.guard import AccountDeletionInProgress
from apps.api.app.features.account.service import (
    DeletionUnavailable,
    ReauthenticationRequired,
)
from apps.api.app.features.auth.dependencies import AuthenticationRequired
from apps.api.app.features.interactions.exceptions import InteractionError
from apps.api.app.features.lessons.exceptions import LessonError
from apps.api.app.features.mathai.isolated import MathAIUnavailable
from apps.api.app.features.shares.exceptions import ShareError
from apps.api.app.features.vision.exceptions import VisionError
from apps.api.app.schemas.responses import ErrorResponse
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    from fastapi.exceptions import RequestValidationError
    from google.api_core.exceptions import GoogleAPICallError, RetryError
    from google.auth.exceptions import GoogleAuthError

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse(status_code=422, content={"error":"validation_error", "detail":"Invalid request."})

    @app.exception_handler(GoogleAuthError)
    @app.exception_handler(GoogleAPICallError)
    @app.exception_handler(RetryError)
    async def unavailable(request, exc):
        return JSONResponse(status_code=503, content={"error":"storage_unavailable", "detail":"Service temporarily unavailable."})

    @app.exception_handler(DuplicateRequest)
    async def duplicate_request(request: Request, exc: DuplicateRequest) -> JSONResponse:
        return JSONResponse(status_code=409, content=ErrorResponse(error="duplicate_request", detail="Bu istek zaten alındı; ücretli işlem tekrar çalıştırılmadı.", request_id=getattr(request.state, "request_id", None)).model_dump())

    @app.exception_handler(GlobalBudgetExhausted)
    async def global_budget_handler(request: Request, exc: GlobalBudgetExhausted) -> JSONResponse:
        return JSONResponse(status_code=503, content=ErrorResponse(error="ai_global_budget_exhausted", detail="Öğretmen servisi bugünlük kapasitesine ulaştı. Lütfen daha sonra tekrar dene.", request_id=getattr(request.state, "request_id", None)).model_dump())

    @app.exception_handler(MathAIUnavailable)
    async def mathai_unavailable(request: Request, exc: MathAIUnavailable) -> JSONResponse:
        # TA-005B: mathai_busy (Retry-After), mathai_timeout, mathai_error ayrı kodlardır.
        # TA-005C: mathai_startup_timeout (süreç başlatma gecikmesi) ayrıca ayrılır.
        detail = {"mathai_busy": "Hesap denetimi şu anda yoğun; birkaç saniye sonra tekrar dene.",
                  "mathai_startup_timeout": "Hesap denetimi başlatılamadı; birkaç saniye sonra tekrar dene."}.get(
            exc.code, "Hesap denetimi şu anda tamamlanamadı.")
        return JSONResponse(status_code=503, headers=exc.headers, content=ErrorResponse(
            error=exc.code, detail=detail, request_id=getattr(request.state, "request_id", None)).model_dump())

    @app.exception_handler(ProviderCallBudgetExhausted)
    async def call_budget_handler(request: Request, exc: ProviderCallBudgetExhausted) -> JSONResponse:
        return JSONResponse(status_code=503, content=ErrorResponse(error="ai_call_budget_exhausted", detail="Bu istek için ek inceleme hakkı doldu; yeni ücretli çağrı yapılmadı.", request_id=getattr(request.state, "request_id", None)).model_dump())

    @app.exception_handler(UsageLimitExceeded)
    async def usage_handler(request: Request, exc: UsageLimitExceeded) -> JSONResponse:
        return JSONResponse(status_code=429, content=ErrorResponse(error="usage_limit_exceeded", detail="Günlük kullanım sınırına ulaşıldı.", request_id=getattr(request.state, "request_id", None)).model_dump())

    @app.exception_handler(AuthenticationRequired)
    async def authentication_handler(request: Request, exc: AuthenticationRequired) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        return JSONResponse(status_code=401, content=ErrorResponse(error="authentication_required", detail="Geçerli bir oturum gerekli.", request_id=request_id).model_dump())

    @app.exception_handler(AccountDeletionInProgress)
    async def deletion_in_progress(request: Request, exc: AccountDeletionInProgress) -> JSONResponse:
        return JSONResponse(status_code=409, content=ErrorResponse(error="account_deletion_in_progress", detail="Hesabın silinme sürecinde; yeni kayıt oluşturulamaz.", request_id=getattr(request.state, "request_id", None)).model_dump())

    @app.exception_handler(ReauthenticationRequired)
    async def reauthentication_required(request: Request, exc: ReauthenticationRequired) -> JSONResponse:
        return JSONResponse(status_code=401, content=ErrorResponse(error="reauthentication_required", detail="Hesabını silmek için yeniden giriş yapmalısın.", request_id=getattr(request.state, "request_id", None)).model_dump())

    @app.exception_handler(DeletionUnavailable)
    async def deletion_unavailable(request: Request, exc: DeletionUnavailable) -> JSONResponse:
        return JSONResponse(status_code=503, content=ErrorResponse(error="account_deletion_unavailable", detail="Hesap silme şu anda kullanılamıyor.", request_id=getattr(request.state, "request_id", None)).model_dump())

    @app.exception_handler(AIOutcomeError)
    async def ai_outcome_handler(request: Request, exc: AIOutcomeError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        return JSONResponse(status_code=exc.status_code, content=ErrorResponse(error=exc.code, detail=exc.public_message, request_id=request_id).model_dump())

    @app.exception_handler(InteractionError)
    async def interaction_exception_handler(request: Request, exc: InteractionError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        return JSONResponse(status_code=exc.status_code, content=ErrorResponse(error=exc.code, detail=exc.public_message, request_id=request_id).model_dump())

    @app.exception_handler(ShareError)
    async def share_exception_handler(request: Request, exc: ShareError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        return JSONResponse(status_code=exc.status_code, content=ErrorResponse(error=exc.code, detail=exc.public_message, request_id=request_id).model_dump())

    @app.exception_handler(LessonError)
    async def lesson_exception_handler(request: Request, exc: LessonError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        return JSONResponse(status_code=exc.status_code, content=ErrorResponse(error=exc.code, detail=exc.public_message, request_id=request_id).model_dump())

    @app.exception_handler(VisionError)
    async def vision_exception_handler(request: Request, exc: VisionError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", request.headers.get("x-request-id", str(uuid4())))
        payload = ErrorResponse(error=exc.code, detail=exc.public_message, request_id=request_id)
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", request.headers.get("x-request-id", str(uuid4())))
        payload = ErrorResponse(error="http_error", detail=str(exc.detail), request_id=request_id)
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", request.headers.get("x-request-id", str(uuid4())))
        payload = ErrorResponse(error="validation_error", detail="Invalid data.", request_id=request_id)
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=payload.model_dump())

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", request.headers.get("x-request-id", str(uuid4())))
        logger.error("Unhandled API error type=%s request_id=%s", type(exc).__name__, request_id)
        payload = ErrorResponse(error="internal_server_error", detail="An unexpected error occurred.", request_id=request_id)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload.model_dump())
