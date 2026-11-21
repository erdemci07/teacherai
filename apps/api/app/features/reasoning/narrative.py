"""Uzun soru metninden sınırlı, belirlenimci anlatı ve nicelik çıkarımı (TA-004).

Bu bir anlama motoru değildir. Yalnızca cümle aralıklarını, son soru cümlesini ve açık "sayı + birim"
kalıplarını çıkarır. Özgün metin değiştirilmez veya kısaltılmaz; aralıklar özgün metne işaret eder.
Önemsiz ayrıntıyı ayıklamaz: belirleyici bir koşul metnin sonunda olsa bile metin bütün olarak kalır.
"""

from __future__ import annotations

import re
from fractions import Fraction

from ..education.science import NarrativeSegment, QuantityValue
from .units import NumberError, UnitError, parse_number, parse_unit

MAX_SEGMENTS = 64
MAX_QUANTITIES = 32
_SENTENCE = re.compile(r"[^.!?\n]+[.!?]?", re.UNICODE)
_QUANTITY = re.compile(
    r"(?:(?P<symbol>(?<![\w])[a-zA-Z](?:_\{?[0-9a-zA-Z]{1,3}\}?)?)\s*=\s*)?"
    r"(?P<number>(?<![\w,.])-?\d+(?:[.,]\d+)?(?:\s*(?:×|·)\s*10\s*(?:\^\s*\{?[-−]?\d+\}?|[⁻]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+))?)"
    r"\s*(?P<unit>(?:°C|[A-Za-zµ][A-Za-z]{0,3})(?:\s*[/·]\s*(?:\(?[A-Za-z]{1,3}(?:\s*·\s*[A-Za-z]{1,3})?\)?)|[²³⁻¹]|\^-?\d)*)"
)
_GIVEN = ("ise", "olduğuna göre", "olmak üzere", "verilmiştir", "olan", "sahip")


def _ratio(value: Fraction) -> str | None:
    text = str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"
    return text if len(re.sub(r"\D", "", text)) <= 15 and len(text) <= 31 else None


def segments(text: str) -> list[NarrativeSegment]:
    spans = [(m.start(), m.end()) for m in _SENTENCE.finditer(text) if m.group(0).strip()]
    if not spans:
        return []
    question = max((i for i, (s, e) in enumerate(spans) if "?" in text[s:e]), default=len(spans) - 1)
    result = []
    for index, (start, end) in enumerate(spans[:MAX_SEGMENTS]):
        sentence = text[start:end].casefold()
        role = "requested" if index == question else "given" if (
            _QUANTITY.search(text[start:end]) or any(word in sentence for word in _GIVEN)) else "unclassified"
        if end > 8192:
            break
        result.append(NarrativeSegment(id=f"seg_{index + 1}", start=start, end=end, role=role))  # type: ignore[arg-type]
    return result


def quantities(text: str, provenance: str = "source_text") -> list[QuantityValue]:
    """Açık "sayı + tanınan birim" kalıpları. Tanınmayan sözcük (``kalem``, ``x``) nicelik sayılmaz."""
    found: list[QuantityValue] = []
    for match in _QUANTITY.finditer(text):
        unit_text = re.split(r"['’]", match.group("unit"))[0].strip()
        try:
            unit = parse_unit(unit_text)
            value, digits, _ = parse_number(match.group("number"))
        except (UnitError, NumberError):
            continue
        if not unit.factors:
            continue
        magnitude = _ratio(value)
        if magnitude is None:
            continue
        found.append(QuantityValue(
            id=f"q_{len(found) + 1}", symbol=match.group("symbol"), magnitude=magnitude,
            original=match.group(0).strip()[:256], unit=unit.spec(), significant_digits=min(digits, 15) or None,
            provenance=provenance,  # type: ignore[arg-type]
        ))
        if len(found) >= MAX_QUANTITIES:
            break
    return found
