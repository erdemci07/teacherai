"""Sınırlı birim ayrıştırıcısı, boyut ve kesin nicelik aritmetiği (TA-004).

Belgelenmiş alt küme: m, km, cm, mm, s, ms, min, h, kg, g, mg, N, kN, J, kJ, W, kW, Pa, kPa, Hz, mol,
mmol, L, mL, K, °C, A, V, Ω, µg ve bunların çarpım/bölüm/tam sayı üsleriyle birleşimleri (m/s, m·s⁻¹, m/s²,
mol/L, J/(mol·K)). Genel önek kuralı yoktur; her sembol tabloda açıkça tanımlıdır.

- ``C`` (coulomb, karbon, Celsius), ``M`` (molar, mega) ve ``l`` (litre, 1) belirsizdir; tahmin edilmez.
- Kimyasal element sembolleri (``Co``, ``Na``) birim değildir ve ``unsupported`` kalır.
- °C ötelemeli (affine) bir ölçektir: K ile toplama ve dönüştürme genel kuralla yapılmaz.
- Kütle (kg) ile ağırlık (N) farklı boyuttadır; birbirine dönüştürülmez.
- Ondalık ayırıcı ve binlik ayırıcı karışabiliyorsa (``1,250``, ``1.000``) değer belirsizdir.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from decimal import Decimal, getcontext
from fractions import Fraction

from ..education.science import UnitSpec

Dim = tuple[int, int, int, int, int, int, int]  # L M T I Θ N J
DIMENSIONLESS: Dim = (0, 0, 0, 0, 0, 0, 0)
MAX_UNIT_CHARS = 40
MAX_FACTORS = 6
MAX_EXPONENT = 4
MAX_DIGITS = 15


def _d(**powers) -> Dim:
    order = ("L", "M", "T", "I", "Th", "N", "J")
    return tuple(powers.get(key, 0) for key in order)  # type: ignore[return-value]


# sembol → (SI ölçeği, boyut, ötelemeli)
UNITS: dict[str, tuple[Fraction, Dim, bool]] = {
    "m": (Fraction(1), _d(L=1), False),
    "km": (Fraction(1000), _d(L=1), False),
    "cm": (Fraction(1, 100), _d(L=1), False),
    "mm": (Fraction(1, 1000), _d(L=1), False),
    "s": (Fraction(1), _d(T=1), False),
    "ms": (Fraction(1, 1000), _d(T=1), False),
    "min": (Fraction(60), _d(T=1), False),
    "h": (Fraction(3600), _d(T=1), False),
    "kg": (Fraction(1), _d(M=1), False),
    "g": (Fraction(1, 1000), _d(M=1), False),
    "mg": (Fraction(1, 10**6), _d(M=1), False),
    "N": (Fraction(1), _d(M=1, L=1, T=-2), False),
    "kN": (Fraction(1000), _d(M=1, L=1, T=-2), False),
    "J": (Fraction(1), _d(M=1, L=2, T=-2), False),
    "kJ": (Fraction(1000), _d(M=1, L=2, T=-2), False),
    "W": (Fraction(1), _d(M=1, L=2, T=-3), False),
    "kW": (Fraction(1000), _d(M=1, L=2, T=-3), False),
    "Pa": (Fraction(1), _d(M=1, L=-1, T=-2), False),
    "kPa": (Fraction(1000), _d(M=1, L=-1, T=-2), False),
    "Hz": (Fraction(1), _d(T=-1), False),
    "mol": (Fraction(1), _d(N=1), False),
    "mmol": (Fraction(1, 1000), _d(N=1), False),
    "L": (Fraction(1, 1000), _d(L=3), False),
    "mL": (Fraction(1, 10**6), _d(L=3), False),
    "K": (Fraction(1), _d(Th=1), False),
    "°C": (Fraction(1), _d(Th=1), True),
    "A": (Fraction(1), _d(I=1), False),
    "V": (Fraction(1), _d(M=1, L=2, T=-3, I=-1), False),
    "Ω": (Fraction(1), _d(M=1, L=2, T=-3, I=-2), False),
    "µg": (Fraction(1, 10**9), _d(M=1), False),
}
ALIASES = {"sn": "s", "dk": "min", "ℓ": "L", "ºC": "°C", "℃": "°C", "lt": "L", "ohm": "Ω", "μg": "µg"}
AMBIGUOUS = {"C", "M", "l"}
_SYMBOLS = sorted(list(UNITS) + list(ALIASES) + list(AMBIGUOUS), key=len, reverse=True)
_SUPERSCRIPT = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")


class UnitError(ValueError):
    def __init__(self, status: str, reason: str):
        super().__init__(reason)
        self.status = status
        self.reason = reason


@dataclass(frozen=True)
class Unit:
    original: str
    scale: Fraction
    dim: Dim
    affine: bool
    factors: tuple[tuple[str, int], ...]
    aliased: bool

    @property
    def canonical(self) -> str:
        if not self.factors:
            return "1"
        return "·".join(symbol if power == 1 else f"{symbol}^{power}" for symbol, power in self.factors)

    def spec(self) -> UnitSpec:
        return UnitSpec(
            original=self.original[:256], status="parsed", canonical=self.canonical, dimension=list(self.dim),
            scale=_ratio_text(self.scale), affine=self.affine, normalization="alias" if self.aliased else "none",
        )


def _ratio_text(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def unit_spec(text: str) -> UnitSpec:
    """Ayrıştırılamayan veya belirsiz birim de özgün yazımıyla korunur."""
    try:
        return parse_unit(text).spec()
    except UnitError as exc:
        return UnitSpec(original=(text.strip() or "?")[:256], status="ambiguous" if exc.status == "ambiguous" else "unsupported")


def parse_unit(text: str) -> Unit:
    source = text.strip()
    if not source:
        return Unit("", Fraction(1), DIMENSIONLESS, False, (), False)
    if len(source) > MAX_UNIT_CHARS:
        raise UnitError("unsupported", "unit_too_long")
    normalized = source.translate(_SUPERSCRIPT)
    normalized = re.sub(r"\^\{\s*(-?\d+)\s*\}", r"^\1", normalized)
    parser = _UnitParser(normalized)
    factors, aliased = parser.parse()
    combined: dict[str, int] = {}
    for symbol, power in factors:
        combined[symbol] = combined.get(symbol, 0) + power
    items = tuple((symbol, power) for symbol, power in combined.items() if power)
    if len(items) > MAX_FACTORS:
        raise UnitError("unsupported", "unit_budget")
    affine = any(UNITS[symbol][2] for symbol, _ in items)
    if affine and items != (("°C", 1),):
        raise UnitError("unsupported", "affine_unit_in_compound")
    scale, dim = Fraction(1), [0] * 7
    for symbol, power in items:
        unit_scale, unit_dim, _ = UNITS[symbol]
        scale *= unit_scale ** power
        dim = [a + b * power for a, b in zip(dim, unit_dim)]
    return Unit(source, scale, tuple(dim), affine, tuple(sorted(items, key=_order)), aliased)  # type: ignore[arg-type]


def _order(item: tuple[str, int]) -> tuple[int, str]:
    return (0 if item[1] > 0 else 1, item[0])


class _UnitParser:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.aliased = False
        self.depth = 0

    def parse(self) -> tuple[list[tuple[str, int]], bool]:
        factors = self._sequence()
        self._space()
        if self.pos != len(self.text):
            raise UnitError("unsupported", "unexpected_character")
        return factors, self.aliased

    def _space(self):
        while self.pos < len(self.text) and self.text[self.pos] == " ":
            self.pos += 1

    def _sequence(self) -> list[tuple[str, int]]:
        factors = self._factor(1)
        while True:
            self._space()
            if self.pos >= len(self.text) or self.text[self.pos] == ")":
                return factors
            char = self.text[self.pos]
            if char in "·⋅*.":
                self.pos += 1
                factors += self._factor(1)
            elif char == "/":
                self.pos += 1
                factors += self._factor(-1)
            else:
                factors += self._factor(1)
            if len(factors) > MAX_FACTORS * 2:
                raise UnitError("unsupported", "unit_budget")

    def _factor(self, sign: int) -> list[tuple[str, int]]:
        self._space()
        if self.pos < len(self.text) and self.text[self.pos] == "(":
            self.depth += 1
            if self.depth > 2:
                raise UnitError("unsupported", "unit_depth")
            self.pos += 1
            inner = self._sequence()
            if self.pos >= len(self.text) or self.text[self.pos] != ")":
                raise UnitError("unsupported", "unbalanced_parenthesis")
            self.pos += 1
            self.depth -= 1
            power = self._exponent()
            return [(symbol, value * power * sign) for symbol, value in inner]
        for candidate in _SYMBOLS:
            end = self.pos + len(candidate)
            if self.text.startswith(candidate, self.pos) and not (end < len(self.text) and self.text[end].isalpha()):
                self.pos = end
                if candidate in AMBIGUOUS:
                    raise UnitError("ambiguous", "ambiguous_symbol")
                symbol = ALIASES.get(candidate, candidate)
                self.aliased = self.aliased or symbol != candidate
                return [(symbol, self._exponent() * sign)]
        raise UnitError("unsupported", "unknown_symbol")

    def _exponent(self) -> int:
        match = re.match(r"\s*\^?\s*([-+]?\d+)", self.text[self.pos:]) if self.pos < len(self.text) and (
            self.text[self.pos] == "^" or self.text[self.pos] in "-+0123456789") else None
        if not match:
            return 1
        value = int(match.group(1))
        if value == 0 or abs(value) > MAX_EXPONENT:
            raise UnitError("unsupported", "exponent_budget")
        self.pos += match.end()
        return value


# --------------------------------------------------------------------------- sayılar


class NumberError(ValueError):
    pass


_NUMBER = re.compile(
    r"^\s*(?P<sign>[-−+]?)\s*(?P<mantissa>\d+(?:[.,]\d+)?)\s*"
    r"(?:(?:×|x|·|\*|\\times|\\cdot)\s*10\s*(?:\^\s*\{?\s*(?P<exp>[-−+]?\d+)\s*\}?|(?P<sup>[⁻⁺]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+)))?\s*"
)


_POWER = re.compile(
    r"^\s*(?P<sign>[-−+]?)\s*10\s*(?:\^\s*\{?\s*(?P<exp>[-−+]?\d+)\s*\}?|(?P<sup>[⁻⁺]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+))\s*"
)


def _match_number(text: str):
    """Yalın on kuvveti (10⁻³, 10^3) üs işaretiyle birlikte korunur; 10⁻³ ile 10³ karışmaz."""
    return _POWER.match(text) or _NUMBER.match(text)


def parse_number(text: str) -> tuple[Fraction, int, int]:
    """(değer, anlamlı basamak, ondalık basamak). Binlik/ondalık karışabiliyorsa NumberError."""
    match = _match_number(text)
    if not match:
        raise NumberError("not_a_number")
    mantissa = match.groupdict().get("mantissa") or "1"
    if len(re.sub(r"\D", "", mantissa)) > MAX_DIGITS:
        raise NumberError("digit_budget")
    separator = next((char for char in mantissa if char in ".,"), None)
    decimals = 0
    if separator:
        whole, fraction = mantissa.split(separator)
        # "1,250" binlik mi ondalık mı belirsizdir; "0,002" ise binlik ayırıcıyla yazılamaz.
        if len(fraction) == 3 and whole.lstrip("-") != "0" and match.group("exp") is None and match.group("sup") is None:
            raise NumberError("ambiguous_separator")
        decimals = len(fraction)
        value = Fraction(int(whole + fraction), 10**decimals)
    else:
        value = Fraction(int(mantissa))
    digits = re.sub(r"\D", "", mantissa).lstrip("0") or "0"
    exponent_text = match.group("exp") or (match.group("sup") or "").translate(_SUPERSCRIPT)
    if exponent_text:
        exponent = int(exponent_text.replace("−", "-"))
        if abs(exponent) > 30:
            raise NumberError("exponent_budget")
        value *= Fraction(10) ** exponent
        decimals = max(0, decimals - exponent)
    if match.group("sign") in ("-", "−"):
        value = -value
    return value, len(digits), decimals


# --------------------------------------------------------------------------- nicelik


class DimensionError(ValueError):
    pass


@dataclass(frozen=True)
class Q:
    """SI değerinde kesin (veya işaretli yaklaşık) nicelik."""

    value: Fraction
    dim: Dim = DIMENSIONLESS
    exact: bool = True

    def __add__(self, other: Q) -> Q:
        if self.dim != other.dim:
            raise DimensionError("incompatible_addition")
        return Q(self.value + other.value, self.dim, self.exact and other.exact)

    def __sub__(self, other: Q) -> Q:
        if self.dim != other.dim:
            raise DimensionError("incompatible_addition")
        return Q(self.value - other.value, self.dim, self.exact and other.exact)

    def __mul__(self, other: Q) -> Q:
        return Q(self.value * other.value, tuple(a + b for a, b in zip(self.dim, other.dim)), self.exact and other.exact)  # type: ignore[arg-type]

    def __truediv__(self, other: Q) -> Q:
        if other.value == 0:
            raise DimensionError("division_by_zero")
        return Q(self.value / other.value, tuple(a - b for a, b in zip(self.dim, other.dim)), self.exact and other.exact)  # type: ignore[arg-type]

    def __neg__(self) -> Q:
        return Q(-self.value, self.dim, self.exact)

    def power(self, exponent: int) -> Q:
        if abs(exponent) > MAX_EXPONENT * 2:
            raise DimensionError("exponent_budget")
        if self.value == 0 and exponent < 0:
            raise DimensionError("division_by_zero")
        return Q(self.value ** exponent, tuple(a * exponent for a in self.dim), self.exact)  # type: ignore[arg-type]

    def sqrt(self) -> Q:
        if any(a % 2 for a in self.dim):
            raise DimensionError("odd_dimension_root")
        if self.value < 0:
            raise DimensionError("negative_root")
        dim = tuple(a // 2 for a in self.dim)
        num, den = _isqrt_exact(self.value.numerator), _isqrt_exact(self.value.denominator)
        if num is not None and den is not None:
            return Q(Fraction(num, den), dim, self.exact)  # type: ignore[arg-type]
        getcontext().prec = 40
        root = (Decimal(self.value.numerator) / Decimal(self.value.denominator)).sqrt()
        return Q(Fraction(root), dim, False)  # type: ignore[arg-type]


def _isqrt_exact(value: int) -> int | None:
    root = math.isqrt(value)
    return root if root * root == value else None


def quantity(value: Fraction, unit: Unit) -> Q:
    if unit.affine:
        raise DimensionError("affine_unit")
    return Q(value * unit.scale, unit.dim)


@dataclass(frozen=True)
class ParsedQuantity:
    original: str
    value: Fraction
    unit: Unit
    significant_digits: int
    decimals: int

    @property
    def si(self) -> Q:
        return quantity(self.value, self.unit)


def parse_quantity(text: str) -> ParsedQuantity:
    source = text.strip()
    match = _match_number(source)
    if not match:
        raise NumberError("not_a_number")
    value, digits, decimals = parse_number(source)
    unit = parse_unit(source[match.end():])
    return ParsedQuantity(source, value, unit, digits, decimals)


def convert(quantity_text: str, target_unit: str) -> Fraction:
    """Tanımlı doğrusal dönüşüm. Farklı boyut veya ötelemeli ölçek için hata."""
    parsed = parse_quantity(quantity_text)
    target = parse_unit(target_unit)
    if parsed.unit.affine or target.affine:
        raise DimensionError("affine_unit")
    if parsed.unit.dim != target.dim:
        raise DimensionError("incompatible_dimensions")
    return parsed.value * parsed.unit.scale / target.scale


def same_dimension(left: str, right: str) -> bool:
    return parse_unit(left).dim == parse_unit(right).dim


def equivalent_units(left: str, right: str) -> bool:
    a, b = parse_unit(left), parse_unit(right)
    return a.dim == b.dim and a.scale == b.scale and a.affine == b.affine


def tolerance(decimals: int, unit: Unit) -> Fraction:
    """Bir iddianın yazılı hassasiyetine göre yarım basamak payı (SI cinsinden)."""
    return Fraction(1, 2) * Fraction(1, 10**decimals) * unit.scale
