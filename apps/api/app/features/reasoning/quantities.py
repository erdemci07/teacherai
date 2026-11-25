"""Türlü nicelik karşılaştırması (TA-009 §3.3, §13). Saf Python; matematik ve fizik aynı mekanizmayı kullanır.

Eşit sayılar eşit fiziksel cevap demek değildir. Karşılaştırma sırası ve her adımın ayrı nedeni vardır:

1. **Kimlik:** aynı cisim/sistem (``entity``) ve aynı an/durum (``state``: ilk, son, en büyük, t = 2 s).
2. **Tür:** sürat ≠ hız (vektör), kütle ≠ ağırlık, enerji ≠ tork, güç ≠ enerji, akım ≠ yük. Aynı boyutlu farklı
   türler (enerji ve tork: N·m) birim eşitliğiyle eşleşmez.
3. **Boyut** (m/s ≠ m/s²) ve **birim dönüşümü** (5 m ≠ 5 km; 72 km/h = 20 m/s).
4. **Gösterim:** büyüklük (işaretsiz) ile işaretli bileşen ve yön ayrıdır. Büyüklük istenip negatif değer verilirse
   veya bileşenin işareti tersse eşleşme yoktur.
5. **Değer** ve yaklaşım politikası: kesin, iddianın yazılı hassasiyeti veya hedefe özgü bağıl tolerans.

Sonuç ``match``, ``mismatch`` veya ``undecidable`` (bilgi eksik; asla eşleşme sayılmaz).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction

from .units import DIMENSIONLESS, Dim, NumberError, Unit, UnitError, parse_number, parse_unit


@dataclass(frozen=True)
class Kind:
    dim: Dim
    vector: bool
    family: str
    magnitude: bool = False  # tanımı gereği negatif olamaz (sürat, alınan yol, kütle, ağırlık büyüklüğü)


def _dim(L=0, M=0, T=0, I=0, Th=0, N=0, J=0) -> Dim:  # noqa: E741, N803
    return (L, M, T, I, Th, N, J)


KINDS: dict[str, Kind] = {
    "length": Kind(_dim(L=1), False, "length", True),
    "distance": Kind(_dim(L=1), False, "length", True),
    "height": Kind(_dim(L=1), False, "length", True),
    "displacement": Kind(_dim(L=1), True, "displacement"),
    "position": Kind(_dim(L=1), True, "position"),
    "time": Kind(_dim(T=1), False, "time", True),
    "period": Kind(_dim(T=1), False, "time", True),
    "frequency": Kind(_dim(T=-1), False, "frequency", True),
    "speed": Kind(_dim(L=1, T=-1), False, "speed", True),
    "velocity": Kind(_dim(L=1, T=-1), True, "velocity"),
    "acceleration": Kind(_dim(L=1, T=-2), True, "acceleration"),
    "acceleration_magnitude": Kind(_dim(L=1, T=-2), False, "acceleration", True),
    "mass": Kind(_dim(M=1), False, "mass", True),
    "weight": Kind(_dim(M=1, L=1, T=-2), False, "weight", True),
    "force": Kind(_dim(M=1, L=1, T=-2), True, "force"),
    "net_force": Kind(_dim(M=1, L=1, T=-2), True, "force"),
    "tension": Kind(_dim(M=1, L=1, T=-2), False, "force", True),
    "normal_force": Kind(_dim(M=1, L=1, T=-2), False, "force", True),
    "friction_force": Kind(_dim(M=1, L=1, T=-2), False, "force", True),
    "energy": Kind(_dim(M=1, L=2, T=-2), False, "energy"),
    "kinetic_energy": Kind(_dim(M=1, L=2, T=-2), False, "energy", True),
    "potential_energy": Kind(_dim(M=1, L=2, T=-2), False, "energy"),
    "mechanical_energy": Kind(_dim(M=1, L=2, T=-2), False, "energy"),
    "work": Kind(_dim(M=1, L=2, T=-2), False, "energy"),
    "heat": Kind(_dim(M=1, L=2, T=-2), False, "energy"),
    "torque": Kind(_dim(M=1, L=2, T=-2), True, "torque"),
    "power": Kind(_dim(M=1, L=2, T=-3), False, "power"),
    "momentum": Kind(_dim(M=1, L=1, T=-1), True, "momentum"),
    "impulse": Kind(_dim(M=1, L=1, T=-1), True, "momentum"),
    "pressure": Kind(_dim(M=1, L=-1, T=-2), False, "pressure"),
    "density": Kind(_dim(M=1, L=-3), False, "density", True),
    "charge": Kind(_dim(T=1, I=1), False, "charge"),
    "current": Kind(_dim(I=1), False, "current"),
    "voltage": Kind(_dim(M=1, L=2, T=-3, I=-1), False, "voltage"),
    "emf": Kind(_dim(M=1, L=2, T=-3, I=-1), False, "voltage"),
    "resistance": Kind(_dim(M=1, L=2, T=-3, I=-2), False, "resistance", True),
    "capacitance": Kind(_dim(M=-1, L=-2, T=4, I=2), False, "capacitance", True),
    "electric_field": Kind(_dim(M=1, L=1, T=-3, I=-1), True, "electric_field"),
    "temperature": Kind(_dim(Th=1), False, "temperature"),
    "angle": Kind(DIMENSIONLESS, False, "angle"),
    "ratio": Kind(DIMENSIONLESS, False, "ratio"),
    "efficiency": Kind(DIMENSIONLESS, False, "ratio", True),
    "count": Kind(DIMENSIONLESS, False, "count", True),
}
TURKISH_KIND = {
    "sürat": "speed", "hız": "velocity", "ivme": "acceleration", "kütle": "mass", "ağırlık": "weight",
    "kuvvet": "force", "net kuvvet": "net_force", "gerilme": "tension", "ip gerilmesi": "tension",
    "tepki kuvveti": "normal_force", "sürtünme kuvveti": "friction_force", "enerji": "energy",
    "kinetik enerji": "kinetic_energy", "potansiyel enerji": "potential_energy", "iş": "work", "tork": "torque",
    "güç": "power", "momentum": "momentum", "itme": "impulse", "basınç": "pressure", "özkütle": "density",
    "yük": "charge", "akım": "current", "potansiyel fark": "voltage", "gerilim": "voltage", "direnç": "resistance",
    "yer değiştirme": "displacement", "alınan yol": "distance", "yol": "distance", "zaman": "time", "süre": "time",
    "periyot": "period", "frekans": "frequency", "yükseklik": "height", "sığa": "capacitance",
}
DIRECTIONS = {"sağa": "+x", "sağ": "+x", "doğu": "+x", "sola": "-x", "sol": "-x", "batı": "-x", "yukarı": "+y",
              "yukarıya": "+y", "kuzey": "+y", "aşağı": "-y", "aşağıya": "-y", "güney": "-y", "+x": "+x", "-x": "-x",
              "+y": "+y", "-y": "-y"}


@dataclass(frozen=True)
class Typed:
    """SI değerli, türü ve kimliği belli nicelik. ``value`` işaretlidir; yön ayrıca tutulur."""

    value: Fraction | None
    dim: Dim | None
    kind: str | None = None
    representation: str = "unspecified"  # magnitude | component | unspecified
    direction: str | None = None  # +x, -x, +y, -y (eksen önce sabitlenmiş olmalı)
    entity: str | None = None
    state: str | None = None
    unit: Unit | None = None
    decimals: int | None = None  # iddianın yazılı ondalık basamağı (hassasiyet)
    exact: bool = True


@dataclass(frozen=True)
class Policy:
    """Yaklaşım politikası: ``exact`` | ``claim_precision`` (yazılı son basamağın yarısı) | ``relative``."""

    mode: str = "claim_precision"
    relative: Fraction = Fraction(1, 100)
    unit_when_missing: Unit | None = None  # soru "kaç m/s'dir?" diye birimi zaten sabitlemişse
    require_direction: bool = False


@dataclass(frozen=True)
class Comparison:
    status: str  # match | mismatch | undecidable
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def matched(self) -> bool:
        return self.status == "match"


def kind_compatible(expected: str | None, claimed: str | None) -> bool | None:
    """Aynı tür veya aynı ailede genel/özel tür (kinetik enerji ↔ enerji). Bilinmeyen tür için None."""
    if expected is None or claimed is None:
        return None
    if expected == claimed:
        return True
    a, b = KINDS.get(expected), KINDS.get(claimed)
    if a is None or b is None:
        return None
    if a.family != b.family:
        return False
    generic = {"energy", "force", "acceleration", "length", "time", "voltage", "momentum"}
    return expected in generic or claimed in generic


def compare(expected: Typed, claimed: Typed, policy: Policy | None = None) -> Comparison:
    policy = policy or Policy()
    if expected.entity and claimed.entity and expected.entity != claimed.entity:
        return Comparison("mismatch", ("entity_mismatch",))
    if expected.state and claimed.state and expected.state != claimed.state:
        return Comparison("mismatch", ("state_mismatch",))
    compatible = kind_compatible(expected.kind, claimed.kind)
    if compatible is False:
        return Comparison("mismatch", ("kind_mismatch",))
    claimed_dim = claimed.dim
    if claimed_dim is None and policy.unit_when_missing is not None:
        claimed_dim = policy.unit_when_missing.dim
    if expected.dim is not None and claimed_dim is not None and expected.dim != claimed_dim:
        return Comparison("mismatch", ("dimension_mismatch",))
    if expected.dim is not None and expected.dim != DIMENSIONLESS and claimed.dim is None and policy.unit_when_missing is None:
        return Comparison("undecidable", ("unit_missing",))
    if expected.value is None or claimed.value is None:
        return Comparison("undecidable", ("value_missing",))
    claimed_value = claimed.value
    if claimed.dim is None and policy.unit_when_missing is not None:
        claimed_value = claimed.value * policy.unit_when_missing.scale
    kind = KINDS.get(expected.kind or "")
    magnitude = (kind is not None and kind.magnitude) or expected.representation == "magnitude"
    if magnitude and claimed_value < 0:
        return Comparison("mismatch", ("negative_magnitude",))
    if expected.representation == "component" and expected.value != 0 and claimed_value != 0 and \
            (expected.value > 0) != (claimed_value > 0):
        return Comparison("mismatch", ("sign_mismatch",))
    if expected.direction and claimed.direction and expected.direction != claimed.direction:
        return Comparison("mismatch", ("direction_mismatch",))
    if policy.require_direction and expected.direction and not claimed.direction:
        return Comparison("undecidable", ("direction_missing",))
    target = abs(expected.value) if magnitude or (claimed.direction and expected.direction) else expected.value
    got = abs(claimed_value) if claimed.direction and expected.direction else claimed_value
    if not _close(target, got, claimed, policy, expected.exact):
        return Comparison("mismatch", ("value_mismatch",))
    return Comparison("match", ())


def _close(expected: Fraction, got: Fraction, claimed: Typed, policy: Policy, exact: bool) -> bool:
    if policy.mode == "exact" and exact:
        return expected == got
    if policy.mode == "relative":
        return abs(expected - got) <= abs(expected) * policy.relative if expected else got == 0
    scale = claimed.unit.scale if claimed.unit is not None else (
        policy.unit_when_missing.scale if policy.unit_when_missing is not None else Fraction(1))
    decimals = claimed.decimals if claimed.decimals is not None else 0
    margin = Fraction(1, 2) * Fraction(1, 10**decimals) * scale
    if not exact:
        margin = max(margin, abs(expected) * Fraction(1, 10**9))
    return abs(expected - got) <= margin


# --------------------------------------------------------------------------- iddia ayrıştırma

_LATEX_FRAC = re.compile(r"^\s*(-?)\s*\\(?:d|t)?frac\{\s*(\d+)\s*\}\{\s*(\d+)\s*\}")
_TEXT_WRAP = re.compile(r"\\(?:text|mathrm|operatorname)\{([^}]*)\}")


@dataclass(frozen=True)
class ParsedClaim:
    symbol: str | None
    typed: Typed
    original: str


def parse_claim(text: str, symbol_kinds: dict[str, str] | None = None) -> ParsedClaim | None:
    """``v = 12 m/s``, ``12 m/s (sağa)``, ``-3 m/s``, ``5 km``, ``\\frac{3}{2} m``, ``70°``. Ayrıştırılamazsa None.

    Tür yalnız açık sembol (``a = …`` ve model sembol tablosu) veya Türkçe nicelik adından çıkarılır; birimden tür
    tahmin edilmez (J ile N·m aynı boyuttadır)."""
    raw = _TEXT_WRAP.sub(r" \1 ", text or "").replace("\\,", " ").replace("\\;", " ").replace("~", " ")
    raw = raw.replace("\\cdot", "·").replace("\\times", "×").replace("{", "").replace("}", "").strip()
    symbol, body = None, raw
    if "=" in raw:
        left, _, body = raw.rpartition("=")
        symbol = left.strip() or None
    direction = None
    lowered = body.replace("İ", "i").replace("I", "ı").lower()
    for word, axis in DIRECTIONS.items():
        if re.search(rf"(?<![\w+-]){re.escape(word)}(?!\w)", lowered):
            direction = axis
            body = re.sub(rf"\(?\s*{re.escape(word)}\w*\s*(?:doğru|yönünde|yönlü)?\s*\)?", " ", body, flags=re.IGNORECASE)
            break
    kind = None
    if symbol and symbol_kinds and symbol in symbol_kinds:
        kind = symbol_kinds[symbol]
    for name, mapped in sorted(TURKISH_KIND.items(), key=lambda item: -len(item[0])):
        if symbol and symbol.lower() == name:
            kind = mapped
    body = body.strip()
    angle = re.search(r"(\^\s*\\?circ|°|\bderece\b)\s*$", body)
    if angle:
        body = body[: angle.start()].strip()
    fraction = _LATEX_FRAC.match(body)
    try:
        if fraction:
            value = Fraction(int(fraction.group(2)), int(fraction.group(3)))
            value = -value if fraction.group(1) else value
            decimals, rest = 0, body[fraction.end():]
        else:
            match = re.match(r"^\s*[-−+]?\s*\d+(?:[.,]\d+)?(?:\s*(?:×|x|·|\*)\s*10\s*\^\s*[-−+]?\d+)?", body)
            if not match:
                return None
            value, _, decimals = parse_number(match.group(0))
            rest = body[match.end():]
        unit_text = rest.strip().strip("()").strip()
        unit = parse_unit(unit_text) if unit_text else None
    except (NumberError, UnitError, ValueError, ZeroDivisionError):
        return None
    if angle:
        return ParsedClaim(symbol, Typed(value, DIMENSIONLESS, kind or "angle", direction=direction, decimals=decimals),
                           text)
    if unit is not None and unit.affine:
        return None
    si = value * unit.scale if unit is not None else value
    typed = Typed(si, unit.dim if unit is not None else None, kind, direction=direction, unit=unit, decimals=decimals)
    return ParsedClaim(symbol, typed, text)


def from_si(value: Fraction, kind: str, **identity) -> Typed:
    """Belirlenimci çözümden beklenen nicelik."""
    spec = KINDS.get(kind)
    return Typed(value, spec.dim if spec else None, kind, **identity)
