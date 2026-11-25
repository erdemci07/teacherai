"""Okul düzeyi limit, türev ve integral denetimleri (TA-008 §19). Yalnız yalıtılmış işçide çalışır.

Ayrımlar: türevin sıfır olması ≠ ekstremum (işaret değişimi gerekir); belirsiz integral ≠ belirli integral;
işaretli integral ≠ geometrik alan; tek yönlü ≠ iki yönlü limit; olağan ≠ genelleştirilmiş (improper) integral;
yerel ≠ mutlak ekstremum. Ters türev türevlenerek denetlenir. Kapalı biçim bulunamazsa ``unsupported``.
"""

from __future__ import annotations

import sympy as sp

from . import expr, sets


def _f(latex: str, variable_name: str):
    f = expr.expression(latex)
    x = expr.symbol(variable_name)
    if f.free_symbols - {x}:
        raise expr.ExprError("parameters")
    return f, x


def limit(latex: str, point, direction: str = "+-", variable_name: str = "x"):
    """direction: "+" sağdan, "-" soldan, "+-" iki yönlü. İki yönlü limit yanlar farklıysa yoktur (None)."""
    f, x = _f(latex, variable_name)
    target = sp.oo if point == "oo" else (-sp.oo if point == "-oo" else sp.nsimplify(point))
    if direction == "+-" and target not in (sp.oo, -sp.oo):
        right, left = sp.limit(f, x, target, "+"), sp.limit(f, x, target, "-")
        return (right if right == left else None), {"left": left, "right": right}
    value = sp.limit(f, x, target, direction if target not in (sp.oo, -sp.oo) else "+")
    return value, {}


def continuous_at(latex: str, point, variable_name: str = "x") -> bool:
    f, x = _f(latex, variable_name)
    a = sp.nsimplify(point)
    if sets.domain_of([f], x).contains(a) != sp.true:
        return False
    value, _ = limit(latex, point, "+-", variable_name)
    return value is not None and sp.simplify(value - f.subs(x, a)) == 0


def derivative(latex: str, variable_name: str = "x"):
    f, x = _f(latex, variable_name)
    return sp.simplify(sp.diff(f, x))


def tangent_slope(latex: str, point, variable_name: str = "x"):
    f, x = _f(latex, variable_name)
    a = sp.nsimplify(point)
    if sets.domain_of([f], x).contains(a) != sp.true:
        raise expr.ExprError("outside_domain")
    return sp.simplify(sp.diff(f, x).subs(x, a))


def critical_points(latex: str, variable_name: str = "x"):
    """Kritik noktalar ve birinci türev testi: (nokta, "local_minimum"|"local_maximum"|"no_extremum")."""
    f, x = _f(latex, variable_name)
    d = sp.diff(f, x)
    domain = sets.domain_of([f], x)
    zeros = sp.Intersection(sp.solveset(sp.Eq(d, 0), x, domain=sp.S.Reals), domain)
    if not isinstance(zeros, sp.FiniteSet):
        return None
    out = []
    for point in sorted(zeros, key=float):
        eps = sp.Rational(1, 1000)
        left, right = d.subs(x, point - eps), d.subs(x, point + eps)
        if left < 0 < right:
            kind = "local_minimum"
        elif left > 0 > right:
            kind = "local_maximum"
        else:
            kind = "no_extremum"  # türev sıfır ama işaret değişmiyor (ör. x³'te 0)
        out.append((point, kind))
    return out


def global_extrema(latex: str, lower, upper, variable_name: str = "x"):
    """Kapalı aralıkta mutlak en küçük/en büyük: kritik noktalar + uç noktalar."""
    f, x = _f(latex, variable_name)
    a, b = sp.nsimplify(lower), sp.nsimplify(upper)
    if sets.domain_of([f], x).contains(a) != sp.true or not sets.domain_of([f], x).is_superset(sp.Interval(a, b)):
        raise expr.ExprError("not_continuous_on_interval")
    candidates = [a, b] + [p for p, _ in (critical_points(latex, variable_name) or []) if a < p < b]
    values = {p: sp.simplify(f.subs(x, p)) for p in candidates}
    return min(values.values()), max(values.values())


def check_antiderivative(integrand: str, candidate: str, variable_name: str = "x") -> bool:
    """F' = f mi? (sabit fark serbesttir)."""
    f, x = _f(integrand, variable_name)
    F, _ = _f(candidate, variable_name)
    return sp.simplify(sp.diff(F, x) - f) == 0


def definite(integrand: str, lower, upper, variable_name: str = "x"):
    """(işaretli integral, geometrik alan, "proper"|"improper"). Kapalı biçim yoksa ExprError."""
    f, x = _f(integrand, variable_name)
    a, b = sp.nsimplify(lower), sp.nsimplify(upper)
    if a in (sp.oo, -sp.oo) or b in (sp.oo, -sp.oo) or not sets.domain_of([f], x).is_superset(sp.Interval(a, b)):
        return None, None, "improper"
    signed = sp.integrate(f, (x, a, b))
    if signed.has(sp.Integral):
        raise expr.ExprError("no_closed_form")
    roots = sorted([r for r in sp.solveset(sp.Eq(f, 0), x, domain=sp.Interval(a, b, True, True)) if r.is_real],
                   key=float) if isinstance(sp.solveset(sp.Eq(f, 0), x, domain=sp.Interval(a, b, True, True)), sp.FiniteSet) else None
    if roots is None:
        return sp.simplify(signed), None, "proper"
    edges = [a, *roots, b]
    area = sum(abs(sp.integrate(f, (x, p, q))) for p, q in zip(edges, edges[1:]))
    return sp.simplify(signed), sp.simplify(area), "proper"


def area_between(upper_curve: str, lower_curve: str, a, b, variable_name: str = "x"):
    """İki eğri arası alan: |f − g| integrali (hangi eğrinin üstte olduğu varsayılmaz)."""
    f, x = _f(upper_curve, variable_name)
    g, _ = _f(lower_curve, variable_name)
    difference = sp.simplify(f - g)
    expression = expr.text(difference)
    _, area, kind = definite_from_expr(difference, x, a, b)
    return area, kind, expression


def definite_from_expr(f, x, lower, upper):
    a, b = sp.nsimplify(lower), sp.nsimplify(upper)
    signed = sp.integrate(f, (x, a, b))
    zeros = sp.solveset(sp.Eq(f, 0), x, domain=sp.Interval(a, b, True, True))
    if not isinstance(zeros, sp.FiniteSet):
        return signed, None, "proper"
    edges = [a, *sorted(zeros, key=float), b]
    return signed, sp.simplify(sum(abs(sp.integrate(f, (x, p, q))) for p, q in zip(edges, edges[1:]))), "proper"
