from typing import Protocol
from .schemas import Action,AdaptiveDraft
from apps.api.app.features.lessons.schemas import LessonPlan
from apps.api.app.features.memory.schemas import TeachingContext
class InteractionProvider(Protocol):
    async def adapt(self,action:Action,lesson:LessonPlan,hint_level:int,teaching_context:TeachingContext|None=None)->AdaptiveDraft:...
