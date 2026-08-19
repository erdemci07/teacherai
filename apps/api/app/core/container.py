from dataclasses import dataclass

from apps.api.app.core.settings import Settings, get_settings
from apps.api.app.features.vision.openai_provider import OpenAIVisionProvider
from apps.api.app.features.vision.service import VisionService
from apps.api.app.features.vision.storage import LocalTemporaryImageStorage
from apps.api.app.features.lessons.openai_provider import OpenAILessonProvider
from apps.api.app.features.lessons.service import LessonService
from apps.api.app.features.mathai.service import MathAIService
from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.interactions.openai_provider import OpenAIInteractionProvider
from apps.api.app.features.interactions.service import InteractionService
from apps.api.app.features.interactions.store import InMemoryPracticeStore
from apps.api.app.services.health_service import HealthService
from apps.api.app.services.version_service import VersionService


@dataclass(frozen=True)
class Container:
    settings: Settings
    health_service: HealthService
    version_service: VersionService
    vision_service: VisionService
    lesson_service: LessonService
    interaction_service: InteractionService


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
        interaction_service=InteractionService(OpenAIInteractionProvider(resolved_settings.openai_api_key, resolved_settings.openai_interaction_model, resolved_settings.interaction_provider_timeout_seconds), MathAIService(), InMemoryPracticeStore()),
        lesson_service=LessonService(OpenAILessonProvider(resolved_settings.openai_api_key, resolved_settings.openai_lesson_model, resolved_settings.lesson_provider_timeout_seconds), MathAIService(), BoardPlanner()),
        vision_service=VisionService(
            provider=vision_provider,
            storage=LocalTemporaryImageStorage(resolved_settings.upload_temp_directory),
            max_upload_size_bytes=resolved_settings.max_upload_size_bytes,
            debug=resolved_settings.debug,
        ),
    )
