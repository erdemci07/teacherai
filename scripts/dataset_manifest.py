"""Veri seti ayrımı ve örtüşme denetimi (TA-006). Ağ ve sağlayıcı çağrısı yoktur.

    python -m scripts.dataset_manifest          # rapor yazdırır
    python -m scripts.dataset_manifest --check  # ihlalde sıfırdan farklı çıkış

Denetimler:

1. Manifestteki her yer vardır (cevap anahtarı gibi henüz gelmemiş dosyalar ``status: missing`` ile işaretlidir).
2. ``generation_context: false`` olan hiçbir yol çalışma zamanı kodunda (``apps/api/app``) anılmaz; böylece
   değerlendirme anahtarı ve bağımsız sorular ders üretimi bağlamına giremez.
3. Bağımsız 24 sorunun metinleri ile bilgi kaydı ve özgün betimlemeler arasındaki 6-kelimelik örtüşme sayılır ve
   raporlanır (örtüşme 0 değilse ``--check`` başarısız olur).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "evals/datasets/TA-006-manifest.json"
PACK = ROOT / "apps/api/tests/fixtures/question_pack/teacherai_24.json"
RUNTIME = ROOT / "apps/api/app"
SHINGLE = 6


def shingles(text: str) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", text.casefold())
    return {tuple(words[i:i + SHINGLE]) for i in range(len(words) - SHINGLE + 1)}


def heldout_texts() -> list[tuple[str, str]]:
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    return [(item["id"], item["reading"].get("question_text", "")) for item in pack["questions"]]


def generation_texts() -> list[tuple[str, str]]:
    texts = []
    knowledge = ROOT / "apps/api/app/features/knowledge/data"
    for path in sorted(knowledge.glob("*.json")):
        if path.name in {"sources.json", "reviewers.json", "contribution_publications.json"}:
            continue
        for entry in json.loads(path.read_text(encoding="utf-8"))["entries"]:
            body = " ".join([entry["statement_tr"], *entry.get("misconceptions_tr", []), *entry.get("conditions_tr", []),
                             *entry.get("assumptions_tr", []), *entry.get("exceptions_tr", [])])
            texts.append((entry["id"], body))
    for path in sorted((ROOT / "apps/api/app/features/curriculum/data/descriptions").glob("*.json")):
        for code, item in json.loads(path.read_text(encoding="utf-8"))["items"].items():
            texts.append((code, item["description_tr"]))
    return texts


def run() -> tuple[list[str], dict]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    problems = []
    rows = []
    sources = {path: path.read_text(encoding="utf-8") for path in RUNTIME.rglob("*.py")}
    for dataset in manifest["datasets"]:
        path = ROOT / dataset["path"]
        exists = path.exists()
        if not exists and dataset["status"] != "missing":
            problems.append(f"Yer bulunamadı: {dataset['path']}")
        if exists and dataset["status"] == "missing":
            problems.append(f"Manifest güncel değil (dosya var): {dataset['path']}")
        if not dataset["generation_context"]:
            needle = dataset["path"]
            for file, text in sources.items():
                if needle in text:
                    problems.append(f"Bağlam dışı veri çalışma zamanı kodunda anılıyor: {needle} ← {file.relative_to(ROOT)}")
        rows.append({"id": dataset["id"], "exists": exists, "status": dataset["status"],
                     "generation_context": dataset["generation_context"]})
    held = heldout_texts()
    generated = generation_texts()
    overlaps = []
    for question_id, text in held:
        grams = shingles(text)
        for entry_id, body in generated:
            common = grams & shingles(body)
            if common:
                overlaps.append({"question": question_id, "record": entry_id, "shared_6grams": len(common)})
    if overlaps:
        problems.append(f"Bağımsız sorularla örtüşme: {len(overlaps)} eşleşme")
    return problems, {"datasets": rows, "heldout_questions": len(held), "generation_records": len(generated),
                      "overlaps": overlaps}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    problems, report = run()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if problems:
        print("\n".join(f"SORUN: {item}" for item in problems))
        if args.check:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
