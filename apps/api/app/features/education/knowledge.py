"""Bilimsel kaynak ve bilgi kaydı sözleşmeleri, öğretmen inceleme akışı (TA-006, ADR TA-006).

İlkeler:

- **Dört ayrı izin.** Akademik başvuru, içeri alma/dönüştürme, öğrenciye yeniden dağıtım ve model eğitimi ayrı
  alanlardır; biri diğerinin izni sayılmaz. Lisansı doğrulanmamış kaynakta yalnız akademik başvuru açık olabilir.
- **Bilgi girdisi özgün yazılır.** Kaynak metni kopyalanmaz; kaynak yalnız konum (bölüm/URL) olarak bağlanır.
  Doğrulanmamış sayfa numarası yazılmaz.
- **Bilimsel ifade ile pedagojik sadeleştirme ayrıdır** (``statement_tr`` ve ``simplifications``).
- **Doğrulayıcı bağlantısı kısmidir.** Bir denetleyici iddianın yalnız belirtilen parçasını sınar; bütün iddiayı
  doğrulanmış göstermez. Denetleyicisi olmayan girdi ``not_checked`` kalır.
- **Onay yalnız kayıtlı insan incelemesiyle.** AI taslağı (``claude-draft``) kendini onaylayamaz; sağlayıcı çıktısı
  onay belirleyemez. Onay, onaylanan sürüm numarasını taşıyan bir inceleme kaydı gerektirir.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from .base import Contract, Identifier, Label, Subject, Text

Permission = Literal["allowed", "not_allowed", "conditional", "unknown"]
ReviewStatus = Literal["draft", "source_verified", "in_review", "revision_requested", "approved", "rejected", "superseded"]
Decision = Literal["source_verified", "request_revision", "approve", "reject", "supersede"]
ReviewerRole = Literal["teacher", "subject_expert", "project_owner"]
KnowledgeKind = Literal["fact", "law", "definition", "theorem", "relationship", "process", "experimental_principle", "method"]
VisualKind = Literal["equation", "derivation", "geometry", "coordinate_graph", "vector_diagram", "free_body_diagram",
                     "circuit", "chemical_equation", "molecular_structure", "labeled_structure", "process_diagram",
                     "data_table", "experiment_graph"]
ReviewerRef = Annotated[str, StringConstraints(pattern=r"^(teacher|expert|owner):[a-z0-9][a-z0-9_-]{2,63}$")]

# Mevcut belirlenimci denetleyiciler (features/reasoning, features/mathai, features/integrity). Kimlik listesi
# knowledge/capabilities.py içindeki tanımlarla birebir eşleşir; test her kimliğin gerçek bir fonksiyona bağlandığını sınar.
VerifierId = Literal[
    "mathai.equation_roots", "mathai.inequality_solution", "mathai.answer_target", "mathai.constant_expression",
    "integrity.expression_ast",
    "reasoning.units.dimension", "reasoning.units.conversion", "reasoning.formula.evaluate", "reasoning.formula.dimensions",
    "reasoning.formula.graph_slope", "reasoning.formula.graph_area", "reasoning.chemistry.parse_species",
    "reasoning.chemistry.balance", "reasoning.chemistry.stoichiometry", "reasoning.chemistry.limiting_reactant",
    "reasoning.chemistry.redox_electrons", "reasoning.sequence.transcription", "reasoning.sequence.codon",
    "reasoning.evidence.controlled_comparison", "reasoning.evidence.claim", "reasoning.evidence.constant_ratio",
    "reasoning.evidence.sequence_order",
]
CheckState = Literal["passed", "failed", "partially_checked", "unsupported", "not_checked"]


class Permissions(Contract):
    academic_reference: Permission
    ingestion: Permission
    redistribution: Permission
    model_training: Permission
    conditions_tr: Text | None = None

    @model_validator(mode="after")
    def conditional_is_explained(self):
        values = (self.academic_reference, self.ingestion, self.redistribution, self.model_training)
        if "conditional" in values and not self.conditions_tr:
            raise ValueError("Koşullu izin koşulu yazar.")
        return self


class SourceRecord(Contract):
    id: Identifier
    title: Label
    authors: list[Label] = Field(default_factory=list, max_length=12)
    institution: Label | None = None
    edition: Label | None = None
    year: int | None = Field(default=None, ge=1800, le=2100)
    url: Label | None = None
    doi: Label | None = None
    isbn: Label | None = None
    kind: Literal["textbook", "open_textbook", "standard", "reference_data", "database", "reference_work",
                  "classic", "official_curriculum", "oer_platform"]
    access: Literal["open_web", "purchase_required", "access_restricted", "not_accessed"]
    subjects: list[Subject] = Field(min_length=1, max_length=6)
    license: Label | None = None
    license_verified: bool
    rights_holder: Label | None = None
    permissions: Permissions
    # Kaynağın kendisinin doğrulanma tarihi (erişim, sayfa, lisans ifadesi).
    verified_on: date | None = None
    edition_verified: bool
    notes_tr: Text
    review_status: Literal["unreviewed", "owner_reviewed"]

    @model_validator(mode="after")
    def rights_are_not_assumed(self):
        perms = self.permissions
        if not self.license_verified and "allowed" in (perms.ingestion, perms.redistribution, perms.model_training):
            raise ValueError("Lisansı doğrulanmamış kaynakta içeri alma, dağıtım veya eğitim izni verilemez.")
        if self.access == "purchase_required" and not self.license_verified and perms.ingestion != "not_allowed":
            raise ValueError("Satın alınan ders kitabı içeri alma izni sayılmaz.")
        if self.license and re.search(r"(?:^|[-\s])SA\b", self.license.upper()) and "conditional" not in (perms.ingestion, perms.redistribution):
            raise ValueError("Share-alike lisansın yükümlülüğü koşul olarak yazılır.")
        if self.license_verified and self.verified_on is None:
            raise ValueError("Doğrulanmış lisans doğrulama tarihi taşır.")
        return self


class Locator(Contract):
    """Kaynakta doğrulanmış konum. ``page`` yalnız gerçekten görülen sayfa için yazılır."""

    source_id: Identifier
    section: Label | None = None
    url: Label | None = None
    page: Label | None = None
    verified_on: date | None = None

    @model_validator(mode="after")
    def located(self):
        if not (self.section or self.url or self.page):
            raise ValueError("Konum bölüm, adres veya sayfa taşır.")
        return self


class QuantitySpec(Contract):
    symbol: Label
    name_tr: Label
    si_unit: Label | None = None


class StructureFunction(Contract):
    structure_tr: Label
    function_tr: Text


class Simplification(Contract):
    """Öğretim için sadeleştirme: bilimsel ifadenin yerine geçmez, hangi düzeyde ve neyi dışarıda bıraktığını söyler."""

    level: Label
    text_tr: Text
    omits_tr: Text


class VerifierLink(Contract):
    verifier: VerifierId
    # Denetleyicinin bu girdinin hangi parçasını sınadığı. Bütün iddia değildir.
    checks_tr: Text
    coverage: Literal["partial"] = "partial"


class ReviewRecord(Contract):
    reviewer: ReviewerRef
    role: ReviewerRole
    reviewed_on: date
    reviewed_version: int = Field(ge=1)
    decision: Decision
    rationale_tr: Text


class KnowledgeEntry(Contract):
    id: Identifier
    version: int = Field(ge=1, le=1000)
    subject: Subject
    topic: Identifier
    subtopic: Identifier | None = None
    kind: KnowledgeKind
    title_tr: Label
    statement_tr: Text
    representation: Label | None = None
    quantities: list[QuantitySpec] = Field(default_factory=list, max_length=16)
    conditions_tr: list[Text] = Field(default_factory=list, max_length=12)
    assumptions_tr: list[Text] = Field(default_factory=list, max_length=12)
    exceptions_tr: list[Text] = Field(default_factory=list, max_length=12)
    prerequisites: list[Identifier] = Field(default_factory=list, max_length=12)
    related: list[Identifier] = Field(default_factory=list, max_length=12)
    outcome_refs: list[Identifier] = Field(default_factory=list, max_length=16)
    structure_function: list[StructureFunction] = Field(default_factory=list, max_length=12)
    misconceptions_tr: list[Text] = Field(default_factory=list, max_length=12)
    simplifications: list[Simplification] = Field(default_factory=list, max_length=6)
    visuals: list[VisualKind] = Field(default_factory=list, max_length=8)
    verifiers: list[VerifierLink] = Field(default_factory=list, max_length=8)
    provenance: list[Locator] = Field(default_factory=list, max_length=8)
    authored_by: Literal["claude-draft", "teacher", "subject_expert"]
    status: ReviewStatus
    reviews: list[ReviewRecord] = Field(default_factory=list, max_length=32)
    supersedes: Identifier | None = None

    @model_validator(mode="after")
    def review_state_is_recorded(self):
        last = self.reviews[-1].decision if self.reviews else None
        expected = {None: {"draft", "in_review"}, "source_verified": {"source_verified", "in_review"},
                    "request_revision": {"revision_requested", "draft"}, "approve": {"approved"},
                    "reject": {"rejected"}, "supersede": {"superseded"}}[last]
        if self.status not in expected:
            raise ValueError(f"Durum ({self.status}) son inceleme kararıyla ({last}) uyuşmuyor.")
        if self.status == "approved":
            approval = self.reviews[-1]
            if approval.role not in {"teacher", "subject_expert"}:
                raise ValueError("Onay yalnız öğretmen veya alan uzmanı incelemesiyle verilir.")
            if approval.reviewed_version != self.version:
                raise ValueError("Onay bu sürüme ait olmalı.")
            if not self.provenance:
                raise ValueError("Kaynaksız girdi onaylanamaz.")
        if self.subject == Subject.BIOLOGY and self.kind in {"law", "theorem"} and not self.conditions_tr:
            raise ValueError("Biyolojide yasa/teorem kaydı geçerlilik koşulunu yazar.")
        if self.kind == "law" and not self.conditions_tr:
            raise ValueError("Yasa kaydı geçerlilik koşulunu yazar.")
        return self


class SourceRegistryFile(Contract):
    schema_name: Literal["teacherai.source_registry"]
    version: Literal["1.0.0"]
    sources: list[SourceRecord] = Field(min_length=1, max_length=1024)


class KnowledgeFile(Contract):
    schema_name: Literal["teacherai.knowledge_registry"]
    version: Literal["1.0.0"]
    subject: Subject
    entries: list[KnowledgeEntry] = Field(default_factory=list, max_length=2048)


class CapabilityCheck(Contract):
    """Bir bilgi girdisinin doğrulayıcı kapsamı. ``claim_state`` bütün iddia için hiçbir zaman ``passed`` değildir."""

    entry_id: Identifier
    verifiers: list[VerifierId] = Field(default_factory=list, max_length=8)
    claim_state: Literal["partially_checked", "not_checked"]
    unchecked_tr: list[Text] = Field(default_factory=list, max_length=8)
