from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..education.mathematics import GraphSegment, MathematicsReport
from ..education.reasoning import TargetResolution


class VerificationCheck(BaseModel):
    id:str; kind:Literal["equation","transformation","final_answer","expression","function","geometry","domain","answer_target"]
    status:Literal["passed","failed","unsupported"]
    statement:str; detail:str|None=None
    # TA-004: belirlenimci neden kodu ve ardışık ifadelerden sınıflandırılan işlem (yoksa None).
    reason:str|None=None
    operation:str|None=None
class GraphData(BaseModel):
    expression:str; variable:str="x"; roots:list[float]=Field(default_factory=list); y_intercept:float|None=None
    critical_points:list[float]=Field(default_factory=list); sample_points:list[tuple[float,float]]=Field(default_factory=list)
    # TA-008: tanımsız noktalar; çizimde grafik bu noktalarda birleştirilmez. Örnek noktalar kanıt değildir.
    discontinuities:list[float]=Field(default_factory=list)
    # TA-008B: doğrulanmış kesintisiz parçalar (açık/kapalı uçlarıyla), kaldırılabilir süreksizlik (x, limit) ve düşey
    # asimptotlar. Örnek noktalar yalnız bu parçaların içinden alınır; çizim parçaları birleştirmez.
    segments:list[GraphSegment]=Field(default_factory=list)
    holes:list[tuple[float,float]]=Field(default_factory=list)
    asymptotes:list[float]=Field(default_factory=list)
class ChoiceMatch(BaseModel):
    """Seçenek uzlaştırmasının açık kaydı. En yakın değer seçilmez; eşleşme yalnızca kesin eşdeğerliktir."""
    model_config=ConfigDict(extra="forbid")
    status:Literal["matched","multiple_equivalent","no_match","choice_dependent","unsupported"]
    value_origin:Literal["independent","provider","none"]
    value:str|None=None
    provider_label:str|None=None
    matched_labels:list[str]=Field(default_factory=list)
class VerificationResult(BaseModel):
    model_config=ConfigDict(extra="forbid")
    status:Literal["verified","partially_verified","unsupported","failed"]
    confidence:float=Field(ge=0,le=1); checks:list[VerificationCheck]
    final_answer_verified:bool; contradiction:bool=False; warnings:list[str]=Field(default_factory=list)
    engine:str="sympy"; engine_version:str; graph:GraphData|None=None; processing_time_ms:int=Field(ge=0)
    choice_match:ChoiceMatch|None=None
    # TA-004: istenen hedef, verilen model, ara değer, öneri ve bağımsız değer ayrı kaydı. Eski kayıtlarda yoktur.
    target:TargetResolution|None=None
    # TA-008: matematik uzmanlığı raporu (aynı yalıtılmış işçide). Durumu yalnız zayıflatabilir.
    mathematics:MathematicsReport|None=None
