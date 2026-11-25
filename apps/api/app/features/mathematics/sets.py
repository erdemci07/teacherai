"""Tanım kümesi ve çözüm kümesi (TA-008 §8–9). Yalnız yalıtılmış işçide çalışır.

- Çözüm kümesi açık bir sayı kümesinde (gerçel, tam sayı, doğal, rasyonel, karmaşık) hesaplanır.
- Kesin aritmetik: rasyonel, kök ve sabitler korunur; yaklaşık değer yalnız ``approximate`` ile ve işaretli.
- ``ConditionSet``, değerlendirilmemiş kesişim/tümleyen, parametreye bağlı veya sonsuz sayılabilir (periyodik)
  sonuç *başarılı doğrulama değildir*: ``conditional``/``unsupported`` döner.
- Tanımsız noktalar (payda sıfırı, çift kök içi negatif, logaritma argümanı ≤ 0) özgün ifadenin tanım
  kümesinden hesaplanır; sadeleştirme tanım kümesini değiştiremez.
"""

from __future__ import annotations

from dataclasses import dataclass

import sympy as sp
from sympy.calculus.util import continuous_domain

from ..education.mathematics import IntervalView, SolutionSetView
from . import expr

MAX_INTEGER_SCAN = 2000
DOMAINS = {"real": sp.S.Reals, "integer": sp.S.Integers, "natural": sp.S.Naturals0, "rational": sp.S.Rationals,
           "complex": sp.S.Complexes}


@dataclass(frozen=True)
class Solved:
    view: SolutionSetView
    value: object  # SymPy kümesi (yalnız işçi içinde kullanılır)
    status: str  # "exact" | "conditional" | "unsupported"


def domain_of(expressions, variable) -> object:
    """Özgün ifadelerin ortak gerçel tanım kümesi."""
    result = sp.S.Reals
    for item in expressions:
        if item is None or variable not in getattr(item, "free_symbols", set()):
            continue
        result = sp.Intersection(result, continuous_domain(item, variable, sp.S.Reals))
    return result


def exclusions(domain) -> list:
    """Gerçel eksenden çıkarılan tekil noktalar (ör. x ≠ 0). Aralık kısıtları burada değil, kümede kalır."""
    if isinstance(domain, sp.Complement) and domain.args[0] == sp.S.Reals and isinstance(domain.args[1], sp.FiniteSet):
        return sorted(domain.args[1], key=sp.default_sort_key)
    if isinstance(domain, sp.Union):
        points = []
        parts = sorted([item for item in domain.args if isinstance(item, sp.Interval)], key=lambda item: item.start)
        for left, right in zip(parts, parts[1:]):
            if left.end == right.start and left.right_open and right.left_open:
                points.append(left.end)
        return points
    return []


def _interval_view(item: sp.Interval) -> IntervalView:
    lower = None if item.start == -sp.oo else expr.text(item.start)
    upper = None if item.end == sp.oo else expr.text(item.end)
    return IntervalView(lower=lower, upper=upper, lower_closed=not item.left_open and lower is not None,
                        upper_closed=not item.right_open and upper is not None)


def view(value, variable=None, domain: str = "real", excluded=()) -> SolutionSetView:
    """SymPy kümesinin gösterilebilir kaydı. Bilinmeyen biçim ``unsupported`` olur (asla ``passed`` değil)."""
    name = str(variable) if variable is not None else None
    base = {"domain": domain, "variable": name, "exclusions": [expr.text(item) for item in excluded][:16]}
    if value == sp.S.EmptySet:
        return SolutionSetView(kind="empty", **base)
    if value in (sp.S.Reals, sp.S.Complexes) or value == DOMAINS.get(domain):
        return SolutionSetView(kind="all", **base)
    if isinstance(value, sp.FiniteSet) and all(item.is_number for item in value):
        items = sorted(value, key=sp.default_sort_key)
        return SolutionSetView(kind="finite", elements=[expr.text(item) for item in items][:32], **base)
    if isinstance(value, sp.Interval):
        return SolutionSetView(kind="intervals", intervals=[_interval_view(value)], **base)
    if isinstance(value, sp.Union) and all(isinstance(item, (sp.Interval, sp.FiniteSet)) for item in value.args):
        intervals, points = [], []
        for item in value.args:
            if isinstance(item, sp.Interval):
                intervals.append(item)
            else:
                points.extend(item)
        views = [_interval_view(item) for item in sorted(intervals, key=lambda item: item.start)]
        views += [IntervalView(lower=expr.text(p), upper=expr.text(p), lower_closed=True, upper_closed=True)
                  for p in sorted(points, key=sp.default_sort_key)]
        return SolutionSetView(kind="intervals", intervals=views[:16], **base)
    if isinstance(value, sp.Complement) and isinstance(value.args[0], sp.Interval) and isinstance(value.args[1], sp.FiniteSet):
        return view(sp.Union(*[sp.Interval(a, b, True, True) for a, b in _cuts(value.args[0], value.args[1])]),
                    variable, domain, excluded)
    if isinstance(value, (sp.ConditionSet, sp.ImageSet)):
        return SolutionSetView(kind="conditional", exact=False, **base)
    return SolutionSetView(kind="unsupported", exact=False, **base)


def _cuts(interval: sp.Interval, points: sp.FiniteSet):
    edges = [interval.start, *sorted((p for p in points if interval.contains(p) == sp.true), key=sp.default_sort_key),
             interval.end]
    return list(zip(edges, edges[1:]))


def _restricted(result, domain: str):
    if domain == "real":
        return result
    return sp.Intersection(result, DOMAINS[domain])


def solve_equation(latex: str, variable_name: str = "x", domain: str = "real") -> Solved:
    """Tek değişkenli denklemin seçilen sayı kümesindeki çözüm kümesi; özgün tanım kümesi uygulanır."""
    ops, sides = expr.relation(latex)
    if ops != ("=",):
        raise expr.ExprError("expected equation")
    variable = expr.symbol(variable_name)
    left, right = sides
    if (left.free_symbols | right.free_symbols) - {variable}:
        raise expr.ExprError("parameters")
    allowed = domain_of([left, right], variable)
    base = sp.S.Complexes if domain == "complex" else sp.S.Reals
    if domain == "complex":
        variable = sp.Symbol(variable_name)
        left, right = left.subs(expr.symbol(variable_name), variable), right.subs(expr.symbol(variable_name), variable)
        allowed = sp.S.Complexes
    raw = sp.solveset(sp.Eq(left, right), variable, domain=base)
    result = _restricted(sp.Intersection(raw, allowed) if domain != "complex" else raw, domain)
    result = _simplify_set(result)
    shown = view(result, variable, domain, exclusions(allowed) if domain != "complex" else ())
    status = "exact" if shown.kind in {"finite", "empty", "all", "intervals"} else shown.kind
    return Solved(shown, result, status)


def _simplify_set(value):
    if isinstance(value, sp.Intersection):
        finite_parts = [item for item in value.args if isinstance(item, sp.FiniteSet)]
        if finite_parts:
            candidates = finite_parts[0]
            others = [item for item in value.args if item is not finite_parts[0]]
            kept = [c for c in candidates if all(other.contains(c) == sp.true for other in others)]
            undecided = [c for c in candidates if any(other.contains(c) not in (sp.true, sp.false) for other in others)]
            if not undecided:
                return sp.FiniteSet(*kept)
    return value


def solve_inequality(latex: str, variable_name: str = "x") -> Solved:
    """Tek değişkenli (zincir dahil) eşitsizliğin gerçel çözüm kümesi; tanımsız noktalar dışarıda kalır."""
    ops, sides = expr.relation(latex)
    relations = {"<": sp.StrictLessThan, "<=": sp.LessThan, ">": sp.StrictGreaterThan, ">=": sp.GreaterThan}
    if not all(op in relations for op in ops):
        raise expr.ExprError("expected inequality")
    variable = expr.symbol(variable_name)
    if set().union(*(item.free_symbols for item in sides)) - {variable}:
        raise expr.ExprError("parameters")
    allowed = domain_of(sides, variable)
    result = allowed
    for op, left, right in zip(ops, sides, sides[1:]):
        result = sp.Intersection(result, sp.solveset(relations[op](left, right), variable, domain=sp.S.Reals))
    result = sp.simplify(result) if isinstance(result, sp.Intersection) else result
    shown = view(result, variable, "real", exclusions(allowed))
    return Solved(shown, result, "exact" if shown.kind in {"finite", "empty", "all", "intervals"} else shown.kind)


def integer_count(value, limit: int = MAX_INTEGER_SCAN) -> int | None:
    """Sınırlı kümedeki tam sayı sayısı; sınırsız veya tarama sınırını aşan küme için None."""
    if value == sp.S.EmptySet:
        return 0
    if isinstance(value, sp.FiniteSet):
        return sum(1 for item in value if item.is_integer)
    try:
        lower, upper = value.inf, value.sup
    except (AttributeError, NotImplementedError):
        return None
    if not (expr.finite(lower) and expr.finite(upper)) or upper - lower > limit:
        return None
    return sum(1 for n in range(int(sp.floor(lower)), int(sp.ceiling(upper)) + 1) if value.contains(n) == sp.true)


def same_set(left, right) -> bool | None:
    """Kesin küme eşitliği; karar verilemezse None."""
    try:
        difference = sp.Union(sp.Complement(left, right), sp.Complement(right, left))
        if difference == sp.S.EmptySet:
            return True
        if isinstance(difference, (sp.Interval, sp.FiniteSet, sp.Union)) and difference.is_empty is False:
            return False
        return None
    except (TypeError, ValueError, NotImplementedError):
        return None


def approximate(value, digits: int = 6) -> str:
    """Açıkça işaretli yaklaşık gösterim (kesin değerin yerine geçmez)."""
    return f"≈ {sp.N(value, digits)}"
