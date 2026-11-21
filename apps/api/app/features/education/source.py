"""Alandan bağımsız soru kaynağı bütünlüğü sözleşmeleri (TA-003).

Bu tipler kaynak gözlemi, normalleştirilmiş içerik, sağlayıcı önerisi, öğrenci onayı ve sunucu
kararını ayrı tutar. Matematik dışı alanlar (fizik birimleri, kimya alt simgeleri, biyoloji etiketleri)
aynı belirsizlik, bölge ve köken kavramlarını kullanabilir. Sunucu kararı hiçbir zaman kaynak
fotoğrafın doğrulandığı anlamına gelmez; yalnızca eldeki kanıtı özetler.
"""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from .base import Contract, Identifier, Label, Subject

SourceText = Annotated[str, StringConstraints(min_length=1, max_length=4000)]
Fragment = Annotated[str, StringConstraints(min_length=1, max_length=400)]
# stem | visual | expression:<sıra> | choice:<etiket> | statement:<Roma rakamı>
ElementRef = Annotated[str, Field(pattern=r"^(stem|visual|expression:[0-9]{1,2}|choice:[A-Za-z0-9]{1,4}|statement:[IVX]{1,4})$")]

UncertaintyCategory = Literal[
    "symbol", "sign", "grouping", "radical_scope", "fraction_scope", "exponent_scope", "subscript", "decimal",
    "text", "negation", "answer_choice", "diagram", "graph", "table", "quantity", "unit", "source_selection",
]
Impact = Literal["noncritical", "material", "fatal"]
Resolution = Literal["unresolved", "resolved_locally", "confirmed_by_recheck", "resolved_by_student", "rejected_by_student"]
EvidenceOrigin = Literal["vision", "vision_recheck", "deterministic", "legacy_text", "student"]

Decision = Literal[
    "ready",
    "ready_with_noncritical_uncertainty",
    "targeted_recheck",
    "clarification_required",
    "retake_required",
    "incomplete",
    "unreadable",
    "no_question",
    "unsupported_subject",
]
SOLVABLE_DECISIONS = frozenset({"ready", "ready_with_noncritical_uncertainty"})

ReasonCode = Literal[
    "clean",
    "normalized_notation",
    "decimal_comma_resolved",
    "mixed_number_convention",
    "unsupported_notation",
    "invalid_structure",
    "latex_exponent_scope",
    "decimal_ambiguity",
    "duplicate_expression",
    "duplicate_choice_labels",
    "missing_choice_label",
    "unlabeled_choices",
    "equivalent_choice_values",
    "single_choice",
    "missing_statements",
    "duplicate_statement_labels",
    "polarity_conflict",
    "negation_present",
    "missing_question_text",
    "provider_uncertainty_material",
    "provider_uncertainty_noncritical",
    "equivalent_alternatives",
    "alternative_not_applicable",
    "legacy_uncertainty",
    "multiple_questions",
    "target_question_unclear",
    "invalid_region_omitted",
    "essential_visual_without_facts",
    # TA-004
    "essential_visual_text_sufficient",
    "essential_visual_insufficient",
    "visual_supplied_by_recheck",
    "legacy_uncertainty_material",
    "legacy_uncertainty_formatting",
    "legacy_uncertainty_context_absent",
    "legacy_uncertainty_unclassified",
    "legacy_uncertainty_merged",
    "recheck_confirmed",
    "recheck_equivalent",
    "recheck_disagreement",
    "recheck_illegible",
    "recheck_unavailable",
    "recheck_budget_exhausted",
    "student_selected",
    "student_rejected",
    "unsupported_subject",
    "not_a_question",
    "unreadable_source",
    "incomplete_source",
]


class SourceRegion(Contract):
    """Görsel üzerinde 0–1 aralığında normalleştirilmiş bölge. Sağlayıcı önerisidir, doğrulanmış gerçek değildir."""

    kind: Literal["question", "expression", "choices", "diagram", "graph", "table", "annotation", "other_question"]
    x0: float = Field(ge=0, le=1)
    y0: float = Field(ge=0, le=1)
    x1: float = Field(ge=0, le=1)
    y1: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def ordered(self):
        if not (self.x0 < self.x1 and self.y0 < self.y1):
            raise ValueError("Bölge köşeleri sıralı olmalı.")
        if (self.x1 - self.x0) * (self.y1 - self.y0) < 0.0025:
            raise ValueError("Bölge çok küçük.")
        return self


class NormalizationNote(Contract):
    """Anlamı değiştirmeyen belirlenimci dönüşüm. Özgün okuma ayrıca saklanır."""

    rule: Literal[
        "unicode_minus", "dash_as_minus", "multiplication_sign", "division_sign", "superscript_digit",
        "latex_spacing", "latex_fraction_variant", "decimal_comma", "whitespace", "unicode_relation",
        "unicode_root", "unicode_constant",
    ]
    original: Label
    normalized: Label


class SourceExpression(Contract):
    id: Identifier
    index: int = Field(ge=0, le=63)
    role: Literal["given", "requested", "answer_choice", "premise", "unknown"]
    source: Fragment
    status: Literal["parsed", "unsupported", "invalid"]
    canonical: Fragment | None = None
    latex: Fragment | None = None
    reason: Label | None = None
    normalizations: list[NormalizationNote] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def parsed_has_structure(self):
        if (self.status == "parsed") != (self.canonical is not None and self.latex is not None):
            raise ValueError("Ayrıştırılmış ifade kanonik ve LaTeX biçimini birlikte taşır.")
        return self


class AnswerChoice(Contract):
    """Etiket ile içerik arasındaki ilişki kaynak verisidir; sıraya göre yeniden etiketlenmez."""

    id: Identifier
    order: int = Field(ge=0, le=11)
    label: Label | None = None
    label_origin: Literal["printed", "none"]
    content: Fragment | None = None
    kind: Literal["expression", "number", "text", "statement_combination", "visual", "empty"]
    canonical: Fragment | None = None
    latex: Fragment | None = None
    statement_refs: list[Annotated[str, Field(pattern=r"^[IVX]{1,4}$")]] = Field(default_factory=list, max_length=6)


class IntentMarker(Contract):
    marker: Label
    category: Literal["negation", "polarity", "extremum", "quantifier", "possibility", "count", "operation"]


class QuestionIntent(Contract):
    kind: Literal[
        "find_value", "find_variable", "simplify", "compare", "identify_true", "identify_false", "find_all_valid",
        "interpret_graph", "interpret_table", "identify_shape", "determine_range", "find_minimum", "find_maximum",
        "determine_possible", "determine_impossible", "count", "unknown",
    ]
    markers: list[IntentMarker] = Field(default_factory=list, max_length=24)
    statement_labels: list[Annotated[str, Field(pattern=r"^[IVX]{1,4}$")]] = Field(default_factory=list, max_length=6)
    choice_dependent: bool
    answer_strategy: Literal["solve_first_hidden", "derive_then_select", "choice_dependent", "open"]


class Alternative(Contract):
    id: Identifier
    text: Fragment
    latex: Fragment | None = None
    origin: Literal["vision", "vision_recheck", "deterministic"]


class SourceUncertainty(Contract):
    id: Identifier
    category: UncertaintyCategory
    element: ElementRef | None = None
    recognized: Fragment | None = None
    alternatives: list[Alternative] = Field(default_factory=list, max_length=4)
    impact: Impact
    resolution: Resolution
    origin: EvidenceOrigin
    evidence: list[ReasonCode] = Field(default_factory=list, max_length=8)
    region: SourceRegion | None = None
    note: Label | None = None

    @model_validator(mode="after")
    def applicable_alternatives(self):
        if self.alternatives and (self.element is None or self.recognized is None):
            raise ValueError("Seçenekli belirsizlik bir öğeye ve okunan parçaya bağlı olmalı.")
        if len({item.id for item in self.alternatives}) != len(self.alternatives):
            raise ValueError("Seçenek kimlikleri benzersiz olmalı.")
        return self


class IntegrityCheck(Contract):
    code: ReasonCode
    impact: Impact
    element: ElementRef | None = None


ImageAdvisoryCategory = Literal[
    "small_image", "downscaled", "low_contrast", "underexposed", "overexposed", "possible_glare",
    "possible_blur", "possible_clipping", "uneven_lighting", "transparency_flattened", "orientation_corrected",
    "metadata_removed",
]


class Correction(Contract):
    """Öğrencinin onayladığı düzeltme. Bağımsız doğrulama değildir."""

    element: ElementRef
    original: Fragment
    corrected: Fragment
    uncertainty_id: Identifier
    from_revision: int = Field(ge=1)


class ClarificationRecord(Contract):
    uncertainty_id: Identifier
    selection: Identifier
    from_revision: int = Field(ge=1)


class ClarificationRequest(Contract):
    """Öğrencinin tek bir belirsizlik için seçimi.

    ``selection``: bir alternatifin kimliği, ilk okumayı onaylamak için ``recognized`` veya hiçbirinin
    doğru olmadığını söylemek için ``none``. İstemci analiz içeriği veya doğrulama durumu gönderemez.
    """

    expected_revision: int = Field(ge=1, le=64)
    uncertainty_id: Identifier
    selection: Identifier


class IntegrityReport(Contract):
    """Sunucunun soru anlama kararı. Kaynak görselin doğru okunduğunu kanıtlamaz."""

    schema_version: Literal["1.0.0"] = "1.0.0"
    revision: int = Field(ge=1, le=64)
    revision_origin: Literal["vision", "vision_recheck", "student_clarification", "legacy"]
    decision: Decision
    recovery: Literal["none", "choose_alternative", "retake", "crop"]
    subject: Subject
    subject_origin: Literal["canonical_label", "vision_math_gate", "unknown"]
    intent: QuestionIntent
    expressions: list[SourceExpression] = Field(default_factory=list, max_length=64)
    choices: list[AnswerChoice] = Field(default_factory=list, max_length=12)
    uncertainties: list[SourceUncertainty] = Field(default_factory=list, max_length=16)
    checks: list[IntegrityCheck] = Field(default_factory=list, max_length=96)
    image: list[ImageAdvisoryCategory] = Field(default_factory=list, max_length=12)
    rechecks_used: int = Field(ge=0, le=2)
    recheck_limit: int = Field(ge=0, le=2)
    corrections: list[Correction] = Field(default_factory=list, max_length=16)
    clarifications: list[ClarificationRecord] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def consistent(self):
        ids = [item.id for item in self.uncertainties]
        if len(set(ids)) != len(ids):
            raise ValueError("Belirsizlik kimlikleri benzersiz olmalı.")
        if self.rechecks_used > self.recheck_limit:
            raise ValueError("Yeniden okuma sınırı aşıldı.")
        if self.decision in SOLVABLE_DECISIONS and any(
            item.impact != "noncritical" and item.resolution in {"unresolved", "rejected_by_student"}
            for item in self.uncertainties
        ):
            raise ValueError("Çözülmemiş kritik belirsizlik varken soru hazır sayılamaz.")
        return self

    @property
    def solvable(self) -> bool:
        return self.decision in SOLVABLE_DECISIONS

    def pending(self) -> list[SourceUncertainty]:
        return [item for item in self.uncertainties if item.impact != "noncritical" and item.resolution == "unresolved"]
