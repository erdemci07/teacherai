"""Özgün 24 soruluk paketin görsellerle tam üretim yolunda değerlendirilmesi (TA-005 §5.3).

    python -m scripts.evaluate_models pack --dry-run --model gpt-6-luna --reasoning-effort low
    python -m scripts.evaluate_models pack --allow-paid --max-usd 5 --max-calls 120 --model gpt-6-luna

Yol: Vision → bütünlük → hedef → ders (gerçek ``VisionService`` ve ``LessonService``; MathAI dahil).
Girdi: ``evals/local/images`` (Git dışı), manifest ``evals/datasets/original-24.images.json`` ve öğretmen
anahtarı ``evals/datasets/original-24.answers.json``. Anahtar yoksa cevap doğruluğu ``anahtar_yok`` kalır;
türetilmiş cevap başarı ölçütü yapılmaz. Paket ``reading`` alanı okuma doğruluğu için referanstır ve
sağlayıcıya hiçbir zaman gönderilmez.

Ücretli koşu yalnız --allow-paid, --max-usd ve --max-calls birlikte verildiğinde başlar. Fiyatlar
``apps/api/app/core/model_catalog.json`` dosyasından okunur. Ön tahmin üst değerdir. Her sorudan önce kalan bütçe
denetlenir; tavan aşılacaksa koşu durur. Ham çıktılar ``evals/runs/`` altına (Git dışı) yazılır.
"""

import io
import json
import math
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from time import perf_counter

from scripts.answer_key import IMAGES, MANIFEST, PACK, ROOT, load_key

MODELS = ROOT / "apps/api/app/core/model_catalog.json"  # TA-005B: tek fiyat kaynağı
RUNS = ROOT / "evals/runs"
VISION_PROMPT = ROOT / "apps/api/app/features/vision/prompts/question_analysis.txt"
LESSON_PROMPT_DIR = ROOT / "apps/api/app/features/lessons/prompts"
# Mantıksal istek başına en çok çağrı: analiz 1 + yeniden okuma 1, ders 3 (Settings varsayılanları).
MAX_CALLS = {"vision": 2, "lessons": 3}


def load_pricing(path: Path = MODELS) -> tuple[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    prices = {model: (m["usd_per_million_tokens"]["input"], m["usd_per_million_tokens"]["cached_input"],
                      m["usd_per_million_tokens"]["output"]) for model, m in data["models"].items()
              if m.get("usd_per_million_tokens")}  # fiyatsız model (ör. kademeli fiyat) maliyetlenmez
    return data["pricing_version"], prices


def plan(manifest_path: Path = MANIFEST, images: Path = IMAGES) -> tuple[list[dict], list[str]]:
    """(koşulacak sorular, görseli eksik soru kimlikleri). sha256 uyuşmayan görsel koşulmaz."""
    import hashlib

    pack = {q["id"]: q for q in json.loads(PACK.read_text(encoding="utf-8"))["questions"]}
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))["images"] if manifest_path.exists() else []
    runs, seen, variants = [], set(), {}
    for entry in entries:
        path = images / entry["file"]
        if entry.get("question_id") not in pack or not path.exists():
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"{entry['file']}: sha256 manifestle uyuşmuyor")
        if entry.get("kind") == "ocr_variant":
            # TA-007: varyant ayrı örnek değildir; özgün sorunun altında aynı anahtarla değerlendirilir.
            variants.setdefault(entry["question_id"], []).append(path)
            continue
        runs.append({"question": pack[entry["question_id"]], "image": path})
        seen.add(entry["question_id"])
    for run in runs:
        run["variants"] = variants.get(run["question"]["id"], [])
    return runs, sorted(set(pack) - seen)


def upper_usd(runs, vision_model, lesson_model, prices, image_tokens=1600) -> float | None:
    """Kaba üst tahmin: her çağrı tam çıktı sınırını kullanır; giriş = istem baytı / 2 (+ görsel)."""
    if vision_model not in prices or lesson_model not in prices:
        return None
    from apps.api.app.core.operations import DEFAULT_LIMITS, Operation

    lesson_prompt = sum(len(p.read_bytes()) for p in LESSON_PROMPT_DIR.glob("*.txt"))
    vision_in = math.ceil(len(VISION_PROMPT.read_bytes()) / 2) + image_tokens
    vision = MAX_CALLS["vision"] * (vision_in * prices[vision_model][0] + DEFAULT_LIMITS[Operation.VISION] * prices[vision_model][2])
    lesson_in = math.ceil(lesson_prompt / 2) + 6000  # ders bağlamı üst sınırı ≈ 24 KB / 4
    lesson = MAX_CALLS["lessons"] * (lesson_in * prices[lesson_model][0] + DEFAULT_LIMITS[Operation.LESSONS] * prices[lesson_model][2])
    return len(runs) * (vision + lesson) / 1_000_000


# --------------------------------------------------------------------------- metrikler (saf)

def _canonical(text: str) -> str | None:
    from apps.api.app.features.integrity.expression import canonical, parse

    result = parse(text)
    return canonical(result.tree) if result.parsed else None


def _field(text: str) -> str:
    return "root_scope" if "sqrt" in text else "exponent" if "^" in text else "fraction_bar" if "frac" in text or "/" in text else "expression"


def reading_scores(expected: dict, analysis) -> dict:
    """Alan türüne göre okuma doğruluğu: her beklenen ifade/şık için yapısal eşleşme (True/False)."""
    scores: dict[str, list[bool]] = {}
    got = {_canonical(item) for item in analysis.mathematical_expressions}
    for item in expected.get("mathematical_expressions", []):
        scores.setdefault(_field(item), []).append(_canonical(item) in got)
    wanted_choices = [" ".join(c.split()) for c in expected.get("answer_choices", [])]
    actual = [" ".join(c.split()) for c in analysis.answer_choices]
    if wanted_choices:
        scores["choices"] = [choice in actual for choice in wanted_choices]
    visual = expected.get("visual_elements") or {}
    if visual.get("has_graph"):
        scores["graph_axis"] = []  # grafik ekseni için yapısal referans yok: ölçülmedi
    return scores


def label_of(final_answer: str | None) -> str | None:
    import re

    match = re.match(r"^\s*([A-E])\)", final_answer or "")
    return match.group(1) if match else None


def percentile(values, q):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1)] if ordered else None


def summarize(rows: list[dict]) -> dict:
    fields: dict[str, list[bool]] = {}
    for row in rows:
        for name, values in row["reading"].items():
            fields.setdefault(name, []).extend(values)
    keyed = [row for row in rows if row["teacher_answer"]]
    latencies = [row["latency_ms"] for row in rows]
    costs = [row["estimated_usd"] for row in rows if row["estimated_usd"] is not None]
    outcomes: dict[str, int] = {}
    for row in rows:
        for outcome in row["outcomes"]:
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
    rate = lambda n, d: round(n / d, 3) if d else None
    return {
        "questions": len(rows),
        "reading_accuracy": {name: (rate(sum(v), len(v)) if v else "ölçülmedi") for name, v in sorted(fields.items())},
        "answer_accuracy_teacher": rate(sum(row["teacher_answer"] == row["selected"] for row in keyed), len(keyed)) if keyed else "anahtar_yok",
        "clarification_rate": rate(sum(row["decision"] == "clarification_required" for row in rows), len(rows)),
        "abstain_rate": rate(sum(row["selected"] is None for row in rows), len(rows)),
        "provider_calls_per_question": rate(sum(row["provider_calls"] for row in rows), len(rows)),
        "outcomes": outcomes,
        "usd_per_question": rate(sum(costs), len(costs)) if costs else None,
        "latency_ms_p50": median(latencies) if latencies else None, "latency_ms_p95": percentile(latencies, 0.95),
        "wrong_by_trap": sorted({f"{row['id']}:{tag}" for row in keyed if row["teacher_answer"] != row["selected"]
                                 for tag in row["trap_tags"] or ["etiketsiz"]}),
    }


# --------------------------------------------------------------------------- yürütme

class Services:
    """Gerçek üretim yolu. Testler bu sınıfın yerine sahte bir nesne verir."""

    def __init__(self, settings, vision_model, lesson_model, effort, lesson_provider="openai", vision_provider="openai",
                 pack_images_to_anthropic=False):
        from apps.api.app.features.board.planner import BoardPlanner
        from apps.api.app.features.lessons.openai_provider import (
            AnthropicLessonProvider,
            OpenAILessonProvider,
        )
        from apps.api.app.features.lessons.service import LessonService
        from apps.api.app.features.mathai.service import MathAIService
        from apps.api.app.features.vision.openai_provider import (
            AnthropicVisionProvider,
            OpenAIVisionProvider,
        )
        from apps.api.app.features.vision.service import VisionService
        from apps.api.app.features.vision.storage import LocalTemporaryImageStorage

        self.settings, self.temp = settings, tempfile.TemporaryDirectory()
        key = settings.openai_api_key
        # TA-005C: Anthropic Vision yalnız özgün paket görselleri için ve açık bayrakla (öğrenci görseli değildir;
        # production izni TEACHERAI_ALLOW_STUDENT_IMAGES_TO_ANTHROPIC bununla açılmaz).
        vision = (AnthropicVisionProvider(settings.anthropic_api_key, vision_model, settings.vision_provider_timeout_seconds,
                                          allow_images=pack_images_to_anthropic)
                  if vision_provider == "anthropic" else
                  OpenAIVisionProvider(key, vision_model, settings.vision_provider_timeout_seconds))
        self.vision = VisionService(vision, LocalTemporaryImageStorage(Path(self.temp.name)), settings.max_upload_size_bytes,
                                    False, recheck_limit=settings.vision_max_rechecks)
        lessons = (AnthropicLessonProvider(settings.anthropic_api_key, lesson_model, settings.lesson_provider_timeout_seconds)
                   if lesson_provider == "anthropic" else
                   OpenAILessonProvider(key, lesson_model, settings.lesson_provider_timeout_seconds))
        self.lessons = LessonService(lessons, MathAIService(), BoardPlanner())

    async def analyze(self, image: Path, request_id: str):
        from starlette.datastructures import Headers, UploadFile

        media = {".png": "image/png", ".webp": "image/webp"}.get(image.suffix.lower(), "image/jpeg")
        upload = UploadFile(file=io.BytesIO(image.read_bytes()), filename=image.name, headers=Headers({"content-type": media}))
        return await self.vision.analyze(upload, request_id)

    async def generate(self, analysis, request_id: str):
        return await self.lessons.generate(analysis, None, request_id)


async def run_question(item: dict, services, settings, teacher: dict) -> dict:
    """Bir soru: analiz ve (çözülebilirse) ders. Kullanım satırları gateway günlüğünden toplanır."""
    import logging

    from apps.api.app.core.ai_outcomes import AIOutcomeError
    from apps.api.app.core.gateway import (
        ProviderCallBudgetExhausted,
        begin_offline_accounting,
        end_accounting,
    )
    from apps.api.app.features.lessons.exceptions import LessonError
    from apps.api.app.features.vision.exceptions import VisionError
    from scripts.evaluate_models import Capture

    question, request_id = item["question"], f"pack-{item['question']['id']}"
    capture, usage = Capture(), logging.getLogger("teacherai.ai_usage")
    usage.addHandler(capture)
    level = usage.level
    usage.setLevel(logging.INFO)
    row = {"id": question["id"], "subject": question["subject"], "decision": None, "selected": None, "error": None,
           "teacher_answer": (teacher.get(question["id"]) or {}).get("expected_choice"),
           "trap_tags": (teacher.get(question["id"]) or {}).get("trap_tags", []), "reading": {}}
    started = perf_counter()
    try:
        # TA-005C: açık offline kapsam (kendi çağrı tavanı; kullanıcı kotası yok). USD tavanı run() içinde.
        token = begin_offline_accounting(request_id, settings, max_calls=MAX_CALLS["vision"])
        try:
            analysis = await services.analyze(item["image"], request_id)
        finally:
            end_accounting(token)
        row["decision"] = analysis.integrity.decision if analysis.integrity else None
        row["reading"] = reading_scores(question["reading"], analysis)
        if analysis.integrity is not None and analysis.integrity.solvable:
            token = begin_offline_accounting(request_id, settings, max_calls=MAX_CALLS["lessons"])
            try:
                lesson = await services.generate(analysis, request_id)
            finally:
                end_accounting(token)
            row["selected"] = label_of(lesson.lesson.content.final_answer)
    except (AIOutcomeError, VisionError, LessonError, ProviderCallBudgetExhausted) as exc:
        row["error"] = getattr(exc, "code", type(exc).__name__)
    finally:
        usage.removeHandler(capture)
        usage.setLevel(level)
    row["latency_ms"] = round((perf_counter() - started) * 1000)
    row["provider_calls"] = len(capture.events)
    row["outcomes"] = [event.get("outcome", "unknown") for event in capture.events]
    costs = [event.get("estimated_usd") for event in capture.events]
    row["estimated_usd"] = sum(costs) if capture.events and all(c is not None for c in costs) else None
    return row


def command(args) -> str:
    effort = f" --reasoning-effort {args.reasoning_effort}" if args.reasoning_effort else ""
    return ("python -m scripts.evaluate_models pack --allow-paid --max-usd <onaylı USD> --max-calls <üst sınır>"
            + (f" --model {args.model}" if args.model else "") + effort + (f" --lesson-model {args.lesson_model}" if args.lesson_model else "")
            + (" --provider anthropic" if getattr(args, "provider", "openai") == "anthropic" else "")
            + (" --vision-provider anthropic --pack-images-to-anthropic"
               if getattr(args, "vision_provider", "openai") == "anthropic" else ""))


def _label(provider):
    return "Anthropic" if provider == "anthropic" else "OpenAI"


async def run(args, settings, services_factory=Services, out_root: Path = RUNS) -> int:
    from apps.api.app.core.operations import Operation, validate_effort

    version, prices = load_pricing()
    vision_model, lesson_model = args.model or settings.openai_vision_model, args.lesson_model or settings.openai_lesson_model
    if args.reasoning_effort:
        validate_effort(vision_model, args.reasoning_effort)
    lesson_provider, vision_provider = getattr(args, "provider", "openai"), getattr(args, "vision_provider", "openai")
    if "anthropic" in (lesson_provider, vision_provider):
        print(f"Sağlayıcı: ders {_label(lesson_provider)}, Vision {_label(vision_provider)}. Fallback yok; "
              "öğretmen anahtarı ve okuma referansı sağlayıcıya gönderilmez.")
    runs, missing = plan()
    estimate = upper_usd(runs, vision_model, lesson_model, prices)
    calls = len(runs) * (MAX_CALLS["vision"] + MAX_CALLS["lessons"])
    print(f"Plan: {len(runs)} soru, en çok {calls} çağrı, üst tahmin {'fiyatsız model' if estimate is None else f'≈{estimate:.4f} USD'} "
          f"(Vision {vision_model}, ders {lesson_model}). Görseli eksik: {', '.join(missing) or 'yok'}.")
    key = load_key()
    print("Öğretmen anahtarı: " + (f"{len(key.entries)} satır" if key else "bekleniyor (cevap doğruluğu ölçülmeyecek)"))
    full = upper_usd([None] * (len(runs) + len(missing)), vision_model, lesson_model, prices)
    if full is not None:
        print(f"Bütün paket ({len(runs) + len(missing)} görsel) gelirse üst tahmin ≈{full:.4f} USD, en çok "
              f"{(len(runs) + len(missing)) * (MAX_CALLS['vision'] + MAX_CALLS['lessons'])} çağrı.")
    if args.dry_run:
        print("Kuru koşu: sağlayıcı çağrısı yapılmadı. Onaydan sonra çalıştırılacak komut:\n  " + command(args))
        return 0
    if not runs:
        print("Koşulacak görsel yok; çağrı yapılmadı.")
        return 3
    if estimate is None or args.max_calls < MAX_CALLS["vision"] + MAX_CALLS["lessons"]:
        print("Durduruldu: fiyat bulunamadı veya çağrı sınırı tek soruya yetmiyor. Çağrı yapılmadı.")
        return 3
    efforts = {Operation.VISION: args.reasoning_effort} if args.reasoning_effort else {}
    run_settings = settings.model_copy(update={"pricing_version": version, "model_prices": prices,
                                               "reasoning_effort_by_operation": efforts})
    extra = {"lesson_provider": "anthropic"} if lesson_provider == "anthropic" else {}
    if vision_provider == "anthropic":
        extra |= {"vision_provider": "anthropic", "pack_images_to_anthropic": bool(getattr(args, "pack_images_to_anthropic", False))}
    services = services_factory(run_settings, vision_model, lesson_model, args.reasoning_effort, **extra)
    teacher = {entry.id: entry.model_dump() for entry in key.entries} if key else {}
    per_question = estimate / len(runs)
    rows, spent, used, stopped = [], 0.0, 0, None
    for item in runs:
        if spent + per_question > args.max_usd:
            stopped = "USD sınırı"
        elif used + MAX_CALLS["vision"] + MAX_CALLS["lessons"] > args.max_calls:
            stopped = "çağrı sınırı"
        if stopped:
            print(f"Kalan sorular koşulmadı: {stopped}.")
            break
        row = await run_question(item, services, run_settings, teacher)
        rows.append(row)
        spent += row["estimated_usd"] if row["estimated_usd"] is not None else per_question
        used += row["provider_calls"]
    out = out_root / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=True)
    (out / "raw.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    summary = summarize(rows) | {"vision_model": vision_model, "lesson_model": lesson_model, "reasoning_effort": args.reasoning_effort,
                                 "pricing_version": version, "spent_usd_estimate": round(spent, 4), "stopped": stopped}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Çıktı: {out} (Git dışı). Yalnız özet rapor commit'lenir.")
    return 0 if stopped is None else 4


# --------------------------------------------------------------------------- TA-005C: hazırlık raporu (çağrı yok)

# Ölçüm boyutları ve bugünkü ölçülebilirlik durumu. "olculur": kod ve referans hazır; "anahtar_gerekli":
# öğretmen anahtarı olmadan ölçülmez; "insan_degerlendirmesi": otomatik metrik yok; uydurulmaz.
DIMENSIONS = {
    "ocr_vision": ("olculur", "paket reading alanına karşı alan türüne göre yapısal eşleşme (reading_scores)"),
    "math_expression_recognition": ("olculur", "ifade AST eşleşmesi (integrity/expression.py)"),
    "source_consistency": ("olculur", "bütünlük kararı ve netleştirme oranı (integrity.decision)"),
    "diagram_interpretation": ("kismi", "visual_elements bayrakları; grafik ekseni için yapısal referans yok"),
    "requested_answer_correctness": ("anahtar_gerekli", "öğretmen anahtarı expected_choice ile; modelden türetilmez"),
    "lesson_generation": ("olculur", "ders üretimi, MathAI doğrulaması, sonuç sınıfları"),
    "method_suitability": ("insan_degerlendirmesi", "yöntem denetimi yalnız kanıt düzeyi verir; uygunluk öğretmen kararıdır"),
    "student_interaction": ("olculur_smoke", "run komutu: ipucunda cevap sızıntısı (sentetik smoke seti; gerçek kalite değil)"),
    "latency": ("olculur", "soru başına uçtan uca süre, p50/p95"),
    "token_usage": ("olculur", "ai_usage satırları; bilinmeyen kullanım None kalır"),
    "estimated_cost": ("olculur", "katalog fiyatı; fiyatsız model veya bilinmeyen kullanım için None"),
}


def readiness(manifest_path: Path = MANIFEST, images: Path = IMAGES) -> dict:
    """Gerçek değerlendirmeye hazırlık: denge, eksik görsel, anahtar ve sağlayıcı desteği. Sağlayıcı çağrısı yok."""
    from collections import Counter

    from apps.api.app.core import model_catalog
    from apps.api.app.core.operations import Operation
    from apps.api.app.core.providers import SUPPORTED_OPERATIONS

    questions = json.loads(PACK.read_text(encoding="utf-8"))["questions"]
    try:
        runs, missing = plan(manifest_path, images)
        image_error = None
    except ValueError as error:
        runs, missing, image_error = [], sorted(q["id"] for q in questions), str(error)
    try:
        key = load_key()
        key_status = f"{len(key.entries)} satır" if key else "bekleniyor"
    except (ValueError, OSError) as error:  # geçersiz anahtar (ValidationError dahil) raporlanır, yok sayılmaz
        key, key_status = None, f"geçersiz: {type(error).__name__}"
    keyed = {entry.id for entry in key.entries} if key else set()
    by_subject = Counter(q["subject"] for q in questions)
    return {
        "pack_questions": len(questions),
        "subjects": dict(sorted(by_subject.items())),
        "balanced": len(set(by_subject.values())) == 1,
        "images_ready": len(runs),
        "ocr_variants_ready": sum(len(run.get("variants", [])) for run in runs),
        "images_missing": missing,
        "image_error": image_error,
        "answer_key": key_status,
        "answer_key_missing": sorted({q["id"] for q in questions} - keyed),
        "answer_key_separate_from_model_inputs": True,
        "dimensions": {name: {"status": status, "basis": basis} for name, (status, basis) in DIMENSIONS.items()},
        "providers": {provider: sorted(str(op) for op in ops) for provider, ops in SUPPORTED_OPERATIONS.items()},
        "models": {name: {"provider": entry["provider"], "priced": bool(entry.get("usd_per_million_tokens")),
                          "vision": model_catalog.supports(name, Operation.VISION),
                          "lessons": model_catalog.supports(name, Operation.LESSONS)}
                   for name, entry in sorted(model_catalog.catalog()["models"].items())},
        "lifecycle": model_catalog.lifecycle_report(),
        "real_accuracy_measured": False,
    }
