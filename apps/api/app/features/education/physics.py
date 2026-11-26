"""Fizik doğrulama raporu sözleşmesi (TA-009 §12). Sağlayıcı bu alanları belirleyemez; yalnız sunucu üretir.

``capability``:

- ``verified``: bu problem için belirlenimci çözücü çalıştı; bütün girdiler kaynağa, uzlaşıma veya kaynaklı sabite
  bağlı; bütün uygulanabilirlik koşulları sağlandı veya öğrenciye görünür varsayım olarak yazıldı; akla yatkınlık
  denetimleri geçti ve türlü cevap hedefle eşleşti. Konu adından çıkarılmaz.
- ``partially_checked``: çözüm var ama bir koşul bilinmiyor, girdi görselden okunmuş veya cevap karşılaştırılamadı.
- ``interpreted``: girdiler veya kuvvetler kaynağa bağlanamadı; hesap yalnız sağlayıcı modelinin yorumudur.
- ``unsupported``: çözücü yok, yasa engellendi veya hedefli açıklama gerekiyor.
"""

from typing import Literal

from pydantic import Field

from .base import Contract, Identifier, Label, Text

PhysicsCapability = Literal["verified", "partially_checked", "interpreted", "unsupported"]


class PhysicsCheck(Contract):
    id: Identifier
    area: Literal["source", "law", "dimension", "solution", "plausibility", "answer", "topology", "graph"]
    status: Literal["passed", "failed", "partially_checked", "not_checked", "unsupported"]
    reason: Identifier
    detail: Text | None = None
    # Maddi çelişki: yanlış istenen cevap, koşulu ihlal edilmiş yasa, boyutça tutarsız denklem, akla yatkınlık ihlali.
    material: bool = False


class PhysicsCondition(Contract):
    law: Identifier
    condition: Identifier
    state: Literal["satisfied", "violated", "unknown"]
    basis: Identifier
    assumption_tr: Text | None = None
    detail: Text | None = None


class ValueUse(Contract):
    symbol: Label
    value: Label
    origin: Identifier  # source_text | problem_convention | standard_constant | student_confirmed | visual | unverified
    source: Text | None = None


class PhysicsReport(Contract):
    schema_version: Literal["1.0.0"] = "1.0.0"
    capability: PhysicsCapability = "unsupported"
    domain: Identifier = "other"
    target_kind: Identifier | None = None
    computed: Label | None = None  # bağımsız değer (SI, birimiyle)
    answer: Literal["matched", "mismatch", "undecidable", "absent"] = "absent"
    answer_reasons: list[Identifier] = Field(default_factory=list, max_length=8)
    laws: list[Identifier] = Field(default_factory=list, max_length=12)
    conditions: list[PhysicsCondition] = Field(default_factory=list, max_length=48)
    values_used: list[ValueUse] = Field(default_factory=list, max_length=32)
    assumptions_tr: list[Text] = Field(default_factory=list, max_length=16)
    steps_tr: list[Text] = Field(default_factory=list, max_length=24)
    checks: list[PhysicsCheck] = Field(default_factory=list, max_length=64)
    material_count: int = Field(default=0, ge=0, le=1000)
    clarification_needed: bool = False
    clarification_tr: Text | None = None
    notes_tr: list[Text] = Field(default_factory=list, max_length=8)
