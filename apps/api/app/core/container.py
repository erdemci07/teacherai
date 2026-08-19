from dataclasses import dataclass

from apps.api.app.core.settings import Settings, get_settings
from apps.api.app.features.vision.openai_provider import OpenAIVisionProvider
from apps.api.app.features.vision.service import VisionService
from apps.api.app.features.vision.storage import LocalTemporaryImageStorage
from apps.api.app.services.health_service import HealthService
from apps.api.app.services.version_service import VersionService


@dataclass(frozen=True)
class Container:
    settings: Settings
    health_service: HealthService
    version_service: VersionService
    vision_service: VisionService


def build_container(settings: Settings | None = None) -> Container:
    resolved_settings = settings or get_settings()
    vision_provider = OpenAIVisionProvider(
        api_key=resolved_settings.openai_api_key,
        model=resolved_settings.openai_vision_model,
        timeout_seconds=resolved_settings.vision_provider_timeout_seconds,
    )
    return Container(
        settings=resolved_settings,
        health_service=HealthService(settings=resolved_settings),
        version_service=VersionService(settings=resolved_settings),
        vision_service=VisionService(
            provider=vision_provider,
            storage=LocalTemporaryImageStorage(resolved_settings.upload_temp_directory),
            max_upload_size_bytes=resolved_settings.max_upload_size_bytes,
            debug=resolved_settings.debug,
        ),
    )
