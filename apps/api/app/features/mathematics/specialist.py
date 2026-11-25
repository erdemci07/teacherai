"""Matematik uzmanlığı raporu (TA-008, TA-008B). MathAI doğrulamasından sonra *aynı yalıtılmış işçide* çalışır.

Ek sağlayıcı çağrısı, ek alt süreç veya Firestore okuması yoktur. Her analiz kendi hata sınırı içindedir;
desteklenmeyen analiz ``unsupported`` olur ve asla başarı sayılmaz.

TA-008B ayrımları:

- **Maddi çelişki** (``material``): doğrulanmış bir küme/hedef/modele karşı kesin çelişki — yanlış istenen cevap, eksik
  veya fazla çözüm, yanlış aralık, geçersiz kabul edilmiş dönüşüm, eksik durum dalı, kaynak olgularının kendi
  aralarında çelişmesi. ``MathAIService`` bu durumda sonucu ``failed`` yapar ve düzeltme akışı çalışır.
- **Eksik doğrulama**: desteklenmeyen hesap, ayrışmayan ifade, model sadakatinin eksikliği, belirsiz hedef. Maddi değildir.
- Zaman bütçesi *işlemler arasında* denetlenir; tek bir SymPy çağrısını kesmez. Kesin koruma dış işçi zaman aşımıdır.
"""

from __future__ import annotations

import re
from time import perf_counter

import sympy as sp

from ..curriculum import topics
from ..education.base import Subject
from ..education.mathematics import GeometryFactStatus, MathCheck, MathematicsReport
from ..integrity import expression as tree
from . import alternatives, expr, functions, geometry, guidance, sets, theorems, transforms, trig, word_problems

TIME_BUDGET_SECONDS = 2.5
MAX_CHECKS = 64
GRAPH_SAMPLES_PER_SEGMENT = 12
FAILURE_TYPES = (expr.ExprError, NotImplementedError, TypeError, ValueError, AttributeError, RecursionError,
                 ZeroDivisionError, sp.SympifyError, sp.PolynomialError)
MATERIAL_REASONS = {"missing_solutions", "extraneous_or_wrong_claim", "claimed_interval_differs", "step_loses",
                    "step_changed", "division_by_expression_with_zero", "inequality_not_reversed", "solution_lost",
                    "case_branch_invalid", "geometry_answer_mismatch", "word_answer_mismatch", "function_value_mismatch",
                    "extremum_mismatch", "constant_value_mismatch", "source_constraints_contradictory",
                    "no_extremum_of_requested_kind"}
FUNCTION_DEFINITION = re.compile(r"^\s*([a-z])\s*\(\s*x\s*\)\s*=\s*(.+)$")


def _integrity(analysis):
    integrity = getattr(analysis, "integrity", None)
    if integrity is None and hasattr(analysis, "mathematical_expressions"):
        from ..integrity.engine import EvaluationState, evaluate

        integrity = evaluate(analysis, EvaluationState(revision=getattr(analysis, "revision", 1), origin="legacy"))
    return integrity


def _given(integrity) -> list[tuple[str, str]]:
    """(tür, kaynak): "equation" | "inequality" | "function" | "definition". Sınıflandırma AST'den."""
    out = []
    for item in integrity.expressions if integrity is not None else []:
        if item.status != "parsed" or item.role != "given":
            continue
        if FUNCTION_DEFINITION.match(item.source):
            out.append(("definition", item.source))
            continue
        result = tree.parse(item.source)
        if not result.parsed or not isinstance(result.tree, tree.Rel):
            continue
        node = result.tree
        if node.ops == ("=",) and isinstance(node.operands[0], tree.Sym) and node.operands[0].name == "y":
            out.append(("function", item.source))
        elif node.ops == ("=",):
            out.append(("equation", item.source))
        elif all(op in {"<", ">", "<=", ">="} for op in node.ops):
            out.append(("inequality", item.source))
    return out


def _requested(integrity) -> list[str]:
    return [item.source for item in (integrity.expressions if integrity is not None else [])
            if item.status == "parsed" and item.role == "requested"]


def _single_variable(latex: str) -> str | None:
    result = tree.parse(latex)
    if not result.parsed:
        return None
    names = tree.symbols(result.tree)
    return next(iter(names)) if len(names) == 1 else None


def _claimed(plan, variable: str):
    """Son cevaptaki ``x = a`` değerleri; ayrıştırılamazsa None."""
    values = set()
    for item in plan.content.final_answer_expressions:
        try:
            ops, sides = expr.relation(item.latex)
        except expr.ExprError:
            continue
        if ops == ("=",) and sides[0] == expr.symbol(variable) and not sides[1].free_symbols:
            values.add(sp.nsimplify(sides[1]))
    return sp.FiniteSet(*values) if values else None


NUMBER = re.compile(r"-?\d+(?:[.,]\d+)?(?:/\d+)?")


def claimed_value(plan):
    """Son cevabın tek sayısal değeri (``BC = 12``, ``12 cm``, ``\\frac{3}{2}``); belirsizse None."""
    candidates = []
    for item in plan.content.final_answer_expressions:
        latex = item.latex.split("=")[-1].strip()
        latex = re.sub(r"\\(?:text|mathrm)\{[^}]*\}", "", latex).strip()
        latex = re.sub(r"\s*(cm|mm|m|km|derece|°|\^\\circ)\s*$", "", latex).strip()
        try:
            value = expr.expression(latex)
            if not value.free_symbols and expr.finite(value):
                candidates.append(sp.nsimplify(value))
                continue
        except expr.ExprError:
            pass
        numbers = NUMBER.findall(latex)
        if len(numbers) == 1:
            candidates.append(sp.nsimplify(numbers[0].replace(",", ".")))
    distinct = {sp.nsimplify(c) for c in candidates}
    return distinct.pop() if len(distinct) == 1 else None


def _compare(claim, value) -> bool | None:
    if claim is None:
        return None
    try:
        return bool(sp.simplify(claim - value) == 0)
    except (TypeError, ValueError):
        return None


def analyze(plan, verification=None, deadline: float | None = None) -> MathematicsReport:
    started = perf_counter()
    deadline = deadline or started + TIME_BUDGET_SECONDS
    analysis = plan.source_analysis
    integrity = _integrity(analysis)
    checks: list[MathCheck] = []
    notes: list[str] = []
    partial = False
    mapping = topics.map_question(analysis, Subject.MATHEMATICS)
    features, domain_notes = guidance.analyze_sources(analysis)
    report: dict = {"topics": list(mapping.keys)[:4],
                    "topic_evidence": "structural" if mapping.status == "structural" else "lexical" if mapping.keys else "none"}

    def add(check: MathCheck):
        if check.status == "failed" and check.reason in MATERIAL_REASONS:
            check = check.model_copy(update={"material": True})
        checks.append(check)

    def guarded(name, fn):
        nonlocal partial
        if perf_counter() > deadline:
            partial = True
            add(MathCheck(id=f"{name}_skipped", area="target", status="unsupported", reason="time_budget"))
            return None
        try:
            return fn()
        except FAILURE_TYPES as exc:
            partial = True
            add(MathCheck(id=f"{name}_error", area="target", status="unsupported", reason="analysis_unsupported",
                          detail=type(exc).__name__))
            return None

    sources = _given(integrity)
    target = verification.target.target if verification is not None and verification.target else None
    target_kind = target.kind if target is not None else None
    equation = next((src for kind, src in sources if kind == "equation" and _single_variable(src)), None)
    inequality = next((src for kind, src in sources if kind == "inequality" and _single_variable(src)), None)
    if equation and "trigonometry" in features:
        def periodic():
            variable = _single_variable(equation)
            _, kind = trig.general_solution(equation, variable)
            add(MathCheck(id="trig_solutions", area="trigonometry",
                          status="partially_checked" if kind == "periodic" else "unsupported",
                          reason="periodic_solutions" if kind == "periodic" else "trig_unsupported", statement=equation[:400],
                          detail="Periyodik çözümler vardır; aralık verilmeden sonlu hedef belirlenmez."))
        guarded("trig", periodic)
    elif equation:
        variable = _single_variable(equation)

        def solve():
            solved = sets.solve_equation(equation, variable)
            report["solution_set"] = solved.view
            report["domain_exclusions"] = solved.view.exclusions
            if solved.status != "exact":
                add(MathCheck(id="solution_set", area="solution_set", status="unsupported", reason=f"solution_{solved.status}",
                              statement=equation[:400]))
                return
            add(MathCheck(id="solution_set", area="solution_set", status="passed" if not solved.view.truncated else
                          "partially_checked", reason="solution_set_exact" if not solved.view.truncated else "display_truncated",
                          statement=equation[:400], detail=f"{solved.view.kind}: {', '.join(solved.view.elements)}"[:400]))
            claimed = _claimed(plan, variable)
            if claimed is not None and target_kind in {None, "variable_value", "solution_set"}:
                same = sets.same_set(claimed, solved.value)
                if same is True:
                    status, reason = "passed", "claimed_set_complete"
                elif same is False and sets.same_set(sp.Intersection(claimed, solved.value), claimed) is True:
                    status, reason = "failed", "missing_solutions"
                elif same is False:
                    status, reason = "failed", "extraneous_or_wrong_claim"
                else:
                    status, reason = "unsupported", "claim_undecidable"
                add(MathCheck(id="claimed_solution_set", area="solution_set", status=status, reason=reason))
            if "quadratic" in features:
                report["alternatives"] = [path for path in alternatives.quadratic(equation, variable) if path.verified]
        guarded("equation", solve)
        guarded("steps", lambda: _steps(plan, equation, variable, add))
    if inequality:
        variable = _single_variable(inequality)

        def inequality_set():
            solved = sets.solve_inequality(inequality, variable)
            report["solution_set"] = solved.view
            report["domain_exclusions"] = solved.view.exclusions
            add(MathCheck(id="inequality_set", area="inequality", status="passed" if solved.status == "exact" else "unsupported",
                          reason="inequality_set_exact" if solved.status == "exact" else f"solution_{solved.status}",
                          statement=inequality[:400]))
            if solved.status != "exact":
                return
            for item in plan.content.final_answer_expressions:
                try:
                    claim = sets.solve_inequality(item.latex, variable)
                except FAILURE_TYPES:
                    continue
                same = sets.same_set(claim.value, solved.value)
                add(MathCheck(id="claimed_inequality_set", area="inequality",
                              status="passed" if same else "failed" if same is False else "unsupported",
                              reason="claimed_interval_matches" if same else "claimed_interval_differs"
                              if same is False else "claim_undecidable", statement=item.latex[:400]))
                break
        guarded("inequality", inequality_set)
    function_source = next((src for kind, src in sources if kind == "function"), None)
    if function_source:
        guarded("function", lambda: _function(plan, function_source, target_kind, report, add))
    definition = next((src for kind, src in sources if kind == "definition"), None)
    if definition:
        guarded("evaluation", lambda: _evaluation(plan, definition, _requested(integrity), add))
    if target is not None and target_kind in {"expression_value", "sum", "difference", "product", "ratio"} \
            and target.expression and "trigonometry" in features and not equation:
        guarded("constant", lambda: _constant(plan, _requested(integrity), add))
    model = getattr(plan.content, "mathematical_model", None)
    accepted = None
    if model is not None:
        report["model_kind"] = model.kind
        if model.word_problem is not None:
            result = guarded("word_problem", lambda: word_problems.analyze(model.word_problem, analysis.question_text))
            if result is not None:
                for check in result.checks:
                    add(check)
                usable = result.status == "determined" and not any(
                    c.status == "failed" and c.area == "model_fidelity" for c in result.checks)
                report["model_status"] = "accepted" if usable else "rejected"
                if usable and len(result.objective_values) == 1:
                    _answer_check(plan, result.objective_values[0], "word", "word_answer_mismatch",
                                  bound=_objective_bound(model.word_problem, target), add=add)
        if model.geometry is not None:
            source = geometry.Source(_source_text(analysis), _has_figure(analysis))
            result = guarded("geometry", lambda: geometry.analyze(model.geometry, source))
            if result is not None:
                accepted = result.accepted
                report["geometry_facts"] = [
                    GeometryFactStatus(id=f.id, status="accepted", basis=result.accepted[f.id]) if f.id in result.accepted
                    else GeometryFactStatus(id=f.id, status="rejected", basis=result.rejected.get(f.id, "not_validated"))
                    for f in model.geometry.facts][:32]
                for check in result.checks:
                    add(check)
                if result.source_contradiction:
                    add(MathCheck(id="geometry_source", area="geometry", status="failed",
                                  reason="source_constraints_contradictory",
                                  detail="Soru metninden alınan olgular kendi aralarında çelişiyor; çözüm doğrulanamaz."))
                report["model_status"] = "accepted" if result.determinacy in {"determined", "consistent"} else "rejected"
                if result.determinacy == "determined" and len(result.target_values) == 1:
                    _answer_check(plan, result.target_values[0], "geometry", "geometry_answer_mismatch",
                                  bound=_geometry_target_bound(model.geometry, analysis), add=add)
                notes.append("Kaynak olguları soru metninden doğrulandı; metnin kendisi görselden AI ile okunmuş olabilir.")
                if model.geometry.schematic:
                    notes.append("Şekil ölçekli değildir; görünen orantılar veri sayılmadı.")
    text = " ".join(f"{s.title} {s.explanation}" for s in plan.content.steps)
    mentioned = theorems.mentioned(text)
    if mentioned:
        for check in geometry.preconditions_for_mentions(model.geometry if model is not None else None, text, mentioned,
                                                         accepted):
            add(check)
    notes.extend(domain_notes)
    material = [c for c in checks if c.material]
    ordered = sorted(checks, key=lambda c: (not c.material, c.status != "failed"))
    report["checks"] = ordered[:MAX_CHECKS]
    report["material_failures"] = material[:16]
    report["material_count"] = len(material)
    report["notes_tr"] = notes[:8]
    report["specialist_status"] = "partial" if partial else "completed"
    passed = [c for c in checks if c.status == "passed" and c.area in {"solution_set", "inequality", "geometry",
                                                                         "word_problem", "function", "target"}]
    failed = [c for c in checks if c.status == "failed"]
    report["capability"] = ("independently_verifiable" if passed and not failed else
                            "partially_verifiable" if passed or any(c.status == "partially_checked" for c in checks) else
                            "ai_assisted_only" if model is not None else "unsupported")
    return MathematicsReport(**report)


def _steps(plan, equation, variable, add):
    """Ardışık adımların denkliği (TA-008B §6).

    - Bir adımdaki ardışık denklemler tek tek önceki denkleme karşı denetlenir.
    - Durum ayrımı (``case`` adımları veya aynı adımda dallara ayrılan birden çok denklem): tek bir dalın daha az
      çözümü olması meşrudur; dalların (özgün tanım kümesindeki) birleşimi önceki denklemin kümesine eşit olmalıdır.
      Ayrımdan sonraki adımlar dal içidir ve bu sürümde ardışık denetlenmez.
    - Kare alma gibi genişleten adımdan sonra yabancı adayın elenmesi kayıp değildir (``eliminates``).
    """
    previous = equation
    steps = list(plan.content.steps)
    for position, step in enumerate(steps):
        equations = _step_equations(step, variable)
        if step.type == "case":
            branches = list(equations)
            for later in steps[position + 1:]:
                if later.type != "case":
                    break
                branches.extend(_step_equations(later, variable))
            if branches:
                _split_check(step.id, previous, branches, equation, variable, add)
            return
        for index, item in enumerate(equations):
            verdict = transforms.compare(previous, item.latex, equation, variable)
            rest = equations[index:]
            if verdict.relation in {"loses", "changed"} and len(rest) > 1:
                _split_check(step.id, previous, rest, equation, variable, add)
                return
            status = {"equivalent": "passed", "eliminates": "passed", "gains": "partially_checked", "loses": "failed",
                      "changed": "failed"}.get(verdict.relation, "unsupported")
            reason = verdict.hazard or ("extraneous_eliminated" if verdict.relation == "eliminates" else f"step_{verdict.relation}")
            add(MathCheck(id=f"{step.id}_{index}_equivalence", area="transformation", status=status, reason=reason,
                          statement=item.latex[:400], detail=verdict.detail))
            if status in {"passed", "partially_checked"}:
                previous = item.latex


def _step_equations(step, variable):
    return [item for item in step.expressions if item.type == "equation" and _single_variable(item.latex) == variable]


def _split_check(step_id, previous, branches, original, variable, add):
    domain = _domain(original, variable)
    try:
        before = sp.Intersection(sets.solve_equation(previous, variable).value, domain)
        union = sp.S.EmptySet
        for item in branches:
            union = sp.Union(union, sets.solve_equation(item.latex, variable).value)
        same = sets.same_set(sp.Intersection(union, domain), before)
    except FAILURE_TYPES:
        same = None
    add(MathCheck(id=f"{step_id}_cases", area="transformation",
                  status="passed" if same else "failed" if same is False else "unsupported",
                  reason="case_split_complete" if same else "case_branch_invalid" if same is False else "case_split_unchecked",
                  detail="Dalların (özgün tanım kümesindeki) birleşimi önceki denklemin çözüm kümesine eşit." if same else
                  "Dalların birleşimi önceki denklemin çözüm kümesini vermiyor (eksik dal veya yanlış eleme)." if same is False
                  else "Dallar kesin karşılaştırılamadı."))


def _domain(latex, variable):
    from . import domain as domains

    return domains.domain_set(domains.conditions_of(latex), expr.symbol(variable))


def _function(plan, source, target_kind, report, add):
    rhs = source.split("=", 1)[1]
    facts = functions.analyze(rhs)
    report["graph_segments"] = facts.segments
    report["graph_holes"] = list(facts.holes)[:16]
    report["graph_asymptotes"] = list(facts.asymptotes)[:16]
    report["graph_points"] = _samples(rhs, facts)
    report["graph_expression"] = rhs.strip()[:200]
    if facts.discontinuities:
        add(MathCheck(id="graph_discontinuities", area="graph", status="passed", reason="undefined_points_split", scope="exact",
                      detail="Grafik tanımsız noktalarda bölündü: " + ", ".join(map(str, facts.discontinuities))))
    if target_kind in {"minimum", "maximum"}:
        try:
            h, value, kind = functions.vertex(rhs)
        except expr.ExprError:
            add(MathCheck(id="function_extremum", area="function", status="unsupported", reason="extremum_not_quadratic"))
            return
        if kind != target_kind:
            claim = claimed_value(plan)
            add(MathCheck(id="function_extremum", area="function", status="failed" if claim is not None else "partially_checked",
                          reason="no_extremum_of_requested_kind",
                          detail=f"Parabolün yalnız {'en küçük' if kind == 'minimum' else 'en büyük'} değeri vardır."))
            return
        _answer_check(plan, value, "function_extremum", "extremum_mismatch", bound=True, add=add, area="function")


def _samples(rhs, facts) -> list[tuple[float, float]]:
    f = expr.expression(rhs)
    x = expr.symbol("x")
    points = []
    per = max(GRAPH_SAMPLES_PER_SEGMENT, 90 // max(len(facts.segments), 1) - 1)
    for segment in facts.segments:
        a, b = segment.start, segment.end
        for i in range(per + 1):
            t = a + (b - a) * i / per
            if (i == 0 and not segment.start_closed) or (i == per and not segment.end_closed):
                continue
            if any(abs(t - float(h)) < 1e-9 for h in facts.discontinuities):
                continue
            value = complex(sp.N(f.subs(x, sp.nsimplify(t))))
            if abs(value.imag) < 1e-12 and abs(value.real) < 1e6:
                points.append((round(t, 6), round(value.real, 6)))
    return points[:96]


def _evaluation(plan, definition, requested, add):
    """f(x) = … verilip f(a) istenmişse: f(a) bağımsız hesaplanır (TA-008B: hedef çarpım "f·a" sanılmaz)."""
    match = FUNCTION_DEFINITION.match(definition)
    name, rhs = match.group(1), match.group(2)
    call = re.compile(rf"^\s*{name}\s*\((.+)\)\s*$")
    asked = next((call.match(item) for item in requested if call.match(item)), None)
    if asked is None:
        add(MathCheck(id="function_value", area="function", status="not_checked", reason="evaluation_target_unclear"))
        return
    point = expr.expression(asked.group(1))
    value = functions.evaluate(rhs, point)
    _answer_check(plan, value, "function_value", "function_value_mismatch", bound=True, add=add, area="function")


def _constant(plan, requested, add):
    """Değişkensiz trigonometrik ifade (radyan cinsinden yazılmış): kesin değer. Derece işareti ayrıştırılmaz."""
    for item in requested:
        try:
            value = expr.expression(item)
        except expr.ExprError:
            continue
        if value.free_symbols or not expr.finite(value):
            continue
        _answer_check(plan, sp.simplify(value), "constant_value", "constant_value_mismatch", bound=True, add=add, area="target")
        return


def _answer_check(plan, value, name, mismatch_reason, *, bound: bool, add, area: str | None = None):
    """Bağımsız hesaplanan hedef ↔ öğrenciye gösterilen son cevap. Hedef kimliği bağımsız kurulamadıysa eşleşme
    yalnız kısmi doğrulamadır; *uyuşmazlık* ise modelin kendisiyle çelişen cevap olduğu için maddi çelişkidir."""
    claim = claimed_value(plan)
    same = _compare(claim, value)
    area = area or ("geometry" if name == "geometry" else "word_problem")
    if same is None:
        add(MathCheck(id=f"{name}_answer", area=area, status="not_checked", reason="claim_unparsed",
                      detail=f"Bağımsız değer: {expr.text(value)}; son cevap sayısal olarak okunamadı."))
    elif same:
        add(MathCheck(id=f"{name}_answer", area=area, status="passed" if bound else "partially_checked",
                      reason="answer_matches_target" if bound else "answer_matches_model_target_identity_unverified",
                      detail=f"Bağımsız değer: {expr.text(value)}"))
    elif bound:
        add(MathCheck(id=f"{name}_answer", area=area, status="failed", reason=mismatch_reason,
                      detail=f"Bağımsız değer {expr.text(value)}; son cevap {expr.text(claim)}."))
    else:
        # Hedef kimliği kaynağa bağlanamadı: model ile cevap çelişiyor ama hangisinin yanlış olduğu (model sadakati mi,
        # cevap mı) belirlenemez. Doğrulanmış sayılmaz; maddi çelişki olarak düzeltme akışını tetiklemez.
        add(MathCheck(id=f"{name}_answer", area=area, status="failed", reason="model_answer_disagreement",
                      detail=f"Modelin hedef değeri {expr.text(value)}; son cevap {expr.text(claim)}. Hedef kimliği "
                             "soru metnine bağlanamadığından hangisinin yanlış olduğu belirlenmedi."))


def _source_text(analysis) -> str:
    statements = list(getattr(getattr(analysis, "source", None), "statements", []) or [])
    return " ".join([analysis.question_text or "", *statements, *list(analysis.mathematical_expressions or [])])


def _has_figure(analysis) -> bool:
    visual = getattr(analysis, "visual_elements", None)
    return bool(visual and (visual.has_geometry_figure or visual.has_diagram))


def _geometry_target_bound(model, analysis) -> bool:
    """Hedef nesnenin adı (ör. "BC", "ABC açısı") soru metninde geçiyorsa hedef kimliği kaynağa bağlıdır."""
    if model.target is None:
        return False
    label = "".join(model.target.points)
    text = analysis.question_text or ""
    return label in text or label[::-1] in text


def _objective_bound(model, target) -> bool:
    """Sözel problemde hedefin anlamı sözcüklerden bağımsız kurulamaz; yalnız istenen ifade AnswerTarget ile aynıysa."""
    return target is not None and target.expression is not None and target.expression.replace(" ", "") == model.objective.replace(" ", "")


def contradiction(report: MathematicsReport | None) -> bool:
    return report is not None and report.material_count > 0
