"""TA-004 çok disiplinli belirlenimci denetim matrisi (çevrimdışı, sağlayıcı çağrısı yok).

``tests/fixtures/science/cases.json`` içindeki özgün sentetik vakaları yerel denetleyicilerle çalıştırır ve
beklenen sonuçla karşılaştırır. Bu bir mimari ve algoritma kabul ölçütüdür; gerçek soru, model kalitesi
veya öğretmen incelemesi değildir.

    python -m scripts.science_matrix          # özet
    python -m scripts.science_matrix --check  # uyuşmazlıkta çıkış kodu 1
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

from apps.api.app.features.education.science import (
    DataTable,
    ExperimentalModel,
    GraphSeries,
    Premise,
    ScientificProblemModel,
)
from apps.api.app.features.integrity.language import parse_choices
from apps.api.app.features.reasoning import (
    chemistry,
    evidence,
    formula,
    narrative,
    sequence,
    units,
)

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "apps/api/tests/fixtures/science/cases.json"


def _value(q) -> str | None:
    if q is None:
        return None
    value = q.value
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def run_case(case: dict) -> dict:
    kind, data = case["kind"], case["input"]
    if kind == "formula":
        result = formula.check_formula(data["formula"], data["quantities"], data.get("claim"))
        return {"outcome": result.outcome, "reason": result.reason, "value": _value(result.value)}
    if kind == "dimensions":
        result = formula.check_dimensions(data["formula"], data["units"])
        return {"outcome": result.outcome, "reason": result.reason}
    if kind == "add":
        result = formula.add_quantities(data["left"], data["right"])
        return {"outcome": result.outcome, "reason": result.reason}
    if kind == "convert":
        try:
            value = units.convert(data["quantity"], data["unit"])
        except (units.DimensionError, units.UnitError, units.NumberError) as exc:
            return {"outcome": "failed" if isinstance(exc, units.DimensionError) else "unsupported",
                    "reason": getattr(exc, "reason", str(exc))}
        return {"outcome": "passed", "reason": "converted", "value": _value(units.Q(value))}
    if kind == "unit_relation":
        same = units.same_dimension(data["left"], data["right"])
        equivalent = units.equivalent_units(data["left"], data["right"])
        return {"outcome": "passed", "reason": "equivalent" if equivalent else "same_dimension" if same else "different_dimension"}
    if kind == "unit_parse":
        spec = units.unit_spec(data["unit"])
        return {"outcome": "passed" if spec.status == "parsed" else "unsupported", "reason": spec.status}
    if kind == "number":
        try:
            value, _, _ = units.parse_number(data["text"])
        except units.NumberError as exc:
            return {"outcome": "unsupported", "reason": str(exc)}
        return {"outcome": "passed", "reason": "parsed", "value": _value(units.Q(value))}
    if kind == "reaction":
        outcome, reason, _ = chemistry.check_reaction(data["equation"])
        return {"outcome": outcome, "reason": reason}
    if kind == "species_distinct":
        try:
            same = chemistry.same_species(data["left"], data["right"])
        except chemistry.ChemistryError as exc:
            return {"outcome": "unsupported", "reason": exc.reason}
        return {"outcome": "passed", "reason": "same" if same else "distinct"}
    if kind == "species":
        try:
            item = chemistry.parse_species(data["species"])
        except chemistry.ChemistryError as exc:
            return {"outcome": "unsupported", "reason": exc.reason}
        return {"outcome": "passed", "reason": "parsed",
                "value": f"{item.coefficient}|{dict(item.composition)}|{item.charge}|{item.state}"}
    if kind == "stoichiometry":
        value = chemistry.stoichiometric_amount(data["equation"], data["given"], data["mol"], data["wanted"])
        return {"outcome": "passed", "reason": "computed", "value": _value(units.Q(value))}
    if kind in {"labels", "sequence", "direction", "problem_model"}:
        try:
            model = ScientificProblemModel.model_validate(data["model"])
        except ValidationError:
            return {"outcome": "invalid", "reason": "model_rejected"}
        if kind == "problem_model":
            return {"outcome": "passed", "reason": "model_accepted"}
        if kind == "labels":
            result = evidence.check_labels(model)
        elif kind == "direction":
            result = evidence.check_direction(model, data["relation"])
        else:
            result = evidence.check_sequence(model, data["claimed"])
        return {"outcome": result.outcome, "reason": result.reason}
    if kind in {"claim", "controlled"}:
        experiment = ExperimentalModel.model_validate(data["experiment"])
        result = evidence.check_claim(experiment, data["claim"]) if kind == "claim" else \
            evidence.check_controlled_comparison(experiment, data["groups"])
        return {"outcome": result.outcome, "reason": result.reason}
    if kind == "premises":
        experiment = ExperimentalModel.model_validate(data["experiment"])
        premises = []
        for label, claim in data["premises"].items():
            status = evidence.premise_status(evidence.check_claim(experiment, claim)) if claim else "unevaluated"
            premises.append(Premise(label=label, text=f"Öncül {label}", status=status,
                                    evaluator="none" if status == "unevaluated" else "evidence_check"))
        polarity = evidence.premise_polarity(data["question"])
        status, labels = evidence.match_combination(evidence.select_premises(premises, polarity),
                                                    parse_choices(data["choices"]).choices)
        return {"outcome": "passed" if status == "matched" else "unsupported", "reason": f"{polarity}:{status}",
                "value": ",".join(labels) or None}
    if kind in {"measured_extremum", "exact_optimum", "measured_value", "pair", "constant_ratio", "proportional"}:
        experiment = ExperimentalModel.model_validate(data["experiment"])
        result = {
            "measured_extremum": lambda: evidence.check_measured_extremum(experiment, data["x"], data["y"], data["at"]),
            "exact_optimum": lambda: evidence.check_exact_optimum(experiment, data["x"], data["y"], data["at"]),
            "measured_value": lambda: evidence.check_measured_value(experiment, data["group"], data["y"], data["relation"], data["value"]),
            "pair": lambda: evidence.check_pair(experiment, data["y"], data["left"], data["right"], data["relation"]),
            "constant_ratio": lambda: evidence.check_constant_ratio(experiment, data["x"], data["y"]),
            "proportional": lambda: evidence.proportional_prediction(experiment, data["x"], data["y"], data["at"], data["claim"]),
        }[kind]()
        return {"outcome": result.outcome, "reason": result.reason}
    if kind in {"balance_coefficients", "element_amount", "limiting", "electron_loss"}:
        try:
            if kind == "balance_coefficients":
                coefficients = chemistry.balance_coefficients(data["equation"])
                return {"outcome": "passed", "reason": ":".join(map(str, coefficients)), "value": str(sum(coefficients))}
            if kind == "element_amount":
                value = chemistry.element_amount(data["formula"], data["mol"], data["element"])
                return {"outcome": "passed", "reason": "computed", "value": _value(units.Q(value))}
            if kind == "limiting":
                value, limiting = chemistry.limiting_amount(data["equation"], data["amounts"], data["wanted"])
                return {"outcome": "passed", "reason": f"limiting:{limiting}", "value": _value(units.Q(value))}
            change = chemistry.electron_change(data["equation"])
            return {"outcome": "passed" if change > 0 else "failed", "reason": f"electrons:{change}"}
        except chemistry.ChemistryError as exc:
            return {"outcome": "unsupported", "reason": exc.reason}
    if kind == "codon":
        try:
            value = sequence.codon(sequence.transcribe_template(data["template"]), data["position"])
        except sequence.SequenceError as exc:
            return {"outcome": "unsupported", "reason": str(exc)}
        return {"outcome": "passed", "reason": "transcribed", "value": value}
    if kind in {"graph_slope", "graph_area"}:
        graph = GraphSeries.model_validate(data["graph"])
        result = formula.graph_slope(graph, 0, -1) if kind == "graph_slope" else formula.graph_area(graph)
        return {"outcome": result.outcome, "reason": result.reason, "value": _value(result.value)}
    if kind == "table_column":
        table = DataTable.model_validate(data["table"])
        values, unit = formula.table_column(table, data["header"])
        text = ",".join("-" if v is None else str(v.numerator if v.denominator == 1 else v) for v in values)
        return {"outcome": "passed", "reason": f"unit:{unit}", "value": text}
    if kind == "narrative":
        found = narrative.quantities(data["text"])
        parts = narrative.segments(data["text"])
        requested = [part for part in parts if part.role == "requested"]
        return {"outcome": "passed", "reason": f"segments:{len(parts)}",
                "value": ";".join(f"{q.symbol or ''}={q.magnitude} {q.unit.canonical}" for q in found)
                + ("|requested_last" if requested and requested[-1].end == parts[-1].end else "")}
    raise ValueError(f"unknown kind {kind}")


def run() -> dict:
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    mismatches, subjects, outcomes = [], Counter(), Counter()
    for case in cases:
        actual = run_case(case)
        subjects[case["subject"]] += 1
        outcomes[actual["outcome"]] += 1
        expected = case["expected"]
        if any(actual.get(key) != value for key, value in expected.items()):
            mismatches.append({"id": case["id"], "expected": expected, "actual": actual})
    return {"cases": len(cases), "by_subject": dict(sorted(subjects.items())), "by_outcome": dict(sorted(outcomes.items())),
            "mismatches": mismatches}


VIEW_FIXTURE = ROOT / "apps/api/tests/fixtures/education/reasoning_v2.json"


def reasoning_views() -> str:
    """Gerçek v2 projeksiyonundan üretilen 2.2.0 görünümleri (ön yüz testleri için). Elle düzenlenmez."""
    from apps.api.app.features.education.math_adapter import validated_math_lesson
    from apps.api.app.features.education.presentation import LessonView, plan_panels
    from apps.api.app.features.integrity.engine import EvaluationState, evaluate
    from apps.api.app.features.lessons.schemas import (
        Expression,
        LessonContent,
        LessonPlan,
        Step,
    )
    from apps.api.app.features.mathai.service import MathAIService
    from apps.api.app.features.vision.schemas import VisionAnalysis, VisualElements

    def view(lesson_id, question, expressions, choices, final, finals, steps):
        raw = VisionAnalysis(request_id=f"source_{lesson_id}", image_status="valid_math_question", is_valid_question=True,
                             rejection_reason=None, subject="Matematik", exam_context=None, topic="Cebir", subtopic=None,
                             question_type="open", language="tr", difficulty="easy", question_text=question,
                             mathematical_expressions=expressions, answer_choices=choices,
                             visual_elements=VisualElements(has_diagram=False, has_graph=False, has_table=False,
                                                            has_geometry_figure=False, description=None),
                             ocr_uncertainties=[], confidence=0.9, provider="fixture", model="fixture", processing_time_ms=1)
        analysis = raw.model_copy(update={"integrity": evaluate(raw, EvaluationState())})
        content = LessonContent(
            question_understanding="Soruda istenen hedefi belirle.", strategy="Önce modeli çöz, sonra hedefi hesapla.",
            strategy_id="strategy_target", final_answer=final, takeaway="Ara değer ile istenen cevap farklı olabilir.",
            final_answer_expressions=[Expression(type="equation", latex=x) for x in finals],
            steps=[Step(id=f"step_{i}", type=kind, title=title, explanation=text,
                        expressions=[Expression(type=etype, latex=latex) for etype, latex in items])
                   for i, (kind, title, text, items) in enumerate(steps, start=1)])
        plan = LessonPlan(lesson_plan_id=lesson_id, source_analysis=analysis, learning_objectives=["istenen hedefi bulmak"],
                          concept_id="concept_target", content=content, provider="fixture", model="fixture", lesson_generation_ms=1)
        result = MathAIService().verify(plan).model_copy(update={"processing_time_ms": 0})
        lesson = validated_math_lesson(plan, result)
        return LessonView(lesson=lesson, panels=plan_panels(lesson), created_at="2026-01-01T00:00:00Z").model_dump(mode="json", by_alias=True)

    views = [
        view("hedef_dogrulandi", "x = 3 olduğuna göre x + 2 kaçtır?", ["x = 3", "x + 2"], [], "5", ["x + 2 = 5"],
             [("transformation", "Değeri yerine koy", "x yerine 3 yazılır.", [("equation", "x + 2 = 5")]),
              ("explanation", "Kontrol", "Sonucun istenen hedef olduğunu kontrol et.", [])]),
        view("hedef_desteklenmiyor", r"\int_0^1 x\,dx integralinin değeri kaçtır?", [r"\int_0^1 x\,dx"], [], "1/2", ["1/2"],
             [("transformation", "Alanı yaz", "Alan bir üçgendir.", [("expression", r"\frac{1}{2}")])]),
    ]
    return json.dumps(views, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write-fixture", action="store_true")
    args = parser.parse_args()
    if args.write_fixture:
        VIEW_FIXTURE.write_text(reasoning_views(), encoding="utf-8", newline="\n")
    elif args.check and (not VIEW_FIXTURE.exists() or VIEW_FIXTURE.read_text(encoding="utf-8") != reasoning_views()):
        raise SystemExit("Güncel olmayan fikstür: python -m scripts.science_matrix --write-fixture")
    summary = run()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.check and summary["mismatches"]:
        raise SystemExit("Bilimsel denetim matrisi beklenen sonuçlarla uyuşmuyor.")
    print("Sentetik bilimsel denetim vakaları sağlandı; sağlayıcı çağrısı yapılmadı.")


if __name__ == "__main__":
    main()
