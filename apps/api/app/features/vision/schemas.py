from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VisualElements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    has_diagram: bool
    has_graph: bool
    has_table: bool
    has_geometry_figure: bool
    description: str | None


class VisionProviderAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

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


class VisionAnalysis(VisionProviderAnalysis):
    request_id: str
    provider: str
    model: str
    processing_time_ms: int = Field(ge=0)
    debug: dict[str, str] | None = None
