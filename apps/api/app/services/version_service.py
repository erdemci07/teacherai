from apps.api.app.core.settings import Settings
from apps.api.app.schemas.responses import VersionData


class VersionService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_version(self) -> VersionData:
        return VersionData(
            service=self._settings.app_name,
            version=self._settings.version,
            environment=self._settings.environment,
        )
