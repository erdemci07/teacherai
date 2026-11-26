"""Bilinen niceliklerin değeri ve kökeninin sunucuda doğrulanması (TA-009 §10).

Sağlayıcı bir değeri "kaynakta verildi" diye işaretleyebilir; bu tek başına kanıt değildir:

- ``source_text``: yazılış (``original``) soru metninde belirteç düzeyinde geçmeli ve aynı sayıyı taşımalı.
- ``problem_convention``: sorunun uzlaşımıyla (``g = 10 m/s²``, ``sin 37° = 0,6``) aynı değer olmalı.
- ``standard_constant``: kaynaklı sabit tablosuyla aynı değer olmalı; öğrenciye kaynağıyla gösterilir.
- ``student_confirmed``: öğrencinin onayladığı düzeltmede geçmeli (bağımsız doğrulama değildir).
- ``visual_reading``: görselden AI okumasıdır; sonuç en fazla kısmi doğrulamadır.
- Diğerleri (``provider_proposed``, ``inferred``…) doğrulanmamış girdidir; sonuç yalnız yorumdur.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from ..education.science import ScientificProblemModel
from ..reasoning import quotes
from ..reasoning.units import DIMENSIONLESS, Dim, NumberError, UnitError, parse_number, parse_unit
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


def _magnitude(text: str) -> Fraction:
    if "/" in text:
        num, den = text.split("/")
        return Fraction(int(num), int(den))
    return Fraction(int(text))


def resolve(problem: ScientificProblemModel, source_text: str, facts: SourceFacts, confirmed: tuple[str, ...] = ()) -> Resolved:
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
    return Resolved(values, unverified, visual, problems)


# Sıfır değeri sayı olmadan da kaynakta yazılı olabilir: "durgun halden", "durmakta olan", "serbest bırakılan",
# yatay atışta düşey ilk hız ("yatay … fırlatılıyor"). Yalnız bu ifadeler ve yalnız 0 için.
ZERO_PHRASES = ("durgun", "durmakta", "serbest bırakıl", "ilk hızsız", "hareketsiz", "yatay")


def _origin(item, magnitude: Fraction, text: str, facts: SourceFacts, confirmed: tuple[str, ...]) -> str:
    written = item.original or ""
    if item.provenance == "source_text":
        if written and quotes.contains(text, written) and magnitude == 0 and any(
                phrase in quotes.lower(written) for phrase in ZERO_PHRASES):
            return "source_text"
        return "source_text" if written and quotes.contains(text, written) and _carries(written, magnitude) else "unverified"
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


def _carries(written: str, magnitude: Fraction) -> bool:
    """Yazılışın sayısı bildirilen büyüklükle aynı mı (``8 m`` ↔ 8; ``0,5 kg`` ↔ 1/2)?"""
    for token in quotes.tokens(written):
        if token.kind == "number":
            try:
                return parse_number(token.text)[0] == abs(magnitude)
            except NumberError:
                return False
    return False
