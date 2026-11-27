"""TA-009B §3: aday matrisi, kör puanlama dosyaları ve gerileme koşusu.

    python -m scripts.evaluate_models matrix --dry-run
    python -m scripts.evaluate_models matrix --allow-paid --max-usd 20 --max-calls 1500 [--pack-images-to-anthropic]
    python -m scripts.evaluate_models matrix-score evals/runs/matrix-<zaman>
    python -m scripts.evaluate_models regress --dry-run

Ücretli koşu yalnız ön koşullar tamamsa başlar:
- öğretmen anahtarı (``original-24.answers.json``, Erdem doldurur),
- sha256'sı eşleşen bütün paket görselleri,
- karar kuralı özetinin değişmemiş olması (``docs/evals/TA-009B-model-selection.md``),
- açık ``--allow-paid --max-usd --max-calls``.

USD ve çağrı tavanı aday arasında paylaştırılır: her aday kalan bütçeyle koşulur, tavan dolunca koşu durur. Ham çıktılar
``evals/runs/`` altında kalır (Git dışı).
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
import secrets
from argparse import Namespace
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "evals/runs"
DOC = ROOT / "docs/evals/TA-009B-model-selection.md"
SMOKE = ROOT / "evals/datasets/smoke.jsonl"
RULE_SHA256 = "b8cba51a3504cac2e3a011ab752e725d2cbce08cc90fb9055d6a6b7f49580b84"
PACK_CALLS = 5  # soru başına en çok: Vision 2 + ders 3 (eval_pack.MAX_CALLS)
VISION_CALLS = 2  # Vision kararlılık tekrarı: yalnız analiz (ders üretilmez)


@dataclass(frozen=True)
class Candidate:
    operation: str  # vision | lessons | interaction
    provider: str
    model: str
    effort: str | None = None
    repeats: int = 1

    @property
    def label(self) -> str:
        return f"{self.operation}:{self.model}:{self.effort or 'varsayilan'}"


CANDIDATES = (
    Candidate("vision", "openai", "gpt-6-luna", "medium", 2),
    Candidate("vision", "openai", "gpt-6-luna", "low", 2),
    Candidate("vision", "openai", "gpt-6.1-terra", "low", 2),
    Candidate("vision", "anthropic", "claude-haiku-5-5", None, 2),
    Candidate("vision", "anthropic", "claude-sonnet-5-5", None, 2),
    Candidate("lessons", "openai", "gpt-5.6-terra"),
    Candidate("lessons", "openai", "gpt-6.1-terra", "medium"),
    Candidate("lessons", "openai", "gpt-6.2-sol", "low"),
    Candidate("lessons", "anthropic", "claude-sonnet-5-5"),
    Candidate("interaction", "openai", "gpt-6-luna", "low"),
    Candidate("interaction", "anthropic", "claude-haiku-5-5"),
)


def rule_digest(path: Path = DOC) -> str | None:
    """Karar kuralı bölümünün sha256 özeti (satır sonları normalize)."""
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    start, end = text.find("<!-- karar-kurali:basla -->"), text.find("<!-- karar-kurali:bitir -->")
    return hashlib.sha256(text[start:end].encode("utf-8")).hexdigest() if 0 <= start < end else None


def prerequisites() -> tuple[list[str], int]:
    """(eksikler, koşulabilir soru sayısı). Eksik varsa ücretli koşu başlamaz."""
    from scripts import eval_pack
    from scripts.answer_key import load_key

    problems = []
    if load_key() is None:
        problems.append("öğretmen anahtarı yok (evals/datasets/original-24.answers.json; Erdem doldurur)")
    runs, missing = eval_pack.plan()
    if missing:
        problems.append(f"görseli eksik veya sha256 uyuşmuyor: {', '.join(missing)}")
    if rule_digest() != RULE_SHA256:
        problems.append("karar kuralı özeti uyuşmuyor (docs/evals/TA-009B-model-selection.md değişmiş)")
    return problems, len(runs)


def pack_args(candidate: Candidate, settings, images_to_anthropic: bool, vision_only: bool = False, **budget) -> Namespace:
    vision = candidate.operation == "vision"
    return Namespace(
        model=candidate.model if vision else settings.openai_vision_model,
        lesson_model=None if vision else candidate.model,
        vision_provider=candidate.provider if vision else "openai",
        provider="openai" if vision else candidate.provider,
        reasoning_effort=candidate.effort if vision else None,
        lesson_reasoning_effort=None if vision else candidate.effort,
        pack_images_to_anthropic=images_to_anthropic, vision_only=vision_only, dry_run=False, **budget)


def _interaction_calls(candidate: Candidate):
    from scripts.evaluate_models import CALLS_PER_REQUEST, Call, load

    items, _ = load(SMOKE)
    return [Call(item, "interaction", candidate.model, candidate.effort, calls=CALLS_PER_REQUEST["interaction"])
            for item in items if item.is_valid_math_question]


def plan(settings, questions: int, images_to_anthropic: bool) -> list[dict]:
    """Aday başına üst tahmin (USD, çağrı) ve atlanma nedeni. Sağlayıcı çağrısı yapmaz."""
    from apps.api.app.core.operations import validate_effort
    from scripts import eval_pack
    from scripts.evaluate_models import price_calls

    _, prices = eval_pack.load_pricing()
    rows = []
    for candidate in CANDIDATES:
        validate_effort(candidate.model, candidate.effort)
        skipped = None
        if candidate.operation == "vision" and candidate.provider == "anthropic" and not images_to_anthropic:
            skipped = "gizlilik kapısı kapalı (--pack-images-to-anthropic yok)"
        if candidate.operation == "interaction":
            calls = price_calls(_interaction_calls(candidate), settings, SMOKE.parent, 1600)
            known = [c.upper_usd for c in calls]
            usd = sum(known) if all(u is not None for u in known) else None
            count = sum(c.calls for c in calls)
        else:
            args = pack_args(candidate, settings, images_to_anthropic)
            lesson_model = args.lesson_model or settings.openai_lesson_model
            first = eval_pack.upper_usd([None] * questions, args.model, lesson_model, prices)
            again = eval_pack.upper_usd([None] * questions, args.model, lesson_model, prices, lessons=False)
            usd = None if first is None or again is None else first + again * (candidate.repeats - 1)
            count = questions * (PACK_CALLS + VISION_CALLS * (candidate.repeats - 1))
        rows.append({"candidate": candidate, "upper_usd": usd, "calls": count, "skipped": skipped})
    return rows


def print_plan(rows) -> None:
    print("| Aday | Tekrar | Üst USD | En çok çağrı | Durum |\n| --- | --- | --- | --- | --- |")
    for row in rows:
        usd = "fiyatsız" if row["upper_usd"] is None else f"{row['upper_usd']:.4f}"
        print(f"| {row['candidate'].label} | {row['candidate'].repeats} | {usd} | {row['calls']} | {row['skipped'] or 'koşulur'} |")
    active = [r for r in rows if not r["skipped"]]
    total = sum(r["upper_usd"] or 0 for r in active)
    print(f"Toplam (koşulacak adaylar): üst ≈{total:.4f} USD, en çok {sum(r['calls'] for r in active)} çağrı.")


async def run_matrix(args, settings, out_root: Path = RUNS) -> int:
    from scripts import eval_pack
    from scripts.evaluate_models import execute

    problems, questions = prerequisites()
    rows = plan(settings, questions or 24, args.pack_images_to_anthropic)
    print_plan(rows)
    for problem in problems:
        print(f"Ön koşul eksik: {problem}")
    if args.dry_run:
        print("Kuru koşu: sağlayıcı çağrısı yapılmadı.\n  python -m scripts.evaluate_models matrix --allow-paid "
              "--max-usd <onaylı USD> --max-calls <üst sınır>" + (" --pack-images-to-anthropic" if args.pack_images_to_anthropic else ""))
        return 0
    if problems:
        print("Durduruldu: ön koşullar tamam değil. Çağrı yapılmadı.")
        return 3
    out = out_root / ("matrix-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    spent, used, results = 0.0, 0, []
    for row in rows:
        candidate = row["candidate"]
        if row["skipped"]:
            results.append({"label": candidate.label, "skipped": row["skipped"]})
            continue
        # Paket adayları soru başına gerçek harcamayla durur (eval_pack.run); etkileşim adayı bütün üst tahminiyle sığmalı.
        whole = row["upper_usd"] if candidate.operation == "interaction" else 0
        if row["upper_usd"] is None or spent + whole >= args.max_usd or used + PACK_CALLS > args.max_calls:
            results.append({"label": candidate.label, "skipped": "bütçe tavanı"})
            continue
        runs = []
        for index in range(candidate.repeats):
            target = out / f"{candidate.label.replace(':', '_')}_{index + 1}"
            if candidate.operation == "interaction":
                outputs = [await execute(call, settings, None, SMOKE.parent, settings.openai_api_key)
                           for call in _interaction_calls(candidate)]
                target.mkdir(parents=True, exist_ok=True)
                (target / "raw.jsonl").write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in outputs), encoding="utf-8")
                cost = sum(o["estimated_usd"] or 0 for o in outputs)
                summary = {"answer_leak_rate": _rate([o.get("answer_leak") for o in outputs]),
                           "success_rate": _rate([o["outcome"] == "success" for o in outputs]), "spent_usd_estimate": cost}
                (target / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                used += sum(o["provider_calls"] for o in outputs)
            else:
                budget = {"max_usd": args.max_usd - spent, "max_calls": args.max_calls - used}
                await eval_pack.run(pack_args(candidate, settings, args.pack_images_to_anthropic, vision_only=index > 0,
                                              **budget), settings, out_root=target)
                summary = json.loads(next(target.glob("*/summary.json")).read_text(encoding="utf-8"))
                cost = summary["spent_usd_estimate"]
                used += sum(json.loads(line)["provider_calls"] for line in next(target.glob("*/raw.jsonl")).open(encoding="utf-8"))
            spent += cost
            runs.append({"path": str(target.relative_to(out)), "summary": summary})
        results.append({"label": candidate.label, "runs": runs, "stability": stability(out, runs)})
    (out / "matrix.json").write_text(json.dumps({"rule_sha256": RULE_SHA256, "spent_usd_estimate": round(spent, 4),
                                                "provider_calls": used, "results": results}, ensure_ascii=False, indent=2)
                                     + "\n", encoding="utf-8")
    blind_files(out, results)
    print(f"Matris koşusu bitti: ≈{spent:.4f} USD, {used} çağrı. Çıktı: {out} (Git dışı).")
    return 0


def _rate(values) -> float | None:
    values = [v for v in values if v is not None]
    return round(sum(bool(v) for v in values) / len(values), 3) if values else None


def _rows(out: Path, run: dict) -> list[dict]:
    files = sorted((out / run["path"]).glob("**/raw.jsonl"))
    return [json.loads(line) for line in files[0].open(encoding="utf-8")] if files else []


def stability(out: Path, runs: list[dict]) -> float | None:
    """İki Vision koşusunda aynı (bütünlük kararı, okuma puanları) veren soruların oranı. İkinci koşu ders üretmez."""
    if len(runs) < 2:
        return None
    first = {r["id"]: (r["decision"], r["reading"]) for r in _rows(out, runs[0])}
    second = {r["id"]: (r["decision"], r["reading"]) for r in _rows(out, runs[1])}
    shared = set(first) & set(second)
    return round(sum(first[i] == second[i] for i in shared) / len(shared), 3) if shared else None


def blind_files(out: Path, results: list[dict]) -> None:
    """Ders ve etkileşim çıktıları rastgele kodla karıştırılır; eşleme anahtarı ayrı dosyadadır."""
    entries, key = [], {}
    for result in results:
        if not result.get("runs") or result["label"].startswith("vision:"):
            continue
        for row in _rows(out, result["runs"][0]):
            output = json.dumps(row["lesson"], ensure_ascii=False) if "lesson" in row else row.get("output")
            if not output:
                continue
            code = secrets.token_hex(4)
            key[code] = result["label"]
            entries.append([code, row.get("id") or row.get("item_id"), result["label"].split(":")[0], output])
    random.SystemRandom().shuffle(entries)
    with (out / "blind.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["kod", "soru", "islem", "cikti", "dogruluk_1_5", "yontem_1_5", "aciklik_1_5", "turkce_1_5",
                         "cevabi_vermeme_1_5", "degerlendiren", "not"])
        writer.writerows(entry + [""] * 7 for entry in entries)
    (out / "blind_key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


SCORES = ("dogruluk_1_5", "yontem_1_5", "aciklik_1_5", "turkce_1_5", "cevabi_vermeme_1_5")


def score(folder: Path) -> dict:
    """Puanlanmış ``blind_scored.csv`` + ``blind_key.json`` → aday başına ortalama puan."""
    key = json.loads((folder / "blind_key.json").read_text(encoding="utf-8"))
    totals: dict[str, list[float]] = {}
    with (folder / "blind_scored.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            values = [float(row[c]) for c in SCORES if (row.get(c) or "").strip()]
            if row["kod"] in key and values:
                totals.setdefault(key[row["kod"]], []).append(sum(values) / len(values))
    result = {label: round(sum(v) / len(v), 3) for label, v in sorted(totals.items())}
    (folder / "blind_scores.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


# --------------------------------------------------------------------------- gerileme

COMPARED = ("confident_wrong_rate", "answer_accuracy_teacher", "clarification_rate", "abstain_rate", "usd_per_question",
            "latency_ms_p95", "provider_calls_per_question")


def last_summary(settings, out_root: Path = RUNS, before: str | None = None) -> tuple[Path, dict] | None:
    """Aynı Vision/ders yapılandırmasının en son özeti (matris veya gerileme koşusundan)."""
    found = []
    for path in out_root.glob("**/summary.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        same = (data.get("vision_model"), data.get("lesson_model")) == (settings.openai_vision_model, settings.openai_lesson_model)
        if same and (before is None or str(path) < before):
            found.append((path.parent.name, path, data))
    return max(found, key=lambda item: item[0])[1:] if found else None


def difference(old: dict, new: dict) -> list[str]:
    lines = ["| Ölçüt | Önceki | Şimdi |", "| --- | --- | --- |"]
    lines += [f"| {name} | {old.get(name, '—')} | {new.get(name, '—')} |" for name in COMPARED]
    return lines


async def regress(args, settings, out_root: Path = RUNS) -> int:
    from apps.api.app.core.operations import Operation
    from scripts import eval_pack

    problems, _ = prerequisites()
    previous = last_summary(settings, out_root)
    print(f"Gerileme: Vision {settings.openai_vision_model}, ders {settings.openai_lesson_model}; "
          f"son sonuç: {previous[0] if previous else 'yok'}.")
    for problem in problems:
        print(f"Ön koşul eksik: {problem}")
    if args.dry_run or problems:
        print("Sağlayıcı çağrısı yapılmadı.")
        return 0 if args.dry_run else 3
    efforts = settings.reasoning_effort_by_operation
    target = out_root / "regress"
    await eval_pack.run(Namespace(model=None, lesson_model=None, provider="openai", vision_provider="openai",
                                  reasoning_effort=efforts.get(Operation.VISION),
                                  lesson_reasoning_effort=efforts.get(Operation.LESSONS), pack_images_to_anthropic=False,
                                  dry_run=False, max_usd=args.max_usd, max_calls=args.max_calls), settings, out_root=target)
    current = max(target.glob("*/summary.json"), key=lambda p: p.parent.name)
    new = json.loads(current.read_text(encoding="utf-8"))
    print("\n".join(difference(previous[1] if previous else {}, new)))
    return 0
