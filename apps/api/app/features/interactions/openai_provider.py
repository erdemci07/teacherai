import asyncio,json
from pathlib import Path
from openai import AsyncOpenAI,APIConnectionError,APITimeoutError,BadRequestError,APIStatusError
from pydantic import ValidationError
from .context import build_interaction_context,fits_context_budget
from .exceptions import InteractionContextTooLargeError,InteractionProviderError,InvalidInteractionResponseError
from .schemas import Action,AdaptiveDraft
from apps.api.app.features.lessons.schemas import LessonPlan
class OpenAIInteractionProvider:
    def __init__(self,api_key:str|None,model:str,timeout:float,context_budget_bytes:int=12000):self.api_key=api_key;self.model=model;self.timeout=timeout;self.context_budget_bytes=context_budget_bytes;self.prompt=(Path(__file__).parent/"prompts"/"interaction.txt").read_text()
    async def adapt(self,action:Action,lesson:LessonPlan,hint_level:int,teaching_context=None)->AdaptiveDraft:
        if not self.api_key:raise InteractionProviderError
        client=AsyncOpenAI(api_key=self.api_key,timeout=self.timeout,max_retries=1)
        try:
            return await self._adapt_with_context(client,action,lesson,hint_level,teaching_context,"normal")
        except BadRequestError as exc:
            if not _is_context_limit(exc):raise InvalidInteractionResponseError from exc
            try:return await self._adapt_with_context(client,action,lesson,hint_level,teaching_context,"emergency")
            except BadRequestError as retry_exc:
                if _is_context_limit(retry_exc):raise InteractionContextTooLargeError from retry_exc
                raise InvalidInteractionResponseError from retry_exc
            except (APIConnectionError,APITimeoutError,asyncio.TimeoutError) as retry_exc:
                raise InteractionProviderError from retry_exc
            except ValidationError as retry_exc:
                raise InvalidInteractionResponseError from retry_exc
        except (APIConnectionError,APITimeoutError,asyncio.TimeoutError) as exc:
            raise InteractionProviderError from exc
        except APIStatusError as exc:
            raise InteractionProviderError from exc
        except ValidationError as exc:
            raise InvalidInteractionResponseError from exc

    async def _adapt_with_context(self,client,action,lesson,hint_level,teaching_context,compact_level):
        context=build_interaction_context(lesson,action,hint_level,compact_level)
        payload={"interaction_context":context,"teaching_context":teaching_context.model_dump(mode="json") if teaching_context else None}
        if compact_level=="normal" and not fits_context_budget(payload,self.context_budget_bytes):
            payload={"interaction_context":build_interaction_context(lesson,action,hint_level,"emergency"),"teaching_context":None}
        r=await asyncio.wait_for(client.responses.parse(model=self.model,input=[{"role":"system","content":self.prompt},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],text_format=AdaptiveDraft),self.timeout+2)
        if r.output_parsed is None:raise InvalidInteractionResponseError
        return AdaptiveDraft.model_validate(r.output_parsed)

def _is_context_limit(exc:Exception)->bool:
    text=str(exc).lower()
    return "context_length_exceeded" in text or "maximum context length" in text or "context length" in text
