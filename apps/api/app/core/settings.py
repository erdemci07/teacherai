from functools import lru_cache
from typing import Literal

from pathlib import Path

from pydantic import AliasChoices, AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_prefix="TEACHERAI_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "TeacherAI API"
    environment: Literal["development", "test", "staging", "production"] = "development"
    version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"
    cors_allowed_origins: list[AnyHttpUrl | str] = Field(default_factory=lambda: ["http://localhost:3000"])
    debug: bool = False
    max_upload_size_bytes: int = 10 * 1024 * 1024
    upload_temp_directory: Path = Path("tmp/uploads")
    vision_provider: str = "openai"
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "TEACHERAI_OPENAI_API_KEY"),
    )
    openai_vision_model: str = Field(
        default="gpt-4.1-mini",
        validation_alias=AliasChoices("OPENAI_VISION_MODEL", "TEACHERAI_OPENAI_VISION_MODEL"),
    )
    vision_provider_timeout_seconds: float = 45.0
    openai_lesson_model: str = Field(default="gpt-4.1-mini", validation_alias=AliasChoices("OPENAI_LESSON_MODEL", "TEACHERAI_OPENAI_LESSON_MODEL"))
    lesson_provider_timeout_seconds: float = 60.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
