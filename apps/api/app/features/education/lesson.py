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
from .reasoning import CheckState, EvidenceRef, NarrationSegment, Operation, OperationOrigin, TargetResolution
from .science import ScientificProblemModel
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


class DerivationStepBlock(Block):
    """Bir akıl yürütme adımı (TA-004). Matematik dönüşümü veya bilimsel çıkarım olabilir.

    ``inputs`` ve ``outputs`` ifade, nicelik, durum veya kanıt referanslarıdır; biyoloji gibi denklemsiz
    akıl yürütmede matematiksel bir ``from/to`` çifti zorunlu değildir. ``operation`` bir işlemdir,
    öğretim yöntemi değildir (``method_ref``). İşlem adı doğruluk kanıtı sayılmaz; kontroller
    ``VerificationReport.block_checks`` içindedir ve yalnızca sunucu doğrulayıcılarından gelir.
    """

    kind: Literal["derivation_step"]
    step_index: int = Field(ge=1, le=256)
    title: Label | None = None
    explanation: Text
    inputs: list[EvidenceRef] = Field(default_factory=list, max_length=16)
    outputs: list[EvidenceRef] = Field(default_factory=list, max_length=16)
    operation: Operation = "unknown"
    operation_origin: OperationOrigin = "unknown"
    method_ref: Identifier | None = None
    assumptions: list[Label] = Field(default_factory=list, max_length=8)
    preconditions: list[Label] = Field(default_factory=list, max_length=8)
    conclusions: list[EvidenceRef] = Field(default_factory=list, max_length=8)
    narration_ref: Identifier | None = None

    @model_validator(mode="after")
    def honest_operation(self):
        if (self.operation == "unknown") != (self.operation_origin == "unknown"):
            raise ValueError("Bilinmeyen işlem ve kökeni tutarlı olmalı.")
        return self


ContentBlock = Annotated[ProseBlock | ExpressionBlock | CalculationBlock | ExampleBlock | TableBlock | VisualBlock
                         | DerivationStepBlock, Field(discriminator="kind")]


class EducationalDraft(Contract):
    activity: Activity
    objectives: list[Text] = Field(min_length=1, max_length=32)
    references: list[Reference] = Field(default_factory=list, max_length=64)
    blocks: list[ContentBlock] = Field(min_length=1, max_length=256)
    answer: Answer | None = None
    takeaway: Text
    # TA-004: yalnızca sözleşme; ses üretimi yoktur.
    narration: list[NarrationSegment] = Field(default_factory=list, max_length=256)

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
            if isinstance(block, DerivationStepBlock):
                refs = [ref.id for ref in block.inputs + block.outputs + block.conclusions if ref.kind == "block"]
                if block.id in refs or not ids.issuperset(refs):
                    raise ValueError("Geçersiz adım referansı.")
        narration_ids = [item.id for item in self.narration]
        orders = [item.order for item in self.narration]
        if len(set(narration_ids)) != len(narration_ids) or orders != sorted(set(orders)):
            raise ValueError("Anlatım parçaları benzersiz ve sıralı olmalı.")
        if not ids.issuperset(item.block for item in self.narration):
            raise ValueError("Anlatım tanımsız bir bloğa bağlı.")
        positions = {block.id: i for i, block in enumerate(self.blocks)}
        anchored = [positions[item.block] for item in self.narration]
        if anchored != sorted(anchored):
            raise ValueError("Anlatım sırası blok sırasıyla çelişiyor.")
        for block in self.blocks:
            if isinstance(block, DerivationStepBlock) and block.narration_ref is not None and block.narration_ref not in narration_ids:
                raise ValueError("Adımın anlatım referansı yok.")
        return self


State = CheckState

Dimension = Literal[
    "calculation", "transformation", "domain", "answer_target", "answer_choice", "source_consistency", "units",
    "stoichiometry", "evidence_consistency", "scientific", "curriculum", "method", "pedagogy",
]
# registry (TA-005): onaylı müfredat ve yöntem kaydı; yalnızca curriculum ve method boyutlarında.
Verifier = Literal["mathai", "integrity", "units", "chemistry", "evidence", "registry", "none"]
SUBJECT_VERIFIERS = frozenset({"units", "chemistry", "evidence"})


class BlockCheck(Contract):
    """Tek bir doğrulama sonucunun hedef bloğu. Hedef bulunamazsa ders düzeyinde ``unmapped`` kalır."""

    id: Identifier
    scope: Literal["block", "answer", "lesson"]
    target: Identifier | None = None
    mapping: Literal["mapped", "unmapped"] = "mapped"
    dimension: Dimension
    verifier: Verifier
    outcome: State
    reason: Identifier
    evidence: list[EvidenceRef] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def trustworthy(self):
        if (self.scope == "block") != (self.target is not None):
            raise ValueError("Blok kontrolü bir hedef bloğa bağlı olmalı.")
        if self.mapping == "unmapped" and self.scope != "lesson":
            raise ValueError("Eşlenemeyen kontrol ders düzeyindedir.")
        if self.dimension == "pedagogy" and self.outcome not in {"not_checked", "not_applicable"}:
            raise ValueError("Pedagoji bu sürümde denetlenmez.")
        if (self.dimension in {"curriculum", "method"}) != (self.verifier == "registry") and self.outcome not in {
                "not_checked", "not_applicable"}:
            raise ValueError("Müfredat ve yöntem yalnızca onaylı kayıtla denetlenir.")
        if self.verifier == "none" and self.outcome in {"passed", "failed", "partially_checked"}:
            raise ValueError("Doğrulayıcısı olmayan kontrol sonuç taşıyamaz.")
        if self.dimension == "scientific" and self.outcome == "passed" and self.verifier not in SUBJECT_VERIFIERS:
            raise ValueError("Bilimsel kontrol yalnızca alan doğrulayıcısıyla geçebilir.")
        return self


class VerificationReport(Contract):
    structural: Literal["passed"]
    scientific: State
    calculation: State
    source_consistency: State
    # TA-005: yalnızca onaylı kayıt (verifier "registry") passed/failed/partially_checked üretebilir.
    curriculum: Literal["passed", "partially_checked", "not_checked"]
    method: Literal["passed", "failed", "partially_checked", "not_checked"]
    pedagogy: Literal["not_checked"]
    engine: Label | None = None
    checked_claims: list[Text] = Field(default_factory=list, max_length=256)
    # TA-004 (2.2.0): blok/adım düzeyi kontroller ve istenen hedefin çözümü.
    block_checks: list[BlockCheck] = Field(default_factory=list, max_length=512)
    target: TargetResolution | None = None

    @model_validator(mode="after")
    def consistent_checks(self):
        ids = [item.id for item in self.block_checks]
        if len(set(ids)) != len(ids):
            raise ValueError("Kontrol kimlikleri benzersiz olmalı.")
        # Yöntem uygunsuzluğu hesap çelişkisi değildir; bağımsız hesap yine geçmiş olabilir.
        if any(item.outcome == "failed" and item.dimension != "method" for item in self.block_checks) and "passed" in (
                self.calculation, self.scientific):
            raise ValueError("Bilinen çelişki doğrulanmış gösterilemez.")
        for dimension in ("method", "curriculum"):
            state = getattr(self, dimension)
            if state != "not_checked" and not any(c.dimension == dimension and c.verifier == "registry" and c.outcome == state
                                                  for c in self.block_checks):
                raise ValueError("Yöntem ve müfredat sonucu yalnızca onaylı kayıt kontrolüyle gösterilir.")
        if self.target is not None and self.target.outcome == "failed" and self.calculation == "passed":
            raise ValueError("Hedef çelişkisi doğrulanmış gösterilemez.")
        return self


class SchemaIdentity(Contract):
    """2.1.0 (TA-003) kaynak revizyonunu, 2.2.0 (TA-004) adım, blok kontrolü, hedef, anlatım ve problem
    modeli alanlarını isteğe bağlı olarak ekler. 2.0.0 ve 2.1.0 belgeleri aynı anlamla geçerlidir."""

    name: Literal["teacherai.lesson_plan"]
    version: Literal["2.0.0", "2.1.0", "2.2.0"]


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
    # TA-004 (2.2.0): sorunun belirlenimci anlam modeli; kaynak gözlemi ile çıkarım ayrıdır.
    problem: ScientificProblemModel | None = None

    @model_validator(mode="after")
    def valid_evidence(self):
        if self.schema_identity.version == "2.0.0" and (self.source_revision is not None or self.source_decision is not None):
            raise ValueError("Kaynak revizyonu alanları 2.1.0 gerektirir.")
        if self.schema_identity.version != "2.2.0" and (
            self.problem is not None or self.verification.block_checks or self.verification.target is not None
            or self.content.narration or any(isinstance(b, DerivationStepBlock) for b in self.content.blocks)
        ):
            raise ValueError("Adım, kontrol, hedef, anlatım ve problem modeli 2.2.0 gerektirir.")
        blocks = {block.id for block in self.content.blocks}
        if any(check.scope == "block" and check.target not in blocks for check in self.verification.block_checks):
            raise ValueError("Kontrol tanımsız bir bloğa bağlı.")
        if self.problem is not None and (self.problem.subject != self.context.subject or (
            self.source_revision is not None and self.problem.source_revision not in (None, self.source_revision)
        )):
            raise ValueError("Problem modeli dersin alanı ve kaynak revizyonuyla uyuşmalı.")
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
