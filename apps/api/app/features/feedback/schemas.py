from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.api.app.features.lessons.service import GeneratedLesson

FeedbackRating = Literal["positive", "negative"]
PositiveFeedbackReason = Literal["clear", "correct_solution", "good_explanation", "useful", "other"]
NegativeFeedbackReason = Literal["wrong_solution", "misread_question", "step_error", "unclear_explanation", "formula_rendering_error", "too_long", "other"]
FeedbackReason = PositiveFeedbackReason | NegativeFeedbackReason

POSITIVE_REASONS = {"clear", "correct_solution", "good_explanation", "useful", "other"}
NEGATIVE_REASONS = {"wrong_solution", "misread_question", "step_error", "unclear_explanation", "formula_rendering_error", "too_long", "other"}
CRITICAL_REASONS = {"wrong_solution", "misread_question", "step_error", "formula_rendering_error"}
MAX_COMMENT_LENGTH = 1000


class SubmitFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: FeedbackRating
    reasons: list[FeedbackReason] = Field(default_factory=list, max_length=8)
    comment: str | None = Field(default=None, max_length=MAX_COMMENT_LENGTH)
    result: GeneratedLesson

    @field_validator("reasons")
    @classmethod
    def unique_reasons(cls, value: list[FeedbackReason]) -> list[FeedbackReason]:
        return list(dict.fromkeys(value))

    @field_validator("comment")
    @classmethod
    def trim_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None

    @model_validator(mode="after")
    def rating_matches_reasons(self):
        allowed = POSITIVE_REASONS if self.rating == "positive" else NEGATIVE_REASONS
        invalid = [reason for reason in self.reasons if reason not in allowed]
        if invalid:
            raise ValueError("feedback reasons do not match rating")
        return self


class FeedbackRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rating: FeedbackRating
    reasons: list[FeedbackReason] = Field(default_factory=list)
    comment: str | None = None
    critical: bool = False
    attention_worthy: bool = False
    request_id: str
    solution_id: str
    user_id: str | None = None
    topic: str | None = None
    subtopic: str | None = None
    vision_model: str | None = None
    lesson_model: str | None = None
    verification_model: str | None = None
    verification_status: str | None = None
    question_type: str | None = None
    difficulty: str | None = None
    app_version: str | None = None


class SubmitFeedbackResponse(BaseModel):
    feedback_id: str
    created: bool
    critical: bool
    notification_attempted: bool = False
