from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field, model_validator
from apps.api.app.features.vision.schemas import VisionAnalysis

class Expression(BaseModel):
    model_config=ConfigDict(extra="forbid")
    type: Literal["equation","expression","inequality","system","function","geometry"]
    latex: str = Field(min_length=1)
class Step(BaseModel):
    model_config=ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^step_[1-9][0-9]*$")
    type: Literal["explanation","equation","transformation","case","warning","result","diagram_reference","graph_reference"]
    title: str; explanation: str = Field(min_length=1)
    expressions: list[Expression] = Field(default_factory=list)
    visual_reference: str|None=None
class LessonContent(BaseModel):
    model_config=ConfigDict(extra="forbid")
    question_understanding: str=Field(min_length=1)
    known_values: list[str]=Field(default_factory=list)
    unknown: str|None=None
    prerequisite_reminder: str|None=None
    key_rule: str|None=None
    strategy: str=Field(min_length=1)
    strategy_id: str=Field(pattern=r"^strategy_[a-z0-9_]+$")
    steps: list[Step]=Field(min_length=1)
    common_mistake: str|None=None
    mistake_type: str|None=None
    shortcut: str|None=None
    mini_example: list[Expression]=Field(default_factory=list)
    teacher_tip: str|None=None
    final_answer: str=Field(min_length=1)
    final_answer_expressions: list[Expression]=Field(min_length=1)
    takeaway: str=Field(min_length=1)
    @model_validator(mode="after")
    def sequential_steps(self):
        if [x.id for x in self.steps] != [f"step_{i}" for i in range(1,len(self.steps)+1)]: raise ValueError("step IDs must be sequential")
        return self
class LessonDraft(BaseModel):
    model_config=ConfigDict(extra="forbid")
    learning_objectives: list[str]=Field(min_length=1)
    concept_id: str=Field(pattern=r"^concept_[a-z0-9_]+$")
    content: LessonContent
class LessonPlan(BaseModel):
    schema_: Annotated[dict[str,str], Field(alias="schema")]=Field(default_factory=lambda:{"name":"teacherai.lesson_plan","version":"1.0.0"})
    lesson_plan_id: str; lesson_plan_version: str="1"; status: str="verification_pending"
    source_analysis: VisionAnalysis
    learning_objectives: list[str]; concept_id: str; content: LessonContent
    provider: str; model: str; lesson_generation_ms: int
    model_config=ConfigDict(populate_by_name=True)
class GenerateLessonRequest(BaseModel):
    analysis: VisionAnalysis
