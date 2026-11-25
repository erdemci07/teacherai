"""Belirlenimci alternatif çözüm yolları (TA-008 §21). Yalnız yalıtılmış işçide çalışır.

Ek sağlayıcı çağrısı yapılmaz. Her yol özgün denklemden SymPy ile adım adım kurulur ve sonucu özgün denklemin
çözüm kümesiyle karşılaştırılır (``verified``). Aynı çözümün başka sözcüklerle yazılması alternatif sayılmaz:
yalnız gerçekten farklı yöntemler (çarpanlara ayırma, tam kareye tamamlama, kök formülü) üretilir.
"""

from __future__ import annotations

import sympy as sp

from ..education.mathematics import AlternativePath
from . import expr, sets


def _latex(value) -> str:
    return sp.latex(value)


def quadratic(latex: str, variable_name: str = "x") -> list[AlternativePath]:
    ops, sides = expr.relation(latex)
    if ops != ("=",):
        return []
    x = expr.symbol(variable_name)
    poly_expr = sp.expand(sides[0] - sides[1])
    if poly_expr.free_symbols - {x}:
        return []
    poly = sp.Poly(poly_expr, x)
    if poly.degree() != 2:
        return []
    a, b, c = poly.all_coeffs()
    expected = sets.solve_equation(latex, variable_name).value
    paths = []
    roots = sp.roots(poly)
    if all(r.is_rational for r in roots):
        factored = sp.factor(poly_expr)
        steps = [f"{_latex(poly_expr)} = 0", f"{_latex(factored)} = 0"]
        steps += [f"{_latex(x - r)} = 0 \\Rightarrow {variable_name} = {_latex(r)}" for r in sorted(roots, key=float)]
        paths.append(AlternativePath(id="alt_factoring", strategy="factoring", title_tr="Çarpanlarına ayırma",
                                     steps=steps[:12], result=[_latex(r) for r in sorted(roots, key=float)],
                                     verified=sets.same_set(sp.FiniteSet(*roots), expected) is True))
    h = sp.Rational(1, 1) * b / (2 * a)
    k = sp.simplify(c / a - h ** 2)
    square_roots = sp.solveset(sp.Eq((x + h) ** 2, -k), x, domain=sp.S.Reals)
    steps = [f"{_latex(poly_expr / a if a != 1 else poly_expr)} = 0" if a != 1 else f"{_latex(poly_expr)} = 0",
             f"\\left({_latex(x + h)}\\right)^2 = {_latex(-k)}"]
    if -k < 0:
        steps.append("\\text{Bir karenin negatif olamayacağından gerçel kök yoktur.}")
    else:
        steps.append(f"{_latex(x + h)} = \\pm {_latex(sp.sqrt(-k))}")
    paths.append(AlternativePath(id="alt_completing_square", strategy="completing_square", title_tr="Tam kareye tamamlama",
                                 steps=steps[:12], result=[_latex(r) for r in sorted(square_roots, key=float)]
                                 if isinstance(square_roots, sp.FiniteSet) else [],
                                 verified=sets.same_set(square_roots, expected) is True))
    discriminant = sp.simplify(b ** 2 - 4 * a * c)
    formula = sp.solveset(sp.Eq(poly_expr, 0), x, domain=sp.S.Reals)
    steps = [f"\\Delta = b^2 - 4ac = {_latex(discriminant)}"]
    steps.append("\\Delta < 0 \\Rightarrow \\text{gerçel kök yok}" if discriminant < 0 else
                 f"{variable_name} = \\frac{{-({_latex(b)}) \\pm \\sqrt{{{_latex(discriminant)}}}}}{{2 \\cdot {_latex(a)}}}")
    paths.append(AlternativePath(id="alt_quadratic_formula", strategy="quadratic_formula", title_tr="Kök formülü",
                                 steps=steps, result=[_latex(r) for r in sorted(formula, key=float)]
                                 if isinstance(formula, sp.FiniteSet) else [],
                                 verified=sets.same_set(formula, expected) is True))
    return paths[:3]
