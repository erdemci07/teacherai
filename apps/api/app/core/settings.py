from functools import lru_cache
from typing import Annotated, Literal
import json
from urllib.parse import urlsplit

from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "https://teacherai-07.web.app",
            "https://math-ai-07.web.app",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> list[str]:
        defaults = ["https://teacherai-07.web.app", "https://math-ai-07.web.app", "http://localhost:3000", "http://127.0.0.1:3000"]
        if isinstance(value, (list, tuple)):
            candidates = [str(item).strip() for item in value]
        elif isinstance(value, str):
            try:
                decoded = json.loads(value)
                candidates = decoded if isinstance(decoded, list) else value.split(",")
            except (json.JSONDecodeError, TypeError):
                candidates = value.split(",")
        else:
            return defaults
        origins: list[str] = []
        for candidate in candidates:
            origin = str(candidate).strip().strip("[]\"'")
            parsed = urlsplit(origin)
            if parsed.scheme in {"http", "https"} and parsed.netloc and not parsed.path.rstrip("/"):
                origins.append(origin.rstrip("/"))
        return list(dict.fromkeys(origins)) or defaults

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
    openai_lesson_model: str = Field(default="gpt-5.6-terra", validation_alias=AliasChoices("OPENAI_LESSON_MODEL", "TEACHERAI_OPENAI_LESSON_MODEL"))
    lesson_provider_timeout_seconds: float = 60.0
    lesson_context_max_bytes: int = Field(default=24_000, validation_alias=AliasChoices("LESSON_CONTEXT_MAX_BYTES", "TEACHERAI_LESSON_CONTEXT_MAX_BYTES"))
    openai_interaction_model: str = Field(default="gpt-4.1-mini", validation_alias=AliasChoices("OPENAI_INTERACTION_MODEL", "TEACHERAI_OPENAI_INTERACTION_MODEL"))
    interaction_provider_timeout_seconds: float = 60.0
    firebase_project_id: str | None = "math-ai-07"
    firebase_service_account_json: str | None = None
    firebase_enabled: bool = False
    authenticated_daily_ai_limit: int = 50
    public_app_url: str = Field(default="https://teacherai-07.web.app", validation_alias=AliasChoices("PUBLIC_APP_URL", "TEACHERAI_PUBLIC_APP_URL"))
    public_share_url_base: str | None = Field(default=None, validation_alias=AliasChoices("PUBLIC_SHARE_URL_BASE", "TEACHERAI_PUBLIC_SHARE_URL_BASE"))
    share_og_image_path: str = "/teacherai-share-og.svg"
    feedback_email_notifications: bool = Field(default=False, validation_alias=AliasChoices("FEEDBACK_EMAIL_NOTIFICATIONS", "TEACHERAI_FEEDBACK_EMAIL_NOTIFICATIONS"))
    feedback_notification_email: str | None = Field(default=None, validation_alias=AliasChoices("FEEDBACK_NOTIFICATION_EMAIL", "TEACHERAI_FEEDBACK_NOTIFICATION_EMAIL"))
    feedback_email_sender: str | None = Field(default=None, validation_alias=AliasChoices("FEEDBACK_EMAIL_SENDER", "TEACHERAI_FEEDBACK_EMAIL_SENDER"))
    resend_api_key: str | None = Field(default=None, validation_alias=AliasChoices("RESEND_API_KEY", "TEACHERAI_RESEND_API_KEY"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
