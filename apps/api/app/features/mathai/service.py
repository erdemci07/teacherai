import re
from time import perf_counter

import sympy
from sympy import Symbol, simplify, solve

from ..integrity import expression as expression_tree
from ..integrity.expression import parse as parse_tree
from ..integrity.language import parse_choices
from ..lessons.schemas import LessonPlan
from .parser import MathParseError, branches, equation, expression, solutions, to_sympy
from .schemas import ChoiceMatch, GraphData, VerificationCheck, VerificationResult


class MathAIService:
    def verify(self, plan: LessonPlan) -> VerificationResult:
        started = perf_counter()
        checks = []
        warnings = []
        graph = None
        originals = self._source_equations(plan)
        if not originals:
            return self._result(
                "unsupported",
                checks,
                False,
                False,
                ["Bu soru türü henüz deterministik olarak doğrulanamıyor."],
                started,
            )
        try:
            if len(originals) != 1:
                raise MathParseError("multiple source equations")
            original = equation(branches(originals[0])[0])
            variables = sorted(original.free_symbols, key=str)
            if (
                str(original.lhs) == "y"
                and Symbol("x", real=True) in original.rhs.free_symbols
            ):
                graph = self.analyze_function(originals[0])
                checks.append(
                    VerificationCheck(
                        id="function_analysis",
                        kind="function",
                        status="passed",
                        statement=originals[0],
                        detail="Kökler, eksen kesişimi ve örnek noktalar deterministik hesaplandı.",
                    )
                )
                _, choice_match = self._answer_choice_check(plan, None, None)
                return self._result(
                    "partially_verified",
                    checks,
                    False,
                    False,
                    [
                        "Grafik özellikleri kontrol edildi; tüm sözel iddialar doğrulanmadı."
                    ],
                    started,
                    0.7,
                    graph,
                ).model_copy(update={"choice_match": choice_match})
            if len(variables) != 1:
                return self._result(
                    "unsupported",
                    checks,
                    False,
                    False,
                    ["Birden fazla değişkenli doğrulama henüz desteklenmiyor."],
                    started,
                )
            variable = variables[0]
            expected = solutions(originals[0], variable)
            checks.append(
                VerificationCheck(
                    id="original_equation",
                    kind="equation",
                    status="passed",
                    statement=originals[0],
                    detail="Denklem güvenli ayrıştırıldı.",
                )
            )
        except (MathParseError, NotImplementedError, TypeError):
            return self._result(
                "unsupported",
                checks,
                False,
                False,
                ["Matematiksel ifade güvenli biçimde ayrıştırılamadı."],
                started,
            )
        previous = expected
        for step in plan.content.steps:
            for item in step.expressions:
                if item.type not in ("equation", "function"):
                    checks.append(
                        VerificationCheck(
                            id=step.id,
                            kind="expression",
                            status="unsupported",
                            statement=item.latex,
                        )
                    )
            equation_items = [
                item
                for item in step.expressions
                if item.type in ("equation", "function")
            ]
            if step.type == "case" and len(equation_items) > 1:
                try:
                    branch_union = set()
                    for item in equation_items:
                        branch_union.update(solutions(item.latex, variable))
                    valid = branch_union == expected
                    checks.append(
                        VerificationCheck(
                            id=step.id,
                            kind="transformation",
                            status="passed" if valid else "failed",
                            statement="; ".join(x.latex for x in equation_items),
                            detail="Durumların birleşimi çözüm kümesini veriyor."
                            if valid
                            else "Durumlardan biri eksik veya geçersiz.",
                        )
                    )
                except (MathParseError, NotImplementedError, TypeError):
                    checks.append(
                        VerificationCheck(
                            id=step.id,
                            kind="transformation",
                            status="unsupported",
                            statement="; ".join(x.latex for x in equation_items),
                        )
                    )
                continue
            for index, item in enumerate(equation_items):
                try:
                    current = solutions(item.latex, variable)
                    valid = current == previous
                    checks.append(
                        VerificationCheck(
                            id=f"{step.id}_{index}",
                            kind="transformation",
                            status="passed" if valid else "failed",
                            statement=item.latex,
                            detail="Çözüm kümesi korundu."
                            if valid
                            else "Dönüşüm çözüm kümesini değiştirdi.",
                        )
                    )
                    if valid:
                        previous = current
                except (MathParseError, NotImplementedError, TypeError):
                    checks.append(
                        VerificationCheck(
                            id=f"{step.id}_{index}",
                            kind="transformation",
                            status="unsupported",
                            statement=item.latex,
                        )
                    )
        claimed = self._claimed_solutions(plan, variable)
        display = plan.content.final_answer.strip()
        if claimed is not None and re.fullmatch(
            rf"{re.escape(str(variable))}\s*=\s*[^=,;]+", display
        ):
            try:
                if solutions(display, variable) != claimed:
                    checks.append(
                        VerificationCheck(
                            id="displayed_answer",
                            kind="final_answer",
                            status="failed",
                            statement=display,
                            detail="Gösterilen cevap sonuç ifadesiyle çelişiyor.",
                        )
                    )
            except MathParseError:
                checks.append(
                    VerificationCheck(
                        id="displayed_answer",
                        kind="final_answer",
                        status="unsupported",
                        statement=display,
                    )
                )
        final_verified = claimed is not None and claimed == expected
        contradiction = claimed is not None and claimed != expected
        checks.append(
            VerificationCheck(
                id="final_answer",
                kind="final_answer",
                status="passed"
                if final_verified
                else "failed"
                if contradiction
                else "unsupported",
                statement=plan.content.final_answer,
                detail=f"Bağımsız çözüm kümesi: {sorted(map(str, expected))}",
            )
        )
        option_check, choice_match = self._answer_choice_check(plan, claimed, expected)
        if option_check:
            checks.append(option_check)
        option_contradiction = (
            option_check is not None and option_check.status == "failed"
        )
        contradiction = contradiction or option_contradiction
        failed = any(x.status == "failed" for x in checks)
        if contradiction:
            warnings.append("Üretilen final cevap bağımsız çözümle çelişiyor.")
        if option_contradiction:
            warnings.append("Final cevap seçeneği hesaplanan değerle çelişiyor.")
        status = (
            "failed"
            if failed
            else "verified"
            if final_verified and all(x.status == "passed" for x in checks)
            else "partially_verified"
        )
        confidence = (
            1.0
            if status == "verified"
            else 0.7
            if status == "partially_verified"
            else 0.0
        )
        if choice_match is not None and choice_match.status == "no_match":
            warnings.append("Hesaplanan sonuç seçeneklerle eşleşmedi; seçenekler yanlış okunmuş olabilir.")
        result = self._result(
            status,
            checks,
            final_verified,
            contradiction,
            warnings,
            started,
            confidence,
            graph,
        )
        return result.model_copy(update={"choice_match": choice_match})

    def reconcile_answer_choice(self, plan: LessonPlan) -> LessonPlan:
        """Seçenek etiketini yalnızca bağımsız/önerilen sonuçla kesin eşdeğerlikte belirler.

        En yakın değer seçilmez, soru veya akıl yürütme değiştirilmez. Eşleşme yoksa yanlış etiket
        kaldırılır ve sonuç etiketsiz gösterilir; uyuşmazlık doğrulama sonucunda açıkça kaydedilir.
        """
        integrity = plan.source_analysis.integrity
        if integrity is not None and integrity.intent.choice_dependent:
            return plan
        variables = self._source_variables(plan)
        variable = variables[0] if len(variables) == 1 else None
        claimed = self._claimed_solutions(plan, variable) if variable is not None else None
        independent = self._independent_solutions(plan, variable) if variable is not None else None
        if claimed and independent and claimed != independent:
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

    def _source_equations(self, plan):
        """Problemi tanımlayan denklemler. Seçenekteki veya öncüldeki denklem problemi tanımlamaz."""
        integrity = plan.source_analysis.integrity
        if integrity is not None and integrity.expressions:
            return [
                item.source for item in integrity.expressions
                if item.role == "given" and item.status == "parsed" and item.canonical
                and item.canonical.count(" = ") == 1 and not any(op in item.canonical for op in ("<", ">", "!="))
            ]
        return [x for x in plan.source_analysis.mathematical_expressions if "=" in x]

    def _independent_solutions(self, plan, variable):
        originals = self._source_equations(plan)
        if len(originals) != 1:
            return None
        try:
            values = solutions(originals[0], variable)
        except (MathParseError, NotImplementedError, TypeError):
            return None
        return values or None

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
        if not originals:
            return []
        try:
            return sorted(equation(branches(originals[0])[0]).free_symbols, key=str)
        except (MathParseError, NotImplementedError, TypeError):
            return []

    def _answer_choice_check(self, plan, claimed, expected=None):
        """Seçenek tutarlılığı: (kontrol, eşleşme kaydı). Eşleşmeme tek başına çözümü başarısız yapmaz."""
        if not plan.source_analysis.answer_choices:
            return None, None
        selected = self._selected_option_label(plan.content.final_answer)
        integrity = plan.source_analysis.integrity
        if integrity is not None and integrity.intent.choice_dependent:
            match = ChoiceMatch(status="choice_dependent", value_origin="none", provider_label=selected)
            return VerificationCheck(id="answer_choice", kind="final_answer", status="unsupported", statement=plan.content.final_answer,
                                     detail="Seçim sorunun ifadesine bağlı; otomatik eşleştirme yapılmadı."), match
        variables = self._source_variables(plan)
        variable = variables[0] if len(variables) == 1 else None
        choices = self._labeled_choice_values(plan, variable)
        if claimed and len(claimed) == 1:
            values, origin = claimed, "independent" if expected is not None and claimed == expected else "provider"
        elif expected and len(expected) == 1:
            values, origin = expected, "independent"
        else:
            values, origin = None, "none"
        if len(choices) != len(plan.source_analysis.answer_choices) or not values:
            match = ChoiceMatch(status="unsupported", value_origin=origin, provider_label=selected)
            return VerificationCheck(id="answer_choice", kind="final_answer", status="unsupported", statement=plan.content.final_answer), match
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
                                     detail=f"Hesaplanan değer {', '.join(matching)} seçeneğine karşılık geliyor."), match
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
