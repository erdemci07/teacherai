"""Öğretmen katkı içe aktarma biçimi (TA-006 → TA-007).

Katkı bir *girdidir*, onay değildir: içeri alınan her öğe ``draft`` olur ve ancak ayrı bir inceleme kaydıyla
(``knowledge.ReviewRecord``) onaylanır. Katkı dosyası öğretmen kimliğini yalnız kararlı bir başvuru olarak taşır
(``teacher:<takma-ad>``); ad, e-posta gibi kişisel bilgi taşımaz. Örnek soruların bağımsız cevap anahtarı ayrı
alandadır ve değerlendirme setine (``evals/``) değil alıştırma havuzuna aittir.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from .base import Contract, Identifier, Subject, Text
from .knowledge import ReviewerRef

ContributionKind = Literal["unfamiliar_question_approach", "common_error", "preferred_strategy", "class_level_method",
                           "alternative_explanation", "visual_strategy", "scientific_condition", "example_question",
                           # TA-007: istisna/karşı örnek koşuldan ayrı tutulur.
                           "scientific_exception"]


class ExampleQuestion(Contract):
    question_tr: Text
    # Öğretmenin kendi çözümüyle verdiği bağımsız anahtar. Modelden türetilmez.
    answer_key_tr: Text
    solution_outline_tr: Text | None = None
    original: Literal[True]


class ContributionItem(Contract):
    kind: ContributionKind
    topic: Identifier
    text_tr: Text
    grades: list[int] = Field(default_factory=list, max_length=8)
    outcome_ids: list[Identifier] = Field(default_factory=list, max_length=16)
    knowledge_ids: list[Identifier] = Field(default_factory=list, max_length=16)
    example: ExampleQuestion | None = None
    # TA-007: öğretmenin yazdığı kaynak (görülmeyen kaynak/sayfa yazılmaz). Doğrulanana kadar yalnız nottur.
    source_note_tr: Text | None = None

    @model_validator(mode="after")
    def example_only_for_questions(self):
        if (self.kind == "example_question") != (self.example is not None):
            raise ValueError("Örnek soru yalnız example_question öğesinde ve onda zorunludur.")
        if any(grade < 5 or grade > 12 for grade in self.grades):
            raise ValueError("Sınıf 5-12 aralığında olmalı.")
        return self


class TeacherContribution(Contract):
    schema_name: Literal["teacherai.teacher_contribution"]
    version: Literal["1.0.0"]
    contributor: ReviewerRef
    role: Literal["teacher", "subject_expert"]
    subject: Subject
    submitted_on: date
    # Katkı sahibinin içeriği TeacherAI'de kullanma iznine onayı (öğrenciye gösterim dahil). Model eğitimi ayrı izindir.
    consent_use: Literal[True]
    consent_model_training: bool = False
    items: list[ContributionItem] = Field(min_length=1, max_length=200)


# --- TA-007: katkı yönetişimi --------------------------------------------------------------------------------------
# Katkı dosyası yalnız girdidir; aşama kayıtları ayrı bir kayıt dosyasındadır (``register.json``). Her aşama
# kaydı katkının o anki içerik özetini taşır: katkı sonradan değişirse eski aşamalar bayat sayılır.

ContributionStage = Literal["submitted", "normalized", "source_verified", "scientific_review", "pedagogical_review",
                            "rights_approved", "published", "revision_requested", "rejected", "superseded",
                            "withdrawn"]
TERMINAL_STAGES = {"rejected", "superseded", "withdrawn"}


class ContributionEvent(Contract):
    stage: ContributionStage
    on: date
    by: ReviewerRef
    role: Literal["teacher", "subject_expert", "project_owner"]
    content_digest: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    note_tr: Text | None = None
    superseded_by: Identifier | None = None


class ContributionRecord(Contract):
    contribution_id: Identifier
    path: Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]{2,120}\.json$")]
    events: list[ContributionEvent] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def ordered(self):
        if self.events[0].stage != "submitted":
            raise ValueError("İlk aşama kaydı 'submitted' olmalı.")
        dates = [event.on for event in self.events]
        if dates != sorted(dates):
            raise ValueError("Aşama kayıtları tarih sırasında olmalı.")
        for index, event in enumerate(self.events[:-1]):
            if event.stage in TERMINAL_STAGES:
                raise ValueError(f"'{event.stage}' sonrası aşama kaydı eklenemez.")
        if any(event.stage == "superseded" and event.superseded_by is None for event in self.events):
            raise ValueError("Yerine geçen katkı belirtilmeli.")
        return self


class ContributionRegister(Contract):
    schema_name: Literal["teacherai.contribution_register"]
    version: Literal["1.0.0"]
    records: list[ContributionRecord] = Field(default_factory=list, max_length=2000)

    @model_validator(mode="after")
    def unique(self):
        ids = [item.contribution_id for item in self.records]
        if len(set(ids)) != len(ids) or len({item.path for item in self.records}) != len(ids):
            raise ValueError("Katkı kimlikleri ve dosyaları benzersiz olmalı.")
        return self
