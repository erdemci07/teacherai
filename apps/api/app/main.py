from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from fastapi.responses import HTMLResponse
from uuid import uuid4
import logging

from apps.api.app.api.v1.router import api_router
from apps.api.app.core.container import build_container
from apps.api.app.core.errors import register_error_handlers
from apps.api.app.core.logging import configure_logging
from apps.api.app.core.settings import get_settings
from apps.api.app.features.shares.exceptions import ShareUnpublishedError


def create_app(settings_override=None) -> FastAPI:
    settings = settings_override or get_settings()
    configure_logging(settings)

    app = FastAPI(title=settings.app_name, version=settings.version)
    app.state.container = build_container(settings)
    diagnostic = app.state.container.vision_service.diagnostics()
    logging.getLogger("teacherai.startup").info(
        "Vision provider configuration provider=%s configured=%s model=%s",
        diagnostic.provider,
        diagnostic.configured,
        diagnostic.model,
    )

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["x-request-id"] = request.state.request_id
        return response

    from apps.api.app.core.body_limit import BodyLimit
    app.add_middleware(BodyLimit, settings=settings)
    from apps.api.app.core.maintenance import maintenance_middleware
    # TA-005: kimlik ve gövde denetiminden önce, CORS'un içinde (503 tarayıcıya CORS başlığıyla ulaşır).
    app.middleware("http")(maintenance_middleware(settings))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.cors_allowed_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/s/{share_id}", response_class=HTMLResponse, include_in_schema=False)
    def public_share_page(request: Request, share_id: str):
        request_origin = f"{request.url.scheme}://{request.url.netloc}"
        try:
            html = app.state.container.share_service.render_public_html(share_id, request_origin)
        except ShareUnpublishedError:
            return HTMLResponse(
                "<!doctype html><html lang=\"tr\"><head><meta charset=\"utf-8\"><meta name=\"robots\" content=\"noindex\"><title>Paylaşım kaldırıldı</title></head><body><h1>Paylaşım kaldırıldı</h1><p>Bu paylaşım bağlantısı yayından kaldırıldı.</p></body></html>",
                status_code=410,
                headers={"Cache-Control": "no-store"},
            )
        if html is None:
            return HTMLResponse(
                "<!doctype html><html lang=\"tr\"><head><meta charset=\"utf-8\"><meta name=\"robots\" content=\"noindex\"><title>Çözüm bulunamadı</title></head><body><h1>Çözüm bulunamadı</h1><p>Bu paylaşım bağlantısı artık kullanılamıyor olabilir.</p></body></html>",
                status_code=404,
                headers={"Cache-Control": "no-store"},
            )
        return HTMLResponse(html, headers={"Cache-Control": "public, max-age=300"})
    return app


app = create_app()
