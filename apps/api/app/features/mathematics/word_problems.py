"""Sözel problem modeli denetimi (TA-008 §11). Yalnız yalıtılmış işçide çalışır.

İki ayrı soru: (1) Model kendi içinde tutarlı ve hedefi belirliyor mu? (aritmetik/cebir) (2) Model soruya sadık
mı? Bilinen her niceliğin değeri soru metninde geçmelidir; ilişkilerin metne uygunluğu otomatik kanıtlanmaz.
Bu yüzden ``model_fidelity`` hiçbir zaman ``passed`` olmaz: en iyi durum ``partially_checked``. Yanlış kurulmuş
modelin doğru çözümü özgün sorunun doğrulanmış çözümü değildir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import sympy as sp

from ..education.mathematics import MathCheck, WordProblemModel
from . import expr

MAX_SYMBOLS = 8
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


@dataclass
class WordResult:
    checks: list[MathCheck] = field(default_factory=list)
    status: str = "not_applicable"  # determined | ambiguous | insufficient | inconsistent | unsupported
    objective_values: list = field(default_factory=list)


def _numbers_in(text: str) -> set:
    out = set()
    for item in NUMBER.findall(text or ""):
        try:
            out.add(sp.nsimplify(item.replace(",", ".")))
        except (TypeError, ValueError, sp.SympifyError):
            continue
    return out


def analyze(model: WordProblemModel, question_text: str) -> WordResult:
    result = WordResult()
    add = result.checks.append
    symbols = {item.symbol: sp.Symbol(item.symbol, real=True) for item in model.quantities}
    if len(symbols) > MAX_SYMBOLS:
        result.status = "unsupported"
        add(MathCheck(id="word_model", area="word_problem", status="unsupported", reason="model_too_large"))
        return result
    equations, stated = [], []
    try:
        for item in model.quantities:
            if item.value is not None:
                value = expr.expression(item.value)
                if value.free_symbols:
                    raise expr.ExprError("known value must be constant")
                equations.append(sp.Eq(symbols[item.symbol], value))
                if item.origin == "stated":
                    stated.append((item, value))
        for index, latex in enumerate(model.relations):
            ops, sides = expr.relation(latex)
            if ops != ("=",):
                raise expr.ExprError("relation must be an equation")
            names = {str(s) for s in set().union(*(side.free_symbols for side in sides))}
            if names - set(symbols):
                add(MathCheck(id=f"relation_{index}", area="word_problem", status="failed", reason="undeclared_symbol",
                              statement=latex, detail="İlişki modelde tanımlanmamış nicelik kullanıyor."))
                result.status = "unsupported"
                return result
            equations.append(sp.Eq(*[side.subs({sp.Symbol(n, real=True): symbols[n] for n in names}) for side in sides]))
        objective = expr.expression(model.objective)
    except expr.ExprError as exc:
        result.status = "unsupported"
        add(MathCheck(id="word_model", area="word_problem", status="unsupported", reason="model_unparsed", detail=str(exc)[:300]))
        return result
    # Sadakat: bilinen değerler metinde geçiyor mu? (ilişkilerin doğruluğu ayrıca kanıtlanmaz)
    numbers = _numbers_in(question_text)
    missing = [item.symbol for item, value in stated if value not in numbers and -value not in numbers]
    add(MathCheck(id="model_fidelity", area="model_fidelity",
                  status="failed" if missing else "partially_checked",
                  reason="value_not_in_source" if missing else "values_grounded_relations_unverified",
                  detail=(f"Metinde bulunmayan bilinen değer(ler): {', '.join(missing)}" if missing else
                          "Bilinen değerler soru metninde geçiyor; ilişkilerin soruya uygunluğu otomatik kanıtlanmadı.")))
    unknown = [symbols[item.symbol] for item in model.quantities if item.value is None]
    try:
        solutions = sp.solve(equations, list(symbols.values()), dict=True)
    except (NotImplementedError, TypeError, ValueError):
        result.status = "unsupported"
        add(MathCheck(id="word_solution", area="word_problem", status="unsupported", reason="solver_incomplete"))
        return result
    constraints = {item.symbol: item.kind for item in model.constraints}
    discrete = {item.symbol for item in model.quantities if item.discrete}
    admissible = [s for s in solutions if _admissible(s, symbols, constraints, discrete)]
    if not solutions:
        result.status = "inconsistent"
        add(MathCheck(id="word_solution", area="word_problem", status="failed", reason="inconsistent_conditions",
                      detail="Koşullar birlikte sağlanamıyor."))
        return result
    if not admissible:
        result.status = "inconsistent"
        add(MathCheck(id="word_solution", area="word_problem", status="failed", reason="constraint_violated",
                      detail="Çözüm var ama pozitiflik/tam sayılık gibi problem koşullarını sağlamıyor."))
        return result
    values = {sp.nsimplify(sp.simplify(objective.subs(s))) for s in admissible}
    if any(value.free_symbols & set(unknown) or value.free_symbols for value in values):
        result.status = "insufficient"
        add(MathCheck(id="word_solution", area="word_problem", status="failed", reason="insufficient_information",
                      detail="Verilen bilgiler hedefi tek başına belirlemiyor."))
        return result
    if len(values) > 1:
        result.status, result.objective_values = "ambiguous", sorted(values, key=float)
        add(MathCheck(id="word_solution", area="word_problem", status="failed", reason="multiple_solutions",
                      detail="Model birden çok hedef değerine izin veriyor."))
        return result
    result.status, result.objective_values = "determined", list(values)
    add(MathCheck(id="word_solution", area="word_problem", status="passed", reason="objective_determined",
                  detail="Model hedefi tek değerle belirliyor (modelin soruya sadakati ayrıca değerlendirilir)."))
    return result


def _admissible(solution, symbols, constraints, discrete) -> bool:
    for name, symbol in symbols.items():
        value = solution.get(symbol)
        if value is None or value.free_symbols:
            continue
        if not expr.finite(value):
            return False
        kind = constraints.get(name)
        if kind == "positive" and not value > 0:
            return False
        if kind == "nonnegative" and not value >= 0:
            return False
        if (kind in {"integer", "natural"} or name in discrete) and not value.is_integer:
            return False
        if kind == "natural" and value < 0:
            return False
    return True
