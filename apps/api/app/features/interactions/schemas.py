from datetime import datetime,timezone
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from apps.api.app.features.board.schemas import BoardPlan
from apps.api.app.features.lessons.schemas import Expression,LessonPlan
Action=Literal["understood","simplify","alternative","hint","similar_example","practice"]
EventName=Literal["solution_completed","understood_clicked","simpler_explanation_requested","alternative_method_requested","hint_requested","similar_example_requested","practice_started","practice_answered","practice_correct","practice_incorrect"]
MistakeType=Literal["sign_error","arithmetic_error","operation_order_error","missing_case","formula_error","concept_error","graph_interpretation_error","unknown"]
class InteractionEvent(BaseModel):
    event_id:str;event:EventName;occurred_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc));student_id:str|None=None
    lesson_id:str;topic:str;subtopic:str|None;skill:str;difficulty:str;action:str
    mistake_type:MistakeType|None=None;correctness:bool|None=None;attempt_count:int|None=None;explanation_mode:str|None=None
class InteractionRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    action:Action;lesson:LessonPlan;hint_level:int=Field(default=1,ge=1,le=3)
class AdaptiveDraft(BaseModel):
    model_config=ConfigDict(extra="forbid")
    title:str;text:str
    steps:list[str]=Field(default_factory=list)
    expressions:list[Expression]=Field(default_factory=list)
    question_expression:str|None=None
    expected_answer_expression:str|None=None
    answer_variable:str|None=None
    feedback_hint:str|None=None
class PracticePublic(BaseModel):
    practice_question_id:str;question:str;question_expression:str;topic:str;subtopic:str|None;skill_id:str;difficulty:str
class InteractionResponse(BaseModel):
    interaction_id:str;action:Action;message:str;board:BoardPlan|None=None;practice:PracticePublic|None=None;event:InteractionEvent
    next_hint_level:int|None=None;verification_status:str|None=None
class PracticeAnswerRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    answer:str=Field(min_length=1,max_length=200)
class PracticeFeedback(BaseModel):
    correct:bool;message:str;attempt_number:int;mistake_type:MistakeType;can_show_solution:bool;event:InteractionEvent
