import io
import base64
import logging
import re
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
    InvalidPreparedImageError,
    MissingImageError,
    PreparedImageExpiredError,
    PreparedImageNotFoundError,
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
MAX_PREPARED_IMAGE_BYTES = 32 * 1024 * 1024
PREPARED_IMAGE_TTL_MINUTES = 15
PREPARED_IMAGE_ID_PATTERN = re.compile(r"^prepared_[a-f0-9]{32}$")

register_heif_opener()


@dataclass(frozen=True)
class PreparedImage:
    image_id: str
    content: bytes
    media_type: str
    suffix: str
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
                self._resolve_media_type(upload.content_type, upload.filename),
            )
            return self._preview_response(prepared)
        finally:
            await upload.close()

    async def analyze(
        self,
        upload: UploadFile | None,
        request_id: str | None = None,
        prepared_image_id: str | None = None,
        prepared_image_data_url: str | None = None,
        prepared_image_expires_at: str | None = None,
    ) -> VisionAnalysis:
        resolved_request_id = request_id or str(uuid4())
        started = perf_counter()

        logger.info("Vision processing started", extra={"request_id": resolved_request_id, "stage": "validation"})
        prepared = await self._resolve_prepared_image(upload, prepared_image_id, prepared_image_data_url, prepared_image_expires_at)
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

    async def _resolve_prepared_image(
        self,
        upload: UploadFile | None,
        prepared_image_id: str | None,
        prepared_image_data_url: str | None,
        prepared_image_expires_at: str | None,
    ) -> PreparedImage:
        if prepared_image_id or prepared_image_data_url or prepared_image_expires_at:
            try:
                if not prepared_image_id or not prepared_image_data_url:
                    raise PreparedImageNotFoundError
                return self._prepared_from_data_url(prepared_image_id, prepared_image_data_url, prepared_image_expires_at)
            except (PreparedImageNotFoundError, PreparedImageExpiredError, InvalidPreparedImageError):
                if upload is None:
                    raise
                return self._prepare_bytes(await self._read_limited(upload), self._resolve_media_type(upload.content_type, upload.filename))
        if upload is None:
            raise MissingImageError
        return self._prepare_bytes(await self._read_limited(upload), self._resolve_media_type(upload.content_type, upload.filename))

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
    def _prepare_bytes(content: bytes, declared_media_type: str) -> PreparedImage:
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
                has_alpha = normalized.mode in {"RGBA", "LA"} or (normalized.mode == "P" and "transparency" in normalized.info)
                normalized.convert("RGBA" if has_alpha else "RGB").save(output, format="PNG", optimize=True)
                width, height = normalized.size
                return PreparedImage(
                    image_id=f"prepared_{uuid4().hex}",
                    content=output.getvalue(),
                    media_type="image/png",
                    suffix="png",
                    width=width,
                    height=height,
                    expires_at=datetime.now(timezone.utc) + timedelta(minutes=PREPARED_IMAGE_TTL_MINUTES),
                )
        except UnsupportedImageError:
            raise
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
            raise InvalidImageError from exc

    def _prepared_from_data_url(self, image_id: str, data_url: str, expires_at: str | None) -> PreparedImage:
        if not PREPARED_IMAGE_ID_PATTERN.fullmatch(image_id):
            raise InvalidPreparedImageError
        expires = self._parse_prepared_expiry(expires_at)
        if expires and expires <= datetime.now(timezone.utc):
            raise PreparedImageExpiredError
        prefix = "data:image/png;base64,"
        if not data_url.startswith(prefix):
            raise InvalidPreparedImageError
        try:
            content = base64.b64decode(data_url[len(prefix):], validate=True)
            if len(content) > MAX_PREPARED_IMAGE_BYTES:
                raise ImageTooLargeError
            with Image.open(io.BytesIO(content)) as image:
                if image.format != "PNG":
                    raise InvalidPreparedImageError
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise InvalidPreparedImageError
                image.verify()
            with Image.open(io.BytesIO(content)) as image:
                width, height = image.size
        except (InvalidPreparedImageError, ImageTooLargeError):
            raise
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
            raise InvalidPreparedImageError from exc
        return PreparedImage(
            image_id=image_id,
            content=content,
            media_type="image/png",
            suffix="png",
            width=width,
            height=height,
            expires_at=expires or datetime.now(timezone.utc) + timedelta(minutes=PREPARED_IMAGE_TTL_MINUTES),
        )

    @staticmethod
    def _parse_prepared_expiry(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise InvalidPreparedImageError from exc
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    @staticmethod
    def _preview_data_url(content: bytes, media_type: str) -> str | None:
        if media_type != "image/png":
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
