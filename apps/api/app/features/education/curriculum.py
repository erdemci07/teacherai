"""Müfredat kazanımı ve sınıf düzeyi yöntem politikası sözleşmeleri (TA-005).

İki katman ayrıdır:

1. ``Outcome``: resmî MEB öğretim programından kaynaklı kazanım. Metin yalnızca kaynak belgeye erişilip
   birebir alındıysa yazılır (``source_status: sourced``); aksi halde ``pending`` ve metinsizdir.
2. ``MethodPolicy``: ``(grade, topic)`` için izinli ve gerekçeli yasak işlemler. Bu katmanı öğretmen yazar.
   Taslak (``draft``) hiçbir kısıtlama uygulamaz; yalnızca ``approved`` kayıt denetime girer.

Sağlayıcı çıktısı müfredatı, yöntemi veya onayı belirleyemez: konu belirlenimci olarak kaynak ifadelerden,
işlemler sunucu sınıflandırmasından ve adım ifadelerinin belirlenimci taramasından gelir.
"""

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from .base import Contract, Identifier, Label, Text
from .reasoning import Operation

# Sınıf düzeyine göre yasaklanabilecek, adım ifadelerinden belirlenimci olarak tanınan yapılar.
Construct = Literal["derivative", "integral", "limit", "logarithm", "trigonometry", "complex_number",
                    "quadratic_formula"]
MethodOperation = Operation | Construct
PolicyState = Literal["passed", "failed", "partially_checked", "not_checked"]


class CurriculumSource(Contract):
    document: Label
    url: Label
    pages: Label | None = None


class Outcome(Contract):
    subject: Literal["mathematics"]
    grade: int = Field(ge=1, le=12)
    unit: Label
    topic: Identifier
    outcome_id: Identifier
    outcome_text_tr: Text | None = None
    source: CurriculumSource
    source_status: Literal["sourced", "pending"]

    @model_validator(mode="after")
    def sourced_text_only(self):
        if (self.outcome_text_tr is None) != (self.source_status == "pending"):
            raise ValueError("Kazanım metni yalnızca kaynaklı kayıtta bulunur.")
        return self


class ForbiddenOperation(Contract):
    operation: MethodOperation
    reason: Text


class MethodPolicy(Contract):
    id: Identifier
    grade: int = Field(ge=1, le=12)
    # "genel": sınıf düzeyinin bütün konularında geçerli yasaklar.
    topic: Identifier
    allowed_operations: list[MethodOperation] = Field(default_factory=list, max_length=64)
    forbidden_operations: list[ForbiddenOperation] = Field(default_factory=list, max_length=32)
    preferred_representations: list[Label] = Field(default_factory=list, max_length=16)
    outcome_ids: list[Identifier] = Field(default_factory=list, max_length=32)
    status: Literal["draft", "approved"]
    authored_by: Literal["claude-draft", "teacher"]
    approved_by: Label | None = None
    # TA-007: onay tarihi ve onaylanan içeriğin özeti. Eksikse politika çalışma zamanında etkin olmaz.
    approved_on: date | None = None
    approval_digest: Label | None = None

    @model_validator(mode="after")
    def approval_is_explicit(self):
        if (self.status == "approved") != (self.approved_by is not None):
            raise ValueError("Onaylı kayıt onaylayanı taşır; taslak taşımaz.")
        if set(self.allowed_operations) & {item.operation for item in self.forbidden_operations}:
            raise ValueError("Bir işlem hem izinli hem yasak olamaz.")
        return self


class CurriculumRegistry(Contract):
    schema_name: Literal["teacherai.curriculum_registry"]
    version: Literal["1.0.0"]
    # Hangi programın hangi sınıfta okutulduğu; kaynak yoksa "doğrulanamadı" notuyla.
    program_note: Text
    outcomes: list[Outcome] = Field(default_factory=list, max_length=512)
    policies: list[MethodPolicy] = Field(default_factory=list, max_length=256)

    @model_validator(mode="after")
    def references_resolve(self):
        ids = {item.outcome_id for item in self.outcomes}
        if len(ids) != len(self.outcomes) or len({p.id for p in self.policies}) != len(self.policies):
            raise ValueError("Kimlikler benzersiz olmalı.")
        if any(ref not in ids for policy in self.policies for ref in policy.outcome_ids):
            raise ValueError("Politika tanımsız kazanıma bağlanamaz.")
        return self


class MethodEvidence(Contract):
    """Bir adımdaki yöntem kanıtı. ``used`` güçlü (sunucu sınıflandırması + AST), ``mentioned`` zayıf (düz metin),
    ``rejected`` olumsuzlanmış söz ("türev kullanmadan"). ``identifiable`` false: adım işlemi belirlenemedi.
    ``unparsed`` > 0: ayrışmayan ifade; o ifade için yöntem doğrulama dışındadır."""

    step: Identifier
    used: list[MethodOperation] = Field(default_factory=list, max_length=16)
    mentioned: list[Construct] = Field(default_factory=list, max_length=8)
    rejected: list[Construct] = Field(default_factory=list, max_length=8)
    identifiable: bool = True
    unparsed: int = Field(default=0, ge=0, le=64)


class PolicyCheck(Contract):
    """Sunucunun yöntem veya müfredat denetimi sonucu. Sağlayıcı bu alanı üretemez."""

    dimension: Literal["method", "curriculum"]
    state: PolicyState
    reason: Identifier
    grade: int | None = Field(default=None, ge=1, le=12)
    topic: Identifier | None = None
    step: Identifier | None = None
    operations: list[MethodOperation] = Field(default_factory=list, max_length=64)
    policy_ids: list[Identifier] = Field(default_factory=list, max_length=8)
    outcome_ids: list[Identifier] = Field(default_factory=list, max_length=32)
    detail: Text | None = None
    # TA-007: adım başına yöntem kanıtı. Yalnız öğrenciye gösterilen adımlar incelenir; MathAI'nin iç çözücü
    # işlemleri yöntem kanıtı değildir.
    evidence: list[MethodEvidence] = Field(default_factory=list, max_length=64)
    topic_candidates: list[Identifier] = Field(default_factory=list, max_length=4)
    inactive_policy_ids: list[Identifier] = Field(default_factory=list, max_length=16)
