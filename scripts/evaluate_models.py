"""Karşılaştırmalı model değerlendirmesi (TA-001B, D paketi).

    python -m scripts.evaluate_models                 # doğrulama (CI), sağlayıcı çağrısı yok
    python -m scripts.evaluate_models validate        # aynı doğrulama
    python -m scripts.evaluate_models run --provider fake
    python -m scripts.evaluate_models pack --dry-run --model gpt-6-luna   # TA-005 paket, çağrı yok
    python -m scripts.evaluate_models run --allow-paid --max-usd 2 --max-calls 60 \\
        --candidate gpt-6-luna --reasoning-effort none low medium

Ücretli koşu yalnız --allow-paid, --max-usd ve --max-calls birlikte verildiğinde ve her
model için doğrulanmış fiyat yapılandırması varsa başlar. Ön tahmin; her iki modeli,
her işlemi, her reasoning kombinasyonunu, görsel ve metin girişi tahminini, işlem
çıktı sınırını ve izinli tekrar çağrısını kapsar. Giriş ve görsel token sayısı tahmindir;
bu nedenle tahmin kesin bir harcama tavanı değildir ve öyle raporlanmaz.

Sahte sağlayıcı (--provider fake) hattı sınar; sonuçları model kalitesi değildir.
Sentetik smoke seti gerçek kalite değerlendirmesi değildir; 100 soruluk özgün set henüz yoktur.
"""

import argparse
import asyncio
import csv
import json
import logging
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from time import perf_counter

from apps.api.app.core.ai_outcomes import AIOutcomeError
from apps.api.app.core.gateway import begin_offline_accounting, end_accounting
from apps.api.app.core.operations import Operation, validate_effort
from apps.api.app.core.settings import get_settings
from apps.api.app.features.interactions.exceptions import InteractionError
from apps.api.app.features.interactions.openai_provider import OpenAIInteractionProvider
from apps.api.app.features.lessons.schemas import (
    Expression,
    LessonContent,
    LessonPlan,
    Step,
)
from apps.api.app.features.vision.exceptions import VisionError
from apps.api.app.features.vision.openai_provider import OpenAIVisionProvider
from apps.api.app.features.vision.schemas import VisionAnalysis, VisualElements
from scripts.eval_dataset import EvalItem, load, root_set, value_set

ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "evals" / "datasets"
FIXTURES = Path(__file__).with_name("eval-fixtures.json")
OPERATIONS = ("vision", "interaction")
EFFORTS = ("none", "low", "medium")
# İzinli tekrar: etkileşim sağlayıcısı bağlam aşımında bir kez daha küçültülmüş bağlamla dener.
CALLS_PER_REQUEST = {"vision": 1, "interaction": 2}
VISION_PROMPT = ROOT / "apps/api/app/features/vision/prompts/question_analysis.txt"
INTERACTION_PROMPT = ROOT / "apps/api/app/features/interactions/prompts/interaction.txt"
FAKE_WARNING = "> **Sahte sağlayıcı — model kalitesi değildir.** Bu özet yalnız değerlendirme hattının çalıştığını gösterir.\n"
SCOPE_NOTE = (
    "> Sentetik smoke seti gerçek model kalite değerlendirmesi değildir. 100 soruluk özgün öğretmen "
    "veri seti henüz bulunmuyor; tam set ve insan değerlendirmesi olmadan model geçişi onaylanmaz.\n"
)


# Doğrulama -------------------------------------------------------------------


def reference(case_id, question, answer_expr, topic):
    """Interaction için sunucu tarafı ders planı referansı (sağlayıcıya gerçek ders verilmez)."""
    source = VisionAnalysis(
        request_id=case_id, image_status="valid_math_question", is_valid_question=True, rejection_reason=None,
        subject="mathematics", exam_context=None, topic=topic, subtopic=None, question_type="open",
        language="tr", difficulty="easy", question_text=question, mathematical_expressions=[question],
        answer_choices=[], visual_elements=VisualElements(has_diagram=False, has_graph=False, has_table=False,
                                                          has_geometry_figure=False, description=None),
        ocr_uncertainties=[], confidence=1, provider="fixture", model="fixture", processing_time_ms=0,
    )
    expr = Expression(type="equation", latex=answer_expr)
    content = LessonContent(
        question_understanding="x değerlerini bul.", strategy="Denklemi düzenle.", strategy_id="strategy_solve",
        steps=[Step(id="step_1", type="result", title="Sonuç", explanation="İki tarafı karşılaştır.", expressions=[expr])],
        final_answer=answer_expr, final_answer_expressions=[expr], takeaway="Sonucu yerine koy.",
    )
    return LessonPlan(lesson_plan_id=case_id, source_analysis=source, learning_objectives=["Denklem çözme"],
                      concept_id="concept_equation", content=content, provider="fixture", model="fixture",
                      lesson_generation_ms=0)


def item_plan(item: EvalItem):
    answer = " veya ".join(f"{item.variable} = {value}" for value in item.expected_solutions)
    return reference(item.id, item.expected_expressions[0], answer, item.topic)


def validate(datasets):
    cases = json.loads(FIXTURES.read_text(encoding="utf-8"))
    for case in cases:
        reference(case["id"], case["question"], "x = " + case["answer"], case["topic"])
    total, failed = 0, False
    for path in datasets:
        items, errors = load(path)
        total += len(items)
        label = "boş — özgün set henüz hazırlanmadı" if not items and not errors else f"{len(items)} öğe"
        print(f"{path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}: {label}")
        for error in errors:
            print(f"  HATA {error}")
        failed |= bool(errors)
    print(f"{len(cases)} fikstür ve {total} veri seti öğesi doğrulandı; sağlayıcı çağrısı yapılmadı.")
    return 1 if failed else 0


# Koşu planı ve bütçe --------------------------------------------------------


@dataclass
class Call:
    item: EvalItem
    operation: str
    model: str
    effort: str | None
    upper_usd: float | None = None
    calls: int = 1


@dataclass
class Budget:
    max_usd: float | None
    max_calls: int | None
    spent_usd: float = 0.0
    provider_calls: int = 0
    stopped: str | None = None
    unknown_cost: int = 0

    def allows(self, call):
        if self.max_calls is not None and self.provider_calls + call.calls > self.max_calls:
            self.stopped = "çağrı sınırı"
        elif self.max_usd is not None and (call.upper_usd is None or self.spent_usd + call.upper_usd > self.max_usd):
            self.stopped = "USD sınırı"
        return self.stopped is None


def plan_calls(items, operations, incumbents, candidate, efforts):
    calls = []
    for item in items:
        for operation in operations:
            if operation == "interaction" and not item.is_valid_math_question:
                continue
            combos = [(incumbents[operation], None)] + [(candidate, effort) for effort in (efforts or [None])]
            for model, effort in dict.fromkeys(combos):
                calls.append(Call(item, operation, model, effort, calls=CALLS_PER_REQUEST[operation]))
    return calls


def input_tokens_estimate(call, dataset_dir, image_tokens):
    """Kaba üst tahmin: UTF-8 bayt / 2 (Türkçe için temkinli) + görsel token tahmini."""
    if call.operation == "vision":
        return math.ceil(len(VISION_PROMPT.read_bytes()) / 2) + image_tokens
    payload = INTERACTION_PROMPT.read_bytes() + item_plan(call.item).model_dump_json().encode()
    return math.ceil(len(payload) / 2)


def price_calls(calls, settings, dataset_dir, image_tokens):
    """Her çağrıya üst maliyet yazar; fiyatı olmayan modelde None bırakır."""
    for call in calls:
        rates = settings.model_prices.get(call.model) if settings.pricing_version else None
        if not rates:
            call.upper_usd = None
            continue
        limit = settings.max_output_tokens_by_operation[Operation(call.operation)]
        per_call = (input_tokens_estimate(call, dataset_dir, image_tokens) * rates[0] + limit * rates[2]) / 1_000_000
        call.upper_usd = per_call * call.calls
    return calls


# Sahte sağlayıcı ------------------------------------------------------------


class _Raw:
    def __init__(self, body):
        self.http_response = type("Http", (), {"json": staticmethod(lambda: body)})()
        self.request_id = "fake"


class FakeEvalClient:
    """Veri setinin beklentisini döndüren deterministik istemci. Ağ çağrısı yapmaz."""

    def __init__(self, call, input_tokens=1200):
        self.call, self.input_tokens = call, input_tokens

        async def parse(**kwargs):
            await asyncio.sleep(0)
            return _Raw(self._body(kwargs))

        self.responses = type("Responses", (), {"with_raw_response": type("Raw", (), {"parse": staticmethod(parse)})()})()

    def _body(self, kwargs):
        item = self.call.item
        if self.call.operation == "vision":
            valid = item.is_valid_math_question
            # Geçersiz görselde şema, uydurulmuş soru içeriğini reddeder; alanlar boş kalır.
            output = {
                "image_status": "valid_math_question" if valid else "not_math_question",
                "is_valid_question": valid, "rejection_reason": None if valid else "Matematik sorusu yok.",
                "subject": "mathematics" if valid else "", "exam_context": None, "topic": item.topic if valid else "",
                "subtopic": None, "question_type": "open" if valid else "", "language": "tr",
                "difficulty": "easy" if valid else "unknown", "question_text": item.question_text if valid else "",
                "mathematical_expressions": item.expected_expressions, "answer_choices": [],
                "visual_elements": {"has_diagram": False, "has_graph": False, "has_table": False,
                                    "has_geometry_figure": False, "description": None},
                "ocr_uncertainties": [], "confidence": 0.9,
            }
        else:
            output = {"title": "İpucu", "text": "Önce bilinmeyeni yalnız bırakmak için hangi işlemi yaparsın?",
                      "steps": [], "expressions": []}
        reasoning = 64 if kwargs.get("reasoning") else 0
        return {"id": "fake", "model": kwargs["model"], "status": "completed", "incomplete_details": None,
                "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(output, ensure_ascii=False)}]}],
                "usage": {"input_tokens": self.input_tokens, "output_tokens": 300 + reasoning, "total_tokens": self.input_tokens + 300 + reasoning,
                          "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": reasoning}}}

    async def close(self):
        pass


# Çalıştırma ve metrikler -----------------------------------------------------


def fake_factory(call, input_tokens):
    def build(**kwargs):
        return FakeEvalClient(call, input_tokens)

    return build


def known_sum(values):
    """TA-005C: bilinmeyen (None) değer varsa toplam da bilinmez; sıfır sayılmaz."""
    values = list(values)
    return None if any(value is None for value in values) else sum(values)


class Capture(logging.Handler):
    """Gateway'in ai_usage satırlarını toplar: sonuç, tokenlar ve tahmini USD üretim yolundan gelir."""

    def __init__(self):
        super().__init__(logging.INFO)
        self.events = []

    def emit(self, record):
        self.events.append(json.loads(record.getMessage()))


async def execute(call, settings, client_factory, dataset_dir, api_key):
    efforts = {Operation(call.operation): call.effort} if call.effort else {}
    run_settings = settings.model_copy(update={"reasoning_effort_by_operation": efforts})
    capture, usage_logger = Capture(), logging.getLogger("teacherai.ai_usage")
    level = usage_logger.level
    usage_logger.addHandler(capture)
    usage_logger.setLevel(logging.INFO)
    # TA-005C: açık offline kapsam; kullanıcı kotasına yazmaz, kendi çağrı tavanı vardır.
    token = begin_offline_accounting(f"eval-{call.item.id}", run_settings, max_calls=CALLS_PER_REQUEST[call.operation])
    row = {"item_id": call.item.id, "operation": call.operation, "model": call.model, "reasoning_effort": call.effort or "",
           "schema_valid": False, "error": None, "output": ""}
    # Yanıt alınamayan öğe metriklerde başarısız sayılır; oranlar yalnız başarılılardan hesaplanmaz.
    if call.operation == "vision":
        row["valid_question_correct"] = False
        if call.item.is_valid_math_question:
            row.update(expression_equivalent=False, roots_match=False)
    started = perf_counter()
    try:
        if call.operation == "vision":
            image = (dataset_dir / call.item.image).read_bytes()
            provider = OpenAIVisionProvider(api_key, call.model, settings.vision_provider_timeout_seconds, client_factory=client_factory)
            analysis = (await provider.analyze_image(image, "image/png", f"eval-{call.item.id}")).analysis
            row.update(schema_valid=True, **vision_metrics(call.item, analysis))
        else:
            provider = OpenAIInteractionProvider(api_key, call.model, settings.interaction_provider_timeout_seconds, client_factory=client_factory)
            draft = await provider.adapt("hint", item_plan(call.item), 1)
            row.update(schema_valid=True, answer_leak=leaks(draft.text, call.item.forbidden_in_hint), output=draft.text)
    except (AIOutcomeError, VisionError, InteractionError) as exc:
        row["error"] = getattr(exc, "code", type(exc).__name__)
    finally:
        end_accounting(token)
        usage_logger.removeHandler(capture)
        usage_logger.setLevel(level)
    row["latency_ms"] = round((perf_counter() - started) * 1000)
    events = capture.events
    row["provider_calls"] = len(events)
    row["outcome"] = events[-1]["outcome"] if events else "local_error"
    for key in ("input_tokens", "output_tokens", "reasoning_tokens"):
        row[key] = known_sum(event.get(key) for event in events)
    costs = [event.get("estimated_usd") for event in events]
    row["estimated_usd"] = sum(costs) if events and all(cost is not None for cost in costs) else None
    return row


def vision_metrics(item, analysis):
    metrics = {"valid_question_correct": analysis.is_valid_question == item.is_valid_math_question,
               "output": " ; ".join(analysis.mathematical_expressions)}
    if item.is_valid_math_question:
        expressions = analysis.mathematical_expressions
        metrics["expression_equivalent"] = bool(expressions) and equivalent(expressions[0], item.expected_expressions[0])
        try:
            metrics["roots_match"] = bool(expressions) and root_set(expressions[0]) == value_set(item.expected_solutions)
        except ValueError:
            metrics["roots_match"] = False
    return metrics


def equivalent(left, right):
    """İki denklem, farkları sabit bir katsayıyla orantılıysa eşdeğerdir (SymPy)."""
    import sympy as sp

    from apps.api.app.features.mathai.parser import equation

    try:
        a, b = equation(left), equation(right)
    except ValueError:
        return False
    da, db = sp.simplify(a.lhs - a.rhs), sp.simplify(b.lhs - b.rhs)
    if da == 0 or db == 0:
        return da == db
    ratio = sp.simplify(da / db)
    return not ratio.free_symbols and ratio != 0


def leaks(text, forbidden):
    """İpucunda yasak değerin bağımsız bir sayı ya da 'x = değer' olarak geçmesi (deterministik)."""
    compact = re.sub(r"\s+", "", text.lower())
    for value in forbidden:
        token = re.sub(r"\s+", "", value.lower())
        if "=" in token and token in compact:
            return True
        # Komşu rakam veya ondalık (4.5, 14) eşleşmez; cümle sonu noktası eşleşir ("Cevap 4.").
        if "=" not in token and re.search(rf"(?<!\w)(?<!\d[.,]){re.escape(value)}(?!\w|[.,]\d)", text):
            return True
    return False


def percentile(values, q):
    ordered = sorted(values)
    if not ordered:
        return None
    return ordered[min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1)]


def summarize(rows):
    groups = {}
    for row in rows:
        groups.setdefault((row["operation"], row["model"], row["reasoning_effort"]), []).append(row)
    summary = []
    for (operation, model, effort), items in sorted(groups.items()):
        def rate(key, items=items):
            values = [r[key] for r in items if key in r]
            return round(sum(values) / len(values), 3) if values else None

        latencies = [r["latency_ms"] for r in items]
        costs = [r["estimated_usd"] for r in items]
        summary.append({
            "operation": operation, "model": model, "reasoning_effort": effort or "varsayılan", "n": len(items),
            "valid_question_accuracy": rate("valid_question_correct"), "expression_equivalence": rate("expression_equivalent"),
            "root_set_match": rate("roots_match"), "schema_valid_rate": rate("schema_valid"), "answer_leak_rate": rate("answer_leak"),
            "outcomes": dict(sorted(_count(r["outcome"] for r in items).items())),
            "latency_p50_ms": median(latencies), "latency_p95_ms": percentile(latencies, 0.95),
            "input_tokens": known_sum(r["input_tokens"] for r in items),
            "output_tokens": known_sum(r["output_tokens"] for r in items),
            "reasoning_tokens": known_sum(r["reasoning_tokens"] for r in items),
            "estimated_usd": round(sum(costs), 6) if all(c is not None for c in costs) else None,
        })
    return summary


def _count(values):
    result = {}
    for value in values:
        result[value] = result.get(value, 0) + 1
    return result


def write_outputs(out_dir, rows, summary, *, fake, budget, estimate):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "raw.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    with (out_dir / "rubric.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["item_id", "operation", "model", "reasoning_effort", "output", "pedagoji_1_5", "aciklik_1_5",
                         "cevabi_vermeme_1_5", "turkce_dogallik_1_5", "degerlendiren", "not"])
        for row in rows:
            if row["schema_valid"]:
                writer.writerow([row["item_id"], row["operation"], row["model"], row["reasoning_effort"], row["output"], "", "", "", "", "", ""])
    columns = ["operation", "model", "reasoning_effort", "n", "valid_question_accuracy", "expression_equivalence", "root_set_match",
               "schema_valid_rate", "answer_leak_rate", "outcomes", "latency_p50_ms", "latency_p95_ms", "input_tokens",
               "output_tokens", "reasoning_tokens", "estimated_usd"]
    lines = ["# Model karşılaştırma özeti", ""]
    if fake:
        lines.append(FAKE_WARNING)
    lines += [SCOPE_NOTE, f"Ön tahmin (üst, kesin değil): {estimate}", f"Sağlayıcı çağrısı: {budget.provider_calls}",
              f"Erken durma: {budget.stopped or 'yok'}", "", "| " + " | ".join(columns) + " |", "|" + " --- |" * len(columns)]
    for entry in summary:
        lines.append("| " + " | ".join("—" if entry[c] is None else str(entry[c]) for c in columns) + " |")
    lines += ["", "Türkçe pedagoji kalitesi otomatik puanlanmaz; `rubric.csv` 1–5 ölçeğiyle insan değerlendirmesi içindir."]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run(args, settings, client_factory, out_root):
    dataset = Path(args.dataset)
    items, errors = load(dataset)
    if errors:
        print("Veri seti geçersiz; koşu başlamadı.")
        return 1
    incumbents = {"vision": settings.openai_vision_model, "interaction": settings.openai_interaction_model}
    calls = plan_calls(items, args.operations, incumbents, args.candidate, args.reasoning_effort)
    for call in calls:
        if call.effort:
            # Desteklenmeyen kombinasyon sağlayıcıya gönderilmeden reddedilir.
            validate_effort(call.model, call.effort)
    price_calls(calls, settings, dataset.parent, args.image_input_tokens)
    planned = sum(call.calls for call in calls)
    known = [call.upper_usd for call in calls if call.upper_usd is not None]
    estimate = f"{len(calls)} istek, en çok {planned} çağrı, ≈{sum(known):.4f} USD" if len(known) == len(calls) else f"{len(calls)} istek, en çok {planned} çağrı, fiyatsız model var"
    print(f"Ön tahmin (giriş ve görsel token tahminine dayalı üst değer, kesin tavan değildir): {estimate}")
    if args.max_calls is not None and planned > args.max_calls:
        print(f"Durduruldu: planlanan {planned} çağrı --max-calls {args.max_calls} değerini aşıyor. Çağrı yapılmadı.")
        return 3
    if args.max_usd is not None and (len(known) != len(calls) or sum(known) > args.max_usd):
        print(f"Durduruldu: tahmini üst maliyet --max-usd {args.max_usd} sınırını aşıyor veya hesaplanamıyor. Çağrı yapılmadı.")
        return 3
    budget, rows = Budget(args.max_usd, args.max_calls), []
    for call in calls:
        if not budget.allows(call):
            print(f"Kalan çağrılar yapılmadı: {budget.stopped}.")
            break
        factory = fake_factory(call, args.fake_input_tokens) if args.provider == "fake" else client_factory
        row = await execute(call, settings, factory, dataset.parent, settings.openai_api_key or "fake")
        rows.append(row)
        budget.provider_calls += row["provider_calls"]
        if row["estimated_usd"] is None:
            budget.unknown_cost += 1
            budget.spent_usd += call.upper_usd or 0
        else:
            budget.spent_usd += row["estimated_usd"]
    out_dir = Path(args.output_dir) if args.output_dir else out_root / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    write_outputs(out_dir, rows, summarize(rows), fake=args.provider == "fake", budget=budget, estimate=estimate)
    print(f"{len(rows)} istek değerlendirildi, {budget.provider_calls} sağlayıcı çağrısı. Çıktı: {out_dir}")
    return 0 if budget.stopped is None else 4


def parser():
    root = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = root.add_subparsers(dest="mode")
    check = commands.add_parser("validate", help="Fikstürleri ve veri setlerini doğrular (varsayılan).")
    check.add_argument("datasets", nargs="*", type=Path)
    go = commands.add_parser("run", help="Karşılaştırmalı değerlendirme koşusu.")
    go.add_argument("--provider", choices=["openai", "fake"], default="openai")
    go.add_argument("--dataset", default=str(DATASETS / "smoke.jsonl"))
    go.add_argument("--operations", nargs="+", choices=OPERATIONS, default=list(OPERATIONS))
    go.add_argument("--candidate", default="gpt-6-luna")
    go.add_argument("--reasoning-effort", nargs="*", choices=EFFORTS, default=[])
    go.add_argument("--allow-paid", action="store_true")
    go.add_argument("--max-usd", type=float)
    go.add_argument("--max-calls", type=int)
    go.add_argument("--image-input-tokens", type=int, default=1600, help="Görsel başına giriş token tahmini")
    go.add_argument("--fake-input-tokens", type=int, default=1200, help=argparse.SUPPRESS)
    go.add_argument("--output-dir")
    pack = commands.add_parser("pack", help="TA-005: 24 özgün soru, görsel + öğretmen anahtarı, tam üretim yolu.")
    pack.add_argument("--provider", choices=["openai", "anthropic"], default="openai", help="ders sağlayıcısı")
    pack.add_argument("--vision-provider", choices=["openai", "anthropic"], default="openai")
    pack.add_argument("--pack-images-to-anthropic", action="store_true",
                      help="özgün paket görsellerinin Anthropic'e gönderilmesine açık izin (öğrenci görseli değildir)")
    pack.add_argument("--model", help="Vision modeli (varsayılan: ayardaki model)")
    pack.add_argument("--lesson-model", help="Ders modeli (varsayılan: ayardaki model)")
    pack.add_argument("--reasoning-effort", choices=["none", "low", "medium", "high", "xhigh", "max"])
    pack.add_argument("--dry-run", action="store_true")
    pack.add_argument("--allow-paid", action="store_true")
    pack.add_argument("--max-usd", type=float)
    pack.add_argument("--max-calls", type=int)
    commands.add_parser("readiness", help="TA-005C: gerçek değerlendirmeye hazırlık raporu (çağrı yok).")
    return root


def main(argv=None, settings=None, client_factory=None, out_root=ROOT / "eval-results"):
    args = parser().parse_args(argv)
    if args.mode in (None, "validate"):
        datasets = getattr(args, "datasets", None) or sorted(DATASETS.glob("*.jsonl"))
        return validate(datasets)
    if args.mode == "readiness":
        from scripts import eval_pack

        print(json.dumps(eval_pack.readiness(), ensure_ascii=False, indent=2))
        print("Hazırlık raporu; sağlayıcı çağrısı yapılmadı. Gerçek doğruluk ölçülmedi.")
        return 0
    settings = settings or get_settings()
    if args.mode == "pack":
        from scripts import eval_pack

        if args.provider == "anthropic" and not args.lesson_model:
            parser().error("--provider anthropic için --lesson-model zorunludur (varsayılan Anthropic modeli yok). Çağrı yapılmadı.")
        if args.vision_provider == "anthropic" and not (args.model and args.pack_images_to_anthropic):
            parser().error("--vision-provider anthropic için --model ve --pack-images-to-anthropic zorunludur. Çağrı yapılmadı.")
        uses_anthropic = "anthropic" in (args.provider, args.vision_provider)
        uses_openai = "openai" in (args.provider, args.vision_provider)
        if uses_anthropic and not args.dry_run and not settings.anthropic_api_key:
            parser().error("Anthropic işlemi için ANTHROPIC_API_KEY gerekli. Çağrı yapılmadı.")
        if not args.dry_run:
            missing = [flag for flag, value in (("--allow-paid", args.allow_paid), ("--max-usd", args.max_usd),
                                                ("--max-calls", args.max_calls)) if not value]
            if missing or (uses_openai and not settings.openai_api_key) or not settings.ai_enabled:
                parser().error("Ücretli koşu için birlikte gerekli: --allow-paid, --max-usd, --max-calls ve anahtar. Çağrı yapılmadı.")
        logging.basicConfig(level=logging.WARNING, format="%(message)s")
        return asyncio.run(eval_pack.run(args, settings))
    if args.provider == "openai":
        missing = [flag for flag, value in (("--allow-paid", args.allow_paid), ("--max-usd", args.max_usd), ("--max-calls", args.max_calls)) if not value]
        if missing:
            parser().error("Ücretli koşu için birlikte gerekli: " + ", ".join(missing) + ". Çağrı yapılmadı.")
        models = {settings.openai_vision_model, settings.openai_interaction_model, args.candidate}
        if not settings.pricing_version or any(model not in settings.model_prices for model in models):
            parser().error("Her model için TEACHERAI_PRICING_VERSION ve TEACHERAI_MODEL_PRICES gerekli. Çağrı yapılmadı.")
        if not settings.openai_api_key or not settings.ai_enabled:
            parser().error("Değerlendirme anahtarı ve etkin AI gerekli. Çağrı yapılmadı.")
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    return asyncio.run(run(args, settings, client_factory, out_root))


if __name__ == "__main__":
    raise SystemExit(main())
