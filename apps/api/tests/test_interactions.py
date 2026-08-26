from dataclasses import replace
import pytest
from fastapi.testclient import TestClient
from apps.api.app.features.interactions.exceptions import InteractionProviderError
from apps.api.app.features.interactions.context import build_interaction_context
from apps.api.app.features.interactions.openai_provider import OpenAIInteractionProvider
from apps.api.app.features.interactions.schemas import AdaptiveDraft,InteractionRequest,PracticeAnswerRequest
from apps.api.app.features.interactions.service import InteractionService
from apps.api.app.features.interactions.store import InMemoryPracticeStore
from apps.api.app.features.lessons.schemas import Expression
from apps.api.app.features.mathai.service import MathAIService
from apps.api.app.main import create_app
from apps.api.tests.test_mathai import plan

class Provider:
    def __init__(self,fail=False,bad_practice=False):self.actions=[];self.fail=fail;self.bad=bad_practice
    async def adapt(self,action,lesson,hint_level,teaching_context=None):
        self.actions.append((action,hint_level))
        if self.fail:raise InteractionProviderError
        common=dict(title="Birlikte bakalım",text="Önce küçük adıma odaklanalım.",steps=["İşlemi iki tarafa da uygula."],expressions=[Expression(type="equation",latex="3x=12")])
        if action == "similar_example":
            return AdaptiveDraft(**common,question_expression="2x+3=11",expected_answer_expression="x=5" if self.bad else "x=4",answer_variable="x",feedback_hint="+3'ten kurtulmak için iki taraftan 3 çıkar.")
        if action=="alternative":return AdaptiveDraft(**{**common,"title":"Başka bir yol","text":"Sonucu yerine koyarak geriye doğru kontrol edelim."})
        if action=="hint":return AdaptiveDraft(title=f"İpucu {hint_level}",text="x'in yanındaki sabit terime bak.")
        return AdaptiveDraft(**common)

def service(provider=None):return InteractionService(provider or Provider(),MathAIService(),InMemoryPracticeStore())

def request(action,hint=1):return InteractionRequest(action=action,lesson=plan(),hint_level=hint)

@pytest.mark.asyncio
async def test_understood_is_local_and_memory_ready():
    provider=Provider();result=await service(provider).interact("lesson_1",request("understood"))
    assert not provider.actions and result.event.event=="understood_clicked" and "ana fikir" in result.message

@pytest.mark.asyncio
@pytest.mark.parametrize("action,event",[("simplify","simpler_explanation_requested"),("alternative","alternative_method_requested"),("hint","hint_requested")])
async def test_adaptive_actions(action,event):
    result=await service().interact("lesson_1",request(action))
    assert result.board and result.event.event==event
    if action=="hint":assert result.next_hint_level==2

@pytest.mark.asyncio
async def test_similar_example_is_mathai_verified():
    result=await service().interact("lesson_1",request("similar_example"))
    assert result.verification_status=="verified"

@pytest.mark.asyncio
async def test_provider_failure_is_controlled():
    with pytest.raises(InteractionProviderError):await service(Provider(fail=True)).interact("lesson_1",request("simplify"))

def test_compact_interaction_context_excludes_image_preview_debug_and_provider_metadata():
    lesson=plan()
    lesson.source_analysis.normalized_preview_url="data:image/jpeg;base64,SECRETIMAGE"
    lesson.source_analysis.debug={"provider_response_id":"resp_secret"}
    lesson.source_analysis.provider="openai"
    lesson.source_analysis.model="vision-model"
    lesson.source_analysis.visual_elements.description="kamera açıklaması "*200

    context=build_interaction_context(lesson,"simplify",1)
    serialized=str(context)

    assert "question_text" in serialized
    assert "final_answer" in serialized
    assert "normalized_preview_url" not in serialized
    assert "SECRETIMAGE" not in serialized
    assert "debug" not in serialized
    assert "provider_response_id" not in serialized
    assert "vision-model" not in serialized
    assert "board" not in serialized

@pytest.mark.asyncio
async def test_openai_interaction_provider_uses_compact_payload(monkeypatch):
    captured={}

    class Responses:
        async def parse(self,**kwargs):
            captured["input"]=kwargs["input"]
            return type("Result",(),{"output_parsed":AdaptiveDraft(title="Kısa anlatım",text="x'e odaklan.",steps=[],expressions=[])})()

    class FakeClient:
        def __init__(self,**kwargs):self.responses=Responses()

    monkeypatch.setattr("apps.api.app.features.interactions.openai_provider.AsyncOpenAI",FakeClient)
    provider=OpenAIInteractionProvider("key","model",1)
    lesson=plan()
    lesson.source_analysis.normalized_preview_url="data:image/jpeg;base64,SECRETIMAGE"

    result=await provider.adapt("simplify",lesson,1)

    payload=captured["input"][1]["content"]
    assert result.text=="x'e odaklan."
    assert "interaction_context" in payload
    assert "lesson_plan_id" in payload
    assert "normalized_preview_url" not in payload
    assert "SECRETIMAGE" not in payload

@pytest.mark.asyncio
async def test_context_limit_gets_one_more_compact_retry(monkeypatch):
    calls=[]

    async def fake_adapt(self,client,action,lesson,hint_level,teaching_context,compact_level):
        calls.append(compact_level)
        if compact_level=="normal":
            from openai import BadRequestError
            import httpx
            response=httpx.Response(400,request=httpx.Request("POST","https://api.openai.test"))
            raise BadRequestError("context_length_exceeded",response=response,body={"code":"context_length_exceeded"})
        return AdaptiveDraft(title="İpucu",text="Daha küçük bağlamla hazırlandı.")

    monkeypatch.setattr(OpenAIInteractionProvider,"_adapt_with_context",fake_adapt)
    result=await OpenAIInteractionProvider("key","model",1).adapt("hint",plan(),1)

    assert result.text=="Daha küçük bağlamla hazırlandı."
    assert calls==["normal","emergency"]

def test_invalid_action_rejected_by_api():
    app=create_app();app.state.container=replace(app.state.container,interaction_service=service())
    with TestClient(app) as client:response=client.post('/api/v1/lessons/lesson_1/interact',json={'action':'run_system_prompt','lesson':plan().model_dump(by_alias=True)})
    assert response.status_code==422

def test_practice_action_removed_from_interaction_contract():
    app=create_app();app.state.container=replace(app.state.container,interaction_service=service())
    with TestClient(app) as client:response=client.post('/api/v1/lessons/lesson_1/interact',json={'action':'practice','lesson':plan().model_dump(by_alias=True)})
    assert response.status_code==422
