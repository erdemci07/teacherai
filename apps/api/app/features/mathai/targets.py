"""İstenen hedefin bağımsız hesabı, öneri rolü ve dönüşüm sınıflandırması (TA-004).

Yalıtılmış MathAI işçisinde çalışır. Desteklenmeyen hedef, model veya kural için ``unsupported``
döner; sınırsız ispat araması yapılmaz. Verilen model, ara değerler, istenen değer ve sağlayıcı
önerisi ayrı tutulur.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import sympy as sp

from ..education.reasoning import EXPRESSION_TARGETS, AnswerTarget
from ..integrity import expression as tree
from .parser import MathParseError, branches, denominators, equation, relation_set, solutions, to_sympy

MAX_INTEGER_SCAN = 2000


@dataclass
class Computed:
    values: set | None
    reason: str
    intermediate: list[str]
    excluded: list[str]


def _same(left, right) -> bool:
    try:
        return bool(sp.simplify(left - right) == 0)
    except (TypeError, ValueError, NotImplementedError):
        return False


def same_values(left: set, right: set) -> bool:
    if len(left) != len(right):
        return False
    return all(any(_same(a, b) for b in right) for a in left) and all(any(_same(a, b) for a in left) for b in right)


def text(value) -> str:
    return str(value)[:400]


def requested_expression(target: AnswerTarget):
    if target.expression is None:
        return None
    parsed = tree.parse(target.expression)
    if not parsed.parsed or isinstance(parsed.tree, tree.Rel):
        return None
    return to_sympy(parsed.tree)


def valid_roots(original: str, variable, roots: set) -> tuple[set, list]:
    """Kökleri *özgün* denkleme koyar; paydayı sıfırlayan veya denklemi sağlamayan kök atılır."""
    kept, excluded = set(), []
    for branch in branches(original):
        eq = equation(branch)
        dens = denominators(eq.lhs) + denominators(eq.rhs)
        for root in roots:
            if any(_same(den.subs(variable, root), 0) for den in dens):
                excluded.append(root)
                continue
            try:
                if _same((eq.lhs - eq.rhs).subs(variable, root), 0):
                    kept.add(root)
            except (TypeError, ValueError):
                continue
    return kept, [item for item in dict.fromkeys(excluded) if item not in kept]


def compute(target: AnswerTarget, original: str | None, inequality: str | None, variables: list) -> Computed:
    """Hedefin bağımsız değeri. ``values`` None ise ``reason`` neden hesaplanamadığını söyler."""
    if not target.computable:
        return Computed(None, "target_unresolved" if target.kind == "unresolved" else "target_not_computable", [], [])
    if inequality is not None:
        return _from_inequality(target, inequality, variables)
    if original is None:
        return constant(target) if target.kind in EXPRESSION_TARGETS else Computed(None, "model_unsupported", [], [])
    if len(variables) == 2 and target.kind in {"expression_value", "sum", "difference", "product", "ratio"}:
        return _two_variable(target, original, variables)
    if len(variables) != 1:
        return Computed(None, "model_unsupported", [], [])
    variable = variables[0]
    try:
        roots = solutions(original, variable)
        roots, excluded = valid_roots(original, variable, roots)
    except (MathParseError, NotImplementedError, TypeError, ValueError):
        return Computed(None, "model_unsupported", [], [])
    intermediate = [f"{variable} = {text(root)}" for root in sorted(roots, key=sp.default_sort_key)][:16]
    excluded_text = [text(item) for item in excluded][:8]
    if not roots:
        return Computed(None, "domain_excluded" if excluded else "model_unsupported", intermediate, excluded_text)
    kind = target.kind
    if target.integer_only and kind in {"minimum", "maximum", "solution_count"}:
        roots = {root for root in roots if root.is_integer}
    if kind in {"variable_value", "solution_set"}:
        return Computed(set(roots), "computed", intermediate, excluded_text)
    if kind == "solution_count":
        return Computed({sp.Integer(len(roots))}, "computed", intermediate, excluded_text)
    if kind in {"minimum", "maximum"}:
        if not roots or not all(root.is_real for root in roots):
            return Computed(None, "model_unsupported", intermediate, excluded_text)
        pick = max if kind == "maximum" else min
        return Computed({pick(roots)}, "computed", intermediate, excluded_text)
    if kind in {"root_sum", "root_product"}:
        if len(branches(original)) == 1 and not _distinct_real_polynomial_roots(original, variable, roots):
            # Katlı veya karmaşık kök varsa "kökler toplamı" Vieta ile gerçel çözüm kümesinden farklı olabilir.
            return Computed(None, "multiplicity_or_complex_roots", intermediate, excluded_text)
        value = sp.Add(*roots) if kind == "root_sum" else sp.Mul(*roots)
        return Computed({sp.simplify(value)}, "computed", intermediate, excluded_text)
    try:
        expr = requested_expression(target)
    except (MathParseError, NotImplementedError, TypeError):
        return Computed(None, "model_unsupported", intermediate, excluded_text)
    if expr is None or not expr.free_symbols <= {variable}:
        return Computed(None, "model_unsupported", intermediate, excluded_text)
    values = set()
    for root in roots:
        if any(_same(den.subs(variable, root), 0) for den in denominators(expr)):
            continue
        values.add(sp.simplify(expr.subs(variable, root)))
    if not values:
        return Computed(None, "domain_excluded", intermediate, excluded_text)
    return Computed(values, "computed", intermediate, excluded_text)


def constant(target: AnswerTarget) -> Computed:
    """Değişken içermeyen istenen ifadenin (sayısal, köklü, üslü, kesirli) kesin gerçel değeri (TA-005).

    Kök, üs ve kesir kapsamı bütünlük ayrıştırıcısının ağacından gelir; değer tahmin edilmez. Değişken
    içeren ifade (sembolik sadeleştirme) burada hesaplanmaz.
    """
    try:
        expr = requested_expression(target)
    except (MathParseError, NotImplementedError, TypeError, ValueError):
        return Computed(None, "model_unsupported", [], [])
    if expr is None or expr.free_symbols:
        return Computed(None, "model_unsupported", [], [])
    if any(_same(den, 0) for den in denominators(expr)):
        return Computed(None, "domain_excluded", [], [])
    value = sp.simplify(expr)
    if value.atoms(sp.Pow):  # iç içe kök: √(4 + 2√3) = 1 + √3; tam sayı girdide sqrtdenest çağrılmaz
        value = sp.simplify(sp.sqrtdenest(value))
    if not value.is_number or value.is_real is not True or value.is_finite is not True:
        return Computed(None, "not_finite", [], [])
    return Computed({value}, "computed", [], [])


def _distinct_real_polynomial_roots(original: str, variable, roots: set) -> bool:
    eq = equation(branches(original)[0])
    try:
        numerator = sp.fraction(sp.together(eq.lhs - eq.rhs))[0]
        poly = sp.Poly(sp.expand(numerator), variable)
    except (sp.PolynomialError, sp.GeneratorsNeeded):
        return True  # polinom değil (mutlak değer, kök): gerçel çözüm kümesi kullanılır
    return poly.degree() == len(roots)


def _two_variable(target: AnswerTarget, original: str, variables: list) -> Computed:
    """İki bilinmeyenli tek denklemde istenen ifade sabitse (ör. 2x = 3y için x/y) değeri."""
    try:
        expr = requested_expression(target)
        eq = equation(branches(original)[0])
    except (MathParseError, NotImplementedError, TypeError):
        return Computed(None, "model_unsupported", [], [])
    if expr is None or len(branches(original)) != 1 or not expr.free_symbols <= set(variables):
        return Computed(None, "model_unsupported", [], [])
    for symbol in variables:
        try:
            solved = sp.solveset(sp.Eq(eq.lhs, eq.rhs), symbol, domain=sp.S.Reals)
        except (TypeError, ValueError, NotImplementedError):
            continue
        if not isinstance(solved, sp.FiniteSet) or not solved:
            continue
        results = {sp.simplify(expr.subs(symbol, item)) for item in solved}
        if all(item.is_number for item in results):
            other = [v for v in variables if v != symbol][0]
            return Computed(results, "computed", [f"{symbol} = {text(item)}" for item in solved][:4], [f"{other} ≠ 0"])
    return Computed(None, "multiple_values", [], [])


def _from_inequality(target: AnswerTarget, inequality: str, variables: list) -> Computed:
    if len(variables) != 1:
        return Computed(None, "model_unsupported", [], [])
    variable = variables[0]
    try:
        region = relation_set(inequality, variable)
    except (MathParseError, NotImplementedError, TypeError, ValueError):
        return Computed(None, "model_unsupported", [], [])
    intermediate = [f"{variable} ∈ {text(region)}"]
    if region == sp.EmptySet:
        return Computed(None, "domain_excluded", intermediate, [])
    kind = target.kind
    if kind in {"maximum", "minimum"}:
        bound = region.sup if kind == "maximum" else region.inf
        if bound.is_infinite:
            return Computed(None, "unbounded_extremum", intermediate, [])
        if target.integer_only:
            candidate = sp.floor(bound) if kind == "maximum" else sp.ceiling(bound)
            step = -1 if kind == "maximum" else 1
            for _ in range(3):
                if region.contains(candidate) is sp.true:
                    return Computed({sp.Integer(candidate)}, "computed", intermediate, [])
                candidate += step
            return Computed(None, "unbounded_extremum", intermediate, [])
        if region.contains(bound) is sp.true:
            return Computed({bound}, "computed", intermediate, [])
        return Computed(None, "unbounded_extremum", intermediate, [])
    if kind == "solution_count" and target.integer_only:
        if region.inf.is_infinite or region.sup.is_infinite:
            return Computed(None, "not_finite", intermediate, [])
        low, high = int(sp.ceiling(region.inf)), int(sp.floor(region.sup))
        if high - low > MAX_INTEGER_SCAN:
            return Computed(None, "not_finite", intermediate, [])
        count = sum(1 for value in range(low, high + 1) if region.contains(value) is sp.true)
        return Computed({sp.Integer(count)}, "computed", intermediate, [])
    return Computed(None, "target_not_computable", intermediate, [])


# --------------------------------------------------------------------------- öneri


def claim(target: AnswerTarget, expressions: list[str], variables: list) -> tuple[set | None, str]:
    """Sağlayıcının son cevap ifadelerinden hedefe ait değeri ve rolünü çıkarır.

    Rol: ``target`` (istenen hedefin değeri), ``intermediate`` (yalnızca değişken ataması, hedef başka),
    ``none`` (ifade yok), ``unparsed``.
    """
    if not expressions:
        return None, "none"
    names = {str(variable) for variable in variables}
    wanted = None
    if target.expression is not None:
        parsed = tree.parse(target.expression)
        wanted = parsed.tree if parsed.parsed else None
    variable_target = target.kind in {"variable_value", "solution_set"} or (
        target.kind in {"minimum", "maximum"} and target.expression is None)
    target_values, intermediate_values = set(), set()
    for raw in expressions:
        source = raw.strip().strip("$")
        match = re.fullmatch(r"([a-zA-Z])\s*(?:\\in|∈)\s*\\?\{([^{}]+?)\\?\}", source)
        if match and match[1] in names:
            values = _numbers(match[2].split(","))
            if values is None:
                return None, "unparsed"
            (target_values if variable_target else intermediate_values).update(values)
            continue
        parsed = tree.parse(source)
        if not parsed.parsed:
            return None, "unparsed"
        node = parsed.tree
        if isinstance(node, tree.Rel):
            if node.ops != ("=",) or len(node.operands) != 2:
                return None, "unparsed"
            left, right = node.operands
            values = _numbers([right])
            if values is None:
                return None, "unparsed"
            left_bare = left.arg if isinstance(left, tree.Group) else left
            if wanted is not None and tree.same_structure(left, wanted):
                target_values.update(values)
            elif isinstance(left_bare, tree.Sym) and (left_bare.name + (f"_{left_bare.sub}" if left_bare.sub else "")) in names:
                (target_values if variable_target else intermediate_values).update(values)
            else:
                return None, "unparsed"
            continue
        values = _numbers([node])
        if values is None:
            return None, "unparsed"
        target_values.update(values)
    if target_values:
        return target_values, "target"
    if intermediate_values:
        return intermediate_values, "intermediate"
    return None, "unparsed"


def _numbers(items) -> set | None:
    values = set()
    for item in items:
        try:
            node = item if not isinstance(item, str) else tree.parse(item.strip()).tree
            if node is None:
                return None
            value = to_sympy(node)
        except (MathParseError, NotImplementedError, TypeError, ValueError):
            return None
        value = sp.simplify(value)
        if not value.is_number or value.is_real is not True:
            return None
        values.add(value)
    return values


# --------------------------------------------------------------------------- dönüşüm sınıflandırması


def classify(previous, current, variable) -> str | None:
    """Ardışık iki denklem arasındaki işlemi yalnızca kanıtlanabiliyorsa adlandırır; değilse None."""
    l1, r1, l2, r2 = previous.lhs, previous.rhs, current.lhs, current.rhs
    try:
        if (l2 == variable and variable not in r2.free_symbols) or (r2 == variable and variable not in l2.free_symbols):
            if not (l1 == variable or r1 == variable):
                return "isolate_variable"
        d1, d2 = sp.simplify(l2 - l1), sp.simplify(r2 - r1)
        if d1 != 0 and _same(d1, d2):
            return "subtract_both_sides" if d1.is_number and d1.is_negative else "add_both_sides"
        if l1 != 0 and r1 != 0:
            k1, k2 = sp.simplify(l2 / l1), sp.simplify(r2 / r1)
            if k1 != 1 and _same(k1, k2):
                if k1.is_number and k1.is_rational and (1 / k1).is_integer and not k1.is_integer:
                    return "divide_both_sides"
                return "multiply_both_sides"
        if _same(l2, l1 ** 2) and _same(r2, r1 ** 2):
            return "square_both_sides"
        if _same(l1, l2) and _same(r1, r2):
            if sp.expand(l2) == l2 and sp.expand(r2) == r2 and (l1 != l2 or r1 != r2):
                return "expand"
            if isinstance(l2, sp.Mul) or isinstance(r2, sp.Mul):
                return "factor"
            return "rewrite"
    except (TypeError, ValueError, ZeroDivisionError, NotImplementedError):
        return None
    return None


# --------------------------------------------------------------------------- tanımlar ve öncüller


def from_definitions(target: AnswerTarget, originals: list[str]) -> Computed:
    """Her verilen denklem ``Sembol = sabit ifade`` tanımıysa istenen ifade yerine koyarak hesaplanır.

    Ör. A = √(16 + √81), B = √16 + √81 için B − A. Tanımlardan biri sembol içeriyorsa desteklenmez.
    """
    try:
        expr = requested_expression(target)
    except (MathParseError, NotImplementedError, TypeError):
        return Computed(None, "model_unsupported", [], [])
    if expr is None:
        return Computed(None, "model_unsupported", [], [])
    values: dict = {}
    for source in originals:
        try:
            if len(branches(source)) != 1:
                return Computed(None, "model_unsupported", [], [])
            eq = equation(source)
        except (MathParseError, NotImplementedError, TypeError):
            return Computed(None, "model_unsupported", [], [])
        if not isinstance(eq.lhs, sp.Symbol) or eq.rhs.free_symbols or eq.lhs in values:
            return Computed(None, "model_unsupported", [], [])
        values[eq.lhs] = sp.simplify(eq.rhs)
    if not expr.free_symbols or not expr.free_symbols <= set(values):
        return Computed(None, "model_unsupported", [], [])
    intermediate = [f"{symbol} = {text(value)}" for symbol, value in values.items()][:16]
    return Computed({sp.simplify(expr.subs(values))}, "computed", intermediate, [])


def premise_truths(statements: list[str], variable, roots: set) -> dict[str, bool] | None:
    """"I. x² = 16" gibi öncülleri tek çözümde değerlendirir. Biri değerlendirilemezse None (tahmin yok)."""
    if len(roots) != 1 or not statements:
        return None
    root = next(iter(roots))
    truths: dict[str, bool] = {}
    for raw in statements:
        match = re.match(r"^\s*(VI|IV|V|III|II|I)\s*[.)]\s*(.+?)\s*\.?\s*$", raw)
        if not match:
            return None
        parsed = tree.parse(match.group(2))
        if not parsed.parsed or not isinstance(parsed.tree, tree.Rel):
            return None
        try:
            operands = [to_sympy(item).subs(variable, root) for item in parsed.tree.operands]
        except (MathParseError, NotImplementedError, TypeError, ValueError):
            return None
        result = True
        for op, left, right in zip(parsed.tree.ops, operands, operands[1:]):
            difference = sp.simplify(left - right)
            if not difference.is_number or difference.is_real is not True:
                return None
            result = result and {"=": difference == 0, "!=": difference != 0, "<": difference < 0, "<=": difference <= 0,
                                 ">": difference > 0, ">=": difference >= 0}[op]
        truths[match.group(1)] = bool(result)
    return truths
