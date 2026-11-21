import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from .operations import DEFAULT_LIMITS, Operation, validate_effort

Price = Annotated[float, Field(ge=0, allow_inf_nan=False)]


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
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> list[str]:
        defaults = ["https://teacherai-07.web.app", "http://localhost:3000", "http://127.0.0.1:3000"]
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
    max_upload_size_bytes: int = Field(10 * 1024 * 1024, ge=1, le=25 * 1024 * 1024)
    upload_timeout_seconds: int = Field(60, ge=1, le=180)
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
    vision_provider_timeout_seconds: float = Field(45, gt=0, le=180)
    openai_lesson_model: str = Field(default="gpt-5.6-terra", validation_alias=AliasChoices("OPENAI_LESSON_MODEL", "TEACHERAI_OPENAI_LESSON_MODEL"))
    lesson_provider_timeout_seconds: float = Field(60, gt=0, le=180)
    lesson_context_max_bytes: int = Field(default=24_000, validation_alias=AliasChoices("LESSON_CONTEXT_MAX_BYTES", "TEACHERAI_LESSON_CONTEXT_MAX_BYTES"))
    openai_interaction_model: str = Field(default="gpt-4.1-mini", validation_alias=AliasChoices("OPENAI_INTERACTION_MODEL", "TEACHERAI_OPENAI_INTERACTION_MODEL"))
    interaction_provider_timeout_seconds: float = Field(60, gt=0, le=180)
    # TA-005: tek Firebase projesi. Varsayılan proje yoktur; production'da ikisi zorunlu ve eşittir.
    firebase_project_id: str | None = None
    firebase_auth_project_id: str | None = None
    maintenance_mode: Literal["off", "read_only", "redirect"] = "off"
    legacy_redirect_base: str | None = None
    firebase_service_account_json: str | None = None
    firebase_enabled: bool = False
    authenticated_daily_ai_limit: int = Field(50, ge=0, le=10000)
    operation_limits: dict[str, int] = {"analyze": 20, "generate": 20, "interact": 40, "preview": 30, "answer": 80, "feedback": 20, "understood": 80}
    daily_output_tokens: int = Field(200000, ge=0)
    # Küresel günlük bütçe; tek UTC gün belgesinde atomik ayrılır. 0 ilgili ücretli yolu kapatır.
    global_daily_paid_operations: int = Field(2000, ge=0)
    global_daily_provider_calls: int = Field(4000, ge=0)
    global_daily_output_tokens: int = Field(20_000_000, ge=0)
    # TA-003: mantıksal istek başına gerçek sağlayıcı çağrısı tavanı. Yeniden denemeler çarpılmaz.
    # analyze = 1 ilk okuma + vision_max_rechecks hedefli yeniden okuma; 0 ek okumayı kapatır.
    vision_max_rechecks: int = Field(1, ge=0, le=2)
    # generate = ilk ders + en çok bir düzeltme + en çok bir bağlam yeniden denemesi, toplamda.
    lesson_max_provider_calls: int = Field(3, ge=1, le=4)
    interaction_max_provider_calls: int = Field(1, ge=1, le=2)
    usage_timeout_seconds: float = Field(5, gt=0, le=30)
    usage_transaction_attempts: int = Field(5, ge=1, le=10)
    ai_enabled: bool = True
    account_deletion_max_auth_age_seconds: int = Field(300, ge=30, le=3600)
    account_deletion_time_budget_seconds: float = Field(20, ge=0, le=120)
    ai_concurrency: int = Field(4, ge=1, le=64)
    max_json_bytes: int = Field(750000, ge=1024, le=8000000)
    max_output_tokens: int | None = Field(None, ge=128, le=32000)
    max_output_tokens_by_operation: dict[Operation, Annotated[int, Field(ge=128, le=32000, strict=True)]] = Field(default_factory=dict)
    reasoning_effort_by_operation: dict[Operation, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def single_project(self):
        if self.environment == "production" and (
                not self.firebase_project_id or self.firebase_project_id != self.firebase_auth_project_id):
            raise ValueError("Production'da TEACHERAI_FIREBASE_PROJECT_ID ve TEACHERAI_FIREBASE_AUTH_PROJECT_ID zorunlu ve eşit olmalı.")
        if self.legacy_redirect_base is not None and not self.legacy_redirect_base.startswith("https://"):
            raise ValueError("TEACHERAI_LEGACY_REDIRECT_BASE https adresi olmalı.")
        return self

    @model_validator(mode="after")
    def configure_operations(self):
        if self.max_output_tokens is not None:
            logging.getLogger(__name__).warning("TEACHERAI_MAX_OUTPUT_TOKENS kullanımdan kaldırılıyor; işleme özel ayarı kullanın.")
        self.max_output_tokens_by_operation = {
            op: self.max_output_tokens_by_operation.get(op, self.max_output_tokens or limit)
            for op, limit in DEFAULT_LIMITS.items()
        }
        models = {Operation.VISION: self.openai_vision_model, Operation.LESSONS: self.openai_lesson_model,
                  Operation.INTERACTION: self.openai_interaction_model}
        for op, effort in self.reasoning_effort_by_operation.items():
            validate_effort(models[op], effort)
        return self

    def provider_call_budget(self, activity: str) -> int | None:
        """Kabul edilen HTTP işleminin en çok kaç gerçek sağlayıcı çağrısı yapabileceği."""
        return {
            "analyze": 1 + self.vision_max_rechecks,
            "generate": self.lesson_max_provider_calls,
            "interact": self.interaction_max_provider_calls,
        }.get(activity)

    app_check_mode: Literal["off", "monitor", "enforce"] = "off"
    pricing_version: str | None = None
    # Verified USD per million tokens: input, cached input, output.
    model_prices: dict[str, tuple[Price, Price, Price]] = {}
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
