import re
from time import perf_counter

import sympy
from sympy import Symbol, simplify, solve

from ..education.reasoning import EXPRESSION_TARGETS, AnswerTarget, TargetResolution
from ..education.science import Premise
from ..integrity import expression as expression_tree
from ..integrity.engine import EvaluationState, evaluate
from ..integrity.expression import parse as parse_tree
from ..integrity.language import parse_choices
from ..lessons.schemas import LessonPlan
from ..reasoning.evidence import match_combination, premise_polarity, select_premises
from ..reasoning.target import target_for
from . import targets
from .parser import (
    MathParseError,
    branches,
    equation,
    expression,
    is_inequality,
    relation_set,
    solutions,
    to_sympy,
)
from .schemas import ChoiceMatch, GraphData, VerificationCheck, VerificationResult

VARIABLE_TARGETS = {"variable_value", "solution_set"}
_TARGET_DETAIL = {
    "variable_value": "değişkenin değeri", "expression_value": "istenen ifadenin değeri", "sum": "istenen toplam",
    "difference": "istenen fark", "product": "istenen çarpım", "ratio": "istenen oran",
    "solution_count": "çözüm sayısı", "root_sum": "kökler toplamı", "root_product": "kökler çarpımı",
    "solution_set": "çözüm kümesi", "minimum": "en küçük değer", "maximum": "en büyük değer",
}


class MathAIService:
    """Sınırlı SymPy doğrulaması. TA-004: son cevap *istenen hedefe* göre denetlenir."""

    def verify(self, plan: LessonPlan) -> VerificationResult:
        started = perf_counter()
        checks: list[VerificationCheck] = []
        warnings: list[str] = []
        graph = None
        target = self.target(plan)
        originals = self._source_equations(plan)
        if not originals:
            inequality = self._source_inequality(plan)
            if inequality is not None and target.computable:
                return self._verify_target_only(plan, target, None, inequality, started)
            return self._unsupported(plan, target, checks, "Bu soru türü henüz deterministik olarak doğrulanamıyor.", started)
        if len(originals) > 1 and target.kind in EXPRESSION_TARGETS:
            computed = targets.from_definitions(target, originals)
            if computed.values is not None:
                return self._verify_target_only(plan, target, None, None, started, [], computed=computed, sources=originals)
        try:
            if len(originals) != 1:
                raise MathParseError("multiple source equations")
            original = equation(branches(originals[0])[0])
            variables = sorted(original.free_symbols, key=str)
            if str(original.lhs) == "y" and Symbol("x", real=True) in original.rhs.free_symbols:
                graph = self.analyze_function(originals[0])
                checks.append(VerificationCheck(id="function_analysis", kind="function", status="passed", statement=originals[0],
                                                detail="Kökler, eksen kesişimi ve örnek noktalar deterministik hesaplandı."))
                _, choice_match = self._answer_choice_check(plan, None)
                result = self._result("partially_verified", checks, False, False,
                                      ["Grafik özellikleri kontrol edildi; tüm sözel iddialar doğrulanmadı."], started, 0.7, graph)
                resolution = self._resolution(target, originals, targets.Computed(None, "target_not_computable", [], []),
                                              None, "none", "not_checked")
                return result.model_copy(update={"choice_match": choice_match, "target": resolution})
            if len(variables) != 1:
                if len(variables) == 2 and target.computable:
                    return self._verify_target_only(plan, target, originals[0], None, started, variables)
                return self._unsupported(plan, target, checks, "Birden fazla değişkenli doğrulama henüz desteklenmiyor.", started, originals)
            variable = variables[0]
            raw = solutions(originals[0], variable)
            expected, excluded = targets.valid_roots(originals[0], variable, raw)
            checks.append(VerificationCheck(id="original_equation", kind="equation", status="passed", statement=originals[0],
                                            detail="Denklem güvenli ayrıştırıldı."))
            if excluded:
                checks.append(VerificationCheck(
                    id="domain_restrictions", kind="domain", status="passed", statement=originals[0], reason="domain_excluded",
                    detail="Tanım kümesi dışında kalan aday değerler atıldı: " + ", ".join(map(str, excluded))[:200]))
        except (MathParseError, NotImplementedError, TypeError):
            return self._unsupported(plan, target, checks, "Matematiksel ifade güvenli biçimde ayrıştırılamadı.", started)

        transformed = self._step_checks(plan, checks, variable, set(expected), originals[0]) | set(raw)
        computed = targets.compute(target, originals[0], None, [variable])
        claimed_target, role = targets.claim(target, [item.latex for item in plan.content.final_answer_expressions], [variable])
        premises = self._premise_choice(plan, target, variable, expected, originals) if target.kind == "statement_combination" else None
        if premises is not None:
            final_verified, contradiction, resolution, option_check, choice_match = premises
            checks.append(option_check)
            failed = any(x.status == "failed" for x in checks)
            status = "failed" if failed else "verified" if final_verified and all(x.status == "passed" for x in checks) else "partially_verified"
            if contradiction:
                warnings.append("Seçilen öncül birleşimi öncüllerin değerlendirmesiyle çelişiyor.")
            result = self._result(status, checks, final_verified, contradiction, warnings, started,
                                  1.0 if status == "verified" else 0.7 if status == "partially_verified" else 0.0)
            return result.model_copy(update={"choice_match": choice_match, "target": resolution})
        if target.kind in VARIABLE_TARGETS or target.origin == "legacy_default":
            final_verified, contradiction = self._variable_final(plan, checks, variable, expected, transformed, target)
            outcome = "passed" if final_verified else "failed" if contradiction else "unsupported"
            claimed_variable = self._claimed_solutions(plan, variable)
            resolution = self._resolution(target, originals, computed, claimed_variable or claimed_target,
                                          "target" if claimed_variable is not None else role, outcome)
        else:
            final_verified, contradiction, resolution = self._target_final(plan, checks, target, originals, computed,
                                                                           claimed_target, role, variable, expected)
        option_check, choice_match = self._answer_choice_check(plan, resolution)
        if option_check:
            checks.append(option_check)
        option_contradiction = option_check is not None and option_check.status == "failed"
        contradiction = contradiction or option_contradiction
        failed = any(x.status == "failed" for x in checks)
        if contradiction:
            warnings.append("Üretilen final cevap bağımsız çözümle çelişiyor.")
        if option_contradiction:
            warnings.append("Final cevap seçeneği hesaplanan değerle çelişiyor.")
        status = (
            "failed" if failed
            else "verified" if final_verified and all(x.status == "passed" for x in checks)
            else "partially_verified"
        )
        confidence = 1.0 if status == "verified" else 0.7 if status == "partially_verified" else 0.0
        if choice_match is not None and choice_match.status == "no_match":
            warnings.append("Hesaplanan sonuç seçeneklerle eşleşmedi; seçenekler yanlış okunmuş olabilir.")
        resolution = resolution.model_copy(update=self._selection(choice_match))
        result = self._result(status, checks, final_verified, contradiction, warnings, started, confidence, graph)
        return result.model_copy(update={"choice_match": choice_match, "target": resolution})

    # ------------------------------------------------------------------ hedef

    def target(self, plan: LessonPlan) -> AnswerTarget:
        analysis = plan.source_analysis
        integrity = analysis.integrity
        if integrity is None:
            integrity = evaluate(analysis, EvaluationState(revision=analysis.revision, origin="legacy"))
        return target_for(analysis, integrity)

    def _resolution(self, target, originals, computed, claimed, role, outcome, reason=None) -> TargetResolution:
        values = sorted(computed.values or [], key=sympy.default_sort_key)
        if outcome == "passed" and (not values or role != "target" and target.kind not in VARIABLE_TARGETS
                                    and target.origin != "legacy_default"):
            outcome = "partially_checked"
        if outcome == "passed" and not target.computable:
            outcome = "partially_checked"
        role_value = "target" if role == "target" or (role == "intermediate" and target.kind in VARIABLE_TARGETS) else role
        if outcome == "passed" and role_value != "target":
            outcome = "partially_checked"
        reason = reason or ("target_value_matched" if outcome == "passed" else
                            computed.reason if computed.values is None and computed.reason != "computed" else
                            "claim_missing" if role == "none" else "claim_unparsed" if role == "unparsed" else
                            "intermediate_not_requested" if role == "intermediate" else
                            "target_value_mismatch" if outcome == "failed" else "target_not_computable")
        return TargetResolution(
            target=target, given=[item[:400] for item in originals[:8]], intermediate=computed.intermediate[:16],
            requested=[targets.text(value) for value in values][:16],
            provider_claim=[targets.text(value) for value in sorted(claimed or [], key=sympy.default_sort_key)][:16],
            claim_role=role_value, outcome=outcome, reason=reason,
        )

    @staticmethod
    def _selection(choice_match):
        if choice_match is None:
            return {}
        if choice_match.status == "matched":
            return {"selected_option": choice_match.matched_labels[0], "option_origin": choice_match.value_origin}
        return {"selected_option": None, "option_origin": "none"}

    def _target_statement(self, target: AnswerTarget, plan) -> str:
        label = _TARGET_DETAIL.get(target.kind, "istenen hedef")
        return f"{label}: {target.expression}" if target.expression else f"{label}: {plan.content.final_answer}"

    def _target_final(self, plan, checks, target, originals, computed, claimed, role, variable, expected):
        statement = self._target_statement(target, plan)[:400]
        intermediate = ("Ara sonuç: " + "; ".join(computed.intermediate[:4])) if computed.intermediate else ""
        if computed.values is None:
            checks.append(VerificationCheck(id="final_answer", kind="answer_target", status="unsupported", statement=statement,
                                            reason=computed.reason, detail=f"İstenen hedef bağımsız hesaplanamadı. {intermediate}"[:400]))
            return False, False, self._resolution(target, originals, computed, claimed, role, "unsupported")
        requested = ", ".join(sorted(map(str, computed.values)))[:200]
        if role == "target" and targets.same_values(claimed, computed.values):
            checks.append(VerificationCheck(id="final_answer", kind="answer_target", status="passed", statement=statement,
                                            reason="target_value_matched", detail=f"İstenen hedefin bağımsız değeri: {requested}"))
            return True, False, self._resolution(target, originals, computed, claimed, role, "passed")
        if role == "target":
            checks.append(VerificationCheck(id="final_answer", kind="answer_target", status="failed", statement=statement,
                                            reason="target_value_mismatch",
                                            detail=f"İstenen hedefin bağımsız değeri {requested}; önerilen cevap bununla çelişiyor."))
            return False, True, self._resolution(target, originals, computed, claimed, role, "failed")
        if role == "intermediate" and not targets.same_values(claimed, computed.values):
            checks.append(VerificationCheck(id="final_answer", kind="answer_target", status="failed", statement=statement,
                                            reason="intermediate_not_requested",
                                            detail=f"Cevap ara değeri veriyor; istenen hedefin değeri {requested}."))
            return False, True, self._resolution(target, originals, computed, claimed, role, "failed")
        checks.append(VerificationCheck(id="final_answer", kind="answer_target", status="unsupported", statement=statement,
                                        reason="claim_unparsed" if role == "unparsed" else "claim_missing",
                                        detail=f"İstenen hedefin bağımsız değeri {requested}; önerilen cevap karşılaştırılamadı."))
        return False, False, self._resolution(target, originals, computed, claimed, role, "unsupported")

    def _premise_choice(self, plan, target, variable, expected, originals):
        """Öncüller çözülen değişkende değerlendirilebilen ilişkilerse doğru birleşimi belirler.

        Herhangi bir öncül değerlendirilemezse None döner ve birleşim uydurulmaz. Kutupluluk (doğrudur /
        yanlıştır / ulaşılamaz) soru kökünden silinmeden okunur.
        """
        analysis = plan.source_analysis
        statements = list(getattr(analysis.source, "statements", []) or []) if getattr(analysis, "source", None) else []
        if not statements:
            statements = [m.group(0) for m in re.finditer(r"(?:VI|IV|V|III|II|I)\s*[.)]\s*[^.?]+?(?=\s+(?:VI|IV|V|III|II|I)\s*[.)]|\.\s|\?|$)",
                                                          analysis.question_text or "")]
        truths = targets.premise_truths(statements, variable, set(expected))
        polarity = premise_polarity(analysis.question_text or "")
        if truths is None or polarity == "unknown":
            return None
        premises = [Premise(label=label, text=f"Öncül {label}", status="supported" if value else "contradicted",
                            evaluator="evidence_check") for label, value in truths.items()]
        integrity = analysis.integrity
        choices = integrity.choices if integrity is not None else parse_choices(list(analysis.answer_choices)).choices
        status, labels = match_combination(select_premises(premises, polarity), choices)
        selected = self._selected_option_label(plan.content.final_answer)
        requested = ["+".join(label for label, value in truths.items() if value == (polarity == "supported")) or "∅"]
        computed = targets.Computed(None, "computed", [f"{label}: {'doğru' if value else 'yanlış'}" for label, value in truths.items()], [])
        base = dict(target=target, given=[item[:400] for item in originals[:8]], intermediate=computed.intermediate,
                    requested=requested, provider_claim=[selected] if selected else [])
        if status != "matched":
            match = ChoiceMatch(status="no_match" if status == "no_match" else "multiple_equivalent", value_origin="independent",
                                value=requested[0], provider_label=selected, matched_labels=labels)
            check = VerificationCheck(id="answer_choice", kind="final_answer", status="unsupported", statement=plan.content.final_answer,
                                      reason="premise_combination_unmatched", detail="Öncül değerlendirmesi hiçbir seçenekle tek başına eşleşmedi.")
            return False, False, TargetResolution(**base, claim_role="target" if selected else "none", outcome="unsupported",
                                                  reason="multiple_values"), check, match
        label = labels[0]
        match = ChoiceMatch(status="matched", value_origin="independent", value=requested[0], provider_label=selected, matched_labels=[label])
        if selected is None:
            check = VerificationCheck(id="answer_choice", kind="final_answer", status="unsupported", statement=plan.content.final_answer,
                                      reason="claim_missing", detail=f"Öncül değerlendirmesi {label} seçeneğini gösteriyor.")
            return False, False, TargetResolution(**base, claim_role="none", outcome="unsupported", reason="claim_missing",
                                                  selected_option=label, option_origin="independent"), check, match
        ok = selected == label
        check = VerificationCheck(id="answer_choice", kind="final_answer", status="passed" if ok else "failed",
                                  statement=plan.content.final_answer, reason="premises_evaluated",
                                  detail=f"Öncüller çözümde değerlendirildi; doğru birleşim {label}.")
        return ok, not ok, TargetResolution(**base, claim_role="target", outcome="passed" if ok else "failed",
                                            reason="target_value_matched" if ok else "target_value_mismatch",
                                            selected_option=label, option_origin="independent"), check, match

    def _variable_final(self, plan, checks, variable, expected, raw, target):
        claimed = self._claimed_solutions(plan, variable)
        display = plan.content.final_answer.strip()
        if claimed is not None and re.fullmatch(rf"{re.escape(str(variable))}\s*=\s*[^=,;]+", display):
            try:
                if solutions(display, variable) != claimed:
                    checks.append(VerificationCheck(id="displayed_answer", kind="final_answer", status="failed", statement=display,
                                                    detail="Gösterilen cevap sonuç ifadesiyle çelişiyor."))
            except MathParseError:
                checks.append(VerificationCheck(id="displayed_answer", kind="final_answer", status="unsupported", statement=display))
        final_verified = claimed is not None and claimed == expected
        contradiction = claimed is not None and claimed != expected
        reason = "target_value_matched" if final_verified else "target_value_mismatch" if contradiction else "claim_unparsed"
        detail = f"Bağımsız çözüm kümesi: {sorted(map(str, expected))}"
        if contradiction and claimed - expected and (claimed - expected) <= set(raw):
            # Fazla kök, dönüştürülmüş (ör. karesi alınmış) bir denklemin kökü ama özgün denklemi sağlamıyor.
            reason = "extraneous_root"
            detail += f". Özgün denklemi sağlamayan kök: {sorted(map(str, claimed - expected))}"
        checks.append(VerificationCheck(
            id="final_answer", kind="final_answer", status="passed" if final_verified else "failed" if contradiction else "unsupported",
            statement=plan.content.final_answer, detail=detail[:400], reason=reason))
        return final_verified, contradiction

    def _verify_target_only(self, plan, target, original, inequality, started, variables=None, computed=None, sources=None):
        """Eşitsizlik, iki bilinmeyenli denklem veya tanım kümesinde yalnızca istenen hedef denetlenir."""
        checks: list[VerificationCheck] = []
        sources = sources or [inequality or original]
        source = "; ".join(sources)[:400]
        try:
            if variables is None:
                node = parse_tree(sources[0])
                variables = sorted({Symbol(name, real=True) for name in expression_tree.symbols(node.tree)}, key=str)
            computed = computed or targets.compute(target, original, inequality, variables)
        except (MathParseError, NotImplementedError, TypeError, ValueError):
            return self._unsupported(plan, target, checks, "Matematiksel ifade güvenli biçimde ayrıştırılamadı.", started)
        checks.append(VerificationCheck(id="original_equation", kind="equation", status="passed", statement=source,
                                        detail="Kaynak ilişki güvenli ayrıştırıldı."))
        if inequality is not None and len(variables) == 1:
            self._inequality_steps(plan, checks, inequality, variables[0])
        else:
            for step in plan.content.steps:
                if step.expressions:
                    checks.append(VerificationCheck(id=step.id, kind="transformation", status="unsupported",
                                                    statement="; ".join(x.latex for x in step.expressions)[:400], reason="step_not_checked"))
        claimed, role = targets.claim(target, [item.latex for item in plan.content.final_answer_expressions], variables)
        final_verified, contradiction, resolution = self._target_final(plan, checks, target, sources, computed, claimed, role,
                                                                       variables[0] if variables else None, set())
        option_check, choice_match = self._answer_choice_check(plan, resolution)
        if option_check:
            checks.append(option_check)
        contradiction = contradiction or (option_check is not None and option_check.status == "failed")
        failed = any(x.status == "failed" for x in checks)
        status = "failed" if failed else "partially_verified" if final_verified else "unsupported"
        warnings = ["Ara adımlar bu soru türünde denetlenmedi; yalnızca istenen hedef hesaplandı."]
        if contradiction:
            warnings.append("Üretilen final cevap bağımsız çözümle çelişiyor.")
        resolution = resolution.model_copy(update=self._selection(choice_match))
        result = self._result(status, checks, final_verified, contradiction, warnings, started, 0.7 if final_verified else 0.0)
        return result.model_copy(update={"choice_match": choice_match, "target": resolution})

    def _unsupported(self, plan, target, checks, message, started, originals=()):
        resolution = self._resolution(target, list(originals), targets.Computed(None, "model_unsupported", [], []), None,
                                      "none", "unsupported", reason="target_unresolved" if not target.computable else "model_unsupported")
        return self._result("unsupported", checks, False, False, [message], started).model_copy(update={"target": resolution})

    # ------------------------------------------------------------------ adımlar

    def _step_checks(self, plan, checks, variable, expected, original_text) -> set:
        """Adım kontrollerini ekler; dönüştürülmüş denklemlerin köklerini (yabancı kök tespiti için) döndürür."""
        previous = expected
        seen: set = set()
        previous_equation = equation(branches(original_text)[0]) if len(branches(original_text)) == 1 else None
        for step in plan.content.steps:
            for item in step.expressions:
                if item.type == "inequality":
                    checks.append(self._inequality_step(step.id, item.latex, variable))
                elif item.type not in ("equation", "function"):
                    checks.append(VerificationCheck(id=step.id, kind="expression", status="unsupported", statement=item.latex))
            equation_items = [item for item in step.expressions if item.type in ("equation", "function")]
            if step.type == "case" and len(equation_items) > 1:
                try:
                    branch_union = set()
                    for item in equation_items:
                        branch_union.update(solutions(item.latex, variable))
                    valid = branch_union == expected
                    checks.append(VerificationCheck(
                        id=step.id, kind="transformation", status="passed" if valid else "failed",
                        statement="; ".join(x.latex for x in equation_items), operation="case_split",
                        reason="cases_cover_solution_set" if valid else "case_missing_or_invalid",
                        detail="Durumların birleşimi çözüm kümesini veriyor." if valid else "Durumlardan biri eksik veya geçersiz."))
                except (MathParseError, NotImplementedError, TypeError):
                    checks.append(VerificationCheck(id=step.id, kind="transformation", status="unsupported",
                                                    statement="; ".join(x.latex for x in equation_items)))
                continue
            for index, item in enumerate(equation_items):
                try:
                    current = solutions(item.latex, variable)
                    seen |= current
                    current_equation = equation(branches(item.latex)[0]) if len(branches(item.latex)) == 1 else None
                    operation = targets.classify(previous_equation, current_equation, variable) if (
                        previous_equation is not None and current_equation is not None) else None
                    if current == previous:
                        status, reason, detail = "passed", "solution_set_preserved", "Çözüm kümesi korundu."
                    elif previous < current and operation in {"square_both_sides", "multiply_both_sides"}:
                        # Tersinir olmayan dönüşüm aday kök ekleyebilir; kökler özgün denklemde ayrıca denetlenir.
                        status, reason = "passed", "nonreversible_superset"
                        detail = "Dönüşüm çözüm kümesini genişletti; adaylar özgün denklemde denetlenmeli."
                    elif current < previous:
                        status, reason, detail = "failed", "solution_lost", "Dönüşüm bir çözümü kaybettirdi (ör. değişken içeren ifadeye bölme)."
                    else:
                        status, reason, detail = "failed", "solution_set_changed", "Dönüşüm çözüm kümesini değiştirdi."
                    checks.append(VerificationCheck(id=f"{step.id}_{index}", kind="transformation", status=status,
                                                    statement=item.latex, detail=detail, reason=reason, operation=operation))
                    if status == "passed":
                        previous = current
                        previous_equation = current_equation
                except (MathParseError, NotImplementedError, TypeError):
                    checks.append(VerificationCheck(id=f"{step.id}_{index}", kind="transformation", status="unsupported",
                                                    statement=item.latex))
        return seen

    def _inequality_steps(self, plan, checks, source, variable):
        """Eşitsizlik adımları: çözüm kümesi korunuyor mu, yön negatif çarpanda ters çevrildi mi?"""
        try:
            previous = relation_set(source, variable)
        except (MathParseError, NotImplementedError, TypeError, ValueError):
            return
        for step in plan.content.steps:
            for index, item in enumerate(step.expressions):
                check_id = f"{step.id}_{index}"
                if not is_inequality(item.latex):
                    checks.append(VerificationCheck(id=check_id, kind="expression", status="unsupported", statement=item.latex,
                                                    reason="step_not_checked"))
                    continue
                try:
                    current = relation_set(item.latex, variable)
                    if current == previous:
                        checks.append(VerificationCheck(id=check_id, kind="transformation", status="passed", statement=item.latex,
                                                        reason="solution_set_preserved", detail="Eşitsizliğin çözüm kümesi korundu."))
                        continue
                    flipped = relation_set(item.latex, variable, flip=True) == previous
                    checks.append(VerificationCheck(
                        id=check_id, kind="transformation", status="failed", statement=item.latex,
                        reason="inequality_direction" if flipped else "solution_set_changed",
                        detail="Negatif bir sayıyla çarpma veya bölmede eşitsizlik yönü değişmeliydi." if flipped
                        else "Dönüşüm eşitsizliğin çözüm kümesini değiştirdi."))
                except (MathParseError, NotImplementedError, TypeError, ValueError):
                    checks.append(VerificationCheck(id=check_id, kind="transformation", status="unsupported", statement=item.latex))

    def _inequality_step(self, step_id, latex, variable):
        try:
            region = relation_set(latex, variable)
        except (MathParseError, NotImplementedError, TypeError, ValueError):
            return VerificationCheck(id=step_id, kind="expression", status="unsupported", statement=latex)
        return VerificationCheck(id=step_id, kind="expression", status="unsupported", statement=latex, reason="inequality_step_unlinked",
                                 detail=f"Eşitsizlik çözüm kümesi: {region}"[:400])

    # ------------------------------------------------------------------ seçenekler

    def reconcile_answer_choice(self, plan: LessonPlan) -> LessonPlan:
        """Seçenek etiketini yalnızca *istenen hedefin* bağımsız/önerilen değeriyle kesin eşdeğerlikte belirler.

        En yakın değer seçilmez; çözülen değişken her sorunun cevabı sayılmaz (x = 3 iken x + 2 sorulduysa
        5 aranır). Hedef belirlenemezse seçenek değiştirilmez. Eşleşme yoksa yanlış etiket kaldırılır.
        """
        integrity = plan.source_analysis.integrity
        if integrity is not None and integrity.intent.choice_dependent:
            return plan
        target, independent, claimed, variable = self._choice_values(plan)
        if claimed and independent and not targets.same_values(claimed, independent):
            return plan  # Çelişki doğrulamada yakalanır ve sınırlı düzeltme turu çalışır.
        values = independent or claimed
        choices = self._labeled_choice_values(plan, variable)
        if not values or len(values) != 1 or not choices or len(choices) != len(plan.source_analysis.answer_choices):
            return plan
        value = next(iter(values))
        matching = [label for label, choice_value, _ in choices if self._same_value(value, choice_value)]
        selected = self._selected_option_label(plan.content.final_answer)
        if len(matching) == 1:
            label = matching[0]
            choice_text = next(text for item_label, _, text in choices if item_label == label)
            if selected == label and plan.content.final_answer.strip() == f"{label}) {choice_text}":
                return plan
            final = f"{label}) {choice_text}"
        elif selected and selected not in matching:
            final = ", ".join(item.latex for item in plan.content.final_answer_expressions)
        else:
            return plan
        content = plan.content.model_copy(update={"final_answer": final})
        return plan.model_copy(update={"content": content})

    def _choice_values(self, plan):
        """(hedef, bağımsız değerler, hedefe ait önerilen değerler, seçenek değişkeni)."""
        target = self.target(plan)
        if not target.computable or target.kind == "statement_combination":
            return target, None, None, None
        originals = self._source_equations(plan)
        if len(originals) > 1 and target.kind in EXPRESSION_TARGETS:
            computed = targets.from_definitions(target, originals)
            claimed, role = targets.claim(target, [item.latex for item in plan.content.final_answer_expressions], [])
            return target, computed.values, claimed if role == "target" else None, None
        inequality = self._source_inequality(plan) if not originals else None
        variables = self._source_variables(plan)
        if not variables or len(originals) > 1:
            return target, None, None, None
        try:
            computed = targets.compute(target, originals[0] if originals else None, inequality, variables)
        except (MathParseError, NotImplementedError, TypeError, ValueError):
            computed = targets.Computed(None, "model_unsupported", [], [])
        claimed, role = targets.claim(target, [item.latex for item in plan.content.final_answer_expressions], variables)
        variable_target = target.kind in VARIABLE_TARGETS or target.origin == "legacy_default"
        if role != "target" and not (variable_target and role == "intermediate"):
            claimed = None
        choice_variable = variables[0] if len(variables) == 1 and variable_target else None
        return target, computed.values, claimed, choice_variable

    def _source_equations(self, plan):
        """Problemi tanımlayan denklemler. Seçenekteki veya öncüldeki denklem problemi tanımlamaz."""
        integrity = plan.source_analysis.integrity
        if integrity is not None and integrity.expressions:
            return [
                item.source for item in integrity.expressions
                if item.role == "given" and item.status == "parsed" and item.canonical
                and item.canonical.count(" = ") == 1 and not any(op in item.canonical for op in ("<", ">", "!="))
            ]
        return [x for x in plan.source_analysis.mathematical_expressions if "=" in x and not is_inequality(x)]

    def _source_inequality(self, plan):
        integrity = plan.source_analysis.integrity
        if integrity is not None and integrity.expressions:
            items = [item.source for item in integrity.expressions if item.role == "given" and item.status == "parsed"
                     and is_inequality(item.source)]
        else:
            items = [x for x in plan.source_analysis.mathematical_expressions if is_inequality(x)]
        return items[0] if len(items) == 1 else None

    def _labeled_choice_values(self, plan, variable):
        """Yalnızca basılı etiketli ve kesin değeri hesaplanabilen seçenekler; sıradan etiket uydurulmaz."""
        integrity = plan.source_analysis.integrity
        choices = integrity.choices if integrity is not None else parse_choices(list(plan.source_analysis.answer_choices)).choices
        parsed = []
        for choice in choices:
            if not choice.label or not choice.content:
                continue
            value = self._choice_value(choice.content, variable)
            if value is not None:
                parsed.append((choice.label, value, choice.content))
        labels = [label for label, _, _ in parsed]
        return parsed if len(set(labels)) == len(labels) else []

    def _choice_value(self, content, variable):
        try:
            result = parse_tree(content)
            if not result.parsed:
                return None
            node = result.tree
            if isinstance(node, expression_tree.Rel):
                left = node.operands[0]
                if node.ops != ("=",) or variable is None or not isinstance(left, expression_tree.Sym) or left.name != str(variable):
                    return None
                node = node.operands[1]
            value = to_sympy(node)
        except (MathParseError, NotImplementedError, TypeError, ValueError):
            return None
        return value if value.is_number else None

    @staticmethod
    def _same_value(left, right) -> bool:
        try:
            return bool(simplify(left - right) == 0)
        except (TypeError, ValueError, NotImplementedError):
            return False

    def _source_variables(self, plan):
        originals = self._source_equations(plan)
        source = originals[0] if originals else self._source_inequality(plan)
        if not source:
            return []
        try:
            node = parse_tree(source)
            if not node.parsed:
                return []
            return sorted({Symbol(name, real=True) for name in expression_tree.symbols(node.tree)}, key=str)
        except (MathParseError, NotImplementedError, TypeError):
            return []

    def _answer_choice_check(self, plan, resolution):
        """Seçenek tutarlılığı: (kontrol, eşleşme kaydı). Eşleşmeme tek başına çözümü başarısız yapmaz.

        Eşleştirilen değer istenen hedefin değeridir; ara değişken değeri değildir.
        """
        if not plan.source_analysis.answer_choices:
            return None, None
        selected = self._selected_option_label(plan.content.final_answer)
        integrity = plan.source_analysis.integrity
        if integrity is not None and integrity.intent.choice_dependent:
            match = ChoiceMatch(status="choice_dependent", value_origin="none", provider_label=selected)
            return VerificationCheck(id="answer_choice", kind="final_answer", status="unsupported", statement=plan.content.final_answer,
                                     detail="Seçim sorunun ifadesine bağlı; otomatik eşleştirme yapılmadı."), match
        target, independent, claimed, variable = self._choice_values(plan)
        choices = self._labeled_choice_values(plan, variable)
        if independent and len(independent) == 1:
            values, origin = independent, "independent"
        elif claimed and len(claimed) == 1:
            values, origin = claimed, "provider"
        else:
            values, origin = None, "none"
        if len(choices) != len(plan.source_analysis.answer_choices) or not values:
            match = ChoiceMatch(status="unsupported", value_origin=origin, provider_label=selected)
            detail = None if target.computable else "Sorunun istediği hedef belirlenemedi; seçenek otomatik eşleştirilmedi."
            return VerificationCheck(id="answer_choice", kind="final_answer", status="unsupported", statement=plan.content.final_answer,
                                     detail=detail, reason=None if target.computable else "target_unresolved"), match
        value = next(iter(values))
        matching = [label for label, choice_value, _ in choices if self._same_value(value, choice_value)]
        status = "matched" if len(matching) == 1 else "multiple_equivalent" if matching else "no_match"
        match = ChoiceMatch(status=status, value_origin=origin, value=str(value)[:120], provider_label=selected, matched_labels=matching)
        if status == "no_match":
            if selected:
                return VerificationCheck(id="answer_choice", kind="final_answer", status="failed", statement=plan.content.final_answer,
                                         detail="Seçilen seçenek hesaplanan değerle uyuşmuyor ve hiçbir seçenek eşleşmedi."), match
            return VerificationCheck(id="answer_choice", kind="final_answer", status="unsupported", statement=plan.content.final_answer,
                                     detail="Hesaplanan değer hiçbir seçenekle eşleşmedi."), match
        conflict = status == "matched" and self._choice_text_conflicts(plan.content.final_answer, value)
        if selected and (selected not in matching or conflict):
            return VerificationCheck(id="answer_choice", kind="final_answer", status="failed", statement=plan.content.final_answer,
                                     detail=f"İstenen hedefin değeri {', '.join(matching)} seçeneğine karşılık geliyor."), match
        detail = f"Hesaplanan değer {matching[0]} seçeneğiyle uyumlu." if status == "matched" else f"Birden fazla eşdeğer seçenek var: {', '.join(matching)}."
        return VerificationCheck(id="answer_choice", kind="final_answer", status="passed", statement=plan.content.final_answer, detail=detail), match

    def _choice_text_conflicts(self, text, value):
        tail = re.sub(r"^[A-Ea-e]\s*[)\].:\-]\s*", "", text.strip())
        try:
            return bool(tail) and simplify(expression(tail) - value) != 0
        except MathParseError:
            return False

    def _selected_option_label(self, text):
        match = re.search(r"(?:^|[\s(])([A-Ea-e])\s*[\)\].:\-]", text)
        return match.group(1).upper() if match else None

    def _claimed_solutions(self, plan, variable):
        values = set()
        for item in plan.content.final_answer_expressions:
            try:
                raw = item.latex.strip().strip("$")
                if "=" in raw:
                    lhs, rhs = raw.split("=", 1)
                    if lhs.strip() != str(variable) or any(
                        expression(v).free_symbols for v in branches(rhs)
                    ):
                        return None
                    values.update(solutions(raw, variable))
                else:
                    match = re.fullmatch(
                        r"([a-zA-Z])\s*(?:\\in|∈)\s*\\?\{([^{}]+?)\\?\}", raw
                    )
                    if not match or match[1] != str(variable):
                        return None
                    for token in match[2].split(","):
                        number = expression(token).doit()
                        if not number.is_number or number.is_real is not True:
                            return None
                        values.add(number)
            except (MathParseError, NotImplementedError, TypeError):
                return None
        return values or None

    def _result(
        self,
        status,
        checks,
        final,
        contradiction,
        warnings,
        started,
        confidence=0.0,
        graph=None,
    ):
        return VerificationResult(
            status=status,
            confidence=confidence,
            checks=checks,
            final_answer_verified=final,
            contradiction=contradiction,
            warnings=warnings,
            engine_version=sympy.__version__,
            graph=graph,
            processing_time_ms=round((perf_counter() - started) * 1000),
        )

    def equivalent(self, left: str, right: str) -> bool:
        return simplify(expression(left) - expression(right)) == 0

    def analyze_function(self, value: str) -> GraphData:
        expr = expression(value.split("=", 1)[-1])
        x = Symbol("x", real=True)
        roots = solve(expr, x)
        derivative = sympy.diff(expr, x)
        critical = solve(derivative, x)
        if expr.free_symbols != {x}:
            raise MathParseError("unsupported graph variables")

        def number(v):
            if v.is_finite is not True or v.is_real is not True:
                raise MathParseError("unsupported graph domain")
            return float(sympy.N(v))

        return GraphData(
            expression=value,
            roots=[number(v) for v in roots if v.is_real],
            y_intercept=number(expr.subs(x, 0)),
            critical_points=[number(v) for v in critical if v.is_real],
            sample_points=[(n, number(expr.subs(x, n))) for n in range(-3, 4)],
        )

    def triangle_missing_angle(self, a: float, b: float) -> float:
        value = 180 - a - b
        if a <= 0 or b <= 0 or value <= 0:
            raise ValueError("invalid triangle")
        return value

    def rectangle_area(self, width: float, height: float) -> float:
        if width <= 0 or height <= 0:
            raise ValueError("lengths must be positive")
        return width * height

    def circle_diameter(self, radius: float) -> float:
        if radius <= 0:
            raise ValueError("radius must be positive")
        return radius * 2

    def pythagorean_hypotenuse(self, a: float, b: float) -> float:
        if a <= 0 or b <= 0:
            raise ValueError("lengths must be positive")
        return float(sympy.sqrt(a * a + b * b))

    def check_answer(
        self, question: str, answer: str, variable_name: str | None = None
    ) -> tuple[bool, str]:
        """Deterministically compare a student's claimed solution set with an equation."""
        original = equation(branches(question)[0])
        variables = sorted(original.free_symbols, key=str)
        if len(variables) != 1:
            raise MathParseError("practice equation must contain one variable")
        variable = variables[0]
        normalized = answer.strip()
        if "=" in normalized and not re.fullmatch(
            rf"{re.escape(str(variable))}\s*=\s*[^=]+", normalized
        ):
            raise MathParseError("expected an answer value")
        if "=" not in normalized:
            normalized = f"{variable_name or variable}={normalized}"
        expected = solutions(question, variable)
        rhs = normalized.split("=", 1)[1]
        if any(expression(part).free_symbols for part in branches(rhs)):
            raise MathParseError("expected numeric values")
        claimed = solutions(normalized, variable)
        if claimed == expected:
            return True, "unknown"
        if len(claimed) < len(expected) and claimed.issubset(expected):
            return False, "missing_case"
        if len(claimed) == len(expected) == 1:
            actual, given = next(iter(expected)), next(iter(claimed))
            if simplify(actual + given) == 0:
                return False, "sign_error"
            if actual.is_number and given.is_number:
                return False, "arithmetic_error"
        return False, "unknown"
