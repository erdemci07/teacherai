"""Fonksiyon ve grafik denetimleri (TA-008 §16). Yalnız yalıtılmış işçide çalışır.

Grafik yalnız doğrulanmış ifadeden üretilir; tanımsız noktada parça birleştirilmez. Örneklenmiş grafik bir
özelliğin kanıtı değildir: yetkili iddialar (kök, tanım kümesi, işaret, monotonluk) kesin sembolik sonuçtan gelir.
"""

from __future__ import annotations

from dataclasses import dataclass

import sympy as sp

from ..education.mathematics import GraphSegment
from . import domain as domains
from . import expr, sets

WINDOW = (-10, 10)
MAX_POINTS = 16


@dataclass(frozen=True)
class FunctionFacts:
    domain: object
    exclusions: list
    roots: object
    discontinuities: list
    segments: list[GraphSegment]
    # TA-008B §18: kaldırılabilir süreksizlik (sonlu limit; açık daire) ve düşey asimptot (sonsuz limit) ayrımı.
    holes: list = ()  # [(x, limit)]
    asymptotes: list = ()


def analyze(latex: str, variable_name: str = "x", window=WINDOW) -> FunctionFacts:
    f = expr.expression(latex)
    x = expr.symbol(variable_name)
    if f.free_symbols - {x}:
        raise expr.ExprError("parameters")
    # TA-008B: tanım kümesi özgün AST'den; (x²−1)/(x−1) sadeleşse de x = 1 tanımsız kalır
    domain = sp.Intersection(domains.domain_set(domains.conditions_of(latex), x), sets.domain_of([f], x))
    roots = sp.Intersection(sp.solveset(sp.Eq(f, 0), x, domain=sp.S.Reals), domain)
    holes = sets.exclusions(domain)
    lo, hi = window
    cut = sorted([p for p in holes if expr.finite(p) and lo < p < hi], key=float)[:MAX_POINTS]
    segments = []
    edges = [sp.Integer(lo), *cut, sp.Integer(hi)]
    window_domain = sp.Intersection(domain, sp.Interval(lo, hi))
    for a, b in zip(edges, edges[1:]):
        piece = sp.Intersection(window_domain, sp.Interval(a, b, a in cut, b in cut))
        if piece == sp.S.EmptySet:
            continue
        parts = piece.args if isinstance(piece, sp.Union) else (piece,)
        for part in parts:
            if isinstance(part, sp.Interval) and part.measure > 0:
                segments.append(GraphSegment(start=float(part.start), end=float(part.end),
                                             start_closed=not part.left_open, end_closed=not part.right_open))
    removable, asymptotes = _classify(f, x, cut, segments)
    return FunctionFacts(domain, holes, roots, cut, segments[:16], removable, asymptotes)


def _classify(f, x, cut, segments):
    """Tanımsız iç noktalar ve açık uç noktalar için tek yanlı limitler: iki yandan aynı sonlu limit → kaldırılabilir
    (delik); herhangi bir yanda sonsuz limit → düşey asimptot. Karar verilemeyen nokta hiçbirine konmaz."""
    removable, asymptotes = [], []
    candidates = {float(p): p for p in cut}
    for segment in segments:
        for value, closed in ((segment.start, segment.start_closed), (segment.end, segment.end_closed)):
            if not closed and WINDOW[0] < value < WINDOW[1]:
                candidates.setdefault(value, sp.nsimplify(value))
    for value, point in sorted(candidates.items())[:MAX_POINTS]:
        try:
            sides = [sp.limit(f, x, point, dir=d) for d in ("-", "+")]
        except (NotImplementedError, TypeError, ValueError):
            continue
        real = [s for s in sides if s.is_extended_real and s is not sp.nan]
        if any(s in (sp.oo, -sp.oo) for s in real):
            asymptotes.append(value)
        elif len(real) == 2 and all(expr.finite(s) for s in real) and sp.simplify(real[0] - real[1]) == 0                 and point in cut:
            removable.append((value, float(real[0])))
    return removable, asymptotes


def evaluate(latex: str, value, variable_name: str = "x"):
    """f(a). Tanım kümesi dışında ExprError (sessiz NaN yok)."""
    f = expr.expression(latex)
    x = expr.symbol(variable_name)
    # TA-008B: özgün ifadenin tanım kümesi (sadeleşmiş ifade x = 1'de tanımlı görünse bile)
    domain = sp.Intersection(domains.domain_set(domains.conditions_of(latex), x), sets.domain_of([f], x))
    if domain.contains(value) != sp.true:
        raise expr.ExprError("outside_domain")
    result = sp.simplify(f.subs(x, value))
    if not expr.finite(result):
        raise expr.ExprError("not_finite")
    return result


def compose(outer: str, inner: str, variable_name: str = "x"):
    """(f∘g)(x) ve tanım kümesi: g tanımlı ve g(x) f'nin tanım kümesinde."""
    x = expr.symbol(variable_name)
    f, g = expr.expression(outer), expr.expression(inner)
    composed = f.subs(x, g)
    domain = sp.Intersection(sets.domain_of([g], x), sets.domain_of([composed], x))
    return composed, domain


def inverse(latex: str, variable_name: str = "x", restrict=None):
    """Ters fonksiyon. Tanım kümesinde birebir değilse (ör. x² gerçel eksende) None ve neden."""
    x = expr.symbol(variable_name)
    y = sp.Symbol("y", real=True)
    f = expr.expression(latex)
    domain = restrict if restrict is not None else sets.domain_of([f], x)
    derivative = sp.diff(f, x)
    try:
        positive = sp.solveset(derivative > 0, x, domain=domain)
        negative = sp.solveset(derivative < 0, x, domain=domain)
        zeros = sp.solveset(sp.Eq(derivative, 0), x, domain=domain)
    except (NotImplementedError, TypeError, ValueError):
        return None, "monotonicity_undecided"
    # Birebir: türev tanım kümesinde işaret değiştirmez ve yalnız tekil noktalarda sıfırdır (x³ birebirdir).
    one_sign = (negative == sp.S.EmptySet) != (positive == sp.S.EmptySet)
    isolated = zeros == sp.S.EmptySet or isinstance(zeros, sp.FiniteSet)
    if not (one_sign and isolated):
        return None, "not_injective_on_domain"
    branches = sp.solve(sp.Eq(y, f), x, dict=False)
    probe = sp.Rational(7, 3)  # gerçel dal: örnek gerçel y için gerçel değer veren dal (karmaşık dallar elenir)
    candidates = [item for item in branches if sp.simplify(f.subs(x, item) - y) == 0
                  and item.subs(y, probe).is_real]
    if not candidates and f.is_polynomial(x) and sp.degree(f, x) % 2 == 1:
        candidates = [sp.real_root(y, sp.degree(f, x))] if f == x ** sp.degree(f, x) else []
    if len(candidates) != 1:
        return None, "inverse_branch_ambiguous"
    return candidates[0].subs(y, x), "injective"


def sign_intervals(latex: str, variable_name: str = "x"):
    """(pozitif küme, negatif küme, sıfırlar) — tanım kümesi içinde, kesin."""
    x = expr.symbol(variable_name)
    f = expr.expression(latex)
    domain = sets.domain_of([f], x)
    return (sp.Intersection(sp.solveset(f > 0, x, domain=sp.S.Reals), domain),
            sp.Intersection(sp.solveset(f < 0, x, domain=sp.S.Reals), domain),
            sp.Intersection(sp.solveset(sp.Eq(f, 0), x, domain=sp.S.Reals), domain))


def intersections(left: str, right: str, variable_name: str = "x"):
    x = expr.symbol(variable_name)
    f, g = expr.expression(left), expr.expression(right)
    domain = sp.Intersection(sets.domain_of([f], x), sets.domain_of([g], x))
    return sp.Intersection(sp.solveset(sp.Eq(f, g), x, domain=sp.S.Reals), domain)


def vertex(latex: str, variable_name: str = "x"):
    """İkinci derece f(x)=ax²+bx+c için tepe noktası ve tür (minimum/maksimum)."""
    x = expr.symbol(variable_name)
    poly = sp.Poly(expr.expression(latex), x)
    if poly.degree() != 2:
        raise expr.ExprError("not_quadratic")
    a, b, _ = poly.all_coeffs()
    h = -b / (2 * a)
    return h, sp.simplify(poly.as_expr().subs(x, h)), "minimum" if a > 0 else "maximum"
