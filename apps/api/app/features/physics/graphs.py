"""Hareket grafiklerinin anlamı (TA-009 §14). Yalnız basılı/açık değerlerden; piksellerden değer uydurulmaz.

- Hız–zaman grafiğinde eğim ivmedir; alan **yer değiştirmedir** (işaretli). Hız işaret değiştiriyorsa **alınan yol**
  |v| alanıdır ve sıfır kesişiminde ayrı hesaplanır. "Alan her zaman yoldur" yanılgısı buradan yakalanır.
- Eğim aralık boyunca değişiyorsa ivme sabit değildir: sabit ivme formülleri (``kinematics.constant_acceleration``)
  bu aralığa uygulanamaz.
- Eksen birimi veya ölçeği bilinmiyorsa hesap yapılmaz (``unsupported``).
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from ..reasoning.units import NumberError, UnitError, parse_number, parse_unit


@dataclass(frozen=True)
class GraphFacts:
    status: str  # ready | unsupported
    reason: str = ""
    displacement: Fraction | None = None
    distance: Fraction | None = None
    slopes: tuple[Fraction, ...] = ()
    constant_slope: bool | None = None


def velocity_time(graph) -> GraphFacts:
    for axis in (graph.x, graph.y):
        if axis.scale != "explicit_linear" or axis.unit is None or axis.unit.status != "parsed":
            return GraphFacts("unsupported", "axis_unit_or_scale_unknown")
    if graph.points_origin != "printed_values" or len(graph.points) < 2:
        return GraphFacts("unsupported", "values_not_printed")
    try:
        ux, uy = parse_unit(graph.x.unit.original), parse_unit(graph.y.unit.original)
        points = [(parse_number(x)[0] * ux.scale, parse_number(y)[0] * uy.scale) for x, y in graph.points]
    except (NumberError, UnitError):
        return GraphFacts("unsupported", "point_unparsed")
    if ux.dim != (0, 0, 1, 0, 0, 0, 0) or uy.dim != (1, 0, -1, 0, 0, 0, 0):
        return GraphFacts("unsupported", "not_velocity_time")
    if [x for x, _ in points] != sorted({x for x, _ in points}):
        return GraphFacts("unsupported", "time_not_increasing")
    displacement, distance, slopes = Fraction(0), Fraction(0), []
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        dt = t1 - t0
        slopes.append((v1 - v0) / dt)
        displacement += (v0 + v1) / 2 * dt
        if v0 * v1 >= 0:
            distance += abs((v0 + v1) / 2 * dt)
        else:  # doğrusal parça sıfırı keser: iki üçgen
            crossing = t0 + dt * abs(v0) / (abs(v0) + abs(v1))
            distance += abs(v0) * (crossing - t0) / 2 + abs(v1) * (t1 - crossing) / 2
    return GraphFacts("ready", "velocity_time", displacement, distance, tuple(slopes), len(set(slopes)) == 1)
