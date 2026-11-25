"""Yapılandırılmış geometri doğrulaması (TA-008, TA-008B). Yalnız yalıtılmış işçide çalışır.

TA-008B kanıt zinciri — bir olgu ancak *sunucu* kabul ederse kısıt olur:

- ``stated``: ``evidence`` alanındaki alıntı soru metninde (normalleştirilmiş) birebir bulunmalı ve olgunun noktalarını
  ve değerini içermelidir → ``source_text``. Bulunmazsa olgu yalnız sağlayıcı önerisidir (``provider_proposed``) ve
  kullanılmaz. Metnin kendisi görselden AI ile okunmuş olabilir; bu sınır raporda yazılır.
- ``marked``: soruda şekil olmalıdır → ``diagram_interpreted`` (işaretin varlığı görselden AI okumasıdır; kısmi).
- ``derived``: ``premises`` ve ``rule`` ile; öncüller kabul edilmiş, kural desteklenen ve yerel olarak uygulanabilir
  olmalı, döngü olmamalı → ``validated_derivation``. Aksi halde açıklayıcı hipotezdir, kısıt değildir.
- ``construction``: yalnız geometrik olarak doğrulanmış bir yardımcı çizimin tanımından izleyen olgu
  (ör. yükseklik dikliği kurar; ayağın kenar *üzerinde* olduğunu veya BD = DC olduğunu kurmaz).
- ``visual_uncertain``: hiçbir zaman kullanılmaz.

Reddedilen olgu hesaptan çıkarılır (kayıt yalnız raporlanmaz). Doğrusallık aradalık değildir: sıralaması bilinmeyen
doğrusal üçlüler için bütün sıralamalar ayrı durumlar olarak çözülür. Sonuç ``model`` kapsamındadır: temsil edilen
kısıt sisteminin bütün çözümleri; Öklid düzleminde gerçekleşebilirlik ayrıca kanıtlanmaz.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field

import sympy as sp

from ..education.mathematics import GeometryModel, MathCheck
from . import expr
from .theorems import THEOREMS

MAX_SYMBOLS = 14
MAX_EQUATIONS = 40
MAX_CASES = 27
DERIVATION_RULES = {"triangle_angle_sum", "isosceles_base_angles", "pythagorean", "similar_aa", "midpoint_halves"}


@dataclass
class GeometryResult:
    checks: list[MathCheck] = field(default_factory=list)
    determinacy: str = "not_applicable"
    target_values: list = field(default_factory=list)
    applied: list[str] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)
    accepted: dict[str, str] = field(default_factory=dict)  # olgu → kanıt sınıfı
    rejected: dict[str, str] = field(default_factory=dict)  # olgu → neden
    source_contradiction: bool = False


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


def _norm(text: str) -> str:
    lowered = (text or "").replace("İ", "i").replace("I", "ı").lower()
    lowered = lowered.replace("°", " derece ").replace("∠", " açı ").replace("'", "").replace("’", "")
    return re.sub(r"\s+", " ", re.sub(r"\s*([=,.:;])\s*", r"\1", lowered)).strip()


def _pair(raw: str, a: str, b: str) -> bool:
    return f"{a}{b}" in raw or f"{b}{a}" in raw or f"|{a}{b}|" in raw


def _supports(fact, fragment: str) -> bool:
    """Alıntı olgunun nesnelerini ve değerini içeriyor mu? (anlamını kanıtlamaz; yalnız kaynağa bağ kurar)"""
    raw = fragment or ""
    lowered = _norm(raw)
    if fact.kind in {"angle_measure", "right_angle"} and len(fact.points) == 3:
        vertex = fact.points[1]
        named = "".join(fact.points) in raw or "".join(reversed(fact.points)) in raw
        has_objects = named or (vertex in raw and ("açı" in lowered or "dik" in lowered))
    elif fact.kind in {"segment_length"} and len(fact.points) == 2:
        has_objects = _pair(raw, *fact.points)
    elif fact.kind == "equal_segments" and len(fact.points) == 2 and len(fact.other) == 2:
        has_objects = _pair(raw, *fact.points) and _pair(raw, *fact.other)
    else:
        has_objects = all(p in raw for p in fact.points + fact.other)
    has_value = fact.value is None or _norm(fact.value).replace(" ", "") in lowered.replace(" ", "")
    return has_objects and has_value


@dataclass(frozen=True)
class Source:
    """Sorunun sunucudaki kaydı: metin ve şekil var mı. ``text`` görselden okunmuş olabilir (AI destekli)."""

    text: str = ""
    has_figure: bool = False


def analyze(model: GeometryModel, source: Source | None = None) -> GeometryResult:
    source = source or Source()
    result = GeometryResult()
    add = result.checks.append
    _validate_objects(model, result)
    _classify_sources(model, source, result)
    valid_constructions = _check_constructions(model, result)
    for item in model.facts:
        if item.origin == "construction" and item.id not in result.rejected:
            if item.id in valid_constructions:
                result.accepted[item.id] = "construction_defined"
            else:
                result.rejected[item.id] = "construction_overreach"
                add(MathCheck(id=f"fact_{item.id}", area="construction", status="failed", reason="construction_overreach",
                              detail="Geçerli bir yardımcı çizimin tanımından izlemeyen olgu kısıt olarak kullanılmadı."))
    _validate_derivations(model, result)
    _tangent_preconditions(model, result)
    usable = [item for item in model.facts if item.id in result.accepted]
    for fid, reason in result.rejected.items():
        result.ignored.append(fid)
        if reason in {"visual_fact_not_given", "provider_proposed", "unsupported_derivation", "circular_derivation",
                      "missing_premise", "tangent_preconditions_unmet", "degenerate_object", "rule_not_applicable"}:
            add(MathCheck(id=f"fact_{fid}", area="geometry", status="not_checked", reason=reason, scope="not_applicable",
                          detail=_REASON_TR.get(reason)))
    try:
        base, collinear, triangles, coords, right_angles = _equations(usable, result)
    except expr.ExprError as exc:
        add(MathCheck(id="geometry_model", area="geometry", status="unsupported", reason="value_unparsed", detail=str(exc)[:300]))
        result.determinacy = "unsupported"
        return result
    for a, b, c in triangles:
        base.append(sp.Eq(A(c, a, b) + A(a, b, c) + A(b, c, a), 180))
        result.applied.append("triangle_angle_sum")
        for vertex_triple in ((b, a, c), (a, b, c), (a, c, b)):
            if vertex_triple in right_angles or vertex_triple[::-1] in right_angles:
                p, v, q = vertex_triple
                base.append(sp.Eq(L(p, q) ** 2, L(p, v) ** 2 + L(v, q) ** 2))  # yalnız bu üçgenin dik açısı
                result.applied.append("pythagorean")
        _isosceles(usable, (a, b, c), base, result)
    _coordinate_equations(coords, base, result)
    _numeric_triangle_checks(base, triangles, result)
    if any(check.reason in {"triangle_inequality_violated", "coincident_points"} for check in result.checks):
        result.determinacy = "inconsistent"
        result.source_contradiction = _all_source(usable, result)
        _theorem_checks(result)
        return result
    _solve(model, base, collinear, result, usable)
    _theorem_checks(result)
    return result


_REASON_TR = {
    "visual_fact_not_given": "Şekilde görünen ama metinde verilmeyen/işaretlenmeyen olgu dayanak olarak kullanılmadı.",
    "provider_proposed": "'Verilen' denilen olgu soru metninde bulunamadı; yalnız sağlayıcı önerisi olarak kaldı.",
    "unsupported_derivation": "Türetme kuralı sunucuda doğrulanamıyor; olgu açıklayıcı hipotez olarak kaldı.",
    "circular_derivation": "Türetme kendi sonucuna dayanıyor (döngü); kullanılmadı.",
    "missing_premise": "Türetmenin öncülü kabul edilmiş bir olgu değil; kullanılmadı.",
    "tangent_preconditions_unmet": "Teğet olgusu için çember merkezi ve değme noktası modelde yok.",
    "degenerate_object": "Nesne tekrarlı noktalarla tanımlanmış (dejenere); kullanılmadı.",
    "rule_not_applicable": "Kural bu olguların yerel nesnelerine uymuyor.",
}


def _validate_objects(model: GeometryModel, result: GeometryResult):
    need_distinct = {"triangle": 3, "angle_measure": 3, "right_angle": 3, "segment_length": 2, "midpoint": 3,
                     "point_on_segment": 3, "collinear": 3, "similar": 3, "congruent": 3, "tangent": 3}
    for item in model.facts:
        size = need_distinct.get(item.kind)
        if size and (len(item.points) != size or len(set(item.points)) != size or
                     (item.other and len(set(item.other)) != len(item.other))):
            result.rejected[item.id] = "degenerate_object"


def _classify_sources(model: GeometryModel, source: Source, result: GeometryResult):
    text = _norm(source.text)
    for item in model.facts:
        if item.id in result.rejected:
            continue
        if item.origin == "visual_uncertain":
            result.rejected[item.id] = "visual_fact_not_given"
        elif item.origin == "stated":
            fragment = item.evidence or ""
            if fragment and _norm(fragment) in text and _supports(item, fragment):
                result.accepted[item.id] = "source_text"
            else:
                result.rejected[item.id] = "provider_proposed"
        elif item.origin == "marked":
            if source.has_figure:
                result.accepted[item.id] = "diagram_interpreted"
            else:
                result.rejected[item.id] = "provider_proposed"


def _validate_derivations(model: GeometryModel, result: GeometryResult):
    facts = {item.id: item for item in model.facts}
    derived = [item for item in model.facts if item.origin == "derived" and item.id not in result.rejected]
    state: dict[str, str] = {}

    def visit(fid: str, stack: tuple[str, ...]) -> bool:
        if fid in result.accepted:
            return True
        if fid in stack:
            result.rejected[stack[0]] = "circular_derivation"
            return False
        item = facts.get(fid)
        if item is None or item.origin != "derived" or fid in result.rejected:
            return False
        if state.get(fid) == "done":
            return fid in result.accepted
        if item.rule not in DERIVATION_RULES:
            result.rejected[fid] = "unsupported_derivation"
            state[fid] = "done"
            return False
        if not item.premises or not all(visit(p, stack + (fid,)) for p in item.premises):
            result.rejected.setdefault(fid, "missing_premise")
            state[fid] = "done"
            return False
        if _rule_holds(item, [facts[p] for p in item.premises]):
            result.accepted[fid] = "validated_derivation"
        else:
            result.rejected[fid] = "rule_not_applicable"
        state[fid] = "done"
        return fid in result.accepted

    for item in derived:
        visit(item.id, ())


def _vertex_angle(points):
    return tuple(points) if len(points) == 3 else None


def _rule_holds(fact, premises) -> bool:
    """Desteklenen kuralların *yerel* uygulanabilirliği (adın geçmesi yetmez)."""
    kinds = {p.kind for p in premises}
    if fact.rule == "midpoint_halves":
        mid = next((p for p in premises if p.kind == "midpoint"), None)
        if mid is None or fact.kind != "equal_segments":
            return False
        m, a, b = mid.points
        return {frozenset(fact.points), frozenset(fact.other)} == {frozenset((a, m)), frozenset((m, b))}
    if fact.rule == "isosceles_base_angles":
        tri = next((p for p in premises if p.kind == "triangle"), None)
        eq = next((p for p in premises if p.kind == "equal_segments"), None)
        if tri is None or eq is None or fact.kind != "equal_angles":
            return False
        shared = set(eq.points) & set(eq.other)
        if len(shared) != 1 or not (set(eq.points) | set(eq.other)) <= set(tri.points):
            return False
        apex = shared.pop()
        b, c = [p for p in tri.points if p != apex]
        return {fact.points[1], fact.other[1]} == {b, c} and set(fact.points) == set(fact.other) == set(tri.points)
    if fact.rule == "triangle_angle_sum":
        tri = next((p for p in premises if p.kind == "triangle"), None)
        angles = [p for p in premises if p.kind == "angle_measure"]
        if tri is None or fact.kind != "angle_measure" or len(angles) != 2 or fact.value is None:
            return False
        vertices = {p.points[1] for p in angles} | {fact.points[1]}
        if vertices != set(tri.points) or not all(set(p.points) == set(tri.points) for p in [*angles, fact]):
            return False
        try:
            return sp.simplify(180 - _value(angles[0].value) - _value(angles[1].value) - _value(fact.value)) == 0
        except expr.ExprError:
            return False
    if fact.rule == "pythagorean":
        tri = next((p for p in premises if p.kind == "triangle"), None)
        right = next((p for p in premises if p.kind == "right_angle"), None)
        sides = [p for p in premises if p.kind == "segment_length"]
        if tri is None or right is None or fact.kind != "segment_length" or len(sides) != 2 or fact.value is None:
            return False
        if set(right.points) != set(tri.points):
            return False  # dik açı başka bir üçgene ait
        p, v, q = right.points
        try:
            known = {frozenset(s.points): _value(s.value) for s in sides}
            known[frozenset(fact.points)] = _value(fact.value)
            hyp, a, b = known.get(frozenset((p, q))), known.get(frozenset((p, v))), known.get(frozenset((v, q)))
            return None not in (hyp, a, b) and sp.simplify(hyp ** 2 - a ** 2 - b ** 2) == 0
        except expr.ExprError:
            return False
    if fact.rule == "similar_aa":
        if fact.kind != "similar" or len(kinds - {"equal_angles"}) or len(premises) < 2:
            return False
        pairs = {(p.points[1], p.other[1]) for p in premises}
        mapping = dict(zip(fact.points, fact.other))
        return len(pairs) >= 2 and all(mapping.get(a) == b or mapping.get(b) == a for a, b in pairs)
    return False


def _tangent_preconditions(model: GeometryModel, result: GeometryResult):
    for item in model.facts:
        if item.kind != "tangent" or item.id not in result.accepted:
            continue
        center, touch = item.points[0], item.points[1]
        ok = any(other.id in result.accepted and ((other.kind == "point_on_circle" and other.points[:2] == [center, touch])
                                                  or (other.kind == "circle" and other.points[0] == center and touch in other.points))
                 for other in model.facts)
        if not ok:
            result.accepted.pop(item.id)
            result.rejected[item.id] = "tangent_preconditions_unmet"


def _equations(usable, result):
    equations, collinear, triangles, coords, right_angles = [], [], [], {}, set()
    for item in usable:
        p, o = item.points, item.other
        if item.kind == "segment_length" and item.value:
            equations.append(sp.Eq(L(*p), _value(item.value)))
        elif item.kind == "angle_measure" and item.value:
            equations.append(sp.Eq(A(*p), _value(item.value)))
        elif item.kind == "right_angle":
            equations.append(sp.Eq(A(*p), 90))
            right_angles.add(tuple(p))
        elif item.kind == "equal_segments" and len(p) == 2 and len(o) == 2:
            equations.append(sp.Eq(L(*p), L(*o)))
        elif item.kind == "equal_angles" and len(p) == 3 and len(o) == 3:
            equations.append(sp.Eq(A(*p), A(*o)))
        elif item.kind == "midpoint":
            m, a, b = p
            equations += [sp.Eq(L(a, m), L(m, b)), sp.Eq(L(a, b), 2 * L(a, m))]
            result.applied.append("midpoint")
        elif item.kind == "point_on_segment":
            q, a, b = p  # aradalık açıkça verilmiş: Q, A ile B arasında
            equations.append(sp.Eq(L(a, q) + L(q, b), L(a, b)))
        elif item.kind == "collinear":
            collinear.append(tuple(p))  # sıralama bilinmiyor: durumlar ayrı çözülür
        elif item.kind == "triangle":
            triangles.append(tuple(p))
        elif item.kind == "coordinate" and item.value:
            coords[p[0]] = _coord(item.value)
        elif item.kind == "tangent":
            o_, t, q = p
            equations.append(sp.Eq(A(o_, t, q), 90))
            result.applied.append("tangent_radius")
        elif item.kind in {"similar", "congruent"} and len(o) == 3:
            ratio = sp.Symbol(f"k_{item.id}", positive=True) if item.kind == "similar" else sp.Integer(1)
            for (a1, b1), (a2, b2) in zip(itertools.combinations(p, 2), itertools.combinations(o, 2)):
                equations.append(sp.Eq(L(a1, b1), ratio * L(a2, b2)))
            for i in range(3):
                equations.append(sp.Eq(A(p[i - 1], p[i], p[(i + 1) % 3]), A(o[i - 1], o[i], o[(i + 1) % 3])))
            result.applied.append(item.kind)
            _correspondence_check(item, usable, result)
    return equations, collinear, triangles, coords, right_angles


def _isosceles(usable, triangle, equations, result):
    """İkizkenar: yalnız *aynı üçgende*, ortak köşeli eşit kenar olgusu varsa taban açıları eşitlenir."""
    for item in usable:
        if item.kind != "equal_segments" or len(item.points) != 2 or len(item.other) != 2:
            continue
        shared = set(item.points) & set(item.other)
        if len(shared) != 1 or not (set(item.points) | set(item.other)) <= set(triangle):
            continue
        apex = shared.pop()
        b, c = [p for p in triangle if p != apex]
        equations.append(sp.Eq(A(apex, b, c), A(apex, c, b)))
        result.applied.append("isosceles")


def _coordinate_equations(coords, equations, result):
    for name, (x1, y1) in coords.items():
        for other, (x2, y2) in coords.items():
            if name < other:
                if (x1, y1) == (x2, y2):
                    result.checks.append(MathCheck(id=f"coincident_{name}{other}", area="geometry", status="failed",
                                                   reason="coincident_points", detail=f"{name} ve {other} aynı nokta."))
                equations.append(sp.Eq(L(name, other), sp.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)))
    if len(coords) > 1:
        result.applied.append("coordinate_distance")


def _correspondence_check(item, usable, result):
    lengths = {}
    for fact in usable:
        if fact.kind == "segment_length" and fact.value and len(fact.points) == 2:
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
                                       reason="correspondence_consistent", scope="model"))
        return
    alternative = any(len(r := ratios(item.points, perm)) >= 2 and all(v == r[0] for v in r)
                      for perm in itertools.permutations(item.other) if list(perm) != list(item.other))
    result.checks.append(MathCheck(id=f"{item.kind}_{item.id}", area="geometry", status="failed",
                                   reason="correspondence_mismatch" if alternative else "ratios_inconsistent",
                                   detail="Köşe eşlemesi verilen uzunluklarla uyuşmuyor."
                                   + (" Başka bir eşleme tutarlı." if alternative else "")))


def _numeric_triangle_checks(equations, triangles, result):
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
                                               reason="triangle_inequality_holds", scope="model"))
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


def _orderings(triple):
    """Doğrusal üç noktanın üç olası aradalık durumu: (orta nokta, uç1, uç2)."""
    a, b, c = triple
    return [(a, b, c), (b, a, c), (c, a, b)]


def _solve(model: GeometryModel, base, collinear, result: GeometryResult, usable):
    target = _target_symbol(model)
    cases = list(itertools.product(*[_orderings(t) for t in collinear])) if collinear else [()]
    if len(cases) > MAX_CASES:
        result.determinacy = "unsupported"
        result.checks.append(MathCheck(id="geometry_system", area="geometry", status="unsupported", reason="too_many_cases"))
        return
    values: set = set()
    free = False
    any_admissible = False
    for case in cases:
        equations = base + [sp.Eq(L(m, a) + L(m, b), L(a, b)) for m, a, b in case]
        if not equations:
            free = True
            continue
        symbols = sorted(set().union(*(eq.free_symbols for eq in equations)), key=str)
        if len(symbols) > MAX_SYMBOLS or len(equations) > MAX_EQUATIONS:
            result.determinacy = "unsupported"
            result.checks.append(MathCheck(id="geometry_system", area="geometry", status="unsupported",
                                           reason="constraint_system_too_large"))
            return
        try:
            solutions = sp.solve(equations, symbols, dict=True)
        except (NotImplementedError, TypeError, ValueError):
            result.determinacy = "unsupported"
            result.checks.append(MathCheck(id="geometry_system", area="geometry", status="unsupported", reason="solver_incomplete"))
            return
        admissible = [s for s in solutions if all(_admissible(sym, value) for sym, value in s.items())]
        if not admissible:
            continue
        any_admissible = True
        if target is not None:
            for s in admissible:
                value = sp.nsimplify(sp.simplify(target.subs(s)))
                if value.free_symbols:
                    free = True
                else:
                    values.add(value)
    if not any_admissible and not free:
        result.determinacy = "inconsistent"
        result.source_contradiction = _all_source(usable, result)
        result.checks.append(MathCheck(id="geometry_system", area="geometry", status="failed", reason="inconsistent_constraints",
                                       detail="Kabul edilen olgular birlikte sağlanamıyor."))
        return
    if target is None:
        result.determinacy = "consistent"
        return
    if free:
        result.determinacy = "underdetermined"
    elif len(values) > 1:
        result.determinacy, result.target_values = "ambiguous", sorted(values, key=float)
    else:
        result.determinacy, result.target_values = "determined", list(values)
    status = {"determined": "passed", "underdetermined": "failed", "ambiguous": "failed"}[result.determinacy]
    detail = {"determined": "Hedef, kabul edilen olgularla temsil edilen modelin bütün çözümlerinde tek değerli "
                            "(Öklid düzleminde gerçekleşebilirlik ayrıca kanıtlanmadı).",
              "underdetermined": "Kabul edilen olgular hedefi belirlemiyor; ek bilgi gerekir.",
              "ambiguous": "Hedef birden çok değer alabiliyor (ör. noktaların sıralaması belirsiz)."}[result.determinacy]
    result.checks.append(MathCheck(id="geometry_target", area="geometry", status=status, reason=f"target_{result.determinacy}",
                                   scope="model" if status == "passed" else "not_applicable", detail=detail))


def _all_source(usable, result) -> bool:
    """Bütün kabul edilen olgular doğrudan kaynaktan mı (metin/şekil)? O zaman çelişki kaynağın kendisindedir."""
    return bool(usable) and all(result.accepted.get(item.id) in {"source_text", "diagram_interpreted"} for item in usable)


def _admissible(symbol, value) -> bool:
    if value.free_symbols:
        return True
    if not expr.finite(value):
        return False
    if str(symbol).startswith("a_"):
        return 0 < value < 180
    return value > 0


def _theorem_checks(result: GeometryResult):
    for theorem_id in sorted(set(result.applied) & set(THEOREMS)):
        result.checks.append(MathCheck(id=f"theorem_{theorem_id}", area="geometry", status="passed",
                                       reason="theorem_preconditions_met", scope="model", detail=THEOREMS[theorem_id].name_tr))


# --- Yardımcı çizimler ------------------------------------------------------------------------------------------

def _check_constructions(model: GeometryModel, result: GeometryResult) -> set[str]:
    """Her çizim için tanımı gereği kurabileceği olguları *geometrik olarak* doğrular. Döndürür: kabul edilen olgular."""
    facts = {item.id: item for item in model.facts}
    accepted: set[str] = set()
    for c in model.constructions:
        problems = []
        if set(c.new_points) & set(model.points):
            problems.append("yeni nokta modelde zaten var")
        allowed = _construction_patterns(c)
        if allowed is None:
            problems.append("başvurular çizim türüne uymuyor")
            allowed = []
        bad = [fid for fid in c.establishes if not any(_matches(facts[fid], pattern) for pattern in allowed)]
        if problems or bad:
            # Aşan olgular reddedilir ve hesaba girmez; çizimin geçerli kısmı (yalnız başvurular tutarlıysa) korunur.
            for fid in c.establishes:
                if fid in bad or problems:
                    result.rejected[fid] = "construction_overreach"
            if not problems:
                accepted.update(fid for fid in c.establishes if fid not in bad)
            result.checks.append(MathCheck(id=f"construction_{c.id}", area="construction", status="failed",
                                           reason="construction_overreach",
                                           detail=("; ".join(problems) or f"Çizim şu olguları kurmaz: {', '.join(bad)}")[:400]))
            continue
        accepted.update(c.establishes)
        status = "partially_checked" if c.requires_proof else "passed"
        result.checks.append(MathCheck(id=f"construction_{c.id}", area="construction", status=status,
                                       reason="construction_requires_proof" if c.requires_proof else "construction_defined",
                                       detail="Çizim yalnız tanımı gereği izleyen olguları kuruyor."))
    return accepted


def _construction_patterns(c):
    """(tür, noktalar kümesi/sırası koşulu) desenleri. ``None``: başvurular türle uyumsuz."""
    refs, new = c.references, c.new_points
    if c.kind == "altitude":
        if len(refs) != 3 or len(new) != 1:
            return None
        a, b, cc = refs
        h = new[0]
        # Yükseklik ayağı BC doğrusu üzerindedir (kenarın uzantısında olabilir): aradalık kurulmaz.
        return [("right_angle", lambda f: f.points[1] == h and set(f.points) in ({a, h, b}, {a, h, cc})),
                ("perpendicular", lambda f: set(f.points) == {a, h} and set(f.other) <= {b, cc, h}),
                ("collinear", lambda f: set(f.points) == {h, b, cc})]
    if c.kind == "perpendicular":
        if len(refs) != 3 or len(new) != 1:
            return None
        p, a, b = refs
        h = new[0]
        return [("right_angle", lambda f: f.points[1] == h and set(f.points) in ({p, h, a}, {p, h, b})),
                ("collinear", lambda f: set(f.points) == {h, a, b})]
    if c.kind == "midpoint":
        if len(refs) != 2 or len(new) != 1:
            return None
        a, b = refs
        m = new[0]
        return [("midpoint", lambda f: f.points[0] == m and set(f.points[1:]) == {a, b})]
    if c.kind == "extension":
        if len(refs) != 2 or len(new) != 1:
            return None
        return [("collinear", lambda f: set(f.points) == {*refs, new[0]})]
    if c.kind == "parallel_line":
        if len(refs) != 3 or len(new) != 1:
            return None
        p, a, b = refs
        return [("parallel", lambda f: set(f.points) == {p, new[0]} and set(f.other) == {a, b})]
    if c.kind == "radius":
        if len(refs) != 2:
            return None
        o, p = refs
        return [("point_on_circle", lambda f: f.points[:2] == [o, p])]
    if c.kind == "angle_bisector":
        if len(refs) != 3 or len(new) != 1:
            return None
        a, b, cc = refs
        d = new[0]
        return [("equal_angles", lambda f: {tuple(f.points), tuple(f.other)} in ({(a, b, d), (d, b, cc)}, {(d, b, a), (cc, b, d)}))]
    if c.kind == "segment":
        return [] if len(refs) == 2 else None  # bir doğru parçası çizmek uzunluk veya ilişki kurmaz
    return None


def _matches(fact, pattern) -> bool:
    kind, predicate = pattern
    return fact.kind == kind and predicate(fact)


def preconditions_for_mentions(model: GeometryModel | None, text: str, mentioned, accepted: dict | None = None) -> list[MathCheck]:
    """Açıklamada adı geçen teorem, *kabul edilmiş* olgularda önkoşulu bulunmadan kullanılmış mı?"""
    checks = []
    if model is None:
        usable = set()
    else:
        usable = {item.kind for item in model.facts if accepted is None or item.id in accepted}
    requirements = {"pythagorean": {"right_angle"}, "similarity": {"similar"}, "isosceles": {"equal_segments"},
                    "tangent_radius": {"tangent"}, "midpoint": {"midpoint"}, "congruence": {"congruent"}}
    for theorem in mentioned:
        needed = requirements.get(theorem.id)
        if needed is None:
            continue
        if not needed & usable:
            checks.append(MathCheck(id=f"mention_{theorem.id}", area="geometry", status="failed",
                                    reason="theorem_preconditions_unmet",
                                    detail=f"{theorem.name_tr} kullanılmış; önkoşul ({', '.join(sorted(needed))}) kabul "
                                           "edilmiş bir olgu olarak yok."))
    return checks
