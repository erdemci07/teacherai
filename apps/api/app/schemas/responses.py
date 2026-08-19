from datetime import datetime, timezone
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T
    request_id: str | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: str | None = None
    request_id: str | None = None


class HealthData(BaseModel):
    status: str = "ok"
    service: str
    environment: str
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VersionData(BaseModel):
    service: str
    version: str
    environment: str
