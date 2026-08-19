from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.features.interactions.schemas import InteractionEvent
from uuid import uuid4
from apps.api.app.features.memory.engine import MemoryEngine
from apps.api.app.features.memory.schemas import StudentMemory,TeachingContext
from .repository import StudentRepository
from .schemas import *
class StudentService:
    def __init__(self,repository:StudentRepository,memory:MemoryEngine):self.repository=repository;self.memory=memory
    def profile(self,user,body):
        value=StudentProfile(student_id=user.uid,display_name=body.display_name,exam_goal=body.exam_goal,email=user.email);self.repository.save_profile(value);return value
    def save_lesson(self,user,result):
        lesson=result.lesson;source=lesson.source_analysis
        record=LessonRecord(lesson_id=lesson.lesson_plan_id,student_id=user.uid,subject=source.subject,exam_context=source.exam_context,topic=source.topic,subtopic=source.subtopic,difficulty=source.difficulty,question_summary=source.question_text[:500],final_answer=lesson.content.final_answer,verification_status=result.verification.status,lesson_data={"lesson":lesson.model_dump(mode="json",by_alias=True),"verification":result.verification.model_dump(mode="json"),"board":result.board.model_dump(mode="json")})
        self.repository.save_lesson(record)
        completed=InteractionEvent(event_id=f"event_{uuid4().hex}",event="solution_completed",lesson_id=record.lesson_id,topic=record.topic,subtopic=record.subtopic,skill=lesson.concept_id,difficulty=record.difficulty,action="solution_completed")
        self.record_event(user,completed)
        return record
    def record_event(self,user,event,practice_id=None):
        self.repository.save_event(user.uid,event)
        if practice_id:self.repository.save_attempt(user.uid,event,practice_id)
        memory=self.repository.get_memory(user.uid);profile=self.repository.get_profile(user.uid);memory.exam_goal=profile.exam_goal if profile else memory.exam_goal
        self.repository.save_memory(self.memory.apply(memory,event))
    def context(self,user,topic):return self.memory.context(self.repository.get_memory(user.uid),topic)
    def history(self,user):return self.repository.lessons(user.uid)
    def memory_summary(self,user):return self.repository.get_memory(user.uid)
    def reset(self,user):self.repository.reset_memory(user.uid)
    def dashboard(self,user):
        m=self.repository.get_memory(user.uid);return DashboardSummary(questions_solved=len(self.repository.lessons(user.uid)),recent_topics=m.recent_topics,practice_attempts=m.practice.attempts,practice_correct=m.practice.correct,frequent_mistakes=m.mistake_counts,last_activity=m.last_activity)
