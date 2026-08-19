import asyncio,json
from pathlib import Path
from openai import AsyncOpenAI,APIConnectionError,APITimeoutError
from .exceptions import InteractionProviderError
from .schemas import Action,AdaptiveDraft
from apps.api.app.features.lessons.schemas import LessonPlan
class OpenAIInteractionProvider:
    def __init__(self,api_key:str|None,model:str,timeout:float):self.api_key=api_key;self.model=model;self.timeout=timeout;self.prompt=(Path(__file__).parent/"prompts"/"interaction.txt").read_text()
    async def adapt(self,action:Action,lesson:LessonPlan,hint_level:int)->AdaptiveDraft:
        if not self.api_key:raise InteractionProviderError
        payload={"action":action,"hint_level":hint_level,"lesson":lesson.model_dump(by_alias=True,exclude={"source_analysis":{"debug"}})}
        try:r=await asyncio.wait_for(AsyncOpenAI(api_key=self.api_key,timeout=self.timeout,max_retries=1).responses.parse(model=self.model,input=[{"role":"system","content":self.prompt},{"role":"user","content":json.dumps(payload,ensure_ascii=False)}],text_format=AdaptiveDraft),self.timeout+2)
        except (APIConnectionError,APITimeoutError,asyncio.TimeoutError,Exception) as exc:raise InteractionProviderError from exc
        if r.output_parsed is None:raise InteractionProviderError
        return AdaptiveDraft.model_validate(r.output_parsed)
