import asyncio
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse
from ..features.auth.dependencies import AuthenticationRequired, require_user


class BodyLimit:
    """Count streamed bytes before multipart or JSON deserialization."""

    def __init__(self, app, settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            return await self.app(scope, receive, send)
        request = Request(scope)
        container = request.app.state.container
        try:
            await run_in_threadpool(
                require_user, request, request.headers.get("authorization"), container
            )
        except AuthenticationRequired:
            return await JSONResponse({"error": "authentication_required"}, 401)(
                scope, receive, send
            )
        except HTTPException as exc:
            return await JSONResponse(
                {"error": "access_denied", "detail": exc.detail}, exc.status_code
            )(scope, receive, send)
        if not container.slots.acquire(blocking=False):
            return await JSONResponse({"error": "busy"}, 429)(scope, receive, send)
        try:
            await self._read(scope, receive, send)
        finally:
            container.slots.release()

    async def _read(self, scope, receive, send):
        upload = scope["path"].endswith(("/vision/analyze", "/vision/preview"))
        limit = (
            self.settings.max_upload_size_bytes + 65536
            if upload
            else self.settings.max_json_bytes
        )
        length = dict(scope["headers"]).get(b"content-length", b"")
        if length.isdigit() and (len(length) > 12 or int(length) > limit):
            return await JSONResponse({"error": "request_too_large"}, 413)(
                scope, receive, send
            )
        deadline = (
            asyncio.get_running_loop().time() + self.settings.upload_timeout_seconds
        )
        body = bytearray()
        while True:
            try:
                async with asyncio.timeout_at(deadline):
                    message = await receive()
            except TimeoutError:
                return await JSONResponse({"error": "upload_timeout"}, 408)(
                    scope, receive, send
                )
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > limit:
                return await JSONResponse({"error": "request_too_large"}, 413)(
                    scope, receive, send
                )
            body.extend(chunk)
            if not message.get("more_body"):
                break
        pending = True

        async def replay():
            nonlocal pending
            if pending:
                pending = False
                return {"type": "http.request", "body": bytes(body)}
            return await receive()

        await self.app(scope, replay, send)
