from datetime import datetime,timezone
from pydantic import BaseModel,Field
from apps.api.app.features.lessons.service import GeneratedLesson
class StudentProfile(BaseModel):
    student_id:str;display_name:str;exam_goal:str|None=None;email:str|None=None;created_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc))
class ProfileInput(BaseModel):display_name:str=Field(min_length=1,max_length=80);exam_goal:str|None=None
class LessonRecord(BaseModel):
    lesson_id:str;student_id:str;created_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc));subject:str;exam_context:str|None;topic:str;subtopic:str|None;difficulty:str;question_summary:str;final_answer:str;verification_status:str;lesson_data:dict
class SaveLessonRequest(BaseModel):result:GeneratedLesson
class DashboardSummary(BaseModel):questions_solved:int;recent_topics:list[str];practice_attempts:int;practice_correct:int;frequent_mistakes:dict[str,int];last_activity:datetime|None
