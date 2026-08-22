from dataclasses import dataclass
from typing import Protocol
from apps.api.app.features.lessons.schemas import LessonDraft
from apps.api.app.features.vision.schemas import VisionAnalysis
@dataclass(frozen=True)
class LessonProviderResult:
    draft: LessonDraft; provider: str; model: str
class LessonProvider(Protocol):
    model: str
    async def generate_lesson_plan(self, analysis: VisionAnalysis, correction_feedback: str|None=None, teaching_context=None, request_id: str|None=None)->LessonProviderResult: ...
