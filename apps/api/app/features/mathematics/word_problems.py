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
    # Sadakat (TA-008B): bilinen değerin metinde geçmesi anlamını kanıtlamaz. Değer, metinden birebir alıntıyla
    # (``evidence``) bağlanırsa "dayanaklı", yalnız sayı metinde varsa "anlamı doğrulanmamış" sayılır.
    numbers = _numbers_in(question_text)
    text = _norm(question_text)
    missing, unanchored = [], []
    for item, value in stated:
        if value not in numbers and -value not in numbers:
            missing.append(item.symbol)
        elif not (item.evidence and _norm(item.evidence) in text and value in _numbers_in(item.evidence)):
            unanchored.append(item.symbol)
    if missing:
        status, reason = "failed", "value_not_in_source"
        detail = f"Metinde bulunmayan bilinen değer(ler): {', '.join(missing)}"
    elif unanchored:
        status, reason = "partially_checked", "value_meaning_unanchored"
        detail = (f"Sayı metinde var ama hangi niceliğe ait olduğu alıntıyla bağlanmadı: {', '.join(unanchored)}. "
                  "İlişkilerin soruya uygunluğu otomatik kanıtlanmadı.")
    else:
        status, reason = "partially_checked", "values_anchored_relations_unverified"
        detail = "Bilinen değerler metindeki alıntılara bağlı; ilişkilerin soruya uygunluğu otomatik kanıtlanmadı."
    add(MathCheck(id="model_fidelity", area="model_fidelity", status=status, reason=reason, detail=detail))
    unit_problem = _unit_mismatch(model, equations, symbols)
    if unit_problem:
        add(MathCheck(id="word_units", area="word_problem", status="failed", reason="unit_mismatch", detail=unit_problem))
        result.status = "inconsistent"
        return result
    unknown = [symbols[item.symbol] for item in model.quantities if item.value is None]
    try:
        solutions = sp.solve(equations, list(symbols.values()), dict=True)
    except (NotImplementedError, TypeError, ValueError):
        result.status = "unsupported"
        add(MathCheck(id="word_solution", area="word_problem", status="unsupported", reason="solver_incomplete"))
        return result
    # TA-008B: aynı değişkene birden çok kısıt birbirini ezmez; hepsi birlikte uygulanır.
    constraints: dict[str, set[str]] = {}
    for item in model.constraints:
        constraints.setdefault(item.symbol, set()).add(item.kind)
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
        kinds = constraints.get(name, set())
        if "positive" in kinds and not value > 0:
            return False
        if "nonnegative" in kinds and not value >= 0:
            return False
        if (kinds & {"integer", "natural"} or name in discrete) and not value.is_integer:
            return False
        if "natural" in kinds and value < 0:
            return False
    return True


def _norm(text: str) -> str:
    lowered = (text or "").replace("İ", "i").replace("I", "ı").lower().replace("'", "").replace("’", "")
    return " ".join(lowered.split())


def _unit_mismatch(model: WordProblemModel, equations, symbols) -> str | None:
    """Toplanan/eşitlenen yalın niceliklerin birimleri aynı olmalı (ör. km ile dakika toplanmaz). Çarpım ve bölümde
    birim cebiri yapılmaz; bu sınır açıkça kısmidir."""
    units = {symbols[item.symbol]: _norm(item.unit) for item in model.quantities if item.unit}
    for equation in equations:
        for side in (equation.lhs - equation.rhs,):
            terms = side.args if isinstance(side, sp.Add) else (side,)
            bare = [term if term.is_Symbol else -term if (-term).is_Symbol else None for term in terms]
            found = {units[t] for t in bare if t is not None and t in units}
            if len(found) > 1:
                return f"Aynı ilişkide farklı birimler toplanıyor/eşitleniyor: {', '.join(sorted(found))}"
    return None
