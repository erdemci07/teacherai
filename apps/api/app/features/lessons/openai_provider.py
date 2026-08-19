import asyncio,json
from pathlib import Path
from openai import AsyncOpenAI, APIConnectionError, APITimeoutError
from pydantic import ValidationError
from .exceptions import *
from .provider import LessonProviderResult
from .schemas import LessonDraft
from ..vision.schemas import VisionAnalysis
class OpenAILessonProvider:
    name="openai"
    def __init__(self,api_key:str|None,model:str,timeout_seconds:float):
        self.api_key=api_key; self.model=model; self.timeout=timeout_seconds
        self.prompt=(Path(__file__).parent/"prompts"/"lesson_plan.txt").read_text()
    async def generate_lesson_plan(self,analysis:VisionAnalysis,correction_feedback:str|None=None)->LessonProviderResult:
        if not self.api_key: raise LessonProviderConfigurationError
        payload={"analysis":analysis.model_dump(exclude={"debug"}),"verification_feedback":correction_feedback}
        try:
            response=await asyncio.wait_for(AsyncOpenAI(api_key=self.api_key,timeout=self.timeout,max_retries=1).responses.parse(model=self.model,input=[{"role":"system","content":self.prompt},{"role":"user","content":json.dumps(payload,ensure_ascii=False)}],text_format=LessonDraft),self.timeout+2)
        except (APITimeoutError,asyncio.TimeoutError) as exc: raise LessonProviderUnavailableError from exc
        except (APIConnectionError,Exception) as exc: raise LessonProviderUnavailableError from exc
        if response.output_parsed is None: raise InvalidLessonPlanError
        try: draft=LessonDraft.model_validate(response.output_parsed)
        except ValidationError as exc: raise InvalidLessonPlanError from exc
        return LessonProviderResult(draft,self.name,self.model)
