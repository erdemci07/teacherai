"""Birimli skaler formül yerine koyma ve açık grafik/tablo aritmetiği (TA-004).

Formül yalnızca ``integrity.expression`` ağacıyla ayrıştırılır (``eval``/``sympify`` yok). Her sembol
açıkça verilmiş bir niceliğe bağlanmalıdır: kurgusal bir gezegende yer çekimi ivmesi verilmemişse
``g = 9,8`` varsayılmaz, kontrol ``unsupported`` olur. Boyut tutarlılığı fizik yasasının doğru seçildiğini
kanıtlamaz; bu yüzden yalnız boyut uyumu ``partially_checked`` sayılır.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from ..integrity import expression as tree
from .units import (
    DIMENSIONLESS,
    DimensionError,
    NumberError,
    ParsedQuantity,
    Q,
    UnitError,
    parse_number,
    parse_quantity,
    parse_unit,
)

MAX_BINDINGS = 12
MAX_POINTS = 64


@dataclass(frozen=True)
class CheckOutcome:
    outcome: str  # passed | failed | partially_checked | unsupported
    reason: str
    value: Q | None = None
    details: dict = field(default_factory=dict)


class _Unsupported(Exception):
    pass


def _name(node: tree.Sym) -> str:
    return node.name + (f"_{node.sub}" if node.sub else "")


def evaluate(node, bindings: dict[str, Q]) -> Q:
    if isinstance(node, tree.Num):
        return Q(node.value)
    if isinstance(node, tree.Sym):
        key = _name(node)
        if key not in bindings:
            raise _Unsupported(f"missing_quantity:{key}")
        return bindings[key]
    if isinstance(node, tree.Group):
        return evaluate(node.arg, bindings)
    if isinstance(node, tree.Neg):
        return -evaluate(node.arg, bindings)
    if isinstance(node, tree.Mixed):
        return Q(Fraction(node.whole * node.den + node.num, node.den))
    if isinstance(node, tree.Frac):
        return evaluate(node.num, bindings) / evaluate(node.den, bindings)
    if isinstance(node, tree.Bin):
        if node.op == "±":
            raise _Unsupported("plus_minus")
        left, right = evaluate(node.left, bindings), evaluate(node.right, bindings)
        return {"+": left.__add__, "-": left.__sub__, "*": left.__mul__, "/": left.__truediv__}[node.op](right)
    if isinstance(node, tree.Pow):
        exponent = tree.exact_value(node.exp)
        if exponent is None or exponent.denominator != 1:
            raise _Unsupported("non_integer_exponent")
        return evaluate(node.base, bindings).power(int(exponent))
    if isinstance(node, tree.Root):
        if node.index is not None and tree.exact_value(node.index) != 2:
            raise _Unsupported("higher_root")
        return evaluate(node.radicand, bindings).sqrt()
    raise _Unsupported("unsupported_node")


def bind(quantities: dict[str, str]) -> dict[str, Q]:
    """Sembol → "4 m/s²" metni. Ayrıştırılamayan nicelik bağlanmaz (sessizce tahmin edilmez)."""
    if len(quantities) > MAX_BINDINGS:
        raise _Unsupported("binding_budget")
    return {symbol: parse_quantity(text).si for symbol, text in quantities.items()}


def check_formula(formula: str, quantities: dict[str, str], claim: str | None = None) -> CheckOutcome:
    """``sonuç = ifade`` biçimindeki formülü verilen niceliklerle hesaplar ve iddiayla karşılaştırır."""
    parsed = tree.parse(formula)
    if not parsed.parsed or not isinstance(parsed.tree, tree.Rel) or parsed.tree.ops != ("=",):
        return CheckOutcome("unsupported", "formula_unparsed")
    left, right = parsed.tree.operands
    if not isinstance(left, tree.Sym):
        return CheckOutcome("unsupported", "formula_not_explicit")
    try:
        bindings = bind(quantities)
        value = evaluate(right, bindings)
    except _Unsupported as exc:
        return CheckOutcome("unsupported", str(exc).split(":")[0], details={"symbol": str(exc).partition(":")[2]})
    except (UnitError, NumberError) as exc:
        return CheckOutcome("unsupported", getattr(exc, "reason", str(exc)))
    except DimensionError as exc:
        # Formülün kendi içinde boyutça geçersiz bir işlem var (ör. uzunluk + zaman).
        return CheckOutcome("failed", str(exc))
    if claim is None:
        return CheckOutcome("partially_checked", "computed_without_claim", value)
    try:
        claimed = parse_quantity(claim)
    except (UnitError, NumberError) as exc:
        return CheckOutcome("unsupported", getattr(exc, "reason", str(exc)), value)
    return compare_claim(value, claimed)


def compare_claim(value: Q, claimed: ParsedQuantity) -> CheckOutcome:
    if claimed.unit.affine:
        return CheckOutcome("unsupported", "affine_unit", value)
    if claimed.unit.dim != value.dim:
        return CheckOutcome("failed", "dimension_mismatch", value)
    target = claimed.si.value
    margin = Fraction(1, 2) * Fraction(1, 10**claimed.decimals) * claimed.unit.scale
    if not value.exact:
        margin = max(margin, abs(value.value) * Fraction(1, 10**12))
    if abs(value.value - target) <= margin:
        return CheckOutcome("passed", "value_matches_claim", value)
    return CheckOutcome("failed", "value_mismatch", value)


def check_dimensions(formula: str, units: dict[str, str]) -> CheckOutcome:
    """Yalnız boyut tutarlılığı: ``v = a t`` için a ve t'nin birimleri, v'nin birimi verilir."""
    parsed = tree.parse(formula)
    if not parsed.parsed or not isinstance(parsed.tree, tree.Rel) or parsed.tree.ops != ("=",):
        return CheckOutcome("unsupported", "formula_unparsed")
    try:
        bindings = {symbol: Q(Fraction(1), parse_unit(text).dim) for symbol, text in units.items()}
        left = evaluate(parsed.tree.operands[0], bindings)
        right = evaluate(parsed.tree.operands[1], bindings)
    except _Unsupported as exc:
        return CheckOutcome("unsupported", str(exc).split(":")[0])
    except UnitError as exc:
        return CheckOutcome("unsupported", exc.reason)
    except DimensionError as exc:
        return CheckOutcome("failed", str(exc))
    if left.dim != right.dim:
        return CheckOutcome("failed", "dimension_mismatch")
    # Boyut uyumu yasanın doğru olduğunu göstermez.
    return CheckOutcome("partially_checked", "dimensions_consistent")


def add_quantities(left: str, right: str) -> CheckOutcome:
    try:
        a, b = parse_quantity(left), parse_quantity(right)
        if a.unit.affine or b.unit.affine:
            return CheckOutcome("unsupported", "affine_unit")
        return CheckOutcome("passed", "compatible_addition", a.si + b.si)
    except DimensionError as exc:
        return CheckOutcome("failed", str(exc))
    except (UnitError, NumberError) as exc:
        return CheckOutcome("unsupported", getattr(exc, "reason", str(exc)))


# --------------------------------------------------------------------------- grafik ve tablo


def _series(points: list[list[str]]) -> list[tuple[Fraction, Fraction]]:
    if not 2 <= len(points) <= MAX_POINTS:
        raise _Unsupported("point_budget")
    values = [(parse_number(x)[0], parse_number(y)[0]) for x, y in points]
    xs = [x for x, _ in values]
    if xs != sorted(set(xs)):
        raise _Unsupported("non_monotonic_x")
    return values


def _axes_ready(graph) -> str | None:
    for axis in (graph.x, graph.y):
        if axis.scale != "explicit_linear":
            return "unknown_scale"
        if axis.unit is None or axis.unit.status != "parsed":
            return "unknown_unit"
    if graph.points_origin != "printed_values" or not graph.points:
        return "values_not_printed"
    return None


def graph_slope(graph, start: int, end: int) -> CheckOutcome:
    """İki açık nokta arasındaki eğim (ör. hız-zaman grafiğinde ivme)."""
    missing = _axes_ready(graph)
    if missing:
        return CheckOutcome("unsupported", missing)
    try:
        values = _series(graph.points)
        (x0, y0), (x1, y1) = values[start], values[end]
    except (_Unsupported, NumberError, IndexError) as exc:
        return CheckOutcome("unsupported", str(exc) or "point_missing")
    ux, uy = parse_unit(graph.x.unit.original), parse_unit(graph.y.unit.original)
    dim = tuple(a - b for a, b in zip(uy.dim, ux.dim))
    return CheckOutcome("passed", "slope_computed", Q((y1 - y0) * uy.scale / ((x1 - x0) * ux.scale), dim))  # type: ignore[arg-type]


def graph_area(graph) -> CheckOutcome:
    """Parçalı doğrusal açık noktaların altındaki alan (ör. hız-zaman grafiğinde yer değiştirme)."""
    missing = _axes_ready(graph)
    if missing:
        return CheckOutcome("unsupported", missing)
    try:
        values = _series(graph.points)
    except (_Unsupported, NumberError) as exc:
        return CheckOutcome("unsupported", str(exc))
    ux, uy = parse_unit(graph.x.unit.original), parse_unit(graph.y.unit.original)
    area = sum(((x1 - x0) * (y0 + y1) / 2 for (x0, y0), (x1, y1) in zip(values, values[1:])), Fraction(0))
    dim = tuple(a + b for a, b in zip(uy.dim, ux.dim))
    return CheckOutcome("passed", "area_computed", Q(area * ux.scale * uy.scale, dim))  # type: ignore[arg-type]


def trend(values: list[Fraction]) -> str:
    if len(values) < 2:
        return "insufficient"
    pairs = list(zip(values, values[1:]))
    if all(b > a for a, b in pairs):
        return "increases"
    if all(b < a for a, b in pairs):
        return "decreases"
    if all(b == a for a, b in pairs):
        return "no_change"
    return "mixed"


def table_column(table, header: str) -> tuple[list[Fraction | None], str | None]:
    """Başlıkla sütun değerleri ve birimi. Eksik hücre None kalır, uydurulmaz."""
    if table.headers.count(header) != 1:
        raise _Unsupported("unknown_column")
    index = table.headers.index(header)
    unit = table.units[index].original if table.units and table.units[index] is not None else None
    values: list[Fraction | None] = []
    for row in table.rows:
        cell = row[index]
        values.append(parse_number(cell)[0] if cell is not None else None)
    return values, unit


def dimensionless(value: Q) -> bool:
    return value.dim == DIMENSIONLESS
