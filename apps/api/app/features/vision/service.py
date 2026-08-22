import io
import base64
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
PREPARED_IMAGE_TTL_MINUTES = 15

register_heif_opener()


@dataclass(frozen=True)
class PreparedImage:
    image_id: str
    content: bytes
    media_type: str
    suffix: str
    source_format: str
    width: int
    height: int
    expires_at: datetime


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

    async def prepare(self, upload: UploadFile | None) -> NormalizedImagePreview:
        if upload is None:
            raise MissingImageError
        try:
            prepared = self._prepare_bytes(
                await self._read_limited(upload),
                upload.content_type,
                upload.filename,
                preview=True,
            )
            return self._preview_response(prepared)
        finally:
            await upload.close()

    async def analyze(
        self,
        upload: UploadFile | None,
        request_id: str | None = None,
    ) -> VisionAnalysis:
        resolved_request_id = request_id or str(uuid4())
        started = perf_counter()

        logger.info("Vision processing started", extra={"request_id": resolved_request_id, "stage": "validation"})
        if upload is None:
            raise MissingImageError
        prepared = self._prepare_bytes(await self._read_limited(upload), upload.content_type, upload.filename)
        logger.info(
            "Vision image normalized",
            extra={
                "request_id": resolved_request_id,
                "stage": "normalization",
                "original_detected_format": prepared.source_format,
                "normalized_vision_format": prepared.media_type,
                "width": prepared.width,
                "height": prepared.height,
                "duration_ms": round((perf_counter() - started) * 1000),
            },
        )
        temporary_path = await self._storage.save(prepared.content, prepared.suffix)
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
            provider_result = await self._provider.analyze_image(prepared.content, prepared.media_type, resolved_request_id)
            duration = round((perf_counter() - started) * 1000)
            analysis = provider_result.analysis.model_copy(
                update={
                    "topic": normalize_topic_name(provider_result.analysis.topic) or "",
                    "subtopic": normalize_topic_name(provider_result.analysis.subtopic),
                }
            )
            logger.info(
                "Vision processing succeeded",
                extra={
                    "request_id": resolved_request_id,
                    "stage": "complete",
                    "provider": provider_result.provider,
                    "model": provider_result.model,
                    "duration_ms": duration,
                    "visual_relevance": analysis.visual_elements.visual_relevance,
                    "visual_relationship_count": len(analysis.visual_elements.relationships),
                    "uncertainty_count": len(analysis.ocr_uncertainties),
                },
            )
            return VisionAnalysis(
                **analysis.model_dump(),
                request_id=resolved_request_id,
                provider=provider_result.provider,
                model=provider_result.model,
                processing_time_ms=duration,
                normalized_preview_url=self._preview_data_url(prepared.content, prepared.media_type),
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
            if upload is not None:
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
    def _validate_upload_metadata(content_type: str | None, filename: str | None) -> None:
        normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
        normalized_type = MEDIA_TYPE_ALIASES.get(normalized_type, normalized_type)
        if normalized_type in SUPPORTED_MEDIA_TYPES or normalized_type in HEIF_MEDIA_TYPES:
            return
        if normalized_type and normalized_type != "application/octet-stream":
            raise UnsupportedImageError

        suffix = (filename or "").rsplit(".", 1)
        extension = f".{suffix[-1].lower()}" if len(suffix) == 2 else ""
        if extension and extension not in SUPPORTED_EXTENSIONS:
            raise UnsupportedImageError
        if not normalized_type and not extension:
            raise UnsupportedImageError

    @staticmethod
    def _prepare_bytes(content: bytes, content_type: str | None, filename: str | None, preview: bool = False) -> PreparedImage:
        VisionService._validate_upload_metadata(content_type, filename)
        try:
            with Image.open(io.BytesIO(content)) as source:
                if source.width * source.height > MAX_IMAGE_PIXELS:
                    raise InvalidImageError
                source.verify()
            with Image.open(io.BytesIO(content)) as source:
                actual_format = source.format
                if actual_format not in {"JPEG", "PNG", "WEBP", "HEIF"}:
                    raise UnsupportedImageError
                normalized = ImageOps.exif_transpose(source)
                output = io.BytesIO()
                if actual_format == "HEIF" or preview:
                    has_alpha = normalized.mode in {"RGBA", "LA"} or (normalized.mode == "P" and "transparency" in normalized.info)
                    normalized.convert("RGBA" if has_alpha else "RGB").save(output, format="PNG", optimize=True)
                    media_type = "image/png"
                    suffix = "png"
                elif actual_format == "JPEG":
                    orientation = source.getexif().get(274, 1)
                    if orientation == 1:
                        output.write(content)
                    else:
                        normalized.convert("RGB").save(output, format="JPEG", quality=95, optimize=True)
                    media_type = "image/jpeg"
                    suffix = "jpg"
                elif actual_format == "PNG":
                    output.write(content)
                    media_type = "image/png"
                    suffix = "png"
                else:
                    output.write(content)
                    media_type = "image/webp"
                    suffix = "webp"
                width, height = normalized.size
                return PreparedImage(
                    image_id=f"prepared_{uuid4().hex}",
                    content=output.getvalue(),
                    media_type=media_type,
                    suffix=suffix,
                    source_format=actual_format,
                    width=width,
                    height=height,
                    expires_at=datetime.now(timezone.utc) + timedelta(minutes=PREPARED_IMAGE_TTL_MINUTES),
                )
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

    def _preview_response(self, prepared: PreparedImage) -> NormalizedImagePreview:
        preview = self._preview_data_url(prepared.content, prepared.media_type)
        if preview is None:
            raise InvalidImageError
        return NormalizedImagePreview(
            image_id=prepared.image_id,
            content_type="image/png",
            width=prepared.width,
            height=prepared.height,
            preview=preview,
            expires_at=prepared.expires_at.isoformat(),
        )
