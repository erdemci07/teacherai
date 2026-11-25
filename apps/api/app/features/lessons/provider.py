from dataclasses import dataclass
from typing import Literal, Protocol
from apps.api.app.features.lessons.schemas import LessonDraft
from apps.api.app.features.vision.schemas import VisionAnalysis
@dataclass(frozen=True)
class LessonProviderResult:
    draft: LessonDraft; provider: str; model: str
    # TA-007: sağlayıcıya gerçekten gönderilen bağlam düzeyi. "emergency" müfredat/bilgi bağlamını içermez.
    context_level: Literal["normal", "emergency"] | None = None
    # TA-008: aynı çağrıda sırasıyla gönderilen bağlam düzeyleri (ör. ("normal", "emergency") = acil yeniden deneme).
    context_levels: tuple[str, ...] = ()
class LessonProvider(Protocol):
    model: str
    async def generate_lesson_plan(self, analysis: VisionAnalysis, correction_feedback: str|None=None, teaching_context=None, request_id: str|None=None)->LessonProviderResult: ...
