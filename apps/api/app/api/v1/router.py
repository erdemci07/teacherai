from fastapi import APIRouter

from apps.api.app.api.v1.health import router as health_router
from apps.api.app.api.v1.version import router as version_router
from apps.api.app.features.vision.router import router as vision_router
from apps.api.app.features.lessons.router import router as lessons_router
from apps.api.app.features.interactions.router import router as interactions_router
from apps.api.app.features.students.router import router as students_router
from apps.api.app.features.feedback.router import router as feedback_router
from apps.api.app.features.shares.router import router as shares_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(version_router)
api_router.include_router(vision_router)
api_router.include_router(lessons_router)
api_router.include_router(interactions_router)
api_router.include_router(students_router)
api_router.include_router(feedback_router)
api_router.include_router(shares_router)
