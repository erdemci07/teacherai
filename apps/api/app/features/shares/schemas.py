from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from apps.api.app.features.board.schemas import BoardPlan
from apps.api.app.features.lessons.schemas import LessonContent
from apps.api.app.features.lessons.service import GeneratedLesson


class CreateShareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: GeneratedLesson
    existing_share_id: str | None = Field(default=None, min_length=8, max_length=32)


class PublicLessonSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")

    lesson_plan_id: str
    learning_objectives: list[str]
    concept_id: str
    content: LessonContent


class PublicSolutionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    share_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: Literal["published", "revoked"] = "published"
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    topic: str
    subtopic: str | None = None
    question_summary: str
    final_answer: str
    lesson_snapshot: PublicLessonSnapshot
    board_snapshot: BoardPlan
    app_version: str
    source_lesson_plan_id: str


class CreateShareResponse(BaseModel):
    share_id: str
    share_url: str


class PublicShareResponse(BaseModel):
    share_id: str
    share_url: str
    snapshot: PublicSolutionSnapshot
