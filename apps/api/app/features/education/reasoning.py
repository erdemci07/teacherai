"""Alandan bağımsız akıl yürütme sözleşmeleri (TA-004).

Bu tipler sorunun *istediği* hedefi (AnswerTarget), verilen modeli, ara değerleri, sağlayıcının
önerdiği cevabı, bağımsız hesaplanan cevabı ve seçilen seçeneği ayrı tutar. Doğrulama sonuçları
yalnızca sunucudaki belirlenimci doğrulayıcılardan gelir; sağlayıcı çıktısı bir kontrolün sonucunu
belirleyemez.
"""

import re
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .base import Contract, Identifier, Label
from .source import ElementRef, Fragment

CheckState = Literal["passed", "failed", "partially_checked", "unsupported", "not_checked", "not_applicable"]

TargetKind = Literal[
    "variable_value", "expression_value", "sum", "difference", "product", "ratio", "solution_count",
    "root_sum", "root_product", "solution_set", "interval", "minimum", "maximum", "comparison",
    "proposition_truth", "statement_combination", "physical_quantity", "chemical_quantity",
    "scientific_interpretation", "textual_explanation", "unresolved",
]
# Sınırlı, belirlenimci hesaplanabilen hedefler. Diğerleri temsil edilir ama otomatik hesaplanmaz.
COMPUTABLE_TARGETS = frozenset({
    "variable_value", "expression_value", "sum", "difference", "product", "ratio", "solution_count",
    "root_sum", "root_product", "solution_set", "minimum", "maximum",
    # Yalnızca öncüller çözülen değişkende değerlendirilebilen ilişkilerse (ör. "I. x² = 16").
    "statement_combination",
})
EXPRESSION_TARGETS = frozenset({"expression_value", "sum", "difference", "product", "ratio"})
VariableName = Annotated[str, Field(pattern=r"^[a-zA-Z](_[a-zA-Z0-9]{1,4})?$")]


class AnswerTarget(Contract):
    """Sorunun istediği şey. Bir denklemin çözümü her zaman istenen cevap değildir (x = 3 iken x + 2)."""

    kind: TargetKind
    # deterministic: kaynak ifadelerinden ve soru kalıplarından; legacy_default: eski kayıtlarda tek
    # denklemin değişkeni; unresolved: hedef belirlenemedi, seçenek otomatik seçilmez.
    origin: Literal["deterministic", "legacy_default", "unresolved"]
    variable: VariableName | None = None
    expression: Fragment | None = None
    latex: Fragment | None = None
    source: ElementRef | None = None
    integer_only: bool = False
    markers: list[Label] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def coherent(self):
        if self.kind in EXPRESSION_TARGETS and self.expression is None:
            raise ValueError("İfade hedefi istenen ifadeyi taşımalı.")
        if (self.kind == "unresolved") != (self.origin == "unresolved"):
            raise ValueError("Çözülmemiş hedef ve kökeni tutarlı olmalı.")
        return self

    @property
    def computable(self) -> bool:
        return self.kind in COMPUTABLE_TARGETS and self.origin != "unresolved"


TargetReason = Literal[
    "target_value_matched", "target_value_mismatch", "intermediate_not_requested", "claim_missing",
    "claim_unparsed", "target_unresolved", "target_not_computable", "model_unsupported",
    "multiplicity_or_complex_roots", "domain_excluded", "not_finite", "unbounded_extremum",
    "multiple_values",
]


class TargetResolution(Contract):
    """Hedefin sunucu kaydı: verilen model, ara değerler, istenen değer, öneri ve seçenek ayrıdır."""

    target: AnswerTarget
    given: list[Fragment] = Field(default_factory=list, max_length=8)
    intermediate: list[Fragment] = Field(default_factory=list, max_length=16)
    requested: list[Fragment] = Field(default_factory=list, max_length=16)
    provider_claim: list[Fragment] = Field(default_factory=list, max_length=16)
    claim_role: Literal["target", "intermediate", "none", "unparsed"]
    outcome: CheckState
    reason: TargetReason
    selected_option: Label | None = None
    option_origin: Literal["independent", "provider", "none"] = "none"

    @model_validator(mode="after")
    def honest(self):
        if self.outcome == "passed" and (not self.requested or self.claim_role != "target"):
            raise ValueError("Hedef yalnızca bağımsız değer ve hedefe ait öneri eşleşince geçer.")
        if self.outcome == "passed" and not self.target.computable:
            raise ValueError("Hesaplanamayan hedef doğrulanmış gösterilemez.")
        return self


EvidenceKind = Literal[
    "block", "source_expression", "source_choice", "source_statement", "source_region", "observation",
    "quantity", "entity", "relation", "figure", "table_cell", "check",
]


class EvidenceRef(Contract):
    kind: EvidenceKind
    id: Identifier


Operation = Literal[
    # matematik dönüşümleri
    "add_both_sides", "subtract_both_sides", "multiply_both_sides", "divide_both_sides", "expand", "factor",
    "complete_square", "square_both_sides", "isolate_variable", "substitute", "compare", "evaluate", "rewrite",
    "case_split",
    # bilimsel akıl yürütme adımları
    "apply_principle", "calculate_quantity", "convert_unit", "compare_observations", "infer_sequence",
    "evaluate_premise", "interpret_visual",
    # açıklama ve bilinmeyen
    "explain", "state_result", "unknown",
]
# deterministic: ardışık ifadelerden sunucu tarafından sınıflandırıldı; v1_step_type: v1 adım türünden
# (yalnızca "case" ve "result"); fixture: çevrimdışı örnek; unknown: belirlenemedi.
OperationOrigin = Literal["deterministic", "v1_step_type", "fixture", "unknown"]


class NarrationSegment(Contract):
    """Gelecekteki sesli anlatım için yalnızca sözleşme. Ses üretimi TA-014'tedir."""

    id: Identifier
    order: int = Field(ge=0, le=1023)
    block: Identifier
    text: Annotated[str, Field(min_length=1, max_length=2000)]
    emphasis: list[Label] = Field(default_factory=list, max_length=8)
    pause_after_ms: int = Field(default=0, ge=0, le=5000)

    @model_validator(mode="after")
    def plain_text(self):
        for value in [self.text, *self.emphasis]:
            if re.search(r"<\s*[a-zA-Z/!]", value) or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", value):
                raise ValueError("Anlatım düz metin olmalı.")
        return self
