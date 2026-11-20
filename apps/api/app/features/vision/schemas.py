from typing import Literal

from apps.api.app.features.education.source import IntegrityReport
from pydantic import BaseModel, ConfigDict, Field, model_validator


class VisualElements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    has_diagram: bool
    has_graph: bool
    has_table: bool
    has_geometry_figure: bool
    description: str | None
    visual_relevance: Literal["none", "supporting", "essential"] = "none"
    relevant_visual_facts: list[str] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)


UncertaintyCategoryWire = Literal[
    "symbol", "sign", "grouping", "radical_scope", "fraction_scope", "exponent_scope", "subscript", "decimal",
    "text", "negation", "answer_choice", "diagram", "graph", "table", "quantity", "unit", "source_selection",
]


class RegionProposal(BaseModel):
    """Sağlayıcının önerdiği 0–1 normalleştirilmiş bölge. Sunucu doğrular; geçersizse atılır."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["question", "expression", "choices", "diagram", "graph", "table", "annotation", "other_question"]
    x0: float
    y0: float
    x1: float
    y1: float


class UncertaintyProposal(BaseModel):
    """Cevabı etkileyebilecek okuma belirsizliği önerisi. Alternatifler doğrulanmış kaynak değildir."""

    model_config = ConfigDict(extra="forbid")

    category: UncertaintyCategoryWire
    element: str
    recognized: str
    alternatives: list[str]
    affects_answer: bool
    region_index: int | None


class SourceProposal(BaseModel):
    """Tel biçimi; özyinelemeli ağaç içermez. Python kanonik yapıyı kendisi kurar."""

    model_config = ConfigDict(extra="forbid")

    question_count: int = Field(default=1, ge=0)
    target_question_clear: bool = True
    statements: list[str] = Field(default_factory=list)
    regions: list[RegionProposal] = Field(default_factory=list)
    uncertainties: list[UncertaintyProposal] = Field(default_factory=list)


class RecheckReading(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: int
    legible: bool
    reading: str


class RecheckResponse(BaseModel):
    """Hedefli yeniden okuma tel biçimi. Sonuç ilk okumayla karşılaştırılır, otomatik doğru sayılmaz."""

    model_config = ConfigDict(extra="forbid")

    readings: list[RecheckReading]


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
    source: SourceProposal = Field(default_factory=SourceProposal)

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
        if not valid_status and (
            self.visual_elements.has_diagram
            or self.visual_elements.has_graph
            or self.visual_elements.has_table
            or self.visual_elements.has_geometry_figure
            or self.visual_elements.description
            or self.visual_elements.visual_relevance != "none"
            or self.visual_elements.relevant_visual_facts
            or self.visual_elements.relationships
        ):
            raise ValueError("invalid images cannot contain invented visual facts")
        if not valid_status and (self.source.statements or self.source.uncertainties or self.source.regions):
            raise ValueError("invalid images cannot contain invented source details")
        return self


class VisionAnalysis(VisionProviderAnalysis):
    request_id: str
    provider: str
    model: str
    processing_time_ms: int = Field(ge=0)
    normalized_preview_url: str | None = None
    debug: dict[str, str] | None = None
    # TA-003: sunucuya ait soru revizyonu ve bütünlük kararı. Eski kayıtlarda yoktur (None).
    revision: int = Field(default=1, ge=1, le=64)
    integrity: IntegrityReport | None = None


class NormalizedImagePreview(BaseModel):
    image_id: str
    format: Literal["jpg", "png"] = "png"
    content_type: Literal["image/jpeg", "image/png"] = "image/png"
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    preview: str
    expires_at: str


class VisionProviderDiagnostics(BaseModel):
    provider: str
    configured: bool
    model: str
