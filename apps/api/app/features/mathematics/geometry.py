"""Yapılandırılmış geometri doğrulaması (TA-008 §12–15). Yalnız yalıtılmış işçide çalışır.

Model olguları sembolik kısıtlara çevrilir (kenar uzunluğu ``L_AB``, açı ``a_ABC`` derece) ve önkoşulu
karşılanan teoremler denklem ekler. Kısıt sistemi SymPy ile *bütün* çözümleriyle çözülür:

- ``determined``: hedef kabul edilebilir bütün yapılandırmalarda tek değerli (modele göre evrensel).
- ``underdetermined``: hedef serbest kalıyor; ``ambiguous``: birden çok değer; ``inconsistent``: çözüm yok.

Rastgele bir uygun şekil üretmek kanıt değildir; sayısal örnekleme yapılmaz. Görünüş (dik görünen açı) olgu
değildir: yalnız ``USABLE_ORIGINS`` kökenli olgular kullanılır. Yardımcı çizim yalnız tanımı gereği izleyen olguları
kurar; ``construction`` kökenli olup çizimin ``establishes`` listesinde olmayan olgu ek varsayımdır ve reddedilir.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import sympy as sp

from ..education.mathematics import USABLE_ORIGINS, GeometryModel, MathCheck
from . import expr
from .theorems import THEOREMS

MAX_SYMBOLS = 14
MAX_EQUATIONS = 40
CONSTRUCTION_FACTS = {"altitude": {"right_angle", "perpendicular", "point_on_segment", "collinear"},
                      "segment": {"segment_length"}, "extension": {"collinear", "point_on_segment"},
                      "parallel_line": {"parallel"}, "midpoint": {"midpoint", "equal_segments", "point_on_segment"},
                      "radius": {"point_on_circle", "segment_length", "equal_segments"},
                      "perpendicular": {"perpendicular", "right_angle"}, "angle_bisector": {"equal_angles"}}


@dataclass
class GeometryResult:
    checks: list[MathCheck] = field(default_factory=list)
    determinacy: str = "not_applicable"
    target_values: list = field(default_factory=list)
    applied: list[str] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)


def L(a: str, b: str) -> sp.Symbol:
    first, second = sorted((a, b))
    return sp.Symbol(f"L_{first}{second}", positive=True)


def A(p: str, vertex: str, q: str) -> sp.Symbol:
    first, second = sorted((p, q))
    return sp.Symbol(f"a_{first}{vertex}{second}", positive=True)


def _value(latex: str):
    value = expr.expression(latex)
    if value.free_symbols or not expr.finite(value):
        raise expr.ExprError("geometry value must be a finite constant")
    return value


def _coord(latex: str):
    text = latex.strip().strip("()")
    parts = [item.strip() for item in text.split(",")]
    if len(parts) != 2:
        raise expr.ExprError("coordinate")
    return tuple(_value(item) for item in parts)


def analyze(model: GeometryModel) -> GeometryResult:
    result = GeometryResult()
    add = result.checks.append
    facts = [item for item in model.facts if item.origin in USABLE_ORIGINS]
    for item in model.facts:
        if item.origin not in USABLE_ORIGINS:
            result.ignored.append(item.id)
            add(MathCheck(id=f"fact_{item.id}", area="geometry", status="not_checked", reason="visual_fact_not_given",
                          scope="not_applicable",
                          detail="Şekilde görünen ama metinde verilmeyen/işaretlenmeyen olgu dayanak olarak kullanılmadı."))
    _check_constructions(model, result)
    construction_ids = {fid for c in model.constructions for fid in c.establishes}
    for item in facts:
        if item.origin == "construction" and item.id not in construction_ids:
            add(MathCheck(id=f"fact_{item.id}", area="construction", status="failed", reason="construction_overreach",
                          detail="Yardımcı çizimin tanımından izlemeyen olgu sessizce varsayılmış."))
    equations: list = []
    coords: dict[str, tuple] = {}
    triangles: list[tuple[str, str, str]] = []
    right_angles: set[tuple[str, str, str]] = set()
    try:
        for item in facts:
            p, o = item.points, item.other
            if item.kind == "segment_length" and len(p) == 2 and item.value:
                equations.append(sp.Eq(L(*p), _value(item.value)))
            elif item.kind == "angle_measure" and len(p) == 3 and item.value:
                equations.append(sp.Eq(A(*p), _value(item.value)))
            elif item.kind == "right_angle" and len(p) == 3:
                equations.append(sp.Eq(A(*p), 90))
                right_angles.add(tuple(p))
            elif item.kind == "equal_segments" and len(p) == 2 and len(o) == 2:
                equations.append(sp.Eq(L(*p), L(*o)))
            elif item.kind == "equal_angles" and len(p) == 3 and len(o) == 3:
                equations.append(sp.Eq(A(*p), A(*o)))
            elif item.kind == "midpoint" and len(p) == 3:
                m, a, b = p
                equations += [sp.Eq(L(a, m), L(m, b)), sp.Eq(L(a, b), 2 * L(a, m))]
                result.applied.append("midpoint")
            elif item.kind in {"point_on_segment", "collinear"} and len(p) == 3:
                q, a, b = p
                equations.append(sp.Eq(L(a, q) + L(q, b), L(a, b)))
            elif item.kind == "triangle" and len(p) == 3:
                triangles.append(tuple(p))
            elif item.kind == "coordinate" and len(p) == 1 and item.value:
                coords[p[0]] = _coord(item.value)
            elif item.kind == "tangent" and len(p) == 3:
                o_, t, q = p
                equations.append(sp.Eq(A(o_, t, q), 90))
                result.applied.append("tangent_radius")
            elif item.kind in {"similar", "congruent"} and len(p) == 3 and len(o) == 3:
                ratio = sp.Symbol(f"k_{item.id}", positive=True) if item.kind == "similar" else sp.Integer(1)
                for (a1, b1), (a2, b2) in zip(itertools.combinations(p, 2), itertools.combinations(o, 2)):
                    equations.append(sp.Eq(L(a1, b1), ratio * L(a2, b2)))
                for i in range(3):
                    equations.append(sp.Eq(A(p[i - 1], p[i], p[(i + 1) % 3]), A(o[i - 1], o[i], o[(i + 1) % 3])))
                result.applied.append(item.kind)
                _correspondence_check(item, model, result)
    except expr.ExprError as exc:
        add(MathCheck(id="geometry_model", area="geometry", status="unsupported", reason="value_unparsed", detail=str(exc)[:300]))
        result.determinacy = "unsupported"
        return result
    for a, b, c in triangles:
        equations.append(sp.Eq(A(c, a, b) + A(a, b, c) + A(b, c, a), 180))
        result.applied.append("triangle_angle_sum")
        for vertex_triple in ((b, a, c), (a, b, c), (a, c, b)):
            if vertex_triple in right_angles or vertex_triple[::-1] in right_angles:
                p, v, q = vertex_triple
                equations.append(sp.Eq(L(p, q) ** 2, L(p, v) ** 2 + L(v, q) ** 2))
                result.applied.append("pythagorean")
    for name, (x1, y1) in coords.items():
        for other, (x2, y2) in coords.items():
            if name < other:
                if (x1, y1) == (x2, y2):
                    add(MathCheck(id=f"coincident_{name}{other}", area="geometry", status="failed",
                                  reason="coincident_points", detail=f"{name} ve {other} aynı nokta."))
                equations.append(sp.Eq(L(name, other), sp.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)))
    if len(coords) > 1:
        result.applied.append("coordinate_distance")
    _numeric_triangle_checks(model, equations, triangles, result)
    if any(check.reason == "triangle_inequality_violated" for check in result.checks):
        result.determinacy = "inconsistent"
        _mentioned_without_preconditions(model, result)
        return result
    _solve(model, equations, result)
    _mentioned_without_preconditions(model, result)
    return result


def _check_constructions(model: GeometryModel, result: GeometryResult):
    facts = {item.id: item for item in model.facts}
    for construction in model.constructions:
        allowed = CONSTRUCTION_FACTS[construction.kind]
        bad = [fid for fid in construction.establishes if facts[fid].kind not in allowed]
        if bad:
            result.checks.append(MathCheck(id=f"construction_{construction.id}", area="construction", status="failed",
                                           reason="construction_overreach",
                                           detail=f"Çizim tanımı şu olguları kurmaz: {', '.join(bad)}"[:400]))
        elif construction.requires_proof:
            result.checks.append(MathCheck(id=f"construction_{construction.id}", area="construction",
                                           status="partially_checked", reason="construction_requires_proof",
                                           detail="Çizimin tanımından izleyen olgular kabul edildi; diğerleri kanıt ister."))
        else:
            result.checks.append(MathCheck(id=f"construction_{construction.id}", area="construction", status="passed",
                                           reason="construction_defined",
                                           detail="Çizim yalnız tanımı gereği izleyen olguları kuruyor."))


def _correspondence_check(item, model, result):
    """Benzerlik/eşlik köşe eşlemesi verilen uzunluklarla tutarlı mı? Başka eşleme tutarlıysa adlandırılır."""
    lengths = {}
    for fact in model.facts:
        if fact.kind == "segment_length" and fact.value and fact.origin in USABLE_ORIGINS and len(fact.points) == 2:
            try:
                lengths[frozenset(fact.points)] = _value(fact.value)
            except expr.ExprError:
                continue

    def ratios(first, second):
        out = []
        for (a1, b1), (a2, b2) in zip(itertools.combinations(first, 2), itertools.combinations(second, 2)):
            x, y = lengths.get(frozenset((a1, b1))), lengths.get(frozenset((a2, b2)))
            if x is not None and y is not None:
                out.append(sp.nsimplify(x / y))
        return out

    given = ratios(item.points, item.other)
    if len(given) < 2:
        return
    consistent = all(r == given[0] for r in given) and (item.kind == "similar" or given[0] == 1)
    if consistent:
        result.checks.append(MathCheck(id=f"{item.kind}_{item.id}", area="geometry", status="passed",
                                       reason="correspondence_consistent", scope="universal"))
        return
    alternative = any(len(r := ratios(item.points, perm)) >= 2 and all(v == r[0] for v in r)
                      for perm in itertools.permutations(item.other) if list(perm) != list(item.other))
    result.checks.append(MathCheck(id=f"{item.kind}_{item.id}", area="geometry", status="failed",
                                   reason="correspondence_mismatch" if alternative else "ratios_inconsistent",
                                   detail="Köşe eşlemesi verilen uzunluklarla uyuşmuyor."
                                   + (" Başka bir eşleme tutarlı." if alternative else "")))


def _numeric_triangle_checks(model, equations, triangles, result):
    known = {}
    for equation in equations:
        if isinstance(equation, sp.Equality) and equation.lhs.is_Symbol and equation.rhs.is_number:
            known[equation.lhs] = equation.rhs
    for a, b, c in triangles:
        sides = [known.get(L(a, b)), known.get(L(b, c)), known.get(L(a, c))]
        if all(item is not None for item in sides):
            x, y, z = sorted(sides, key=float)
            if not x + y > z:
                result.checks.append(MathCheck(id=f"triangle_{a}{b}{c}", area="geometry", status="failed",
                                               reason="triangle_inequality_violated",
                                               detail=f"{a}{b}{c} için kenarlar üçgen oluşturamaz (dejenere veya imkânsız)."))
            else:
                result.checks.append(MathCheck(id=f"triangle_{a}{b}{c}", area="geometry", status="passed",
                                               reason="triangle_inequality_holds", scope="universal"))
                if sp.simplify(x ** 2 + y ** 2 - z ** 2) == 0:
                    result.applied.append("pythagorean_converse")


def _target_symbol(model: GeometryModel):
    target = model.target
    if target is None:
        return None
    if target.kind == "length" and len(target.points) == 2:
        return L(*target.points)
    if target.kind == "angle" and len(target.points) == 3:
        return A(*target.points)
    return None


def _solve(model: GeometryModel, equations, result: GeometryResult):
    target = _target_symbol(model)
    symbols = sorted(set().union(*(eq.free_symbols for eq in equations)) if equations else set(), key=str)
    if not equations:
        result.determinacy = "underdetermined" if target is not None else "not_applicable"
    elif len(symbols) > MAX_SYMBOLS or len(equations) > MAX_EQUATIONS:
        result.determinacy = "unsupported"
        result.checks.append(MathCheck(id="geometry_system", area="geometry", status="unsupported",
                                       reason="constraint_system_too_large"))
        return
    else:
        try:
            solutions = sp.solve(equations, symbols, dict=True)
        except (NotImplementedError, TypeError, ValueError):
            result.determinacy = "unsupported"
            result.checks.append(MathCheck(id="geometry_system", area="geometry", status="unsupported",
                                           reason="solver_incomplete"))
            return
        admissible = [s for s in solutions if all(_admissible(sym, value) for sym, value in s.items())]
        if not admissible:
            result.determinacy = "inconsistent"
            result.checks.append(MathCheck(id="geometry_system", area="geometry", status="failed",
                                           reason="inconsistent_constraints",
                                           detail="Verilen olgular birlikte sağlanamıyor."))
            return
        if target is not None:
            values = {sp.nsimplify(sp.simplify(target.subs(s))) for s in admissible}
            if any(value.free_symbols for value in values):
                result.determinacy = "underdetermined"
            elif len(values) > 1:
                result.determinacy, result.target_values = "ambiguous", sorted(values, key=float)
            else:
                result.determinacy, result.target_values = "determined", list(values)
        else:
            result.determinacy = "consistent"
    if target is not None:
        status = {"determined": "passed", "underdetermined": "failed", "ambiguous": "failed"}.get(result.determinacy)
        if status:
            result.checks.append(MathCheck(
                id="geometry_target", area="geometry", status=status, reason=f"target_{result.determinacy}",
                scope="universal" if status == "passed" else "not_applicable",
                detail={"determined": "Hedef, verilen olgularla bütün uygun yapılandırmalarda tek değerli.",
                        "underdetermined": "Verilen olgular hedefi belirlemiyor; ek bilgi gerekir.",
                        "ambiguous": "Hedef birden çok değer alabiliyor."}[result.determinacy]))


def _admissible(symbol, value) -> bool:
    if value.free_symbols:
        return True
    if not expr.finite(value):
        return False
    if str(symbol).startswith("a_"):
        return 0 < value < 180
    return value > 0


def _mentioned_without_preconditions(model: GeometryModel, result: GeometryResult):
    applied = set(result.applied)
    for theorem_id in sorted(applied & set(THEOREMS)):
        result.checks.append(MathCheck(id=f"theorem_{theorem_id}", area="geometry", status="passed",
                                       reason="theorem_preconditions_met", scope="universal",
                                       detail=THEOREMS[theorem_id].name_tr))


def preconditions_for_mentions(model: GeometryModel | None, text: str, mentioned) -> list[MathCheck]:
    """Açıklamada adı geçen teorem, modelde önkoşulu bulunmadan kullanılmış mı?"""
    checks = []
    usable = {item.kind for item in (model.facts if model else []) if item.origin in USABLE_ORIGINS}
    requirements = {"pythagorean": {"right_angle"}, "similarity": {"similar"}, "isosceles": {"equal_segments"},
                    "tangent_radius": {"tangent"}, "midpoint": {"midpoint"}, "congruence": {"congruent"}}
    for theorem in mentioned:
        needed = requirements.get(theorem.id)
        if needed is None:
            continue
        if not needed & usable:
            checks.append(MathCheck(id=f"mention_{theorem.id}", area="geometry", status="failed",
                                    reason="theorem_preconditions_unmet",
                                    detail=f"{theorem.name_tr} kullanılmış; önkoşul ({', '.join(sorted(needed))}) "
                                           "metinde verilmemiş veya işaretlenmemiş."))
    return checks
