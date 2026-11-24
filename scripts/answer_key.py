"""Bağımsız öğretmen cevap anahtarı ve yerel görsel manifesti (TA-005 §5.1–5.2).

    python -m scripts.answer_key validate              # anahtar varsa doğrular; yoksa "bekleniyor" der
    python -m scripts.answer_key template              # doldurulacak şablonu yazar (cevap yazmaz)
    python -m scripts.answer_key manifest              # evals/local/images içeriğinden sha256 manifesti

Anahtarı proje sahibi doldurur; bu betik hiçbir cevabı kendisi yazmaz. Görseller varsayılan olarak
Git dışındaki ``evals/local/images/`` altındadır; yalnızca dosya adı, sha256 ve soru kimliği commit'lenir.
ÖSYM veya yayınevi görseli eklenmez.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "apps/api/tests/fixtures/question_pack/teacherai_24.json"
KEY = ROOT / "evals/datasets/original-24.answers.json"
TEMPLATE = ROOT / "evals/datasets/original-24.answers.template.json"
MANIFEST = ROOT / "evals/datasets/original-24.images.json"
IMAGES = ROOT / "evals/local/images"
VARIANTS = ROOT / "evals/ocr_variants/manifest.json"
TRAP_TAGS = Literal["nested_radical_scope", "radical_scope", "exponent_precedence", "fraction_bar_scope", "choice_bait",
                    "negation", "intermediate_value", "unit_conversion", "graph_reading", "premise_combination", "sign"]


class KeyEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[MPCB][0-9]{2}$")
    expected_choice: str | None = Field(default=None, pattern=r"^[A-E]$")
    expected_value: str | None = Field(default=None, max_length=200)
    answer_origin: Literal["teacher"]
    notes: str | None = Field(default=None, max_length=1000)
    trap_tags: list[TRAP_TAGS] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def has_answer(self):
        if self.expected_choice is None and self.expected_value is None:
            raise ValueError("Cevap anahtarı satırı en az bir beklenen değer taşımalı.")
        return self


class AnswerKey(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pack: Literal["teacherai_24"]
    answer_origin: Literal["teacher"]
    reviewed_by: str = Field(min_length=1, max_length=120)
    entries: list[KeyEntry] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def unique(self):
        ids = [entry.id for entry in self.entries]
        if len(set(ids)) != len(ids):
            raise ValueError("Soru kimlikleri benzersiz olmalı.")
        return self


class ImageEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,120}\.(png|jpe?g|webp|heic)$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    question_id: str | None = Field(default=None, pattern=r"^[MPCB][0-9]{2}$")
    # TA-007: OCR dayanıklılık varyantı ayrı örnek değildir; özgün soruya bağlıdır (ör. M01_light_blur.png → M01).
    kind: Literal["ocr_variant"] | None = None


def pack_ids() -> list[str]:
    return [question["id"] for question in json.loads(PACK.read_text(encoding="utf-8"))["questions"]]


def load_key(path: Path = KEY) -> AnswerKey | None:
    """Anahtar yoksa None; geçersizse ValidationError. Bilinmeyen soru kimliği reddedilir."""
    if not path.exists():
        return None
    key = AnswerKey.model_validate_json(path.read_text(encoding="utf-8"))
    unknown = sorted({entry.id for entry in key.entries} - set(pack_ids()))
    if unknown:
        raise ValueError(f"Pakette olmayan soru kimliği: {', '.join(unknown)}")
    return key


def template() -> dict:
    """Doldurulacak şablon. Cevap alanları boştur; şablon geçerli bir anahtar değildir."""
    return {"pack": "teacherai_24", "answer_origin": "teacher", "reviewed_by": "",
            "entries": [{"id": qid, "expected_choice": None, "expected_value": None, "answer_origin": "teacher",
                         "notes": None, "trap_tags": []} for qid in pack_ids()]}


def manifest(images: Path = IMAGES) -> list[dict]:
    """Yerel görsellerin adı, sha256 değeri ve dosya adından okunan soru kimliği (ör. M03_kok.png → M03)."""
    rows = []
    # TA-007: varyant türü dosya adından tahmin edilmez; yalnız içe aktarılan varyant manifestinden gelir.
    listed = VARIANTS.exists() and json.loads(VARIANTS.read_text(encoding="utf-8")).get("variants", [])
    variants = {item["file"] for item in listed or []}
    for path in sorted(images.glob("*")) if images.exists() else []:
        if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".heic"}:
            continue
        match = re.match(r"^([MPCB][0-9]{2})(?=[_.-])", path.name)
        qid = match.group(1) if match else None
        row = ImageEntry(file=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), question_id=qid,
                         kind="ocr_variant" if path.name in variants else None).model_dump()
        if row["kind"] is None:
            row.pop("kind")
        rows.append(row)
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", nargs="?", choices=["validate", "template", "manifest"], default="validate")
    args = parser.parse_args(argv)
    if args.mode == "template":
        TEMPLATE.write_text(json.dumps(template(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Şablon yazıldı: {TEMPLATE.relative_to(ROOT)}. Doldurup {KEY.name} adıyla kaydedin.")
        return 0
    if args.mode == "manifest":
        rows = manifest()
        MANIFEST.write_text(json.dumps({"images_dir": "evals/local/images", "images": rows}, indent=2) + "\n", encoding="utf-8")
        print(f"{len(rows)} görsel manifeste yazıldı: {MANIFEST.relative_to(ROOT)}")
        return 0
    try:
        key = load_key()
        for item in json.loads(MANIFEST.read_text(encoding="utf-8"))["images"] if MANIFEST.exists() else []:
            ImageEntry.model_validate(item)
    except (ValidationError, ValueError) as exc:
        print(f"Geçersiz: {exc}")
        return 1
    print("Öğretmen cevap anahtarı bekleniyor (dosya yok)." if key is None else f"Anahtar geçerli: {len(key.entries)} satır.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
