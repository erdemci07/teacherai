"""TeacherAI 24 özgün soru paketi: çevrimdışı mimari regresyonu (sağlayıcı çağrısı yok).

Her soru için:
1. ``reading`` (doğru bir görsel okumanın benzetimi) gerçek bütünlük motorundan geçer; olağan soruda ek
   okuma veya öğrenci onayı gerekmemelidir. FKB soruları üretime yönlendirilmez (``unsupported_subject``).
2. Matematik: gerçek MathAI hedef/seçenek yolu, sahte sağlayıcı önerisiyle çalışır (``proposal`` cevap
   anahtarından türetilmez; bazıları bilinçli olarak yanlıştır).
3. FKB: yalnızca yerel belirlenimci denetimler; denetleyici yoksa cevap seçilmez (``abstain``).
4. ``evaluation`` yalnızca en sonda okunur ve hiçbir sağlayıcı bağlamına girmez.

    python -m scripts.question_pack           # özet
    python -m scripts.question_pack --check   # yanlış cevap veya beklenti uyuşmazlığında çıkış kodu 1
"""

import argparse
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

from apps.api.app.features.education.science import ExperimentalModel, Premise
from apps.api.app.features.integrity.engine import EvaluationState, evaluate
from apps.api.app.features.integrity.language import parse_choices
from apps.api.app.features.lessons.context import build_lesson_generation_context
from apps.api.app.features.lessons.schemas import (
    Expression,
    LessonContent,
    LessonPlan,
    Step,
)
from apps.api.app.features.mathai.service import MathAIService
from apps.api.app.features.reasoning import evidence, units
from apps.api.app.features.vision.schemas import VisionAnalysis
from scripts.answer_key import load_key
from scripts.science_matrix import run_case

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "apps/api/tests/fixtures/question_pack/teacherai_24.json"
BASE = {"image_status": "valid_math_question", "is_valid_question": True, "rejection_reason": None, "exam_context": None,
        "topic": "Paket", "subtopic": None, "question_type": "multiple_choice", "language": "tr", "difficulty": "medium",
        "mathematical_expressions": [], "ocr_uncertainties": [], "confidence": 0.9}


def analysis(reading: dict, recheck_limit: int = 1, overrides: dict | None = None) -> VisionAnalysis:
    data = {**BASE, **reading, **(overrides or {})}
    raw = VisionAnalysis(**data, request_id="pack", provider="fixture", model="fixture", processing_time_ms=1)
    return raw.model_copy(update={"integrity": evaluate(raw, EvaluationState(recheck_limit=recheck_limit))})


def _choice_values(question: dict) -> dict[str, Fraction]:
    values = {}
    for choice in parse_choices(question["reading"]["answer_choices"]).choices:
        try:
            values[choice.label] = units.parse_number(choice.content)[0]
        except (units.NumberError, TypeError):
            continue
    return values


def _match_value(question: dict, value: str | None, unit: str | None) -> str | None:
    if value is None:
        return None
    number = Fraction(value)
    if unit:  # SI değeri sorunun istediği birime çevrilir
        number = number / units.parse_unit(unit).scale
    matches = [label for label, choice in _choice_values(question).items() if choice == number]
    return matches[0] if len(matches) == 1 else None


def select_fkb(question: dict, results: dict) -> str | None:
    select = question.get("select")
    if not select:
        return None
    strategy = select["strategy"]
    if strategy == "value":
        result = results[select["check"]]
        # Formülün iddiasız hesabı "partially_checked" döner: değer hesaplandı, yasa seçimi denetlenmedi.
        computed = result["outcome"] == "passed" or result.get("reason") == "computed_without_claim"
        return _match_value(question, result.get("value"), select.get("unit")) if computed else None
    if strategy == "claim":
        return select["label"] if results[select["check"]]["outcome"] == "passed" else None
    if strategy == "text":
        result = results[select["check"]]
        if result["outcome"] != "passed":
            return None
        matches = [c.label for c in parse_choices(question["reading"]["answer_choices"]).choices if c.content == result["value"]]
        return matches[0] if len(matches) == 1 else None
    if strategy == "single":
        passed = [label for label, result in results.items() if len(label) == 1 and result["outcome"] == "passed"]
        return passed[0] if len(passed) == 1 else None
    choices = parse_choices(question["reading"]["answer_choices"]).choices
    polarity = evidence.premise_polarity(question["reading"]["question_text"])
    if strategy == "premises":
        experiment = ExperimentalModel.model_validate(select["experiment"])
        statuses = {label: evidence.premise_status(evidence.check_claim(experiment, claim)) for label, claim in select["premises"].items()}
    else:  # premise_checks: öncül etiketi → denetim sonucu
        statuses = {}
        for label, result in results.items():
            outcome = evidence.CheckOutcome(result["outcome"], result["reason"])
            statuses[label] = evidence.premise_status(outcome)
    premises = [Premise(label=label, text=f"Öncül {label}", status=status, evaluator="none" if status == "unevaluated" else "evidence_check")
                for label, status in statuses.items()]
    status, labels = evidence.match_combination(evidence.select_premises(premises, polarity), choices)
    return labels[0] if status == "matched" else None


def run_math(question: dict, source: VisionAnalysis) -> dict:
    proposal = question["proposal"]
    content = LessonContent(question_understanding="Soruyu anla.", strategy="Çöz.", strategy_id="strategy_pack",
                            steps=[Step(id="step_1", type="result", title="Sonuç", explanation="Sonuç yazılır.", expressions=[])],
                            final_answer=proposal["final"], takeaway="Hedefe dikkat et.",
                            final_answer_expressions=[Expression(type="equation", latex=x) for x in proposal["finals"]])
    plan = LessonPlan(lesson_plan_id=f"pack_{question['id']}", source_analysis=source, learning_objectives=["paket"],
                      concept_id="concept_pack", content=content, provider="fixture", model="fixture", lesson_generation_ms=1)
    service = MathAIService()
    reconciled = service.reconcile_answer_choice(plan)
    result = service.verify(reconciled)
    target = result.target
    selected = target.selected_option if target is not None and target.option_origin == "independent" else None
    context = build_lesson_generation_context(source).serialized
    return {"selected": selected, "status": result.status, "target": target.target.kind if target else None,
            "target_outcome": target.outcome if target else None, "provider_label": result.choice_match.provider_label if result.choice_match else None,
            "context_has_evaluation": any(word in context for word in ('"evaluation"', '"answer_key"', '"cevap_anahtari"'))}


def run(key_path=None) -> dict:
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    rows, mismatches = [], []
    # TA-005: bağımsız öğretmen anahtarı geldiyse başarı ölçütü odur; türetilmiş cevap ayrı sütunda kalır.
    key = load_key(key_path) if key_path is not None else load_key()
    teacher = {entry.id: entry.expected_choice for entry in key.entries} if key else {}
    disagreements = []
    for question in pack["questions"]:
        source = analysis(question["reading"])
        decision = source.integrity.decision
        row = {"id": question["id"], "subject": question["subject"], "decision": decision,
               "extra_vision_calls": int(decision == "targeted_recheck"), "clarification": decision == "clarification_required"}
        results = {}
        for case in question.get("checks", []):
            results[case["id"]] = run_case({"kind": case["kind"], "input": case["input"]})
            if "expect" in case and results[case["id"]]["outcome"] != case["expect"]:
                mismatches.append(f"{question['id']}:{case['id']} beklenen {case['expect']}, gelen {results[case['id']]['outcome']}")
        if question["subject"] == "mathematics":
            math = run_math(question, source)
            row.update(math)
            selected = math["selected"] or select_fkb(question, results)
        else:
            selected = select_fkb(question, results)
        row["selected"] = selected
        for variant in question.get("variants", []):
            varied = analysis(question["reading"], overrides=variant["overrides"])
            target = MathAIService().target(_plan_stub(varied)) if "expect_target" in variant else None
            ok = varied.integrity.decision.startswith(variant["expect_decision"]) and (
                target is None or target.kind == variant["expect_target"])
            if not ok:
                mismatches.append(f"{variant['id']}: karar {varied.integrity.decision}, hedef {target.kind if target else '-'}")
        # Değerlendirme (cevap anahtarı) yalnızca burada okunur.
        evaluation = question["evaluation"]
        row["expected"] = evaluation["expect"]
        row["derived_answer"], row["teacher_answer"] = evaluation["answer"], teacher.get(question["id"])
        if row["teacher_answer"] and evaluation["answer"] and row["teacher_answer"] != evaluation["answer"]:
            disagreements.append(f"{question['id']}: türetilmiş {evaluation['answer']}, öğretmen {row['teacher_answer']}")
        reference = row["teacher_answer"] or (None if key else evaluation["answer"])
        row["correct"] = selected == reference if selected and reference else None
        if row["correct"] is False:
            mismatches.append(f"{question['id']}: yanlış cevap {selected}")
        if (selected is not None) != (evaluation["expect"] == "answer"):
            mismatches.append(f"{question['id']}: beklenti {evaluation['expect']}, seçim {selected}")
        if question["subject"] == "mathematics" and (row["decision"] not in {"ready", "ready_with_noncritical_uncertainty"}
                                                     or row.get("context_has_evaluation")):
            mismatches.append(f"{question['id']}: olağan matematik sorusu kesintiye uğradı veya bağlam değerlendirme içeriyor")
        if question["subject"] != "mathematics" and decision != "unsupported_subject":
            mismatches.append(f"{question['id']}: FKB sorusu üretime yönlendirilebilir görünüyor ({decision})")
        rows.append(row)
    by_subject = Counter(row["subject"] for row in rows)
    answered = Counter(row["subject"] for row in rows if row["selected"])
    return {
        "questions": len(rows), "answer_origin": pack["answer_origin"],
        "success_reference": "teacher" if key else "derived", "teacher_key": f"{len(teacher)} satır" if key else "bekleniyor",
        "derived_teacher_disagreements": disagreements,
        "deterministic_answers": dict(sorted(answered.items())), "by_subject": dict(sorted(by_subject.items())),
        "correct": sum(1 for row in rows if row["correct"]), "wrong": sum(1 for row in rows if row["correct"] is False),
        "abstained": [row["id"] for row in rows if not row["selected"]],
        "extra_vision_calls_on_clean_reading": sum(row["extra_vision_calls"] for row in rows),
        "clarification_on_clean_reading": sum(row["clarification"] for row in rows),
        "variants": sum(len(q.get("variants", [])) for q in pack["questions"]),
        "mismatches": mismatches, "rows": rows,
    }


def _plan_stub(source):
    content = LessonContent(question_understanding="-", strategy="-", strategy_id="strategy_pack", final_answer="-", takeaway="-",
                            steps=[Step(id="step_1", type="result", title="-", explanation="-", expressions=[])],
                            final_answer_expressions=[Expression(type="expression", latex="0")])
    return LessonPlan(lesson_plan_id="pack_stub", source_analysis=source, learning_objectives=["-"], concept_id="concept_pack",
                      content=content, provider="fixture", model="fixture", lesson_generation_ms=1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--rows", action="store_true")
    args = parser.parse_args()
    summary = run()
    if not args.rows:
        summary.pop("rows")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.check and summary["mismatches"]:
        raise SystemExit("Soru paketi beklentileri sağlanmadı.")
    print("Soru paketi çevrimdışı değerlendirildi; sağlayıcı çağrısı yapılmadı. Bu bir model başarı ölçümü değildir.")


if __name__ == "__main__":
    main()
