"""Soru uzlaşımları, standart sabitler ve idealleştirmeler (TA-009 §10).

Öncelik sırası: **sorunun verdiği uzlaşım** (``g = 10 m/s²``, ``sin 37° = 0,6``, ``π = 3``) her zaman standart sabitin
önüne geçer. Soru bir değer vermiyorsa ve hesap gerektiriyorsa kullanılan standart değer ve kaynağı öğrenciye
görünür olmalıdır; sessizce yerine konmaz. Soruda yazmayan idealleştirme (sürtünmesiz, ipin kütlesi önemsiz) bir
*varsayımdır*, verilen bilgi olarak gösterilmez.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction

from ..reasoning import quotes
from ..reasoning.units import NumberError, UnitError, parse_quantity

# Standart değerler (SI, tam rasyonel). Tanımlı sabitler SI (2019) gereği tamdır; ölçülmüş sabit CODATA 2022'dir.
STANDARD_CONSTANTS: dict[str, tuple[Fraction, str, str, str]] = {
    # sembol: (SI değeri, birim, kaynak, durum)
    "g_n": (Fraction(980665, 10**5), "m/s^2", "CGPM 3 (1901): standart yerçekimi ivmesi (geleneksel tanımlı değer)",
            "defined"),
    "c": (Fraction(299792458), "m/s", "BIPM SI Broşürü, 9. baskı (2019): tanımlı sabit", "defined"),
    "e": (Fraction(1602176634, 10**28), "C", "BIPM SI Broşürü, 9. baskı (2019): tanımlı sabit", "defined"),
    "h": (Fraction(662607015, 10**42), "J·s", "BIPM SI Broşürü, 9. baskı (2019): tanımlı sabit", "defined"),
    "k_B": (Fraction(1380649, 10**29), "J/K", "BIPM SI Broşürü, 9. baskı (2019): tanımlı sabit", "defined"),
    "N_A": (Fraction(602214076 * 10**15), "mol^-1", "BIPM SI Broşürü, 9. baskı (2019): tanımlı sabit", "defined"),
    "G": (Fraction(667430, 10**16), "N·m^2/kg^2", "NIST CODATA 2022 önerilen değer (göreli belirsizlik 2,2 × 10⁻⁵)",
          "measured"),
}

_G_CONVENTION = re.compile(r"\bg\s*=\s*(\d+(?:[.,]\d+)?)\s*(m\s*/\s*s\s*(?:\^?\s*2|²)|N\s*/\s*kg)", re.IGNORECASE)
_G_PROSE = re.compile(r"(?:yer[çc]ekimi|çekim)\s+ivmesi\w*\s+(\d+(?:[.,]\d+)?)\s*(m\s*/\s*s\s*(?:\^?\s*2|²)|N\s*/\s*kg)",
                      re.IGNORECASE)
_TRIG_CONVENTION = re.compile(r"\b(sin|cos|tan)\s*\(?\s*(\d+(?:[.,]\d+)?)\s*(?:°|\^\s*\\?circ|derece)?\s*\)?\s*=\s*"
                              r"(\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?)", re.IGNORECASE)
_PI_CONVENTION = re.compile(r"(?:π|\\pi|\bpi\b)\s*=\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)
_SQRT_CONVENTION = re.compile(r"(?:√|\\sqrt)\s*\{?\s*(\d+)\s*\}?\s*=\s*(\d+(?:[.,]\d+)?)")


@dataclass(frozen=True)
class Convention:
    symbol: str  # g | sin(37) | cos(53) | pi | sqrt(2)
    value: Fraction
    unit: str | None
    quote: str


# Türkçe idealleştirme ifadeleri → açık koşul. Kök eşleşmesi (ekler: "sürtünmesiz", "sürtünmesizdir").
IDEALIZATIONS: dict[str, tuple[str, ...]] = {
    "frictionless": ("sürtünmesiz", "sürtünme önemsiz", "sürtünmeler önemsiz", "sürtünme ihmal", "sürtünmeler ihmal"),
    "no_air_resistance": ("hava direnci önemsiz", "hava direnci ihmal", "hava sürtünmesi önemsiz", "hava sürtünmesi ihmal",
                          "hava direnci yok", "sürtünmeler önemsiz"),
    "massless_string": ("ipin kütlesi önemsiz", "ip kütlesi önemsiz", "iplerin kütlesi önemsiz", "ağırlığı önemsiz ip",
                        "kütlesi önemsiz ip", "ip ağırlığı önemsiz", "iplerin ağırlığı önemsiz"),
    "ideal_pulley": ("makara sürtünmesiz", "makaranın kütlesi önemsiz", "makara ağırlığı önemsiz", "ağırlığı önemsiz makara",
                     "kütlesi önemsiz makara", "ideal makara", "makaraların ağırlığı önemsiz"),
    "point_mass": ("noktasal", "boyutları önemsiz"),
    "ideal_ammeter": ("ideal ampermetre", "ampermetreler ideal", "ampermetre ideal"),
    "ideal_voltmeter": ("ideal voltmetre", "voltmetreler ideal", "voltmetre ideal"),
    "ideal_source": ("iç direnci önemsiz", "iç dirençleri önemsiz", "ideal üreteç", "üreteçler ideal", "iç direnci yok"),
    "ideal_wires": ("bağlantı kablolarının direnci önemsiz", "tellerin direnci önemsiz", "kabloların direnci önemsiz"),
    "elastic_collision": ("esnek çarpışma", "esnek olarak çarpış", "tam esnek"),
    "perfectly_inelastic": ("yapışarak", "kenetlen", "birlikte hareket", "tamamen esnek olmayan", "yapışıp"),
    "starts_from_rest": ("durgun halden", "durgun hâlden", "durgun duran", "durgunken", "durmakta olan", "ilk hızsız",
                         "serbest bırakıl", "hareketsiz duran"),
    "constant_velocity": ("sabit hızla", "sabit süratle", "düzgün doğrusal hareket"),
    "constant_acceleration": ("sabit ivme", "düzgün hızlanan", "düzgün yavaşlayan", "düzgün değişen"),
    "free_fall": ("serbest düşme", "serbest bırakıl", "serbest düş"),
    "isolated_system": ("dış kuvvet yok", "dış kuvvetler önemsiz", "yalıtılmış sistem", "sürtünmesiz yatay düzlemde çarpış"),
}
NEGATED_IDEALIZATIONS = {"frictionless": ("sürtünmeli", "sürtünme katsayısı", "sürtünme kuvveti")}


@dataclass
class SourceFacts:
    """Soru metninden belirlenimci olarak çıkarılan uzlaşımlar ve açıkça yazılı idealleştirmeler."""

    conventions: dict[str, Convention] = field(default_factory=dict)
    stated: dict[str, str] = field(default_factory=dict)  # koşul → metindeki alıntı
    contradicted: dict[str, str] = field(default_factory=dict)  # "sürtünmeli" → frictionless çelişir
    off_earth: str | None = None  # "gezegen", "Ay", "Mars": standart g uygulanmaz


def _fraction(text: str) -> Fraction:
    if "/" in text:
        num, den = text.split("/")
        return Fraction(num.strip().replace(",", ".")) / Fraction(den.strip())
    return Fraction(text.strip().replace(",", "."))


def read(text: str) -> SourceFacts:
    facts = SourceFacts()
    source = text or ""
    for pattern in (_G_PROSE, _G_CONVENTION):
        for match in pattern.finditer(source):
            facts.conventions["g"] = Convention("g", _fraction(match.group(1)), "m/s^2", match.group(0))
    for match in _TRIG_CONVENTION.finditer(source):
        name = f"{match.group(1).lower()}({_fraction(match.group(2))})"
        facts.conventions[name] = Convention(name, _fraction(match.group(3)), None, match.group(0))
    for match in _PI_CONVENTION.finditer(source):
        facts.conventions["pi"] = Convention("pi", _fraction(match.group(1)), None, match.group(0))
    for match in _SQRT_CONVENTION.finditer(source):
        name = f"sqrt({match.group(1)})"
        facts.conventions[name] = Convention(name, _fraction(match.group(2)), None, match.group(0))
    lowered = quotes.lower(source)
    place = re.search(r"gezegen|ay(?:'|’)?(?:da|ın|a)|ay yüzey|mars|jüpiter|venüs|uzay", lowered)
    facts.off_earth = place.group(0) if place else None
    for condition, phrases in IDEALIZATIONS.items():
        for phrase in phrases:
            index = lowered.find(phrase)
            if index >= 0 and not _negated_near(lowered, index, len(phrase)):
                facts.stated[condition] = source[index:index + len(phrase)]
                break
    for condition, phrases in NEGATED_IDEALIZATIONS.items():
        found = next((phrase for phrase in phrases if phrase in lowered), None)
        if found is not None:
            # İkisi birden yazılıysa (yatay düzlem sürtünmesiz, eğik düzlem sürtünmeli) koşul yüzeye özgüdür:
            # yasa düzeyinde "bilinmiyor" olarak değerlendirilir, hiçbiri kesin sayılmaz.
            facts.contradicted[condition] = found
    return facts


def _negated_near(lowered: str, index: int, length: int) -> bool:
    window = lowered[index + length: index + length + 24]
    return bool(re.match(r"\w*\s*(değil|olmayan|olmadığı)", window))


@dataclass(frozen=True)
class ValueChoice:
    """Hesapta kullanılan değer ve kökeni (öğrenciye görünür)."""

    symbol: str
    value: Fraction
    unit: str | None
    origin: str  # problem_convention | standard_constant
    source: str


def gravity(facts: SourceFacts) -> ValueChoice | None:
    """g: önce soru uzlaşımı; yoksa standart yerçekimi ivmesi açıkça işaretlenerek. Dünya dışı ortamda (gezegen, Ay)
    soru değer vermemişse None: değer uydurulmaz, hesap ``unsupported`` kalır."""
    if "g" in facts.conventions:
        item = facts.conventions["g"]
        return ValueChoice("g", item.value, "m/s^2", "problem_convention", item.quote)
    if facts.off_earth:
        return None
    value, unit, source, _ = STANDARD_CONSTANTS["g_n"]
    return ValueChoice("g", value, unit, "standard_constant", source)


def trig_value(facts: SourceFacts, function: str, degrees: Fraction) -> ValueChoice | None:
    """sin/cos değeri: önce uzlaşım; tam değeri bilinen açılarda (0, 30, 90, …) kesin değer; aksi halde None
    (37° ve 53° için soru uzlaşımı yoksa yaklaşık değer uydurulmaz)."""
    key = f"{function}({degrees})"
    if key in facts.conventions:
        item = facts.conventions[key]
        return ValueChoice(key, item.value, None, "problem_convention", item.quote)
    complement = {"sin": "cos", "cos": "sin"}.get(function)
    other = f"{complement}({90 - degrees})" if complement else None
    if other and other in facts.conventions:
        item = facts.conventions[other]
        return ValueChoice(key, item.value, None, "problem_convention", item.quote)
    exact = {("sin", 0): 0, ("sin", 30): Fraction(1, 2), ("sin", 90): 1, ("cos", 0): 1, ("cos", 60): Fraction(1, 2),
             ("cos", 90): 0, ("sin", 180): 0, ("cos", 180): -1}
    value = exact.get((function, int(degrees)) if degrees.denominator == 1 else None)
    if value is None:
        return None
    return ValueChoice(key, Fraction(value), None, "standard_constant", "Tam trigonometrik değer")


def constant(symbol: str) -> ValueChoice | None:
    item = STANDARD_CONSTANTS.get(symbol)
    return ValueChoice(symbol, item[0], item[1], "standard_constant", item[2]) if item else None


def quantity_si(text: str) -> Fraction | None:
    try:
        return parse_quantity(text).si.value
    except (NumberError, UnitError, ValueError):
        return None
