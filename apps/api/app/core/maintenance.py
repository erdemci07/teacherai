"""Proje taşıma dönemi için bakım modu ve eski bağlantı yönlendirmesi (TA-005).

``TEACHERAI_MAINTENANCE_MODE``:
- ``off``: normal.
- ``read_only``: yazma ve ücretli uçlar ``Retry-After`` ile 503 ``maintenance_read_only`` döner; okuma ve
  paylaşım görüntüleme çalışır. Son fark kopyası bu modda alınır.
- ``redirect``: eski serviste kullanılır. API dışı GET istekleri ``TEACHERAI_LEGACY_REDIRECT_BASE`` adresine
  301 ile gider; API okumaları 503 ``service_moved``, yazmalar 503 ``maintenance_read_only`` alır.

``TEACHERAI_LEGACY_REDIRECT_BASE`` doluysa ``/s/{id}`` her modda yeni Hosting adresine 301 ile yönlenir;
böylece run.app paylaşım bağlantıları geçiş döneminde kırılmaz. Sağlık ucu her modda yanıt verir.
"""

from starlette.responses import JSONResponse, RedirectResponse

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
RETRY_AFTER_SECONDS = "900"


def maintenance_middleware(settings):
    prefix = settings.api_prefix.rstrip("/")
    base = (settings.legacy_redirect_base or "").rstrip("/")

    def unavailable(request, code, detail):
        return JSONResponse(status_code=503, headers={"Retry-After": RETRY_AFTER_SECONDS, "Cache-Control": "no-store"},
                            content={"error": code, "detail": detail, "request_id": getattr(request.state, "request_id", None)})

    async def middleware(request, call_next):
        path, mode = request.url.path, settings.maintenance_mode
        target = base + path + (f"?{request.url.query}" if request.url.query else "")
        if base and request.method in {"GET", "HEAD"} and (path.startswith("/s/") or (
                mode == "redirect" and not path.startswith(prefix + "/"))):
            return RedirectResponse(target, status_code=301)
        if mode == "off" or path == f"{prefix}/health":
            return await call_next(request)
        if request.method not in SAFE_METHODS:
            return unavailable(request, "maintenance_read_only",
                               "TeacherAI kısa bir bakımda. Şu an yeni soru gönderilemiyor; geçmişin ve paylaşımların açık.")
        if mode == "redirect" and request.method != "OPTIONS":
            return unavailable(request, "service_moved", "TeacherAI yeni adresine taşındı. Sayfayı yenileyip tekrar dene.")
        return await call_next(request)

    return middleware
