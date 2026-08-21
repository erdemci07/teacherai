from time import perf_counter
import re
import sympy
from sympy import Eq, Symbol, simplify, solve
from .parser import MathParseError,equation,expression,normalize
from .schemas import GraphData,VerificationCheck,VerificationResult
from ..lessons.schemas import LessonPlan
class MathAIService:
    def verify(self,plan:LessonPlan)->VerificationResult:
        started=perf_counter(); checks=[]; warnings=[]; graph=None
        originals=[x for x in plan.source_analysis.mathematical_expressions if "=" in x]
        if not originals:
            return self._result("unsupported",checks,False,False,["Bu soru türü henüz deterministik olarak doğrulanamıyor."],started)
        try:
            original=equation(originals[0]); variables=sorted(original.free_symbols,key=str)
            if str(original.lhs)=="y" and Symbol("x",real=True) in original.rhs.free_symbols:
                graph=self.analyze_function(originals[0])
                checks.append(VerificationCheck(id="function_analysis",kind="function",status="passed",statement=originals[0],detail="Kökler, eksen kesişimi ve örnek noktalar deterministik hesaplandı."))
                return self._result("partially_verified",checks,False,False,["Grafik özellikleri kontrol edildi; tüm sözel iddialar doğrulanmadı."],started,.7,graph)
            if len(variables)!=1: return self._result("unsupported",checks,False,False,["Birden fazla değişkenli doğrulama henüz desteklenmiyor."],started)
            variable=variables[0]; expected=set(solve(original,variable))
            checks.append(VerificationCheck(id="original_equation",kind="equation",status="passed",statement=originals[0],detail="Denklem güvenli ayrıştırıldı."))
        except (MathParseError,NotImplementedError,TypeError):
            return self._result("unsupported",checks,False,False,["Matematiksel ifade güvenli biçimde ayrıştırılamadı."],started)
        previous=expected
        for step in plan.content.steps:
            equation_items=[item for item in step.expressions if item.type in ("equation","function")]
            if step.type=="case" and len(equation_items)>1:
                try:
                    branch_union=set()
                    for item in equation_items: branch_union.update(solve(equation(item.latex),variable))
                    valid=branch_union==expected
                    checks.append(VerificationCheck(id=step.id,kind="transformation",status="passed" if valid else "failed",statement="; ".join(x.latex for x in equation_items),detail="Durumların birleşimi çözüm kümesini veriyor." if valid else "Durumlardan biri eksik veya geçersiz."))
                except (MathParseError,NotImplementedError,TypeError): checks.append(VerificationCheck(id=step.id,kind="transformation",status="unsupported",statement="; ".join(x.latex for x in equation_items)))
                continue
            for index,item in enumerate(equation_items):
                try:
                    current_eq=equation(item.latex); current=set(solve(current_eq,variable))
                    valid=current==previous
                    checks.append(VerificationCheck(id=f"{step.id}_{index}",kind="transformation",status="passed" if valid else "failed",statement=item.latex,detail="Çözüm kümesi korundu." if valid else "Dönüşüm çözüm kümesini değiştirdi."))
                    if valid: previous=current
                except (MathParseError,NotImplementedError,TypeError): checks.append(VerificationCheck(id=f"{step.id}_{index}",kind="transformation",status="unsupported",statement=item.latex))
        claimed=self._claimed_solutions(plan,variable)
        final_verified=claimed is not None and claimed==expected
        contradiction=claimed is not None and claimed!=expected
        checks.append(VerificationCheck(id="final_answer",kind="final_answer",status="passed" if final_verified else "failed" if contradiction else "unsupported",statement=plan.content.final_answer,detail=f"Bağımsız çözüm kümesi: {sorted(map(str,expected))}"))
        option_check=self._answer_choice_check(plan,claimed)
        if option_check:
            checks.append(option_check)
        option_contradiction=option_check is not None and option_check.status=="failed"
        contradiction=contradiction or option_contradiction
        failed=any(x.status=="failed" for x in checks)
        if contradiction: warnings.append("Üretilen final cevap bağımsız çözümle çelişiyor.")
        if option_contradiction: warnings.append("Final cevap seçeneği hesaplanan değerle çelişiyor.")
        status="failed" if failed else "verified" if final_verified and all(x.status=="passed" for x in checks) else "partially_verified"
        confidence=1.0 if status=="verified" else .7 if status=="partially_verified" else 0.0
        return self._result(status,checks,final_verified,contradiction,warnings,started,confidence,graph)

    def reconcile_answer_choice(self,plan:LessonPlan)->LessonPlan:
        claimed=self._claimed_solutions_from_final_expressions(plan)
        choices=self._numeric_answer_choices(plan.source_analysis.answer_choices)
        selected=self._selected_option_label(plan.content.final_answer)
        if not claimed or len(claimed)!=1 or not choices:
            return plan
        matching=[label for label,value,text in choices if simplify(next(iter(claimed))-value)==0]
        if len(matching)!=1:
            return plan
        label=matching[0]
        if selected==label:
            return plan
        choice_text=next(text for item_label,_,text in choices if item_label==label)
        content=plan.content.model_copy(update={"final_answer":f"{label}) {choice_text}"})
        return plan.model_copy(update={"content":content})

    def _claimed_solutions_from_final_expressions(self,plan):
        variables=self._source_variables(plan)
        if len(variables)!=1:
            return None
        return self._claimed_solutions(plan,variables[0])

    def _source_variables(self,plan):
        originals=[x for x in plan.source_analysis.mathematical_expressions if "=" in x]
        if not originals:
            return []
        try:
            return sorted(equation(originals[0]).free_symbols,key=str)
        except (MathParseError,NotImplementedError,TypeError):
            return []

    def _answer_choice_check(self,plan,claimed):
        choices=self._numeric_answer_choices(plan.source_analysis.answer_choices)
        selected=self._selected_option_label(plan.content.final_answer)
        if not choices or not claimed or len(claimed)!=1:
            return None
        value=next(iter(claimed))
        matching=[label for label,choice_value,_ in choices if simplify(value-choice_value)==0]
        if len(matching)!=1:
            return VerificationCheck(id="answer_choice",kind="final_answer",status="unsupported",statement=plan.content.final_answer,detail="Cevap seçenekleri güvenli biçimde eşleştirilemedi.")
        expected_label=matching[0]
        if selected and selected!=expected_label:
            return VerificationCheck(id="answer_choice",kind="final_answer",status="failed",statement=plan.content.final_answer,detail=f"Hesaplanan değer {expected_label} seçeneğine karşılık geliyor.")
        return VerificationCheck(id="answer_choice",kind="final_answer",status="passed",statement=plan.content.final_answer,detail=f"Hesaplanan değer {expected_label} seçeneğiyle uyumlu.")

    def _numeric_answer_choices(self,choices):
        parsed=[]
        for index,choice in enumerate(choices):
            text=choice.strip()
            match=re.match(r"^\s*([A-Ea-e])\s*[\)\].:\-]\s*(.+?)\s*$",text)
            label=match.group(1).upper() if match else chr(ord("A")+index)
            value_text=match.group(2).strip() if match else text
            try:
                parsed.append((label,expression(value_text),value_text))
            except MathParseError:
                continue
        return parsed

    def _selected_option_label(self,text):
        match=re.search(r"(?:^|[\s(])([A-Ea-e])\s*[\)\].:\-]",text)
        return match.group(1).upper() if match else None

    def _claimed_solutions(self,plan,variable):
        values=set()
        for item in plan.content.final_answer_expressions:
            text=normalize(item.latex)
            try:
                if "=" in text:
                    eq=equation(item.latex)
                    values.update(solve(eq,variable))
                elif "in" in text or "\\in" in item.latex:
                    for token in re.findall(r"-?\d+(?:\.\d+)?",text): values.add(sympy.sympify(token))
            except (MathParseError,NotImplementedError): return None
        return values or None
    def _result(self,status,checks,final,contradiction,warnings,started,confidence=0.0,graph=None):
        return VerificationResult(status=status,confidence=confidence,checks=checks,final_answer_verified=final,contradiction=contradiction,warnings=warnings,engine_version=sympy.__version__,graph=graph,processing_time_ms=round((perf_counter()-started)*1000))
    def equivalent(self,left:str,right:str)->bool:
        return simplify(expression(left)-expression(right))==0
    def analyze_function(self,value:str)->GraphData:
        expr=expression(value.split("=",1)[-1]); x=Symbol("x",real=True); roots=solve(expr,x)
        derivative=sympy.diff(expr,x); critical=solve(derivative,x)
        def number(v): return float(sympy.N(v))
        return GraphData(expression=value,roots=[number(v) for v in roots if v.is_real],y_intercept=number(expr.subs(x,0)),critical_points=[number(v) for v in critical if v.is_real],sample_points=[(n,number(expr.subs(x,n))) for n in range(-3,4)])
    def triangle_missing_angle(self,a:float,b:float)->float:
        value=180-a-b
        if a<=0 or b<=0 or value<=0: raise ValueError("invalid triangle")
        return value
    def rectangle_area(self,width:float,height:float)->float:
        if width<=0 or height<=0: raise ValueError("lengths must be positive")
        return width*height
    def circle_diameter(self,radius:float)->float:
        if radius<=0: raise ValueError("radius must be positive")
        return radius*2
    def pythagorean_hypotenuse(self,a:float,b:float)->float:
        if a<=0 or b<=0: raise ValueError("lengths must be positive")
        return float(sympy.sqrt(a*a+b*b))
    def check_answer(self, question: str, answer: str, variable_name: str | None = None) -> tuple[bool, str]:
        """Deterministically compare a student's claimed solution set with an equation."""
        original = equation(question)
        variables = sorted(original.free_symbols, key=str)
        if len(variables) != 1:
            raise MathParseError("practice equation must contain one variable")
        variable = variables[0]
        normalized = answer.strip()
        if "=" not in normalized:
            normalized = f"{variable_name or variable}={normalized}"
        claimed_equation = equation(normalized)
        expected = set(solve(original, variable))
        claimed = set(solve(claimed_equation, variable))
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
