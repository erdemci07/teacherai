import pytest
from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.lessons.exceptions import VerificationContradictionError
from apps.api.app.features.lessons.provider import LessonProviderResult
from apps.api.app.features.lessons.schemas import Expression,LessonContent,LessonDraft,Step
from apps.api.app.features.lessons.service import LessonService
from apps.api.app.features.mathai.service import MathAIService
from apps.api.tests.test_mathai import plan

class CorrectingProvider:
    model="mock"
    def __init__(self,remain_wrong=False): self.calls=[];self.remain_wrong=remain_wrong
    async def generate_lesson_plan(self,analysis,correction_feedback=None,teaching_context=None):
        self.calls.append(correction_feedback)
        answer="x = 5" if correction_feedback is None or self.remain_wrong else "x = 4"
        content=LessonContent(question_understanding="x'i yalnız bırak",unknown="x",key_rule="Eşitliğin iki tarafına aynı işlem uygulanır.",strategy="terimleri düzenle",strategy_id="strategy_isolate",steps=[Step(id="step_1",type="transformation",title="Sabit terimi çıkar",explanation="İki taraftan 7 çıkar.",expressions=[Expression(type="equation",latex="3x = 12")]),Step(id="step_2",type="result",title="Katsayıya böl",explanation="İki tarafı 3'e böl.",expressions=[Expression(type="equation",latex=answer)])],common_mistake="Yalnızca bir taraftan 7 çıkarma.",mistake_type="equality_balance",final_answer=answer,final_answer_expressions=[Expression(type="equation",latex=answer)],takeaway="Eşitlik dengedir.")
        return LessonProviderResult(LessonDraft(learning_objectives=["doğrusal denklem çözmek"],concept_id="concept_linear_equation",content=content),"mock","mock")

@pytest.mark.asyncio
async def test_pipeline_corrects_once_then_builds_verified_board():
    provider=CorrectingProvider();service=LessonService(provider,MathAIService(),BoardPlanner())
    result=await service.generate(plan().source_analysis)
    assert len(provider.calls)==2 and provider.calls[1]
    assert result.correction_attempted and result.verification.status=="verified"
    assert result.board.elements[-1].mark=="check"

@pytest.mark.asyncio
async def test_persistent_contradiction_is_not_returned():
    with pytest.raises(VerificationContradictionError):
        await LessonService(CorrectingProvider(True),MathAIService(),BoardPlanner()).generate(plan().source_analysis)
def test_generate_endpoint_returns_verified_board():
    from dataclasses import replace
    from fastapi.testclient import TestClient
    from apps.api.app.main import create_app
    app=create_app();app.state.container=replace(app.state.container,lesson_service=LessonService(CorrectingProvider(),MathAIService(),BoardPlanner()))
    with TestClient(app) as client: response=client.post('/api/v1/lessons/generate',json={'analysis':plan().source_analysis.model_dump()})
    assert response.status_code==200
    assert response.json()['data']['verification']['status']=='verified'
    assert response.json()['data']['board']['elements'][-1]['type']=='final_answer'
