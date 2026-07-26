from dataclasses import dataclass

from apps.api.app.core.settings import Settings, get_settings
from apps.api.app.services.health_service import HealthService
from apps.api.app.services.version_service import VersionService


@dataclass(frozen=True)
class Container:
    settings: Settings
    health_service: HealthService
    version_service: VersionService


def build_container(settings: Settings | None = None) -> Container:
    resolved_settings = settings or get_settings()
    return Container(
        settings=resolved_settings,
        health_service=HealthService(settings=resolved_settings),
        version_service=VersionService(settings=resolved_settings),
    )
