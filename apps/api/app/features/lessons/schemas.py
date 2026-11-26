from typing import Annotated, Literal

from apps.api.app.features.vision.schemas import VisionAnalysis
from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.api.app.features.education.mathematics import MathematicalModel
from apps.api.app.features.education.science import ScientificProblemModel


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
    # TA-008: sağlayıcının önerdiği yapılandırılmış model (sözel problem/geometri). Sunucu bağımsız denetler.
    mathematical_model: MathematicalModel|None=None
    # TA-009: fizik dersinde sağlayıcının önerdiği fiziksel model (kanonik ScientificProblemModel). Yetkili değildir.
    physics_model: ScientificProblemModel|None=None
    @model_validator(mode="after")
    def sequential_steps(self):
        if [x.id for x in self.steps] != [f"step_{i}" for i in range(1,len(self.steps)+1)]: raise ValueError("step IDs must be sequential")
        return self
class LessonDraft(BaseModel):
    model_config=ConfigDict(extra="forbid")
    learning_objectives: list[str]=Field(min_length=1)
    concept_id: str=Field(pattern=r"^concept_[a-z0-9_]+$")
    content: LessonContent

class ExpressionResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    type: Literal["equation","expression","inequality","system","function","geometry"]
    latex: str
class StepResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    id: str
    type: Literal["explanation","equation","transformation","case","warning","result","diagram_reference","graph_reference"]
    title: str
    explanation: str
    expressions: list[ExpressionResponse]
    visual_reference: str|None
class WordQuantityResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    symbol: str
    name_tr: str
    unit: str|None
    value: str|None
    discrete: bool
    origin: Literal["stated","derived","assumed","visual_uncertain"]
    evidence: str|None
class WordConstraintResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    symbol: str
    kind: Literal["positive","nonnegative","integer","natural"]
class WordProblemResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    problem_type: Literal["age","motion","work_rate","mixture","percent","profit_loss","ratio","linear_system","data_table","scheduling","other"]
    quantities: list[WordQuantityResponse]
    relations: list[str]
    constraints: list[WordConstraintResponse]
    objective: str
class GeometryFactResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    id: str
    kind: Literal["segment_length","angle_measure","equal_segments","equal_angles","parallel","perpendicular","right_angle","collinear","midpoint","point_on_segment","triangle","polygon","circle","point_on_circle","tangent","similar","congruent","coordinate","area"]
    points: list[str]
    other: list[str]
    value: str|None
    origin: Literal["stated","marked","derived","visual_uncertain","construction"]
    evidence: str|None
    premises: list[str]
    rule: str|None
class ConstructionResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    id: str
    kind: Literal["altitude","segment","extension","parallel_line","midpoint","radius","perpendicular","angle_bisector"]
    references: list[str]
    new_points: list[str]
    establishes: list[str]
    requires_proof: list[str]
    purpose_tr: str
class GeometryTargetResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    kind: Literal["length","angle","area","perimeter","ratio","coordinate"]
    points: list[str]
class GeometryResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    points: list[str]
    facts: list[GeometryFactResponse]
    constructions: list[ConstructionResponse]
    target: GeometryTargetResponse|None
    schematic: bool
class MathematicalModelResponse(BaseModel):
    """TA-008: kısıtsız düz tipler (Anthropic izdüşümü gerekmez); sunucuda özgün sözleşmeyle doğrulanır."""
    model_config=ConfigDict(extra="forbid")
    kind: Literal["word_problem","geometry"]
    word_problem: WordProblemResponse|None
    geometry: GeometryResponse|None
class LessonContentResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    question_understanding: str
    known_values: list[str]
    unknown: str|None
    prerequisite_reminder: str|None
    key_rule: str|None
    strategy: str
    strategy_id: str
    steps: list[StepResponse]
    common_mistake: str|None
    mistake_type: str|None
    shortcut: str|None
    mini_example: list[ExpressionResponse]
    teacher_tip: str|None
    final_answer: str
    final_answer_expressions: list[ExpressionResponse]
    takeaway: str
    mathematical_model: MathematicalModelResponse|None=None
class LessonDraftResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    learning_objectives: list[str]
    concept_id: str
    content: LessonContentResponse
# --------------------------------------------------------------------------- TA-009 fizik yanıt şeması
# Düz tipler, sınır yok (Anthropic izdüşümü gerekmez); sunucuda kanonik sözleşmeyle doğrulanır, geçersizse atılır.
PhysicsProvenance=Literal["source_text","visual_reading","problem_convention","standard_constant","modeling_assumption",
                          "provider_proposed"]
class PhysicsQuantityResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    id: str
    symbol: str|None
    kind: str|None
    magnitude: str|None  # bilinmeyende null; "8", "0,5", "3/2"
    unit: str|None
    original: str|None  # sorudaki yazılış (birebir alıntı)
    provenance: PhysicsProvenance
    entity: str|None
    state: str|None
    representation: Literal["magnitude","component","unspecified"]
class PhysicsBodyResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    entity: str
    mass: str|None
    surface: str|None
class PhysicsSurfaceResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    id: str
    kind: Literal["horizontal","incline","vertical"]
    angle_deg: str|None
    friction: Literal["none","present","unknown"]
    mu_static: str|None
    mu_kinetic: str|None
    provenance: PhysicsProvenance
class PhysicsForceResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    id: str
    kind: Literal["gravity","normal","tension","static_friction","kinetic_friction","applied","spring","electric","magnetic",
                  "buoyancy","drag","other"]
    on: str
    by: str|None
    magnitude: str|None
    direction: Literal["+x","-x","+y","-y","up_incline","down_incline","angle"]
    angle_deg: str|None
    provenance: PhysicsProvenance
class PhysicsStringResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    id: str
    bodies: list[str]
    over_pulley: bool
    provenance: PhysicsProvenance
class PhysicsPhaseResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    id: str
    entity: str
    axis: Literal["horizontal","vertical","incline"]
    acceleration_kind: Literal["constant","zero","varying","unknown"]
    initial_velocity: str|None
    final_velocity: str|None
    displacement: str|None
    distance: str|None
    duration: str|None
    acceleration: str|None
    free_fall: bool
class PhysicsCollisionResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    id: str
    bodies: list[str]
    kind: Literal["elastic","perfectly_inelastic","inelastic","explosion","unknown"]
    velocities_before: list[str|None]
    velocities_after: list[str|None]
    external_impulse: Literal["none_stated","negligible_assumed","present","unknown"]
class PhysicsElementResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    id: str
    kind: Literal["resistor","bulb","battery","switch","ammeter","voltmeter","wire"]
    nodes: list[str]
    value: str|None
    internal_resistance: str|None
    positive_node: str|None
    closed: bool|None
    connection_certain: bool
    provenance: PhysicsProvenance
class PhysicsCircuitResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    nodes: list[str]
    elements: list[PhysicsElementResponse]
class PhysicsLawResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    law: str
    system: list[str]
class PhysicsTargetResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    quantity: str|None
    kind: str
    entity: str|None
    state: str|None
    representation: Literal["magnitude","component","unspecified"]
    unit: str|None
    element: str|None
    between: list[str]
class PhysicsModelResponse(BaseModel):
    model_config=ConfigDict(extra="forbid")
    domain: Literal["kinematics","dynamics","energy","momentum","dc_circuit","other"]
    sign_convention: str|None
    quantities: list[PhysicsQuantityResponse]
    bodies: list[PhysicsBodyResponse]
    surfaces: list[PhysicsSurfaceResponse]
    forces: list[PhysicsForceResponse]
    strings: list[PhysicsStringResponse]
    phases: list[PhysicsPhaseResponse]
    collisions: list[PhysicsCollisionResponse]
    circuit: PhysicsCircuitResponse|None
    laws: list[PhysicsLawResponse]
    equations: list[str]
    target: PhysicsTargetResponse|None
class PhysicsLessonContentResponse(LessonContentResponse):
    physics_model: PhysicsModelResponse|None
class PhysicsLessonDraftResponse(BaseModel):
    """Yalnız fizik dersi isteğinde gönderilen şema; matematik isteğinin şeması ve maliyeti değişmez."""
    model_config=ConfigDict(extra="forbid")
    learning_objectives: list[str]
    concept_id: str
    content: PhysicsLessonContentResponse
class LessonPlan(BaseModel):
    schema_: Annotated[dict[str,str], Field(alias="schema")]=Field(default_factory=lambda:{"name":"teacherai.lesson_plan","version":"1.0.0"})
    lesson_plan_id: str; lesson_plan_version: str="1"; status: str="verification_pending"
    source_analysis: VisionAnalysis
    learning_objectives: list[str]; concept_id: str; content: LessonContent
    provider: str; model: str; lesson_generation_ms: int
    model_config=ConfigDict(populate_by_name=True)
class GenerateLessonRequest(BaseModel):
    analysis: VisionAnalysis | None = None
    analysis_id: str | None = Field(None, min_length=1, max_length=128)
    # TA-003: istemcinin gördüğü soru revizyonu. Verilirse sunucudaki güncel revizyonla eşleşmelidir.
    expected_revision: int | None = Field(None, ge=1, le=64)
    # TA-005: öğrencinin beyan ettiği sınıf (isteğe bağlı). Yoksa profildeki değer; o da yoksa yöntem not_checked.
    grade: int | None = Field(None, ge=5, le=12)
    # TA-007: açık okul izleği beyanı (ör. fen lisesi). Yoksa profildeki değer; o da yoksa genel program.
    school_track: Literal["general", "science_high_school", "basic_level"] | None = None
    # TA-007: öğrenci düzey üstü yöntemi açıkça isterse yasak işlem "failed" değil "partially_checked" olur.
    advanced_method_requested: bool = False
