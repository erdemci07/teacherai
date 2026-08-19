from dataclasses import replace
from datetime import datetime,timezone
from fastapi.testclient import TestClient
from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.features.interactions.schemas import InteractionEvent
from apps.api.app.features.memory.engine import MemoryEngine
from apps.api.app.features.memory.schemas import StudentMemory
from apps.api.app.features.students.repository import InMemoryStudentRepository
from apps.api.app.features.students.service import StudentService
from apps.api.app.main import create_app
from apps.api.tests.test_lesson_pipeline import CorrectingProvider
from apps.api.app.features.lessons.service import LessonService
from apps.api.app.features.mathai.service import MathAIService
from apps.api.app.features.board.planner import BoardPlanner
from apps.api.tests.test_mathai import plan
import asyncio
class Verifier:
    def verify(self,token):
        if token=="student-a":return AuthenticatedUser(uid="uid-a",email="a@example.com")
        if token=="student-b":return AuthenticatedUser(uid="uid-b",email="b@example.com")
        raise ValueError

def event(name="practice_incorrect",mistake="sign_error",correct=False,attempt=1):return InteractionEvent(event_id=f"event-{name}-{attempt}-{mistake}",event=name,lesson_id="lesson_1",topic="Denklem",subtopic="Doğrusal",skill="concept_linear",difficulty="easy",action=name,mistake_type=mistake,correctness=correct,attempt_count=attempt,explanation_mode="practice")

def test_memory_aggregation_requires_repeated_evidence():
    engine=MemoryEngine();memory=StudentMemory(student_id="u")
    engine.apply(memory,event(attempt=1));assert not engine.context(memory,"Denklem").recurring_mistakes
    engine.apply(memory,event(attempt=2));context=engine.context(memory,"Denklem")
    assert context.recurring_mistakes[0].signal=="sign_error" and context.recurring_mistakes[0].count==2

def test_simplification_and_hint_support_signals():
    engine=MemoryEngine();memory=StudentMemory(student_id="u")
    for i in range(3):engine.apply(memory,event("simpler_explanation_requested",None,None,i+1));engine.apply(memory,event("hint_requested",None,None,i+1))
    context=engine.context(memory,"Denklem");assert context.preferred_explanation_depth=="foundation" and context.support_need=="high"

def test_repository_persists_events_attempts_and_reset():
    repo=InMemoryStudentRepository();service=StudentService(repo,MemoryEngine());user=AuthenticatedUser(uid="u")
    service.record_event(user,event(),"practice-1");assert repo.events and repo.attempts and service.memory_summary(user).mistake_counts["sign_error"]==1
    service.reset(user);assert not service.memory_summary(user).mistake_counts

def test_protected_history_and_ownership_boundary():
    app=create_app();repo=InMemoryStudentRepository();students=StudentService(repo,MemoryEngine());app.state.container=replace(app.state.container,token_verifier=Verifier(),student_service=students)
    with TestClient(app) as client:
        assert client.get('/api/v1/students/me/history').status_code==401
        result=asyncio.run(LessonService(CorrectingProvider(),MathAIService(),BoardPlanner()).generate(plan().source_analysis))
        saved=client.post('/api/v1/students/me/lessons',headers={'Authorization':'Bearer student-a'},json={'result':result.model_dump(mode='json',by_alias=True)})
        assert saved.status_code==200
        assert len(client.get('/api/v1/students/me/history',headers={'Authorization':'Bearer student-a'}).json()['data'])==1
        assert client.get('/api/v1/students/me/history',headers={'Authorization':'Bearer student-b'}).json()['data']==[]

def test_token_verifier_abstraction_rejects_bad_token():
    app=create_app();app.state.container=replace(app.state.container,token_verifier=Verifier())
    with TestClient(app) as client:assert client.get('/api/v1/students/me/memory',headers={'Authorization':'Bearer invalid'}).status_code==401
