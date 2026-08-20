from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VisualElements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    has_diagram: bool
    has_graph: bool
    has_table: bool
    has_geometry_figure: bool
    description: str | None


class VisionProviderAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_status: Literal[
        "valid_math_question",
        "not_math_question",
        "unreadable",
        "incomplete_question",
    ]
    is_valid_question: bool
    rejection_reason: str | None
    subject: str
    exam_context: str | None
    topic: str
    subtopic: str | None
    question_type: str
    language: str
    difficulty: Literal["easy", "medium", "hard", "unknown"]
    question_text: str
    mathematical_expressions: list[str]
    answer_choices: list[str]
    visual_elements: VisualElements
    ocr_uncertainties: list[str]
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_image_decision(self) -> "VisionProviderAnalysis":
        valid_status = self.image_status == "valid_math_question"
        if self.is_valid_question != valid_status:
            raise ValueError("is_valid_question must match image_status")
        if valid_status and self.rejection_reason is not None:
            raise ValueError("valid questions cannot have a rejection_reason")
        if not valid_status and not self.rejection_reason:
            raise ValueError("invalid images require a rejection_reason")
        if not valid_status and any(
            (
                self.subject,
                self.exam_context,
                self.topic,
                self.subtopic,
                self.question_type,
                self.question_text,
                self.mathematical_expressions,
                self.answer_choices,
            )
        ):
            raise ValueError("invalid images cannot contain invented question content")
        if not valid_status and self.difficulty != "unknown":
            raise ValueError("invalid images must use unknown difficulty")
        return self


class VisionAnalysis(VisionProviderAnalysis):
    request_id: str
    provider: str
    model: str
    processing_time_ms: int = Field(ge=0)
    debug: dict[str, str] | None = None
