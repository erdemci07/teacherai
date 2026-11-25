from typing import Literal
from ..education.mathematics import IntervalView
from pydantic import BaseModel,ConfigDict,Field
from apps.api.app.features.mathai.schemas import GraphData
class BoardElement(BaseModel):
    model_config=ConfigDict(extra="forbid")
    id:str
    type:Literal["title","teacher_note","equation","rule","arrow","box","check","cross","warning","tip","known_values","unknown_value","mini_example","graph","geometry_diagram","final_answer","number_line","geometry_facts"]
    text:str|None=None; latex:str|None=None; mark:Literal["none","check","cross","warning"]="none"
    source_step_id:str|None=None; graph:GraphData|None=None
    shape:Literal["triangle","rectangle","circle","line_segment"]|None=None
    # TA-008: yalnız doğrulanmış çözüm kümesinden (sayı doğrusu) ve modelin kullanılabilir olgularından (geometri).
    intervals:list[IntervalView]|None=None
    exclusions:list[str]|None=None
    facts:list[str]|None=None
    schematic:bool=False
class BoardPlan(BaseModel):
    schema_version:Literal["1.0.0"]="1.0.0"; board_id:str; lesson_plan_id:str
    title:str; elements:list[BoardElement]=Field(min_length=1)
