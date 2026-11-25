"""Özgün ifadenin tanım kümesi (TA-008B §4). Ortak mekanizma: bütün uzmanlık modülleri buradan alır.

Kısıtlar *doğrulanmış AST'den*, yıkıcı sadeleştirmeden önce toplanır. SymPy ``x/x``'i 1'e, ``0·(1/x)``'i 0'a,
``x⁻¹·x``'i 1'e kendiliğinden indirger; bu indirgeme tanım kümesini değiştiremez. Toplanan koşullar:

- payda ≠ 0 (kesir ve bölme), negatif üslü kuvvetin tabanı ≠ 0, sıfırıncı kuvvetin tabanı ≠ 0 (okul matematiğinde
  0⁰ tanımsız kabul edilir),
- çift dereceli kökün içi ≥ 0,
- logaritma argümanı > 0; taban > 0 ve ≠ 1,
- tan için cos ≠ 0, cot için sin ≠ 0,
- iç içe ifadelerin bütün alt kısıtları.

``conditions`` saf Python'dur (SymPy gerektirmez; ``guidance`` süreç içinde kullanır). ``domain_set`` SymPy ile
kümeyi kurar ve yalnız yalıtılmış işçide çağrılır. Karmaşık sayılarda yalnız eşitsizlik içermeyen koşullar
(payda ≠ 0, taban ≠ 0) uygulanır.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..integrity import expression as tree

MAX_CONDITIONS = 24


@dataclass(frozen=True)
class Condition:
    kind: str  # nonzero | nonnegative | positive | not_one
    node: object
    reason: str  # denominator | negative_power | zero_power | even_root | log_argument | log_base | tan | cot

    @property
    def latex(self) -> str:
        return tree.to_latex(self.node)

    def text_tr(self) -> str:
        operator = {"nonzero": "≠ 0", "nonnegative": "≥ 0", "positive": "> 0", "not_one": "≠ 1"}[self.kind]
        return f"{self.latex} {operator}"


def _children(node):
    return tree._children(node)


def _is_number(node) -> bool:
    return not tree.symbols(node)


def _even_index(node) -> bool:
    return node.index is None or (isinstance(node.index, tree.Num) and node.index.value.denominator == 1
                                  and int(node.index.value) % 2 == 0)


def conditions(node) -> list[Condition]:
    """Ağacın her düğümünden tanım koşulları (tekrarsız). Değişkensiz koşul ancak yanlışsa anlamlıdır; tutulur."""
    found: list[Condition] = []
    seen: set[tuple[str, str]] = set()

    def add(kind, sub, reason):
        key = (kind, tree.to_latex(sub))
        if key not in seen and len(found) < MAX_CONDITIONS:
            seen.add(key)
            found.append(Condition(kind, sub, reason))

    def walk(item):
        if isinstance(item, tree.Frac):
            add("nonzero", item.den, "denominator")
        elif isinstance(item, tree.Bin) and item.op == "/":
            add("nonzero", item.right, "denominator")
        elif isinstance(item, tree.Pow) and isinstance(item.exp, (tree.Num, tree.Neg, tree.Group)):
            exponent = item.exp.arg if isinstance(item.exp, tree.Group) else item.exp
            negative = isinstance(exponent, tree.Neg) or (isinstance(exponent, tree.Num) and exponent.value < 0)
            zero = isinstance(exponent, tree.Num) and exponent.value == 0
            if negative:
                add("nonzero", item.base, "negative_power")
            elif zero:
                add("nonzero", item.base, "zero_power")
            if isinstance(exponent, tree.Num) and exponent.value.denominator % 2 == 0:
                add("nonnegative", item.base, "even_root")
        elif isinstance(item, tree.Root) and _even_index(item):
            add("nonnegative", item.radicand, "even_root")
        elif isinstance(item, tree.Func):
            if item.name in {"log", "ln"}:
                add("positive", item.arg, "log_argument")
                if item.base is not None:
                    add("positive", item.base, "log_base")
                    add("not_one", item.base, "log_base")
            elif item.name == "tan":
                add("nonzero", tree.Func("cos", item.arg), "tan")
            elif item.name == "cot":
                add("nonzero", tree.Func("sin", item.arg), "cot")
        for child in _children(item):
            walk(child)

    walk(node)
    return found


def conditions_of(latex: str) -> list[Condition]:
    result = tree.parse(latex)
    return conditions(result.tree) if result.parsed else []


def domain_set(conds: list[Condition], variable, complex_domain: bool = False):
    """Koşulların kesişimi (SymPy; yalnız işçide). Değişkensiz ve yanlış koşul boş küme verir."""
    import sympy as sp

    from . import expr

    base = sp.S.Complexes if complex_domain else sp.S.Reals
    result = base
    for cond in conds:
        value = expr.build(cond.node)
        if complex_domain:
            value = value.subs(variable, sp.Symbol(str(variable)))
            var = sp.Symbol(str(variable))
        else:
            var = variable
        if complex_domain and cond.kind != "nonzero":
            continue  # sıralama koşulları karmaşık sayılarda anlamsızdır
        if var not in value.free_symbols:
            truth = {"nonzero": value != 0, "nonnegative": value >= 0, "positive": value > 0, "not_one": value != 1}[cond.kind]
            if truth in (False, sp.false):
                return sp.S.EmptySet
            continue
        if cond.kind == "nonzero":
            zeros = sp.solveset(sp.Eq(value, 0), var, domain=base)
            result = sp.Complement(result, zeros)
        elif cond.kind == "not_one":
            result = sp.Complement(result, sp.solveset(sp.Eq(value, 1), var, domain=base))
        else:
            relation = value >= 0 if cond.kind == "nonnegative" else value > 0
            result = sp.Intersection(result, sp.solveset(relation, var, domain=sp.S.Reals))
    return result


def domain_of_latex(latexes: list[str], variable, complex_domain: bool = False):
    conds = [c for latex in latexes for c in conditions_of(latex)]
    return domain_set(conds, variable, complex_domain), conds
