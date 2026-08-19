from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from uuid import uuid4
import logging

usage_logger = logging.getLogger("teacherai.ai_usage")

from apps.api.app.api.v1.router import api_router
from apps.api.app.core.container import build_container
from apps.api.app.core.errors import register_error_handlers
from apps.api.app.core.logging import configure_logging
from apps.api.app.core.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(title=settings.app_name, version=settings.version)
    app.state.container = build_container(settings)

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request.state.request_id = request.headers.get("x-request-id") or str(uuid4())
        if request.method == "POST" and any(part in request.url.path for part in ("/vision/analyze", "/lessons/generate", "/interact")):
            authorization = request.headers.get("authorization", "")
            if authorization.lower().startswith("bearer "):
                try:
                    user = app.state.container.token_verifier.verify(authorization.split(" ", 1)[1])
                    operation = request.url.path.rsplit("/", 1)[-1]
                    count = app.state.container.usage_tracker.record(user.uid, operation)
                    usage_logger.info("Authenticated AI request", extra={"student_id": user.uid, "operation": operation, "daily_count": count})
                except Exception as exc:
                    from apps.api.app.core.usage import UsageLimitExceeded
                    if isinstance(exc, UsageLimitExceeded):
                        raise
        response = await call_next(request)
        response.headers["x-request-id"] = request.state.request_id
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.cors_allowed_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
