from dataclasses import replace
import pytest
from fastapi.testclient import TestClient
from apps.api.app.features.interactions.exceptions import InteractionProviderError,InvalidPracticeError
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
        if action in ("practice","similar_example"):
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
async def test_practice_does_not_leak_answer_and_checks_attempts():
    current=service();created=await current.interact("lesson_1",request("practice"));practice=created.practice
    assert practice and "expected" not in practice.model_dump_json()
    wrong=current.submit("lesson_1",practice.practice_question_id,PracticeAnswerRequest(answer="x=-4"))
    assert not wrong.correct and wrong.mistake_type=="sign_error" and not wrong.can_show_solution
    second=current.submit("lesson_1",practice.practice_question_id,PracticeAnswerRequest(answer="3"))
    assert not second.correct and second.attempt_number==2
    third=current.submit("lesson_1",practice.practice_question_id,PracticeAnswerRequest(answer="x=4"))
    assert third.correct and third.event.event=="practice_correct"

@pytest.mark.asyncio
async def test_invalid_generated_practice_rejected():
    with pytest.raises(InvalidPracticeError):await service(Provider(bad_practice=True)).interact("lesson_1",request("practice"))

@pytest.mark.asyncio
async def test_provider_failure_is_controlled():
    with pytest.raises(InteractionProviderError):await service(Provider(fail=True)).interact("lesson_1",request("simplify"))

def test_invalid_action_rejected_by_api():
    app=create_app();app.state.container=replace(app.state.container,interaction_service=service())
    with TestClient(app) as client:response=client.post('/api/v1/lessons/lesson_1/interact',json={'action':'run_system_prompt','lesson':plan().model_dump(by_alias=True)})
    assert response.status_code==422
