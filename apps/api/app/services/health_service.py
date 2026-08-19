from apps.api.app.core.settings import Settings
from apps.api.app.schemas.responses import HealthData


class HealthService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_health(self) -> HealthData:
        return HealthData(service=self._settings.app_name, environment=self._settings.environment)
