import io
import base64
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

from apps.api.app.features.vision.exceptions import (
    ImageTooLargeError,
    InvalidImageError,
    MissingImageError,
    UnsupportedImageError,
    VisionError,
)
from apps.api.app.features.vision.provider import VisionProvider
from apps.api.app.features.vision.schemas import NormalizedImagePreview, VisionAnalysis, VisionProviderDiagnostics
from apps.api.app.features.vision.storage import TemporaryImageStorage
from apps.api.app.features.vision.topic_normalization import normalize_topic_name

logger = logging.getLogger(__name__)
SUPPORTED_MEDIA_TYPES = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
HEIF_MEDIA_TYPES = {"image/heic": "HEIF", "image/heif": "HEIF"}
MEDIA_TYPE_ALIASES = {"image/jpg": "image/jpeg"}
SUPPORTED_EXTENSIONS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
}
MAX_IMAGE_PIXELS = 40_000_000

register_heif_opener()


class VisionService:
    def __init__(
        self,
        provider: VisionProvider,
        storage: TemporaryImageStorage,
        max_upload_size_bytes: int,
        debug: bool,
    ) -> None:
        self._provider = provider
        self._storage = storage
        self._max_upload_size_bytes = max_upload_size_bytes
        self._debug = debug

    def diagnostics(self) -> VisionProviderDiagnostics:
        return VisionProviderDiagnostics.model_validate(self._provider.diagnostics())

    async def preview(self, upload: UploadFile | None) -> NormalizedImagePreview:
        if upload is None:
            raise MissingImageError
        try:
            media_type = self._resolve_media_type(upload.content_type, upload.filename)
            content = await self._read_limited(upload)
            normalized, media_type, _ = self._normalize(content, media_type)
            preview_url = self._preview_data_url(normalized, media_type)
            if preview_url is None:
                raise InvalidImageError
            return NormalizedImagePreview(normalized_preview_url=preview_url, media_type=media_type)
        finally:
            await upload.close()

    async def analyze(self, upload: UploadFile | None, request_id: str | None = None) -> VisionAnalysis:
        resolved_request_id = request_id or str(uuid4())
        started = perf_counter()
        if upload is None:
            raise MissingImageError
        media_type = self._resolve_media_type(upload.content_type, upload.filename)

        logger.info("Vision processing started", extra={"request_id": resolved_request_id, "stage": "validation"})
        content = await self._read_limited(upload)
        normalized, media_type, suffix = self._normalize(content, media_type)
        temporary_path = await self._storage.save(normalized, suffix)
        try:
            logger.info(
                "Vision provider analysis started",
                extra={
                    "request_id": resolved_request_id,
                    "stage": "provider",
                    "provider": self._provider.name,
                    "model": self._provider.model,
                },
            )
            provider_result = await self._provider.analyze_image(normalized, media_type, resolved_request_id)
            duration = round((perf_counter() - started) * 1000)
            logger.info(
                "Vision processing succeeded",
                extra={
                    "request_id": resolved_request_id,
                    "stage": "complete",
                    "provider": provider_result.provider,
                    "model": provider_result.model,
                    "duration_ms": duration,
                },
            )
            analysis = provider_result.analysis.model_copy(
                update={
                    "topic": normalize_topic_name(provider_result.analysis.topic) or "",
                    "subtopic": normalize_topic_name(provider_result.analysis.subtopic),
                }
            )
            return VisionAnalysis(
                **analysis.model_dump(),
                request_id=resolved_request_id,
                provider=provider_result.provider,
                model=provider_result.model,
                processing_time_ms=duration,
                normalized_preview_url=self._preview_data_url(normalized, media_type),
                debug={"provider_response_id": provider_result.response_id} if self._debug and provider_result.response_id else None,
            )
        except VisionError:
            logger.warning(
                "Vision processing failed",
                extra={
                    "request_id": resolved_request_id,
                    "stage": "provider",
                    "provider": self._provider.name,
                    "model": self._provider.model,
                    "duration_ms": round((perf_counter() - started) * 1000),
                },
            )
            raise
        finally:
            await self._storage.delete(temporary_path)
            await upload.close()

    async def _read_limited(self, upload: UploadFile) -> bytes:
        content = bytearray()
        while chunk := await upload.read(1024 * 1024):
            content.extend(chunk)
            if len(content) > self._max_upload_size_bytes:
                raise ImageTooLargeError
        if not content:
            raise InvalidImageError
        return bytes(content)

    @staticmethod
    def _resolve_media_type(content_type: str | None, filename: str | None) -> str:
        normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
        normalized_type = MEDIA_TYPE_ALIASES.get(normalized_type, normalized_type)
        if normalized_type in SUPPORTED_MEDIA_TYPES or normalized_type in HEIF_MEDIA_TYPES:
            return normalized_type
        if normalized_type and normalized_type != "application/octet-stream":
            raise UnsupportedImageError

        suffix = (filename or "").rsplit(".", 1)
        extension = f".{suffix[-1].lower()}" if len(suffix) == 2 else ""
        try:
            return SUPPORTED_EXTENSIONS[extension]
        except KeyError as exc:
            raise UnsupportedImageError from exc

    @staticmethod
    def _normalize(content: bytes, declared_media_type: str) -> tuple[bytes, str, str]:
        try:
            with Image.open(io.BytesIO(content)) as source:
                if source.width * source.height > MAX_IMAGE_PIXELS:
                    raise InvalidImageError
                source.verify()
            with Image.open(io.BytesIO(content)) as source:
                expected_format = (SUPPORTED_MEDIA_TYPES | HEIF_MEDIA_TYPES)[declared_media_type]
                if source.format != expected_format:
                    raise UnsupportedImageError
                normalized = ImageOps.exif_transpose(source)
                output = io.BytesIO()
                if source.format in {"JPEG", "HEIF"}:
                    normalized.convert("RGB").save(output, format="JPEG", quality=95, optimize=True)
                    return output.getvalue(), "image/jpeg", "jpg"
                normalized.save(output, format=source.format, optimize=True)
                suffix = "png" if source.format == "PNG" else "webp"
                return output.getvalue(), declared_media_type, suffix
        except UnsupportedImageError:
            raise
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
            raise InvalidImageError from exc

    @staticmethod
    def _preview_data_url(content: bytes, media_type: str) -> str | None:
        if media_type not in {"image/jpeg", "image/png", "image/webp"}:
            return None
        try:
            encoded = base64.b64encode(content).decode("ascii")
        except (ValueError, OSError):
            return None
        return f"data:{media_type};base64,{encoded}"
