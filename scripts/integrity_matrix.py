"""TA-003 sentetik davranış matrisi: güvenlik ile gereksiz kesintiyi birlikte ölçer.

Senaryolar gerçek ``OpenAIVisionProvider``, gerçek gateway (çağrı bütçesi ve muhasebe) ve gerçek
``VisionService`` orkestrasyonundan geçer; yalnızca OpenAI istemcisi ağsız bir sahteyle değiştirilir.
Seçenek vakaları MathAI uzlaştırma ve doğrulamasını süreç içinde çalıştırır.

Bu sonuçlar sabit fikstürlerin kabul ölçütleridir. Gerçek model tanıma doğruluğu, gerçek açıklama
oranı veya üretim maliyeti hakkında bilgi vermez.

Kullanım: python -m scripts.integrity_matrix [--check]
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import io
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "apps/api/tests/fixtures/integrity/scenarios.json"
SOLVABLE = {"ready", "ready_with_noncritical_uncertainty"}
MUST_PROCEED = {"clean", "harmless", "local", "unsupported_parse"}
MUST_STOP = {"persistent", "fatal"}


def load():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _merge(base: dict, override: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _image() -> bytes:
    image = Image.new("RGB", (640, 400), "white")
    draw = ImageDraw.Draw(image)
    for row in range(40, 360, 40):
        draw.text((30, row), "3x + 7 = 19     A) 2   B) 3   C) 4   D) 5", fill="black")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _body(model) -> dict:
    return {
        "id": "resp_matrix", "model": "matrix", "status": "completed", "incomplete_details": None,
        "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": model.model_dump_json()}]}],
        "usage": {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20,
                  "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}},
    }


class _Raw:
    def __init__(self, body):
        self.http_response = SimpleNamespace(json=lambda: body)
        self.request_id = "req_matrix"


async def run_scenario(base: dict, scenario: dict) -> dict:
    from starlette.datastructures import Headers, UploadFile

    from apps.api.app.core.gateway import begin_accounting, end_accounting
    from apps.api.app.core.settings import Settings
    from apps.api.app.core.usage import UsageTracker
    from apps.api.app.features.lessons.context import strategy_decision
    from apps.api.app.features.vision.openai_provider import OpenAIVisionProvider
    from apps.api.app.features.vision.schemas import (
        RecheckResponse,
        VisionProviderAnalysis,
    )
    from apps.api.app.features.vision.service import VisionService
    from apps.api.app.features.vision.storage import LocalTemporaryImageStorage

    wire = VisionProviderAnalysis.model_validate(_merge(base, scenario.get("vision", {})))
    responses = [_body(wire)]
    if scenario.get("recheck"):
        responses.append(_body(RecheckResponse.model_validate(scenario["recheck"])))
    calls: list[dict] = []

    async def parse(**kwargs):
        calls.append(kwargs)
        if len(calls) > len(responses):
            raise AssertionError("senaryo beklenenden fazla sağlayıcı çağrısı yaptı")
        return _Raw(responses[len(calls) - 1])

    async def close():
        return None

    def client_factory(**_):
        return SimpleNamespace(responses=SimpleNamespace(with_raw_response=SimpleNamespace(parse=parse)), close=close)

    limit = scenario.get("recheck_limit", 1)
    settings = Settings(environment="test", vision_max_rechecks=limit)
    tracker = UsageTracker(settings)
    with tempfile.TemporaryDirectory() as directory:
        service = VisionService(OpenAIVisionProvider("matrix-key", "gpt-4.1-mini", 5, client_factory=client_factory),
                                LocalTemporaryImageStorage(Path(directory)), 10 * 1024 * 1024, False, recheck_limit=limit)
        token = begin_accounting("req_matrix", settings, tracker, "matrix-user",
                                 max_calls=scenario.get("max_calls", settings.provider_call_budget("analyze")))
        try:
            upload = UploadFile(file=io.BytesIO(_image()), filename="q.png", headers=Headers({"content-type": "image/png"}))
            analysis = await service.analyze(upload, "req_matrix")
        finally:
            end_accounting(token)
    report = analysis.integrity
    decision = strategy_decision(analysis)
    recheck_images = []
    if len(calls) > 1:
        recheck_images = [part for part in calls[1]["input"][0]["content"] if part["type"] == "input_image"]
    return {
        "id": scenario["id"], "group": scenario["group"], "kind": scenario["kind"],
        "decision": report.decision, "recovery": report.recovery, "calls": len(calls),
        "solvable": report.decision in SOLVABLE,
        "intent": report.intent.kind, "strategy": report.intent.answer_strategy,
        # TA-005: ders bağlamındaki seçenek stratejisi ve belirlenimci nedeni.
        "lesson_strategy": f"{decision.strategy}|{decision.reason}",
        "labels": [choice.label for choice in report.choices],
        "canonical": [item.canonical for item in report.expressions],
        "alternatives": max((len(item.alternatives) for item in report.pending()), default=0),
        "evidence": sorted({code for item in report.uncertainties for code in item.evidence}),
        "content_unchanged": analysis.mathematical_expressions == wire.mathematical_expressions
        and analysis.answer_choices == wire.answer_choices and analysis.question_text == wire.question_text,
        "recheck_images": len(recheck_images),
        "recheck_crop": bool(recheck_images) and recheck_images[0]["image_url"].startswith("data:image/png")
        and len(recheck_images[0]["image_url"]) != 0 and calls[1]["input"][0]["content"][1]["image_url"] != calls[0]["input"][0]["content"][1]["image_url"],
        "expect": scenario["expect"],
    }


def run_choice_case(case: dict) -> dict:
    from apps.api.app.features.education.math_adapter import with_integrity
    from apps.api.app.features.lessons.schemas import (
        Expression,
        LessonContent,
        LessonPlan,
        Step,
    )
    from apps.api.app.features.mathai.service import MathAIService
    from apps.api.app.features.vision.schemas import VisionAnalysis, VisualElements

    analysis = VisionAnalysis(
        request_id="matrix", image_status="valid_math_question", is_valid_question=True, rejection_reason=None,
        subject="Matematik", exam_context=None, topic="Denklem", subtopic=None, question_type="multiple_choice",
        language="tr", difficulty="easy", question_text=case.get("question", f"{case['equation']} ise x kaçtır?"),
        mathematical_expressions=[case["equation"]], answer_choices=case["choices"],
        visual_elements=VisualElements(has_diagram=False, has_graph=False, has_table=False, has_geometry_figure=False, description=None),
        ocr_uncertainties=[], confidence=0.9, provider="matrix", model="matrix", processing_time_ms=1,
    )
    analysis = with_integrity(analysis)
    content = LessonContent(
        question_understanding="Soruyu anla", strategy="Çöz", strategy_id="strategy_solve",
        steps=[Step(id="step_1", type="result", title="Sonuç", explanation="Sonucu bul.", expressions=[Expression(type="equation", latex=case["final_expr"])])],
        final_answer=case["final"], final_answer_expressions=[Expression(type="equation", latex=case["final_expr"])], takeaway="Özet",
    )
    plan = LessonPlan(lesson_plan_id="lesson_matrix", source_analysis=analysis, learning_objectives=["hedef"], concept_id="concept_matrix",
                      content=content, provider="matrix", model="matrix", lesson_generation_ms=1)
    service = MathAIService()
    reconciled = service.reconcile_answer_choice(plan)
    verification = service.verify(reconciled)
    match = verification.choice_match
    return {
        "id": case["id"], "final": reconciled.content.final_answer, "status": match.status if match else None,
        "labels": match.matched_labels if match else [], "verification": verification.status, "expect": case["expect"],
    }


def evaluate(data: dict | None = None) -> dict:
    data = data or load()
    rows = [asyncio.run(run_scenario(data["base"], item)) for item in data["scenarios"]]
    choices = [run_choice_case(item) for item in data["choice_cases"]]
    kinds = Counter(row["kind"] for row in rows)
    metrics = {
        "scenarios": len(rows),
        "clean_accepted": f"{sum(r['solvable'] for r in rows if r['kind'] == 'clean')}/{kinds['clean']}",
        "harmless_accepted": f"{sum(r['solvable'] for r in rows if r['kind'] == 'harmless')}/{kinds['harmless']}",
        "local_resolutions": f"{sum(r['solvable'] and r['calls'] == 1 for r in rows if r['kind'] == 'local')}/{kinds['local']}",
        "unsupported_parse_accepted": f"{sum(r['solvable'] for r in rows if r['kind'] == 'unsupported_parse')}/{kinds['unsupported_parse']}",
        "additional_vision_calls": sum(r["calls"] - 1 for r in rows),
        "material_detected": sum(not r["solvable"] or r["calls"] > 1 for r in rows if r["kind"] in {"recoverable", "persistent"}),
        "material_total": kinds["recoverable"] + kinds["persistent"],
        "recheck_resolved_without_student": sum(r["solvable"] for r in rows if r["kind"] == "recoverable"),
        "clarification_required": sum(r["decision"] == "clarification_required" for r in rows),
        "false_blocking": sum(not r["solvable"] for r in rows if r["kind"] in MUST_PROCEED),
        "unresolved_critical_allowed": sum(r["solvable"] for r in rows if r["kind"] in MUST_STOP),
        "wrong_automatic_source_correction": sum(not r["content_unchanged"] for r in rows),
        "max_calls_per_scenario": max(r["calls"] for r in rows),
        "decision_mismatches": [r["id"] for r in rows if r["decision"] != r["expect"]["decision"] or r["calls"] != r["expect"]["calls"]],
        "choice_cases": len(choices),
        "wrong_choice_reconciliation": [c["id"] for c in choices if c["final"] != c["expect"]["final"] or c["status"] != c["expect"]["status"]
                                        or c["labels"] != c["expect"]["labels"]],
    }
    return {"metrics": metrics, "rows": rows, "choices": choices}


def failures(result: dict) -> list[str]:
    metrics, problems = result["metrics"], []
    for key in ("false_blocking", "unresolved_critical_allowed", "wrong_automatic_source_correction"):
        if metrics[key]:
            problems.append(f"{key}={metrics[key]}")
    if metrics["decision_mismatches"]:
        problems.append(f"decision_mismatches={metrics['decision_mismatches']}")
    if metrics["wrong_choice_reconciliation"]:
        problems.append(f"wrong_choice_reconciliation={metrics['wrong_choice_reconciliation']}")
    if metrics["max_calls_per_scenario"] > 2:
        problems.append("unbounded_calls")
    for row in result["rows"]:
        expect = row["expect"]
        for key in ("intent", "strategy", "lesson_strategy", "recovery", "labels", "canonical"):
            if key in expect and row[key] != expect[key]:
                problems.append(f"{row['id']}:{key}={row[key]!r}")
        if "alternatives" in expect and row["alternatives"] != expect["alternatives"]:
            problems.append(f"{row['id']}:alternatives={row['alternatives']}")
        if "evidence" in expect and expect["evidence"] not in row["evidence"]:
            problems.append(f"{row['id']}:evidence={row['evidence']}")
        if expect.get("recheck_crop") and not row["recheck_crop"]:
            problems.append(f"{row['id']}:recheck_crop")
    for case in result["choices"]:
        if "verification" in case["expect"] and case["verification"] != case["expect"]["verification"]:
            problems.append(f"{case['id']}:verification={case['verification']}")
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="kabul ölçütü sağlanmazsa sıfırdan farklı çıkış")
    args = parser.parse_args(argv)
    result = evaluate()
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))
    problems = failures(result)
    if problems:
        print("Kabul ölçütü sağlanmadı: " + "; ".join(problems), file=sys.stderr)
        return 1 if args.check else 0
    print("Sentetik fikstür kabul ölçütleri sağlandı; sağlayıcı çağrısı yapılmadı (sahte istemci).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
