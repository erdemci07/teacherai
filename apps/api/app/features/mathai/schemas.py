from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
class VerificationCheck(BaseModel):
    id:str; kind:Literal["equation","transformation","final_answer","expression","function","geometry"]
    status:Literal["passed","failed","unsupported"]
    statement:str; detail:str|None=None
class GraphData(BaseModel):
    expression:str; variable:str="x"; roots:list[float]=Field(default_factory=list); y_intercept:float|None=None
    critical_points:list[float]=Field(default_factory=list); sample_points:list[tuple[float,float]]=Field(default_factory=list)
class VerificationResult(BaseModel):
    model_config=ConfigDict(extra="forbid")
    status:Literal["verified","partially_verified","unsupported","failed"]
    confidence:float=Field(ge=0,le=1); checks:list[VerificationCheck]
    final_answer_verified:bool; contradiction:bool=False; warnings:list[str]=Field(default_factory=list)
    engine:str="sympy"; engine_version:str; graph:GraphData|None=None; processing_time_ms:int=Field(ge=0)
