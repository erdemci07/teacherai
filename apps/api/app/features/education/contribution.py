"""Öğretmen katkı içe aktarma biçimi (TA-006 → TA-007).

Katkı bir *girdidir*, onay değildir: içeri alınan her öğe ``draft`` olur ve ancak ayrı bir inceleme kaydıyla
(``knowledge.ReviewRecord``) onaylanır. Katkı dosyası öğretmen kimliğini yalnız kararlı bir başvuru olarak taşır
(``teacher:<takma-ad>``); ad, e-posta gibi kişisel bilgi taşımaz. Örnek soruların bağımsız cevap anahtarı ayrı
alandadır ve değerlendirme setine (``evals/``) değil alıştırma havuzuna aittir.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from .base import Contract, Identifier, Subject, Text
from .knowledge import ReviewerRef

ContributionKind = Literal["unfamiliar_question_approach", "common_error", "preferred_strategy", "class_level_method",
                           "alternative_explanation", "visual_strategy", "scientific_condition", "example_question"]


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
