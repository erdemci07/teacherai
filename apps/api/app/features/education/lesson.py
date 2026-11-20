"""Sürüm 2 özel ders sözleşmesi. Taslak, sunucu kimliği ve doğrulama ayrı tiplerdir."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .domain import (
    Activity,
    Contract,
    EducationContext,
    Identifier,
    Label,
    Quantity,
    Reference,
    Table,
    Text,
)
from .source import SOLVABLE_DECISIONS, Decision


class MathAnswer(Contract):
    kind: Literal["math"]
    expressions: list[Text] = Field(min_length=1, max_length=64)
    description: Text


class NumberAnswer(Contract):
    kind: Literal["number"]
    value: float = Field(strict=True)


class QuantityAnswer(Contract):
    kind: Literal["quantity"]
    quantity: Quantity


class ChoiceAnswer(Contract):
    kind: Literal["choice"]
    choices: list[Label] = Field(min_length=2, max_length=12)
    selected: int = Field(ge=0)

    @model_validator(mode="after")
    def valid_selection(self):
        if self.selected >= len(self.choices):
            raise ValueError("Seçenek dizin dışında.")
        return self


class TextAnswer(Contract):
    kind: Literal["text"]
    text: Text


class TableAnswer(Contract):
    kind: Literal["table"]
    table: Table


Answer = Annotated[MathAnswer | NumberAnswer | QuantityAnswer | ChoiceAnswer | TextAnswer | TableAnswer,
                   Field(discriminator="kind")]


class Block(Contract):
    id: Identifier
    relates_to: list[Identifier] = Field(default_factory=list, max_length=16)
    references: list[Reference] = Field(default_factory=list, max_length=16)


class ProseBlock(Block):
    title: Label | None = None
    kind: Literal["explanation", "definition", "warning", "hint", "checkpoint", "result", "summary"]
    text: Text


class ExpressionBlock(Block):
    kind: Literal["expression"]
    latex: Text


class CalculationBlock(Block):
    kind: Literal["calculation"]
    expression: Text
    result: Answer


class ExampleBlock(Block):
    kind: Literal["worked_example"]
    prompt: Text
    explanation: Text
    answer: Answer


class TableBlock(Block):
    kind: Literal["table"]
    table: Table


class VisualBlock(Block):
    kind: Literal["visual"]
    visual_type: Literal["number_line", "source_figure", "unsupported"]
    description: Text
    positions: list[Annotated[float, Field(strict=True)]] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def valid_positions(self):
        if self.visual_type == "number_line":
            if not self.positions or self.positions != sorted(set(self.positions)):
                raise ValueError("Sayı doğrusu artan ve farklı konumlar gerektirir.")
        elif self.positions:
            raise ValueError("Konumlar yalnızca sayı doğrusunda kullanılır.")
        return self


ContentBlock = Annotated[ProseBlock | ExpressionBlock | CalculationBlock | ExampleBlock | TableBlock | VisualBlock,
                         Field(discriminator="kind")]


class EducationalDraft(Contract):
    activity: Activity
    objectives: list[Text] = Field(min_length=1, max_length=32)
    references: list[Reference] = Field(default_factory=list, max_length=64)
    blocks: list[ContentBlock] = Field(min_length=1, max_length=256)
    answer: Answer | None = None
    takeaway: Text

    @model_validator(mode="after")
    def validate_content(self):
        if self.activity == "question_solution" and self.answer is None:
            raise ValueError("Soru çözümü cevap gerektirir.")
        ids = {b.id for b in self.blocks}
        if len(ids) != len(self.blocks):
            raise ValueError("Blok kimlikleri benzersiz olmalıdır.")
        for block in self.blocks:
            if block.id in block.relates_to or not ids.issuperset(block.relates_to):
                raise ValueError("Geçersiz blok referansı.")
        return self


State = Literal["passed", "failed", "partially_checked", "unsupported", "not_checked", "not_applicable"]


class VerificationReport(Contract):
    structural: Literal["passed"]
    scientific: State
    calculation: State
    source_consistency: State
    curriculum: Literal["not_checked"]
    method: Literal["not_checked"]
    pedagogy: Literal["not_checked"]
    engine: Label | None = None
    checked_claims: list[Text] = Field(default_factory=list, max_length=256)


class SchemaIdentity(Contract):
    """2.1.0 (TA-003) yalnızca isteğe bağlı kaynak revizyonu alanlarını ekler; 2.0.0 belgeleri geçerlidir."""

    name: Literal["teacherai.lesson_plan"]
    version: Literal["2.0.0", "2.1.0"]


class Provenance(Contract):
    provider: Label
    model: Label


class LessonPlanV2(Contract):
    schema_identity: SchemaIdentity = Field(alias="schema")
    lesson_id: Identifier
    source_id: Label
    context: EducationContext
    # TA-003: dersin dayandığı kabul edilmiş soru revizyonu ve bütünlük kararı (2.1.0).
    source_revision: int | None = Field(default=None, ge=1, le=64)
    source_decision: Decision | None = None
    content: EducationalDraft
    provenance: Provenance
    verification: VerificationReport

    @model_validator(mode="after")
    def valid_evidence(self):
        if self.schema_identity.version == "2.0.0" and (self.source_revision is not None or self.source_decision is not None):
            raise ValueError("Kaynak revizyonu alanları 2.1.0 gerektirir.")
        if self.source_decision is not None and self.source_decision not in SOLVABLE_DECISIONS:
            raise ValueError("Ders yalnızca çözülebilir kabul edilmiş bir soruya dayanabilir.")
        from .domain import capabilities
        if not capabilities(self.context.subject).representable:
            raise ValueError("Dersin alanı belirlenemedi.")
        if self.verification.scientific == "passed":
            raise ValueError("Bu sürüm tam bilimsel doğrulama yapmaz.")
        if capabilities(self.context.subject).verification == "unsupported" and any(
            value in {"passed", "partially_checked"} for value in
            (self.verification.scientific, self.verification.calculation)
        ):
            raise ValueError("Bu alan için doğrulama motoru yok.")
        return self
