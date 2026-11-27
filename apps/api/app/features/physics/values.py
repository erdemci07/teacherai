"""Bilinen niceliklerin değeri ve kökeninin sunucuda doğrulanması (TA-009 §10).

Sağlayıcı bir değeri "kaynakta verildi" diye işaretleyebilir; bu tek başına kanıt değildir:

- ``source_text``: yazılış (``original``) soru metninde belirteç düzeyinde ve birim sınırına saygıyla geçmeli
  (``20 m`` ``20 m/s`` içinde değildir) ve aynı değeri birimiyle taşımalı (``20 cm`` ≠ 20 m).
- TA-009B §1 değer bağı: metinde aynı boyutta birden çok değer varsa (iki kütle, iki sürtünme katsayısı, iki direnç)
  değerin doğru cisme/etikete bağlandığı kanıtlanmalı: aynı yan cümlede kendi etiketi rakip etiketlerden daha yakın
  ("A cisminin kütlesi 6 kg", "statik sürtünme katsayısı 0,4", "R₁ = 3 Ω"), görsel gözlem kaydında veya öğrenci
  onayında. Kanıt yoksa değer ``unbound``dır: ``source_text`` sayılmaz, sonuç en fazla kısmi doğrulamadır.
- ``problem_convention``: sorunun uzlaşımıyla (``g = 10 m/s²``, ``sin 37° = 0,6``) aynı değer olmalı.
- ``standard_constant``: kaynaklı sabit tablosuyla aynı değer olmalı; öğrenciye kaynağıyla gösterilir.
- ``student_confirmed``: öğrencinin onayladığı düzeltmede geçmeli (bağımsız doğrulama değildir).
- ``visual_reading``: görselden AI okumasıdır; sonuç en fazla kısmi doğrulamadır.
- Diğerleri (``provider_proposed``, ``inferred``…) doğrulanmamış girdidir; sonuç yalnız yorumdur.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from ..education.science import ScientificProblemModel
from ..reasoning import quotes
from ..reasoning.units import DIMENSIONLESS, Dim, NumberError, UnitError, parse_number, parse_quantity, parse_unit
from .conventions import STANDARD_CONSTANTS, SourceFacts


@dataclass(frozen=True)
class Value:
    id: str
    symbol: str | None
    si: Fraction
    dim: Dim
    kind: str | None
    origin: str  # source_text | problem_convention | standard_constant | student_confirmed | visual | unverified
    text: str
    representation: str = "unspecified"


@dataclass
class Resolved:
    values: dict[str, Value]
    unverified: list[str]
    visual: list[str]
    problems: list[str]
    unbound: list[str] = field(default_factory=list)  # metinde var ama hangi cisme/etikete ait olduğu kanıtlanmadı


def _magnitude(text: str) -> Fraction:
    if "/" in text:
        num, den = text.split("/")
        return Fraction(int(num), int(den))
    return Fraction(int(text))


def resolve(problem: ScientificProblemModel, source_text: str, facts: SourceFacts, confirmed: tuple[str, ...] = (),
            observations: tuple[str, ...] = ()) -> Resolved:
    values: dict[str, Value] = {}
    unverified, visual, problems = [], [], []
    for item in problem.known:
        try:
            magnitude = _magnitude(item.magnitude)
            unit = parse_unit(item.unit.original) if item.unit is not None else None
        except (UnitError, ValueError, ZeroDivisionError):
            problems.append(item.id)
            continue
        if unit is not None and unit.affine:
            problems.append(item.id)  # °C ötelemeli ölçek; fark/mutlak sıcaklık ayrımı yapılmadan dönüştürülmez
            continue
        si = magnitude * (unit.scale if unit is not None else 1)
        dim = unit.dim if unit is not None else DIMENSIONLESS
        origin = _origin(item, magnitude, source_text, facts, confirmed)
        if origin == "unverified":
            unverified.append(item.id)
        elif origin == "visual":
            visual.append(item.id)
        values[item.id] = Value(item.id, item.symbol, si, dim, item.kind, origin, item.original or item.magnitude,
                                item.representation)
    unbound, by_figure = _binding(problem, source_text, values, confirmed, observations)
    visual.extend(item for item in by_figure if item not in visual)
    for item_id in unbound:
        values[item_id] = Value(**{**values[item_id].__dict__, "origin": "unbound"})
    return Resolved(values, unverified, visual, problems, unbound)


# --------------------------------------------------------------------------- TA-009B §1 değer bağı

MU_KEYS = {"s": ("statik", "μs", "μ_s"), "k": ("kinetik", "μk", "μ_k")}
SUBSCRIPTS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def _keys(item, problem) -> tuple[str, ...]:
    """Değeri cismine/etiketine bağlayan anahtarlar: cisim kimliği ve etiketi, sembol alt simgesi (m_A → A,
    R_1 → R₁), sürtünme katsayısında statik/kinetik."""
    keys: list[str] = []
    for entity in (item.entity, _model_entity(problem, item.id)):
        if not entity:
            continue
        keys.append(entity)
        label = next((e.label for e in problem.entities if e.id == entity and e.label), None)
        if label:
            keys.append(label)
    base, _, sub = (item.symbol or "").partition("_")
    sub = sub.strip("{}")
    if sub:
        if base in {"mu", "μ"}:
            keys.extend(MU_KEYS.get(sub.lower(), ()))
        else:
            # Sayısal alt simge tek başına anahtar değildir ("2", "2 kg" içindeki sayıyla karışır): yalnız R_1, R₁, R1.
            keys.extend(([sub] if sub.isalpha() else []) + [f"{base}_{sub}", f"{base}{sub.translate(SUBSCRIPTS)}",
                                                            f"{base}{sub}"])
    return tuple(dict.fromkeys(k for k in keys if k))


def _model_entity(problem, quantity_id: str) -> str | None:
    """Fiziksel modelin kendi ilişkisinden niceliğin sahibi: cismin kütlesi, çarpışmadaki hız sırası, kuvvetin etki
    ettiği cisim, devre elemanının değeri (eleman kimliği)."""
    model = problem.physics
    if model is None:
        return None
    for body in model.bodies:
        if body.mass == quantity_id:
            return body.entity
    for collision in model.collisions:
        for ids in (collision.velocities_before, collision.velocities_after):
            for index, qid in enumerate(ids):
                if qid == quantity_id and index < len(collision.bodies):
                    return collision.bodies[index]
    for force in model.forces:
        if force.magnitude == quantity_id:
            return force.on
    if model.circuit is not None:
        for element in model.circuit.elements:
            if quantity_id in {element.value, element.internal_resistance}:
                return element.id
    return None


def _source_quantities(text: str) -> list[tuple[Dim, Fraction]]:
    """Metindeki sayı + birim çiftleri (boyut, SI değer). Birimsiz sayılar rakip sayılmaz."""
    found = quotes.tokens(text)
    out = []
    for index, token in enumerate(found):
        if token.kind != "number":
            continue
        best = None
        for end in range(index + 2, min(index + 6, len(found)) + 1):
            written = token.text + " " + "".join(t.text for t in found[index + 1:end])
            try:
                parsed = parse_quantity(written)
            except (NumberError, UnitError, ValueError):
                continue
            if parsed.unit.factors and not parsed.unit.affine:
                best = (parsed.unit.dim, parsed.si.value)
        if best is not None:
            out.append(best)
    return out


def _binding(problem, text: str, values: dict[str, Value], confirmed, observations) -> tuple[list[str], list[str]]:
    """Bağı kanıtlanmayanlar ve bağı yalnız görsel gözlem kaydına dayananlar (sağlayıcı okuması; en fazla kısmi)."""
    anchored = {k: v for k, v in values.items() if v.origin == "source_text" and v.si != 0}
    by_dim: dict[Dim, set[Fraction]] = {}
    for dim, value in _source_quantities(text):
        by_dim.setdefault(dim, set()).add(value)
    for value in anchored.values():
        by_dim.setdefault(value.dim, set()).add(value.si)
    items = {q.id: q for q in problem.known}
    unbound, by_figure = [], []
    for key, value in anchored.items():
        rivals = [k for k, v in anchored.items() if k != key and v.dim == value.dim and v.si != value.si]
        if len(by_dim.get(value.dim, ())) < 2 and not rivals:
            continue  # boyutunda tek değer: bağ kanıtı gerekmez
        own = _keys(items[key], problem)
        rival_keys = {k for r in rivals for k in _keys(items[r], problem)} - set(own)
        written = items[key].original or ""
        if own and any(_bound(source, written, own, rival_keys) for source in (text, *confirmed)):
            continue
        if own and any(_bound(source, written, own, rival_keys) for source in observations):
            by_figure.append(key)
        else:
            unbound.append(key)
    return unbound, by_figure


def _bound(source: str, written: str, own, rivals) -> bool:
    """Yazılışın bir geçişinde, aynı yan cümlede kendi anahtarı rakip anahtarlardan kesin olarak daha yakın mı?
    Açık atama (``R₂ = 3 Ω``) uzaklıktan bağımsız olarak bağ kanıtıdır."""
    for clause in quotes.clauses(source):
        text = " ".join(t.text for t in clause)
        _, starts = quotes.occurrences(text, written)
        if not starts:
            continue
        if any(quotes.contains(text, f"{key} = {written}") for key in own):
            return True
        hay = [t for t in clause if t.text not in quotes.APOSTROPHES]
        mine = _distances(text, own, hay, starts)
        theirs = _distances(text, rivals, hay, starts)
        if mine is not None and (theirs is None or mine < theirs):
            return True
    return False


def _distances(text: str, keys, hay, starts) -> int | None:
    best = None
    for key in keys:
        _, at = quotes.occurrences(text, key)
        for position in at:
            for start in starts:
                distance = abs(position - start)
                best = distance if best is None else min(best, distance)
    return best


# Sıfır değeri sayı olmadan da kaynakta yazılı olabilir: "durgun halden", "durmakta olan", "serbest bırakılan",
# yatay atışta düşey ilk hız ("yatay … fırlatılıyor"). Yalnız bu ifadeler ve yalnız 0 için.
ZERO_PHRASES = ("durgun", "durmakta", "serbest bırakıl", "ilk hızsız", "hareketsiz", "yatay")


def _origin(item, magnitude: Fraction, text: str, facts: SourceFacts, confirmed: tuple[str, ...]) -> str:
    written = item.original or ""
    if item.provenance == "source_text":
        if written and quotes.contains(text, written) and magnitude == 0 and any(
                phrase in quotes.lower(written) for phrase in ZERO_PHRASES):
            return "source_text"
        anchored = written and quotes.contains(text, written) and _carries(written, magnitude, item.unit)
        return "source_text" if anchored else "unverified"
    if item.provenance == "student_confirmed":
        return "student_confirmed" if written and any(quotes.contains(c, written) for c in confirmed) else "unverified"
    if item.provenance == "problem_convention":
        symbol = (item.symbol or "").replace(" ", "")
        convention = facts.conventions.get(symbol) or facts.conventions.get(symbol.lower())
        return "problem_convention" if convention is not None and convention.value == magnitude else "unverified"
    if item.provenance == "standard_constant":
        constant = STANDARD_CONSTANTS.get(item.symbol or "")
        if constant is None:
            return "unverified"
        scale = parse_unit(item.unit.original).scale if item.unit is not None else 1
        return "standard_constant" if magnitude * scale == constant[0] else "unverified"
    if item.provenance == "visual_reading":
        return "visual"
    return "unverified"


def _carries(written: str, magnitude: Fraction, unit=None) -> bool:
    """Yazılış bildirilen değeri birimiyle taşıyor mu (``8 m`` ↔ 8 m; ``20 cm`` ≠ 20 m; ``0,5`` ↔ 1/2)?"""
    found = _quantity_in(written)
    if found is None:
        return False
    number, dim, si = found
    if magnitude == 0:
        return number == 0  # sıfır her birimde sıfırdır ("0'dan")
    if unit is None:
        return dim is None and number == abs(magnitude)
    try:
        declared = parse_unit(unit.original)
    except UnitError:
        return False
    return dim == declared.dim and abs(si) == abs(magnitude) * declared.scale


def _quantity_in(written: str) -> tuple[Fraction, Dim | None, Fraction | None] | None:
    """Yazılıştaki ilk sayı ve hemen ardından gelen birim (kesme işaretinde durulur): (sayı, boyut, SI)."""
    found = quotes.tokens(written)
    index = next((i for i, t in enumerate(found) if t.kind == "number"), None)
    if index is None:
        return None
    try:
        number = parse_number(found[index].text)[0]
    except NumberError:
        return None
    best = None
    tail = []
    for token in found[index + 1:index + 6]:
        if token.text in quotes.APOSTROPHES:
            break
        tail.append(token.text)
        try:
            parsed = parse_quantity(found[index].text + " " + "".join(tail))
        except (NumberError, UnitError, ValueError):
            continue
        if parsed.unit.factors and not parsed.unit.affine:
            best = (parsed.unit.dim, parsed.si.value)
    return (number, *best) if best else (number, None, None)
