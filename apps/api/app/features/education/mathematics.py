"""TA-008 matematik uzmanlığı sözleşmeleri.

İlkeler:

- Yapılandırılmış model (sözel problem, geometri) *önerilir*; sunucu yalnız desteklenen kalıpları bağımsız
  denetler. Modelin doğru çözülmesi modelin soruya doğru kurulduğunu kanıtlamaz (``model_fidelity``).
- Geometride olgunun kökeni ayrı tutulur: metinde verilen, şekilde işaretli, türetilmiş, belirsiz görsel
  gözlem, yardımcı çizim. Şeklin görünümü (dik görünen açı, eşit görünen kenar) olgu değildir.
- Denetim durumu ``passed`` / ``failed`` / ``partially_checked`` / ``not_checked`` / ``unsupported``.
  Kapsam (``scope``) sonucun neyi kanıtladığını söyler: tek yapılandırma ``configuration``, bütün kabul
  edilebilir yapılandırmalar ``universal``, örneklenmiş değerler ``sampled``.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from .base import Contract, Identifier, Label, Text

Latex = Annotated[str, StringConstraints(min_length=1, max_length=400)]
PointLabel = Annotated[str, StringConstraints(pattern=r"^[A-Z](_?[0-9]{1,2}|'{1,2})?$")]
CheckStatus = Literal["passed", "failed", "partially_checked", "not_checked", "unsupported"]
CheckArea = Literal[
    "domain", "solution_set", "transformation", "inequality", "target", "function", "graph", "trigonometry",
    "probability", "statistics", "calculus", "geometry", "construction", "word_problem", "model_fidelity",
    "strategy", "alternative",
]
# TA-008B: ``model`` = temsil edilen kısıt sisteminin bütün çözümleri (Öklid gerçekleşebilirliği ayrıca kanıtlanmaz).
# ``universal`` yalnız matematiksel olarak gerekçelendirilebilen evrensel iddialar içindir.
CheckScope = Literal["exact", "universal", "model", "configuration", "sampled", "not_applicable"]


class MathCheck(Contract):
    id: Identifier
    area: CheckArea
    status: CheckStatus
    reason: Identifier
    scope: CheckScope = "exact"
    statement: Latex | None = None
    detail: Text | None = None
    # TA-008B: ``material``: doğrulanmış bir hedefe/modele/küme sonucuna karşı *kesin* matematiksel çelişki (ör. yanlış
    # istenen cevap, eksik çözüm, geçersiz kabul edilmiş dönüşüm). Maddi çelişki doğrulanmış ders sonucunu engeller.
    # Belirsizlik, desteklenmeyen hesap veya model sadakati eksikliği maddi değildir.
    material: bool = False


class IntervalView(Contract):
    lower: Label | None = None  # None: −∞
    upper: Label | None = None  # None: +∞
    lower_closed: bool = False
    upper_closed: bool = False


class SolutionSetView(Contract):
    """Çözüm kümesinin gösterilebilir, belirlenimci kaydı."""

    kind: Literal["finite", "empty", "all", "intervals", "conditional", "unsupported"]
    domain: Literal["real", "integer", "natural", "rational", "complex"] = "real"
    variable: Label | None = None
    elements: list[Label] = Field(default_factory=list, max_length=32)
    intervals: list[IntervalView] = Field(default_factory=list, max_length=16)
    exclusions: list[Label] = Field(default_factory=list, max_length=16)
    exact: bool = True
    # TA-008B: gösterim sınırını aşan küme kesilmez gibi sunulmaz; ``truncated`` true ise görünüm eksiktir ve
    # bütünlük karşılaştırması yalnız işçideki kesin küme üzerinden yapılır.
    truncated: bool = False
    # TA-008B: özgün ifadeden (sadeleştirmeden önce) toplanan tanım koşulları.
    conditions: list[Label] = Field(default_factory=list, max_length=24)

    @model_validator(mode="after")
    def coherent(self):
        if self.kind == "finite" and not self.elements:
            raise ValueError("Sonlu küme eleman taşır.")
        if self.kind == "intervals" and not self.intervals:
            raise ValueError("Aralık kümesi aralık taşır.")
        return self


# --- Sözel problem modeli --------------------------------------------------------------------------------------

WordProblemType = Literal["age", "motion", "work_rate", "mixture", "percent", "profit_loss", "ratio",
                          "linear_system", "data_table", "scheduling", "other"]
ModelOrigin = Literal["stated", "derived", "assumed", "visual_uncertain"]


class WordQuantity(Contract):
    symbol: Annotated[str, StringConstraints(pattern=r"^[a-zA-Z](_[a-zA-Z0-9]{1,4})?$")]
    name_tr: Label
    unit: Label | None = None
    value: Latex | None = None  # bilinen nicelik; bilinmeyende None
    discrete: bool = False
    origin: ModelOrigin = "stated"
    # TA-008B: değerin soru metnindeki dayanağı (birebir alıntı). Aynı sayının metinde geçmesi anlamını kanıtlamaz.
    evidence: Text | None = None


class WordConstraint(Contract):
    symbol: Annotated[str, StringConstraints(pattern=r"^[a-zA-Z](_[a-zA-Z0-9]{1,4})?$")]
    kind: Literal["positive", "nonnegative", "integer", "natural"]


class WordProblemModel(Contract):
    problem_type: WordProblemType
    quantities: list[WordQuantity] = Field(min_length=1, max_length=12)
    relations: list[Latex] = Field(min_length=1, max_length=8)
    constraints: list[WordConstraint] = Field(default_factory=list, max_length=12)
    objective: Latex

    @model_validator(mode="after")
    def unique_symbols(self):
        symbols = [item.symbol for item in self.quantities]
        if len(set(symbols)) != len(symbols):
            raise ValueError("Nicelik sembolleri benzersiz olmalı.")
        return self


# --- Geometri modeli -------------------------------------------------------------------------------------------

FactOrigin = Literal["stated", "marked", "derived", "visual_uncertain", "construction"]
# Bir olgunun dayanak olarak kullanılabileceği kökenler. Görsel belirsiz gözlem dayanak değildir.
USABLE_ORIGINS = frozenset({"stated", "marked", "derived", "construction"})
FactKind = Literal[
    "segment_length", "angle_measure", "equal_segments", "equal_angles", "parallel", "perpendicular",
    "right_angle", "collinear", "midpoint", "point_on_segment", "triangle", "polygon", "circle",
    "point_on_circle", "tangent", "similar", "congruent", "coordinate", "area",
]


class GeometryFact(Contract):
    id: Identifier
    kind: FactKind
    points: list[PointLabel] = Field(min_length=1, max_length=8)
    # İkinci nokta grubu (eşit kenar/açı, paralellik, benzerlik eşlemesi). Sıra karşılık gelen köşeleri verir.
    other: list[PointLabel] = Field(default_factory=list, max_length=8)
    value: Latex | None = None
    origin: FactOrigin
    # TA-008B kanıt zinciri. ``stated``: soru metninden birebir alıntı (sunucu metinde arar; bulunmazsa olgu yalnız
    # sağlayıcı önerisidir). ``derived``: öncül olgu kimlikleri ve kural (sunucu doğrular; doğrulanmayan türetme
    # açıklayıcı hipotez kalır ve kısıt olmaz).
    evidence: Text | None = None
    premises: list[Identifier] = Field(default_factory=list, max_length=6)
    rule: Identifier | None = None


ConstructionKind = Literal["altitude", "segment", "extension", "parallel_line", "midpoint", "radius",
                           "perpendicular", "angle_bisector"]


class Construction(Contract):
    """Yardımcı çizim. Tanımı gereği izleyen olgular (``establishes``) ayrı, kanıt gerektirenler ayrıdır."""

    id: Identifier
    kind: ConstructionKind
    references: list[PointLabel] = Field(min_length=1, max_length=6)
    new_points: list[PointLabel] = Field(default_factory=list, max_length=3)
    establishes: list[Identifier] = Field(default_factory=list, max_length=6)
    requires_proof: list[Text] = Field(default_factory=list, max_length=6)
    purpose_tr: Text


class GeometryTarget(Contract):
    kind: Literal["length", "angle", "area", "perimeter", "ratio", "coordinate"]
    points: list[PointLabel] = Field(min_length=1, max_length=8)


class GeometryModel(Contract):
    points: list[PointLabel] = Field(min_length=1, max_length=16)
    facts: list[GeometryFact] = Field(default_factory=list, max_length=48)
    constructions: list[Construction] = Field(default_factory=list, max_length=6)
    target: GeometryTarget | None = None
    # Şekil ölçekli değildir; görünen orantılar veri sayılmaz.
    schematic: bool = True

    @model_validator(mode="after")
    def references_resolve(self):
        known = set(self.points) | {p for item in self.constructions for p in item.new_points}
        facts = {item.id for item in self.facts}
        if len(facts) != len(self.facts):
            raise ValueError("Olgu kimlikleri benzersiz olmalı.")
        for fact in self.facts:
            if not set(fact.points + fact.other) <= known:
                raise ValueError(f"Tanımsız noktaya başvuru: {fact.id}")
        for construction in self.constructions:
            if not set(construction.references) <= known or not set(construction.establishes) <= facts:
                raise ValueError(f"Yardımcı çizim tanımsız öğeye başvuruyor: {construction.id}")
        if self.target is not None and not set(self.target.points) <= known:
            raise ValueError("Hedef tanımsız noktaya başvuruyor.")
        return self


class MathematicalModel(Contract):
    """Sağlayıcının önerdiği yapılandırılmış model; sunucu denetler, kabul etmek zorunda değildir."""

    kind: Literal["word_problem", "geometry"]
    word_problem: WordProblemModel | None = None
    geometry: GeometryModel | None = None

    @model_validator(mode="after")
    def matches_kind(self):
        if (self.kind == "word_problem") != (self.word_problem is not None) or \
                (self.kind == "geometry") != (self.geometry is not None):
            raise ValueError("Model türü ile içerik uyuşmalı.")
        return self


# --- Strateji ve rapor -----------------------------------------------------------------------------------------

class StrategyRef(Contract):
    id: Identifier
    status: Literal["draft", "approved"]
    applicable: bool
    reason: Identifier
    suitable_for_grade: bool | None = None


class AlternativePath(Contract):
    """Belirlenimci üretilmiş ve özgün soruya karşı bağımsız denetlenmiş alternatif çözüm yolu."""

    id: Identifier
    strategy: Identifier
    title_tr: Label
    steps: list[Latex] = Field(min_length=1, max_length=12)
    result: list[Label] = Field(default_factory=list, max_length=8)
    verified: bool


class GraphSegment(Contract):
    """Kesintisiz grafik parçası. Tanımsız noktada grafik birleştirilmez."""

    start: float
    end: float
    start_closed: bool = True
    end_closed: bool = True


class GeometryFactStatus(Contract):
    """TA-008B §19: sunucunun olgu kararı. ``basis``: kabul edilmişse kanıt sınıfı (source_text, diagram_observation, student_confirmed,
    validated_derivation, construction_defined), reddedilmişse neden kodu. Tahta etiketini sağlayıcının ``origin``
    alanından değil bu karardan alır."""

    id: Identifier
    status: Literal["accepted", "rejected"]
    basis: Identifier


class MathematicsReport(Contract):
    schema_version: Literal["1.0.0"] = "1.0.0"
    topics: list[Identifier] = Field(default_factory=list, max_length=4)
    topic_evidence: Literal["structural", "lexical", "none"] = "none"
    checks: list[MathCheck] = Field(default_factory=list, max_length=64)
    solution_set: SolutionSetView | None = None
    domain_exclusions: list[Label] = Field(default_factory=list, max_length=16)
    model_kind: Literal["word_problem", "geometry", "none"] = "none"
    model_status: Literal["accepted", "rejected", "absent"] = "absent"
    geometry_facts: list[GeometryFactStatus] = Field(default_factory=list, max_length=32)
    strategies: list[StrategyRef] = Field(default_factory=list, max_length=8)
    alternatives: list[AlternativePath] = Field(default_factory=list, max_length=3)
    graph_expression: Latex | None = None
    graph_segments: list[GraphSegment] = Field(default_factory=list, max_length=16)
    # TA-008B: yalnız doğrulanmış parçaların içinden, tanımsız noktalar dışlanarak alınmış örnek noktalar (gösterim).
    graph_points: list[tuple[float, float]] = Field(default_factory=list, max_length=96)
    # Kaldırılabilir süreksizlik (x, limit) — açık daire; düşey asimptot x değerleri — kesikli çizgi.
    graph_holes: list[tuple[float, float]] = Field(default_factory=list, max_length=16)
    graph_asymptotes: list[float] = Field(default_factory=list, max_length=16)
    # TA-008B: maddi çelişkiler kesmeden önce ayrı tutulur; ``checks`` kesilse bile durum hesabından düşmez.
    material_failures: list[MathCheck] = Field(default_factory=list, max_length=16)
    material_count: int = Field(default=0, ge=0, le=1000)
    specialist_status: Literal["completed", "partial", "unavailable"] = "completed"
    capability: Literal["independently_verifiable", "partially_verifiable", "ai_assisted_only", "unsupported"] = "unsupported"
    notes_tr: list[Text] = Field(default_factory=list, max_length=8)
