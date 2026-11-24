"""Ders amacı (intent) ile sunumu ayıran ortak model (TA-006).

``LessonIntent`` dersin *ne için* üretildiğini söyler; ``presentation.LessonView`` ise *nasıl gösterildiğini*.
Konu anlatımı uydurulmuş bir soru, cevap veya görsel gerektirmez. Bugün yalnız matematikte soru çözümü
çalışır; diğer kipler sözleşmede temsil edilir ama ``mode_support`` hangi fazda açılacağını söyler ve
arayüz yalnız ``available`` kipleri etkin gösterir.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .base import Contract, Identifier, Label, Subject
from .domain import capabilities

LessonMode = Literal["question_solving", "topic_explanation", "conversation", "interactive_whiteboard", "practice",
                     "student_feedback", "voice_narration"]
Presentation = Literal["steps", "board", "chat", "voice"]

# Kip → planlanan faz. "available" bugün öğrenci akışında çalışır.
MODE_PHASE: dict[str, str] = {
    "question_solving": "available",
    "practice": "available",
    "student_feedback": "available",
    "topic_explanation": "TA-013",
    "conversation": "TA-013",
    "interactive_whiteboard": "TA-014",
    "voice_narration": "TA-014",
}


class LessonIntent(Contract):
    mode: LessonMode
    subject: Subject
    topic_key: Identifier | None = None
    outcome_ids: list[Identifier] = Field(default_factory=list, max_length=16)
    # Yalnız soru çözümünde: sunucudaki analiz kimliği. Konu anlatımı soru gerektirmez.
    source_analysis_id: Label | None = None
    presentations: list[Presentation] = Field(default_factory=lambda: ["steps", "board"], min_length=1, max_length=4)

    @model_validator(mode="after")
    def coherent(self):
        if self.mode == "question_solving" and self.source_analysis_id is None:
            raise ValueError("Soru çözümü bir kaynak analiz gerektirir.")
        if self.mode == "topic_explanation":
            if self.source_analysis_id is not None:
                raise ValueError("Konu anlatımı soruya bağlanmaz.")
            if self.topic_key is None and not self.outcome_ids:
                raise ValueError("Konu anlatımı konu veya kazanım belirtir.")
        return self


class ModeSupport(Contract):
    mode: LessonMode
    subject: Subject
    available: bool
    planned_phase: Label | None = None
    reason: Literal["available", "planned", "subject_generation_unavailable"]


def mode_support(mode: str, subject: Subject) -> ModeSupport:
    phase = MODE_PHASE[mode]
    if phase != "available":
        return ModeSupport(mode=mode, subject=subject, available=False, planned_phase=phase, reason="planned")
    if not capabilities(subject).generation:
        # FKB üretimi kapalıdır (422 subject_generation_unavailable); arayüz bunu işlevsel göstermez.
        return ModeSupport(mode=mode, subject=subject, available=False, planned_phase="TA-009–TA-011",
                           reason="subject_generation_unavailable")
    return ModeSupport(mode=mode, subject=subject, available=True, reason="available")
