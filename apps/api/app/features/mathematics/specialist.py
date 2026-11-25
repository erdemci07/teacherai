"""Matematik uzmanlığı raporu (TA-008 §4, §24). MathAI doğrulamasından sonra *aynı yalıtılmış işçide* çalışır.

Ek sağlayıcı çağrısı, ek alt süreç veya Firestore okuması yoktur. Her analiz kendi hata sınırı içindedir;
desteklenmeyen veya zamanı aşan analiz ``unsupported`` olur ve asla başarı sayılmaz. Rapor mevcut doğrulama
durumunu yalnız *zayıflatabilir* (``verified`` → ``partially_verified``); hiçbir zaman güçlendirmez.
"""

from __future__ import annotations

from time import perf_counter

import sympy as sp

from ..curriculum import topics
from ..education.base import Subject
from ..education.mathematics import MathCheck, MathematicsReport
from ..integrity import expression as tree
from . import alternatives, expr, functions, geometry, guidance, sets, theorems, transforms, trig, word_problems

TIME_BUDGET_SECONDS = 2.5
CONTRADICTION_AREAS = {"solution_set", "inequality"}
FAILURE_TYPES = (expr.ExprError, NotImplementedError, TypeError, ValueError, AttributeError, RecursionError,
                 ZeroDivisionError, sp.SympifyError, sp.PolynomialError)


def _given(analysis) -> list[tuple[str, str]]:
    """(tür, kaynak): "equation" | "inequality" | "function". Sınıflandırma AST'den yapılır."""
    integrity = getattr(analysis, "integrity", None)
    if integrity is None and hasattr(analysis, "mathematical_expressions"):
        # Eski kayıt: bütünlük raporu yoksa MathAI ile aynı biçimde (legacy) hesaplanır.
        from ..integrity.engine import EvaluationState, evaluate

        integrity = evaluate(analysis, EvaluationState(revision=getattr(analysis, "revision", 1), origin="legacy"))
    out = []
    for item in integrity.expressions if integrity is not None else []:
        if item.status != "parsed" or item.role != "given":
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


def _single_variable(latex: str) -> str | None:
    result = tree.parse(latex)
    if not result.parsed:
        return None
    names = tree.symbols(result.tree)
    return next(iter(names)) if len(names) == 1 else None


def _claimed(plan, variable: str):
    """Son cevaptaki ``x = a`` (veya ``x \\in \\{...\\}``) değerleri; ayrıştırılamazsa None."""
    values = set()
    for item in plan.content.final_answer_expressions:
        try:
            ops, sides = expr.relation(item.latex)
        except expr.ExprError:
            continue
        if ops == ("=",) and sides[0] == expr.symbol(variable) and not sides[1].free_symbols:
            values.add(sp.nsimplify(sides[1]))
    return sp.FiniteSet(*values) if values else None


def analyze(plan, verification=None, deadline: float | None = None) -> MathematicsReport:
    started = perf_counter()
    deadline = deadline or started + TIME_BUDGET_SECONDS
    analysis = plan.source_analysis
    checks: list[MathCheck] = []
    notes: list[str] = []
    mapping = topics.map_question(analysis, Subject.MATHEMATICS)
    features, domain_notes = guidance.analyze_sources(analysis)
    report = {"topics": list(mapping.keys)[:4],
              "topic_evidence": "structural" if mapping.status == "structural" else "lexical" if mapping.keys else "none"}

    def guarded(name, fn):
        if perf_counter() > deadline:
            checks.append(MathCheck(id=f"{name}_skipped", area="target", status="unsupported", reason="time_budget"))
            return None
        try:
            return fn()
        except FAILURE_TYPES as exc:
            checks.append(MathCheck(id=f"{name}_error", area="target", status="unsupported", reason="analysis_unsupported",
                                    detail=type(exc).__name__))
            return None

    sources = _given(analysis)
    equation = next((src for kind, src in sources if kind == "equation" and _single_variable(src)), None)
    inequality = next((src for kind, src in sources if kind == "inequality" and _single_variable(src)), None)
    target_kind = verification.target.target.kind if verification is not None and verification.target else None
    if equation and "trigonometry" in features:
        def periodic():
            variable = _single_variable(equation)
            result, kind = trig.general_solution(equation, variable)
            checks.append(MathCheck(id="trig_solutions", area="trigonometry",
                                    status="partially_checked" if kind == "periodic" else "unsupported",
                                    reason="periodic_solutions" if kind == "periodic" else "trig_unsupported",
                                    statement=equation[:400],
                                    detail="Periyodik çözümler vardır; aralık verilmeden sonlu hedef belirlenmez."))
        guarded("trig", periodic)
    elif equation:
        variable = _single_variable(equation)

        def solve():
            solved = sets.solve_equation(equation, variable)
            report["solution_set"] = solved.view
            report["domain_exclusions"] = solved.view.exclusions
            if solved.status != "exact":
                checks.append(MathCheck(id="solution_set", area="solution_set", status="unsupported",
                                        reason=f"solution_{solved.status}", statement=equation[:400]))
                return
            checks.append(MathCheck(id="solution_set", area="solution_set", status="passed", reason="solution_set_exact",
                                    statement=equation[:400], detail=f"{solved.view.kind}: {', '.join(solved.view.elements)}"[:400]))
            claimed = _claimed(plan, variable)
            if claimed is not None and (target_kind in {None, "variable_value", "solution_set"}):
                same = sets.same_set(claimed, solved.value)
                if same is True:
                    status, reason = "passed", "claimed_set_complete"
                elif same is False and sets.same_set(sp.Intersection(claimed, solved.value), claimed) is True:
                    status, reason = "failed", "missing_solutions"
                elif same is False:
                    status, reason = "failed", "extraneous_or_wrong_claim"
                else:
                    status, reason = "unsupported", "claim_undecidable"
                checks.append(MathCheck(id="claimed_solution_set", area="solution_set", status=status, reason=reason))
            if "quadratic" in features:
                report["alternatives"] = alternatives.quadratic(equation, variable)
        guarded("equation", solve)

        def steps():
            previous = equation
            for step in plan.content.steps:
                for index, item in enumerate(step.expressions):
                    if item.type not in {"equation"} or _single_variable(item.latex) != variable:
                        continue
                    verdict = transforms.compare(previous, item.latex, equation, variable)
                    status = {"equivalent": "passed", "gains": "partially_checked", "loses": "failed",
                              "changed": "failed"}.get(verdict.relation, "unsupported")
                    checks.append(MathCheck(id=f"{step.id}_{index}_equivalence", area="transformation", status=status,
                                            reason=verdict.hazard or f"step_{verdict.relation}", statement=item.latex[:400],
                                            detail=verdict.detail))
                    if status in {"passed", "partially_checked"}:
                        previous = item.latex
        guarded("steps", steps)
    if inequality:
        variable = _single_variable(inequality)

        def inequality_set():
            solved = sets.solve_inequality(inequality, variable)
            report["solution_set"] = solved.view
            report["domain_exclusions"] = solved.view.exclusions
            checks.append(MathCheck(id="inequality_set", area="inequality",
                                    status="passed" if solved.status == "exact" else "unsupported",
                                    reason="inequality_set_exact" if solved.status == "exact" else f"solution_{solved.status}",
                                    statement=inequality[:400]))
            for item in plan.content.final_answer_expressions:
                try:
                    claim = sets.solve_inequality(item.latex, variable)
                except FAILURE_TYPES:
                    continue
                same = sets.same_set(claim.value, solved.value)
                checks.append(MathCheck(id="claimed_inequality_set", area="inequality",
                                        status="passed" if same else "failed" if same is False else "unsupported",
                                        reason="claimed_interval_matches" if same else "claimed_interval_differs"
                                        if same is False else "claim_undecidable", statement=item.latex[:400]))
                break
        guarded("inequality", inequality_set)
    function_source = next((src for kind, src in sources if kind == "function"), None)
    if function_source:
        def graph():
            rhs = function_source.split("=", 1)[1]
            facts = functions.analyze(rhs)
            report["graph_segments"] = facts.segments
            if facts.discontinuities:
                checks.append(MathCheck(id="graph_discontinuities", area="graph", status="passed",
                                        reason="undefined_points_split", scope="exact",
                                        detail="Grafik tanımsız noktalarda bölündü: " + ", ".join(map(str, facts.discontinuities))))
        guarded("function", graph)
    model = getattr(plan.content, "mathematical_model", None)
    if model is not None:
        report["model_kind"] = model.kind
        if model.word_problem is not None:
            result = guarded("word_problem", lambda: word_problems.analyze(model.word_problem, analysis.question_text))
            if result is not None:
                checks.extend(result.checks)
                report["model_status"] = "rejected" if any(c.status == "failed" for c in result.checks) else "accepted"
        if model.geometry is not None:
            result = guarded("geometry", lambda: geometry.analyze(model.geometry))
            if result is not None:
                checks.extend(result.checks)
                report["model_status"] = "rejected" if result.determinacy in {"inconsistent", "underdetermined"} else "accepted"
                if model.geometry.schematic:
                    notes.append("Şekil ölçekli değildir; görünen orantılar veri sayılmadı.")
    text = " ".join(f"{s.title} {s.explanation}" for s in plan.content.steps)
    mentioned = theorems.mentioned(text)
    if mentioned:
        checks.extend(geometry.preconditions_for_mentions(model.geometry if model is not None else None, text, mentioned))
    if domain_notes:
        notes.extend(domain_notes)
    report["checks"] = checks[:64]
    report["notes_tr"] = notes[:8]
    passed = [c for c in checks if c.status == "passed" and c.area in {"solution_set", "inequality", "geometry", "word_problem"}]
    failed = [c for c in checks if c.status == "failed"]
    report["capability"] = ("independently_verifiable" if passed and not failed else
                            "partially_verifiable" if passed or any(c.status == "partially_checked" for c in checks) else
                            "ai_assisted_only" if model is not None else "unsupported")
    return MathematicsReport(**report)


def contradiction(report: MathematicsReport | None) -> bool:
    return report is not None and any(c.status == "failed" and c.area in CONTRADICTION_AREAS for c in report.checks)
