import pytest
from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.lessons.exceptions import InvalidQuestionAnalysisError, LessonProviderUnavailableError, VerificationContradictionError
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

class OptionMismatchProvider:
    model="mock"
    def __init__(self): self.calls=[]
    async def generate_lesson_plan(self,analysis,correction_feedback=None,teaching_context=None):
        self.calls.append(correction_feedback)
        content=LessonContent(question_understanding="x'i bul",unknown="x",strategy="yalnız bırak",strategy_id="strategy_isolate",steps=[Step(id="step_1",type="result",title="Sonuç",explanation="x = 4 bulunur.",expressions=[Expression(type="equation",latex="x = 4")])],final_answer="B) 2",final_answer_expressions=[Expression(type="equation",latex="x = 4")],takeaway="Denklemi dengeyle çöz.")
        return LessonProviderResult(LessonDraft(learning_objectives=["denklem çözmek"],concept_id="concept_linear_equation",content=content),"mock","mock")

class UnavailableProvider:
    model="mock"
    async def generate_lesson_plan(self,analysis,correction_feedback=None,teaching_context=None):
        raise LessonProviderUnavailableError

@pytest.mark.asyncio
async def test_pipeline_corrects_once_then_builds_verified_board():
    provider=CorrectingProvider();service=LessonService(provider,MathAIService(),BoardPlanner())
    result=await service.generate(plan().source_analysis)
    assert len(provider.calls)==2 and provider.calls[1]
    assert result.correction_attempted and result.verification.status=="verified"
    assert result.board.elements[-1].mark=="check"

@pytest.mark.asyncio
async def test_persistent_contradiction_is_not_returned():
    provider=CorrectingProvider(True)
    with pytest.raises(VerificationContradictionError):
        await LessonService(provider,MathAIService(),BoardPlanner()).generate(plan().source_analysis)
    assert len(provider.calls)==2


@pytest.mark.asyncio
async def test_invalid_image_analysis_stops_before_lesson_generation():
    provider = CorrectingProvider()
    analysis = plan().source_analysis.model_copy(
        update={
            "image_status": "not_math_question",
            "is_valid_question": False,
            "rejection_reason": "Matematik sorusu bulunamadı.",
        }
    )

    with pytest.raises(InvalidQuestionAnalysisError):
        await LessonService(provider, MathAIService(), BoardPlanner()).generate(analysis)

    assert provider.calls == []


@pytest.mark.asyncio
async def test_safe_answer_choice_mismatch_is_reconciled_without_second_ai_call():
    provider=OptionMismatchProvider();service=LessonService(provider,MathAIService(),BoardPlanner())
    analysis=plan().source_analysis.model_copy(update={"answer_choices":["A) 1","B) 2","C) 4","D) 5"]})

    result=await service.generate(analysis)

    assert provider.calls==[None]
    assert result.correction_attempted is False
    assert result.lesson.content.final_answer=="C) 4"
    assert result.verification.status=="verified"


@pytest.mark.asyncio
async def test_unresolved_contradiction_triggers_one_correction_and_rechecks():
    provider=CorrectingProvider();service=LessonService(provider,MathAIService(),BoardPlanner())

    result=await service.generate(plan().source_analysis)

    assert len(provider.calls)==2
    assert provider.calls[1] and "MathAI çelişki buldu" in provider.calls[1]
    assert result.correction_attempted is True
    assert result.verification.status=="verified"


@pytest.mark.asyncio
async def test_lesson_provider_network_errors_remain_provider_errors():
    with pytest.raises(LessonProviderUnavailableError):
        await LessonService(UnavailableProvider(),MathAIService(),BoardPlanner()).generate(plan().source_analysis)
def test_generate_endpoint_returns_verified_board():
    from dataclasses import replace
    from fastapi.testclient import TestClient
    from apps.api.app.main import create_app
    app=create_app();app.state.container=replace(app.state.container,lesson_service=LessonService(CorrectingProvider(),MathAIService(),BoardPlanner()))
    with TestClient(app) as client: response=client.post('/api/v1/lessons/generate',json={'analysis':plan().source_analysis.model_dump()})
    assert response.status_code==200
    assert response.json()['data']['verification']['status']=='verified'
    assert response.json()['data']['board']['elements'][-1]['type']=='final_answer'
