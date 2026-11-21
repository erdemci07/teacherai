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
        return self
