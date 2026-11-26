"""Çok disiplinli bilimsel problem modeli ve çok kipli kanıt sözleşmeleri (TA-004).

Bu bir anlam temsilidir, ayrı bir AI hizmeti değildir. Matematik, geometri, fizik, kimya, biyoloji ve
fen aynı tipleri kullanır. Nitel akıl yürütme (biyoloji açıklaması, nitel fizik) denklem gerektirmez.

Kökenler ayrıdır: kaynak metin, görselden okunan bilgi, öğrencinin onayladığı bilgi, bilimsel arka plan,
modelleme varsayımı, çıkarım ve türetilmiş sonuç. Çıkarım hiçbir zaman sessizce kaynak gözlemine
yükseltilmez; çıkarım ve türetim en az bir kanıta dayanır. Sağlayıcı çıktısı bir doğrulama durumu
belirleyemez.
"""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .base import Contract, Identifier, Label, Subject, Text
from .domain import Reference
from .reasoning import AnswerTarget, EvidenceRef
from .source import ElementRef, Fragment, SourceRegion

Provenance = Literal[
    "source_text", "visual_reading", "student_confirmed", "background_knowledge", "modeling_assumption",
    "inferred", "derived",
    # TA-009 §10: sorunun verdiği uzlaşım (g = 10 m/s²), standart sabit (sürümüyle) ve denetlenmemiş sağlayıcı önerisi.
    "problem_convention", "standard_constant", "provider_proposed",
]
DIRECT_PROVENANCE = frozenset({"source_text", "visual_reading", "student_confirmed"})
Roman = Annotated[str, Field(pattern=r"^[IVX]{1,4}$")]
ShortText = Annotated[str, Field(min_length=1, max_length=1000)]
NumberText = Annotated[str, Field(pattern=r"^-?[0-9]{1,15}(/[1-9][0-9]{0,14})?$")]


class Observation(Contract):
    id: Identifier
    statement: ShortText
    provenance: Provenance
    evidence: list[EvidenceRef] = Field(default_factory=list, max_length=8)
    figure: Identifier | None = None
    source: ElementRef | None = None

    @model_validator(mode="after")
    def grounded(self):
        if self.provenance in {"inferred", "derived"} and not self.evidence:
            raise ValueError("Çıkarım ve türetim kanıt göstermeli.")
        return self


class UnitSpec(Contract):
    """Özgün yazım korunur. Kanonik sembol ve boyut yalnızca yerel ayrıştırıcıdan gelir."""

    original: Label
    status: Literal["parsed", "ambiguous", "unsupported"]
    canonical: Label | None = None
    # SI taban boyut üsleri: uzunluk, kütle, zaman, akım, sıcaklık, madde miktarı, ışık şiddeti.
    dimension: list[Annotated[int, Field(ge=-12, le=12)]] = Field(default_factory=list, max_length=7)
    scale: NumberText | None = None
    affine: bool = False
    normalization: Literal["none", "alias", "defined_conversion"] = "none"

    @model_validator(mode="after")
    def parsed_has_dimension(self):
        if (self.status == "parsed") != (self.canonical is not None and len(self.dimension) == 7 and self.scale is not None):
            raise ValueError("Ayrıştırılmış birim kanonik sembol, boyut ve ölçek taşır.")
        return self


Direction = Literal["none", "positive", "negative", "left", "right", "up", "down", "into", "out_of", "unclear"]


class QuantityValue(Contract):
    id: Identifier
    symbol: Label | None = None
    name: Label | None = None
    magnitude: NumberText | None = None
    original: Label | None = None
    unit: UnitSpec | None = None
    significant_digits: int | None = Field(default=None, ge=1, le=15)
    direction: Direction = "none"
    provenance: Provenance
    evidence: list[EvidenceRef] = Field(default_factory=list, max_length=8)
    entity: Identifier | None = None
    # TA-009: nicelik türü (sürat/hız, kütle/ağırlık…; ``reasoning.quantities.KINDS``), durum (ilk, son, t = 2 s),
    # gösterim (büyüklük/işaretli bileşen), standart sabitin kaynağı, türetme adımı, görsel okumanın güveni.
    kind: Identifier | None = None
    state: Label | None = None
    representation: Literal["magnitude", "component", "unspecified"] = "unspecified"
    constant_source: Label | None = None
    derivation: Identifier | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


EntityKind = Literal[
    "object", "body", "vehicle", "planet", "field", "charge", "circuit_element", "lens", "particle", "species",
    "substance", "solution", "apparatus", "cell", "organelle", "organism", "population", "structure",
    "process_stage", "gene", "point", "segment", "angle", "region", "axis", "other",
]


class Entity(Contract):
    id: Identifier
    kind: EntityKind
    label: Label | None = None
    figure: Identifier | None = None
    provenance: Provenance


RelationType = Literal[
    "connected_to", "contains", "part_of", "points_to", "measured_at", "labeled_as", "precedes", "increases",
    "decreases", "adjacent_to", "acts_on",
]


class Relation(Contract):
    """Gözlenen ilişki ile onun bilimsel yorumu ayrıdır (aynı ok kuvvet, taşınma veya neden olabilir)."""

    id: Identifier
    type: RelationType
    subject: Identifier
    object: Identifier
    figure: Identifier | None = None
    provenance: Provenance
    direction_clear: bool = True
    interpretation: Label | None = None
    interpretation_provenance: Provenance | None = None

    @model_validator(mode="after")
    def interpretation_origin(self):
        if (self.interpretation is None) != (self.interpretation_provenance is None):
            raise ValueError("Yorum kökeniyle birlikte verilir.")
        if self.interpretation_provenance in DIRECT_PROVENANCE - {"source_text", "student_confirmed"}:
            raise ValueError("Görsel gözlem bir yorumun kökeni olamaz.")
        return self


FigureKind = Literal[
    "geometry_figure", "force_diagram", "circuit", "optics", "planetary_system", "motion_diagram",
    "reaction_diagram", "molecular_structure", "particle_model", "apparatus", "cell_diagram",
    "biological_system", "process_diagram", "experimental_setup", "graph", "table", "other",
]


class Figure(Contract):
    id: Identifier
    kind: FigureKind
    panel_label: Label | None = None
    region: SourceRegion | None = None
    scale: Label | None = None
    legend: list[Label] = Field(default_factory=list, max_length=12)


class Axis(Contract):
    name: Label
    unit: UnitSpec | None = None
    # Ölçek ve başlangıç yalnızca açıkça verilmişse bilinir; sıfırdan başladığı varsayılmaz.
    scale: Literal["explicit_linear", "explicit_nonlinear", "unknown"]
    origin: Literal["explicit", "unknown"] = "unknown"


class GraphSeries(Contract):
    id: Identifier
    figure: Identifier
    x: Axis
    y: Axis
    # Yalnızca basılı/açık sayısal değerler; piksellerden değer uydurulmaz.
    points: list[Annotated[list[NumberText], Field(min_length=2, max_length=2)]] = Field(default_factory=list, max_length=64)
    points_origin: Literal["printed_values", "none"] = "none"

    @model_validator(mode="after")
    def explicit(self):
        if self.points and self.points_origin != "printed_values":
            raise ValueError("Grafik noktaları yalnızca açık değerlerden gelir.")
        return self


class DataTable(Contract):
    id: Identifier
    figure: Identifier | None = None
    headers: list[Label] = Field(min_length=1, max_length=12)
    units: list[UnitSpec | None] = Field(default_factory=list, max_length=12)
    rows: list[Annotated[list[Label | None], Field(min_length=1, max_length=12)]] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def rectangular(self):
        if any(len(row) != len(self.headers) for row in self.rows):
            raise ValueError("Tablo satırı başlık sayısıyla uyuşmuyor.")
        if self.units and len(self.units) != len(self.headers):
            raise ValueError("Birim listesi sütun sayısıyla uyuşmalı.")
        return self


class Variable(Contract):
    id: Identifier
    name: Label
    unit: UnitSpec | None = None


class Condition(Contract):
    variable: Identifier
    value: Label


class ExperimentGroup(Contract):
    id: Identifier
    conditions: list[Condition] = Field(min_length=1, max_length=12)


class Measurement(Contract):
    group: Identifier
    variable: Identifier
    value: NumberText
    unit: UnitSpec | None = None


Trend = Literal["increases", "decreases", "no_change", "differs", "equal"]


class Claim(Contract):
    id: Identifier
    text: ShortText
    x: Identifier | None = None
    y: Identifier
    relation: Trend
    causal: bool = False
    groups: list[Identifier] = Field(default_factory=list, max_length=12)
    provenance: Provenance


class ExperimentalModel(Contract):
    objective: ShortText | None = None
    hypothesis: ShortText | None = None
    variables: list[Variable] = Field(min_length=1, max_length=16)
    independent: list[Identifier] = Field(default_factory=list, max_length=4)
    dependent: list[Identifier] = Field(default_factory=list, max_length=4)
    controlled: list[Identifier] = Field(default_factory=list, max_length=12)
    groups: list[ExperimentGroup] = Field(default_factory=list, max_length=12)
    measurements: list[Measurement] = Field(default_factory=list, max_length=128)
    claims: list[Claim] = Field(default_factory=list, max_length=12)
    limitations: list[ShortText] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def references(self):
        names = {item.id for item in self.variables}
        groups = {item.id for item in self.groups}
        used = set(self.independent) | set(self.dependent) | set(self.controlled)
        used |= {c.variable for g in self.groups for c in g.conditions} | {m.variable for m in self.measurements}
        used |= {v for claim in self.claims for v in (claim.x, claim.y) if v}
        if not used <= names:
            raise ValueError("Deney değişkeni tanımlı değil.")
        if not ({m.group for m in self.measurements} | {g for c in self.claims for g in c.groups}) <= groups:
            raise ValueError("Deney grubu tanımlı değil.")
        return self


PremiseStatus = Literal["supported", "contradicted", "not_decidable", "true_not_deducible", "unevaluated"]


class Premise(Contract):
    """Öncül: bilimsel olarak doğru olmak ile verilen kaynaktan çıkarılabilir olmak ayrıdır."""

    label: Roman
    text: ShortText
    status: PremiseStatus = "unevaluated"
    evaluator: Literal["evidence_check", "none"] = "none"
    evidence: list[EvidenceRef] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def evaluated_by_checker(self):
        if self.status != "unevaluated" and self.evaluator == "none":
            raise ValueError("Öncül durumu yalnızca bir denetleyiciden gelir.")
        return self


class NarrativeSegment(Contract):
    """Uzun anlatımda bir cümle aralığı ve rolü. Özgün metin ayrıca saklanır; kısaltılmaz."""

    id: Identifier
    start: int = Field(ge=0, le=8192)
    end: int = Field(ge=1, le=8192)
    role: Literal["scenario", "initial_state", "event", "given", "constraint", "requested", "unclassified"]
    provenance: Literal["source_text"] = "source_text"

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("Geçersiz metin aralığı.")
        return self


# --------------------------------------------------------------------------- TA-009 fiziksel model

PhysicsDomain = Literal["kinematics", "dynamics", "energy", "momentum", "dc_circuit", "other"]
AxisDirection = Literal["+x", "-x", "+y", "-y", "up_incline", "down_incline", "angle"]
ForceKind = Literal["gravity", "normal", "tension", "static_friction", "kinetic_friction", "applied", "spring",
                    "electric", "magnetic", "buoyancy", "drag", "other"]
ConditionState = Literal["satisfied", "violated", "unknown"]


class PhysicalBody(Contract):
    entity: Identifier
    mass: Identifier | None = None  # nicelik kimliği
    surface: Identifier | None = None


class Surface(Contract):
    id: Identifier
    kind: Literal["horizontal", "incline", "vertical"]
    angle_deg: NumberText | None = None
    # none: sürtünmesiz (yalnız kaynakta yazılıysa veya açık varsayımsa); unknown: bilinmiyor.
    friction: Literal["none", "present", "unknown"] = "unknown"
    mu_static: Identifier | None = None
    mu_kinetic: Identifier | None = None
    provenance: Provenance


class ForceSpec(Contract):
    """Hangi kuvvetin hangi cisme, hangi yönde etkidiği. Sağlayıcının çizdiği ok bir kuvvetin kanıtı değildir."""

    id: Identifier
    kind: ForceKind
    on: Identifier
    by: Identifier | None = None
    magnitude: Identifier | None = None
    direction: AxisDirection
    angle_deg: NumberText | None = None  # angle yönünde +x eksenine göre
    provenance: Provenance


class StringLink(Contract):
    id: Identifier
    bodies: list[Identifier] = Field(min_length=2, max_length=2)
    over_pulley: bool = False
    provenance: Provenance


class MotionPhase(Contract):
    """Bir cismin bir zaman aralığındaki hareketi. İvmenin sabitliği yasa seçiminin ön koşuludur."""

    id: Identifier
    entity: Identifier
    axis: Literal["horizontal", "vertical", "incline"] = "horizontal"
    acceleration_kind: Literal["constant", "zero", "varying", "unknown"] = "unknown"
    acceleration_basis: Provenance | None = None
    initial_velocity: Identifier | None = None
    final_velocity: Identifier | None = None
    displacement: Identifier | None = None
    distance: Identifier | None = None
    duration: Identifier | None = None
    acceleration: Identifier | None = None
    graph: Identifier | None = None  # hız-zaman grafiği (GraphSeries kimliği)
    free_fall: bool = False


class Collision(Contract):
    id: Identifier
    bodies: list[Identifier] = Field(min_length=2, max_length=2)
    kind: Literal["elastic", "perfectly_inelastic", "inelastic", "explosion", "unknown"] = "unknown"
    velocities_before: list[Identifier | None] = Field(default_factory=list, max_length=2)
    velocities_after: list[Identifier | None] = Field(default_factory=list, max_length=2)
    # Sistemin sınırı ve net dış itmenin sıfır (veya ihmal edilebilir) olduğu kaynağa dayanmalı.
    external_impulse: Literal["none_stated", "negligible_assumed", "present", "unknown"] = "unknown"


class CircuitElement(Contract):
    id: Identifier
    kind: Literal["resistor", "bulb", "battery", "switch", "ammeter", "voltmeter", "wire"]
    nodes: list[Identifier] = Field(min_length=2, max_length=2)
    value: Identifier | None = None  # direnç veya EMK nicelik kimliği
    internal_resistance: Identifier | None = None
    positive_node: Identifier | None = None
    closed: bool | None = None  # anahtar
    # Bağlantı görselden okunduysa ve kesin değilse false: seri/paralel kararı tahminle verilmez.
    connection_certain: bool = True
    provenance: Provenance


class CircuitModel(Contract):
    nodes: list[Identifier] = Field(min_length=2, max_length=24)
    elements: list[CircuitElement] = Field(min_length=1, max_length=32)


class ConditionClaim(Contract):
    condition: Identifier
    state: ConditionState
    basis: Provenance


class LawUse(Contract):
    """Sağlayıcının önerdiği yasa ve koşul iddiaları. Sunucu koşulları kendisi yeniden değerlendirir."""

    law: Identifier
    system: list[Identifier] = Field(default_factory=list, max_length=8)
    conditions: list[ConditionClaim] = Field(default_factory=list, max_length=12)


class PhysicsTarget(Contract):
    quantity: Identifier | None = None  # bilinmeyen nicelik kimliği
    kind: Identifier
    entity: Identifier | None = None
    state: Label | None = None
    representation: Literal["magnitude", "component", "unspecified"] = "unspecified"
    unit: UnitSpec | None = None
    element: Identifier | None = None  # devre: ölçülen eleman
    between: list[Identifier] = Field(default_factory=list, max_length=2)  # devre: eşdeğer direnç uçları


class PhysicsModel(Contract):
    domain: PhysicsDomain
    sign_convention: Label | None = None  # ör. "+x sağa"; eksen önce sabitlenir
    bodies: list[PhysicalBody] = Field(default_factory=list, max_length=8)
    surfaces: list[Surface] = Field(default_factory=list, max_length=4)
    forces: list[ForceSpec] = Field(default_factory=list, max_length=24)
    strings: list[StringLink] = Field(default_factory=list, max_length=4)
    phases: list[MotionPhase] = Field(default_factory=list, max_length=6)
    collisions: list[Collision] = Field(default_factory=list, max_length=2)
    circuit: CircuitModel | None = None
    laws: list[LawUse] = Field(default_factory=list, max_length=8)
    equations: list[Fragment] = Field(default_factory=list, max_length=12)  # sağlayıcı denklemleri: yetkili değildir
    target: PhysicsTarget | None = None


class ScientificProblemModel(Contract):
    schema_version: Literal["1.0.0"] = "1.0.0"
    subject: Subject
    source_revision: int | None = Field(default=None, ge=1, le=64)
    narrative: list[NarrativeSegment] = Field(default_factory=list, max_length=64)
    observations: list[Observation] = Field(default_factory=list, max_length=128)
    entities: list[Entity] = Field(default_factory=list, max_length=64)
    relations: list[Relation] = Field(default_factory=list, max_length=128)
    known: list[QuantityValue] = Field(default_factory=list, max_length=64)
    unknown: list[QuantityValue] = Field(default_factory=list, max_length=16)
    assumptions: list[Observation] = Field(default_factory=list, max_length=16)
    constraints: list[Fragment] = Field(default_factory=list, max_length=32)
    initial_conditions: list[Identifier] = Field(default_factory=list, max_length=16)
    boundary_conditions: list[Identifier] = Field(default_factory=list, max_length=16)
    principles: list[Reference] = Field(default_factory=list, max_length=16)
    candidate_models: list[Fragment] = Field(default_factory=list, max_length=16)
    target: AnswerTarget | None = None
    figures: list[Figure] = Field(default_factory=list, max_length=12)
    graphs: list[GraphSeries] = Field(default_factory=list, max_length=8)
    tables: list[DataTable] = Field(default_factory=list, max_length=8)
    experiment: ExperimentalModel | None = None
    premises: list[Premise] = Field(default_factory=list, max_length=6)
    uncertainties: list[Identifier] = Field(default_factory=list, max_length=16)
    notes: list[Text] = Field(default_factory=list, max_length=8)
    # TA-009: fiziksel sistem (isteğe bağlı; eski kayıtlarda yoktur).
    physics: PhysicsModel | None = None

    @model_validator(mode="after")
    def integrity(self):
        observations = {item.id for item in self.observations + self.assumptions}
        entities = {item.id: item for item in self.entities}
        quantities = {item.id for item in self.known + self.unknown}
        figures = {item.id for item in self.figures}
        for group in (self.observations, self.assumptions, self.entities, self.relations, self.known + self.unknown,
                      self.figures, self.premises):
            keys = [getattr(item, "id", None) or getattr(item, "label") for item in group]
            if len(set(keys)) != len(keys):
                raise ValueError("Kimlikler benzersiz olmalı.")
        if any(item.provenance != "modeling_assumption" for item in self.assumptions):
            raise ValueError("Varsayım yalnızca modelleme varsayımı kökenini taşır.")
        if any(item.provenance == "modeling_assumption" for item in self.observations):
            raise ValueError("Varsayım gözlem listesine yazılamaz.")
        for relation in self.relations:
            left, right = entities.get(relation.subject), entities.get(relation.object)
            if left is None or right is None:
                raise ValueError("İlişki tanımsız bir varlığa işaret ediyor.")
            # Ayrı paneller veya sorulardaki olgular birbirine karıştırılmaz.
            if left.figure != right.figure or (relation.figure is not None and relation.figure != left.figure):
                raise ValueError("Farklı panellerdeki varlıklar arasında ilişki kurulamaz.")
        refs = [ref for item in self.observations + self.assumptions for ref in item.evidence]
        refs += [ref for item in self.known + self.unknown for ref in item.evidence]
        refs += [ref for item in self.premises for ref in item.evidence]
        known_ids = {"observation": observations, "entity": set(entities), "quantity": quantities,
                     "relation": {item.id for item in self.relations}, "figure": figures}
        for ref in refs:
            if ref.kind in known_ids and ref.id not in known_ids[ref.kind]:
                raise ValueError("Kanıt referansı modelde yok.")
        linked = [item.figure for item in self.entities + self.observations + self.relations + self.tables]
        linked += [item.figure for item in self.graphs]
        if any(figure is not None and figure not in figures for figure in linked):
            raise ValueError("Öğe tanımsız bir şekle bağlı.")
        if not set(self.initial_conditions + self.boundary_conditions) <= observations | quantities:
            raise ValueError("Koşul referansı modelde yok.")
        for item in self.known:
            if item.magnitude is None:
                raise ValueError("Bilinen nicelik bir değer taşır.")
        if self.physics is not None:
            _physics_references(self.physics, set(entities), quantities, {item.id for item in self.graphs})
        return self


def _physics_references(model: PhysicsModel, entities: set[str], quantities: set[str], graphs: set[str]) -> None:
    """Fiziksel modelin bütün başvuruları modelde tanımlı olmalı (tanımsız cisim veya niceliğe kuvvet bağlanmaz)."""
    surfaces = {item.id for item in model.surfaces}
    used = {b.entity for b in model.bodies} | {f.on for f in model.forces} | {f.by for f in model.forces if f.by}
    used |= {b for link in model.strings for b in link.bodies} | {phase.entity for phase in model.phases}
    used |= {b for c in model.collisions for b in c.bodies}
    if not used <= entities:
        raise ValueError("Fiziksel model tanımsız bir cisme başvuruyor.")
    refs = [b.mass for b in model.bodies] + [f.magnitude for f in model.forces]
    refs += [item.mu_static for item in model.surfaces] + [item.mu_kinetic for item in model.surfaces]
    for phase in model.phases:
        refs += [phase.initial_velocity, phase.final_velocity, phase.displacement, phase.distance, phase.duration,
                 phase.acceleration]
    for collision in model.collisions:
        refs += [*collision.velocities_before, *collision.velocities_after]
    if model.circuit is not None:
        refs += [e.value for e in model.circuit.elements] + [e.internal_resistance for e in model.circuit.elements]
        nodes = set(model.circuit.nodes)
        for element in model.circuit.elements:
            if not set(element.nodes) <= nodes or (element.positive_node and element.positive_node not in nodes):
                raise ValueError("Devre elemanı tanımsız bir düğüme bağlı.")
        if len({e.id for e in model.circuit.elements}) != len(model.circuit.elements):
            raise ValueError("Devre eleman kimlikleri benzersiz olmalı.")
    if model.target is not None:
        refs.append(model.target.quantity)
    if not {ref for ref in refs if ref} <= quantities:
        raise ValueError("Fiziksel model tanımsız bir niceliğe başvuruyor.")
    if any(b.surface and b.surface not in surfaces for b in model.bodies):
        raise ValueError("Cisim tanımsız bir yüzeyde.")
    if any(phase.graph and phase.graph not in graphs for phase in model.phases):
        raise ValueError("Hareket evresi tanımsız bir grafiğe bağlı.")
