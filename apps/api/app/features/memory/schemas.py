from datetime import datetime,timezone
from pydantic import BaseModel,Field
class EvidenceSignal(BaseModel):
    signal:str;count:int;confidence:float
class PracticeStatistics(BaseModel):
    attempts:int=0;correct:int=0;first_attempt_correct:int=0
class StudentMemory(BaseModel):
    student_id:str;exam_goal:str|None=None;topic_counts:dict[str,int]=Field(default_factory=dict);mistake_counts:dict[str,int]=Field(default_factory=dict);hint_requests:int=0;simplification_requests:int=0;practice:PracticeStatistics=Field(default_factory=PracticeStatistics);recent_topics:list[str]=Field(default_factory=list);last_activity:datetime=Field(default_factory=lambda:datetime.now(timezone.utc))
class TeachingContext(BaseModel):
    exam_goal:str|None;topic_experience:int;recurring_mistakes:list[EvidenceSignal];support_need:str;preferred_explanation_depth:str;recent_topics:list[str]
