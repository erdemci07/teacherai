"""Adım dönüşümlerinin denkliği (TA-008 §9). Yalnız yalıtılmış işçide çalışır.

Ardışık iki ilişki *özgün tanım kümesinde* karşılaştırılır:

- ``equivalent``: çözüm kümesi aynı.
- ``gains``: yeni küme özgünü kapsar (kare alma, değişkenli ifadeyle çarpma): yabancı kök riski. Tek başına hata
  değildir; adaylar özgün denklemde denetlenmelidir.
- ``loses``: çözüm kaybı (ör. değişken içeren ifadeye bölme ``x = 0``'ı kaybettirir): hata.
- ``changed``: başka bir küme: hata.

Ayrıca işlem tehlikeleri adlandırılır: sıfır olabilen ifadeye bölme, işareti bilinmeyen ifadeyle eşitsizliği
çarpma, negatif sayıyla çarpıp yönü çevirmeme.
"""

from __future__ import annotations

from dataclasses import dataclass

import sympy as sp

from . import domain as domains
from . import expr, sets

RELATIONS = {"<": sp.StrictLessThan, "<=": sp.LessThan, ">": sp.StrictGreaterThan, ">=": sp.GreaterThan}


@dataclass(frozen=True)
class StepVerdict:
    relation: str  # equivalent | gains | eliminates | loses | changed | unsupported
    hazard: str | None
    detail: str


def _set(latex: str, variable, allowed):
    ops, sides = expr.relation(latex)
    if set().union(*(item.free_symbols for item in sides)) - {variable}:
        raise expr.ExprError("parameters")
    result = allowed
    if ops == ("=",):
        return sp.Intersection(result, sp.solveset(sp.Eq(*sides), variable, domain=sp.S.Reals)), ops, sides
    for op, left, right in zip(ops, sides, sides[1:]):
        if op not in RELATIONS:
            raise expr.ExprError("relation")
        result = sp.Intersection(result, sp.solveset(RELATIONS[op](left, right), variable, domain=sp.S.Reals))
    return result, ops, sides


def _factor_between(before, after, variable):
    """after = k · before (her iki tarafta aynı k) ise k; değilse None."""
    try:
        (l1, r1), (l2, r2) = before, after
        if l1 == 0 or r1 == 0:
            return None
        k1, k2 = sp.simplify(l2 / l1), sp.simplify(r2 / r1)
        if sp.simplify(k1 - k2) == 0 and k1 != 1:
            return k1
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return None


def compare(previous: str, current: str, original: str, variable_name: str = "x") -> StepVerdict:
    variable = expr.symbol(variable_name)
    try:
        _, _, original_sides = _set(original, variable, sp.S.Reals)
        # TA-008B: özgün ilişkinin AST tanım kümesi (sadeleştirme öncesi) + sürekli tanım kümesi
        allowed = sp.Intersection(domains.domain_set(domains.conditions_of(original), variable),
                                  sets.domain_of(original_sides, variable))
        before, ops_before, sides_before = _set(previous, variable, allowed)
        after, ops_after, sides_after = _set(current, variable, allowed)
    except (expr.ExprError, NotImplementedError, TypeError, ValueError):
        return StepVerdict("unsupported", None, "Adım güvenli ayrıştırılamadı veya çözülemedi.")
    hazard = None
    if len(sides_before) == 2 and len(sides_after) == 2:
        factor = _factor_between(sides_before, sides_after, variable)
        inverse = _factor_between(sides_after, sides_before, variable)
        if inverse is not None and variable in inverse.free_symbols:
            # current = before / g(x): g'nin sıfırları kaybolabilir
            zeros = sp.solveset(sp.Eq(inverse, 0), variable, domain=sp.S.Reals)
            if zeros != sp.S.EmptySet:
                hazard = "division_by_expression_with_zero"
        if factor is not None and ops_before != ("=",):
            if factor.is_number and factor.is_negative and ops_after == ops_before:
                hazard = "inequality_not_reversed"
            elif not factor.is_number and factor.free_symbols:
                hazard = "unknown_sign_multiplier"
    equal = sets.same_set(before, after)
    if equal is True:
        return StepVerdict("equivalent", hazard, "Çözüm kümesi (özgün tanım kümesinde) korundu.")
    if equal is None:
        return StepVerdict("unsupported", hazard, "Kümeler kesin karşılaştırılamadı.")
    if sets.same_set(sp.Intersection(before, after), before) is True:
        return StepVerdict("gains", hazard, "Dönüşüm çözüm kümesini genişletti; yabancı kök özgün denklemde elenmeli.")
    if sets.same_set(sp.Intersection(before, after), after) is True:
        # TA-008B: önceki adım kümeyi genişletmişse (ör. kare alma), yalnız özgün denklemi sağlamayan adayların elenmesi
        # kayıp değildir. Özgün çözümlerin tamamı korunuyorsa "eliminates" döner.
        original_set, _, _ = _set(original, variable, allowed)
        if sets.same_set(sp.Intersection(after, original_set), original_set) is True:
            return StepVerdict("eliminates", None, "Yalnız özgün denklemi sağlamayan (yabancı) adaylar elendi; özgün "
                                                   "çözümlerin tamamı korundu.")
        return StepVerdict("loses", hazard or "solution_lost", "Dönüşüm bir veya daha çok çözümü kaybettirdi.")
    return StepVerdict("changed", hazard, "Dönüşüm çözüm kümesini değiştirdi.")
