from typing import Annotated

from fastapi import Depends, Request

from apps.api.app.core.container import Container
from apps.api.app.features.vision.service import VisionService
from apps.api.app.features.lessons.service import LessonService
from apps.api.app.services.health_service import HealthService
from apps.api.app.services.version_service import VersionService


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_health_service(container: Annotated[Container, Depends(get_container)]) -> HealthService:
    return container.health_service


def get_version_service(container: Annotated[Container, Depends(get_container)]) -> VersionService:
    return container.version_service


def get_vision_service(container: Annotated[Container, Depends(get_container)]) -> VisionService:
    return container.vision_service


def get_lesson_service(container: Annotated[Container, Depends(get_container)]) -> LessonService:
    return container.lesson_service
