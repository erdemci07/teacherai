"""Trigonometri (TA-008 §17). Yalnız yalıtılmış işçide çalışır.

Derece ve radyan her zaman ayrıdır; birim belirtilmeden açı sayısı yorumlanmaz. Denklem çözümü verilen aralıkla
sınırlanır ve periyodik kökler kaybolmaz; aralık verilmezse genel çözüm ``conditional`` (periyodik) kalır.
Özdeşlik sadeleştirmeden önce özgün ifadenin tanım kümesi (ör. tan'ın tanımsız olduğu açılar) korunur.
"""

from __future__ import annotations

import sympy as sp
from sympy.functions.elementary.trigonometric import TrigonometricFunction

from . import expr, sets

UNITS = ("degree", "radian")
MAX_ROOTS = 64


def to_radians(value, unit: str):
    if unit not in UNITS:
        raise expr.ExprError("angle_unit_unknown")
    return value * sp.pi / 180 if unit == "degree" else value


def exact_value(function: str, angle, unit: str):
    """Standart açılarda kesin değer; tanımsızsa ExprError (ör. tan 90°)."""
    radians = to_radians(sp.nsimplify(angle), unit)
    func = {"sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "cot": sp.cot}.get(function)
    if func is None:
        raise expr.ExprError("unsupported function")
    value = sp.simplify(func(radians))
    if value.has(sp.zoo, sp.nan) or not expr.finite(value):
        raise expr.ExprError("undefined_at_angle")
    return value


def solve_in_interval(latex: str, lower, upper, unit: str, variable_name: str = "x",
                      closed=(True, False)):
    """Aralıktaki bütün kökler (periyodik çözümler dahil). Birim derece ise sonuç derece cinsinden döner."""
    ops, sides = expr.relation(latex)
    if ops != ("=",):
        raise expr.ExprError("expected equation")
    x = expr.symbol(variable_name)
    left, right = sides
    if unit not in UNITS:
        raise expr.ExprError("angle_unit_unknown")
    if unit == "degree":
        # Değişken derece cinsinden: trigonometrik fonksiyonların argümanı radyana çevrilir (sin x° = sin(xπ/180)).
        def degrees(e):
            return e.replace(lambda item: isinstance(item, TrigonometricFunction),
                             lambda item: item.func(item.args[0] * sp.pi / 180))
        left, right = degrees(left), degrees(right)
    lo, hi, variable = sp.nsimplify(lower), sp.nsimplify(upper), x
    interval = sp.Interval(lo, hi, not closed[0], not closed[1])
    allowed = sp.Intersection(sets.domain_of([left, right], variable), interval)
    roots = sp.solveset(sp.Eq(left, right), variable, domain=interval)
    roots = sp.Intersection(roots, allowed)
    if not isinstance(roots, sp.FiniteSet):
        roots = sp.simplify(roots)
    if not isinstance(roots, sp.FiniteSet) and roots != sp.S.EmptySet:
        return None, "conditional"
    values = sorted(roots, key=float)
    if len(values) > MAX_ROOTS:
        return None, "too_many_roots"
    return values, "exact"


def general_solution(latex: str, variable_name: str = "x"):
    """Aralık verilmeden: SymPy'nin periyodik çözüm kümesi. Sonlu değildir; hedef sayısı belirlenemez."""
    ops, sides = expr.relation(latex)
    x = expr.symbol(variable_name)
    result = sp.solveset(sp.Eq(*sides), x, domain=sp.S.Reals)
    return result, "periodic" if isinstance(result, (sp.ImageSet, sp.Union)) else "other"


def identity_holds(left: str, right: str, variable_name: str = "x") -> tuple[bool | None, object]:
    """İki ifade *ortak tanım kümesinde* özdeş mi? (tanım kümesi farkı da döner)."""
    x = expr.symbol(variable_name)
    f, g = expr.expression(left), expr.expression(right)
    df, dg = sets.domain_of([f], x), sets.domain_of([g], x)
    difference = sp.simplify(sp.trigsimp(f - g))
    holds = True if difference == 0 else (False if difference.is_number else None)
    return holds, sp.Complement(dg, df)
