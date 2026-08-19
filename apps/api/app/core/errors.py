import logging
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from apps.api.app.schemas.responses import ErrorResponse
from apps.api.app.features.vision.exceptions import VisionError

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
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
        payload = ErrorResponse(error="validation_error", detail=str(exc), request_id=request_id)
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=payload.model_dump())

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", request.headers.get("x-request-id", str(uuid4())))
        logger.exception("Unhandled API error", extra={"request_id": request_id})
        payload = ErrorResponse(error="internal_server_error", detail="An unexpected error occurred.", request_id=request_id)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload.model_dump())
