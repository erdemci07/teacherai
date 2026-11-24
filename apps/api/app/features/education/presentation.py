from datetime import datetime

from pydantic import Field, model_validator

from .curriculum_v2 import EducationalProvenance
from .domain import Contract, Identifier
from .lesson import ExpressionBlock, LessonPlanV2


class BoardPanel(Contract):
    blocks: list[Identifier] = Field(min_length=1, max_length=256)


class LessonView(Contract):
    lesson: LessonPlanV2
    panels: list[BoardPanel] = Field(min_length=1, max_length=256)
    created_at: datetime
    # TA-007: dersin üretildiği andaki bağlam kaydı (aşamalı gösterim için). Eski derslerde yoktur.
    provenance: EducationalProvenance | None = None

    @model_validator(mode="after")
    def complete_board(self):
        expected = [block.id for block in self.lesson.content.blocks]
        if [key for panel in self.panels for key in panel.blocks] != expected:
            raise ValueError("Tahta tüm blokları ders sırasıyla bir kez içermeli.")
        return self


def plan_panels(lesson: LessonPlanV2) -> list[BoardPanel]:
    """Ardışık bağımlı ifadeleri açıklamasıyla birlikte gösterir."""
    panels = []
    for block in lesson.content.blocks:
        if panels and isinstance(block, ExpressionBlock) and panels[-1].blocks[0] in block.relates_to:
            panels[-1].blocks.append(block.id)
        else:
            panels.append(BoardPanel(blocks=[block.id]))
    return panels
