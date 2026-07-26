from fastapi import APIRouter

from apps.api.app.api.v1.health import router as health_router
from apps.api.app.api.v1.version import router as version_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(version_router)
