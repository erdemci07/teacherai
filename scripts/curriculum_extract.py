"""Resmî MEB öğretim programı PDF'inden kazanım/öğrenme çıktısı envanteri çıkarır (TA-006).

Çıktı yalnız şunları taşır: resmî kod, sınıf, üst başlık (ünite/tema/alt öğrenme alanı/konu adı), PDF sayfa
numarası. Resmî kazanım cümleleri ve açıklamaları **kopyalanmaz**; birebir metnin yeniden kullanım izni
doğrulanmadı (ADR TA-006 §Karar 3). PDF depoya alınmaz; dosyanın sha256 özeti kayda yazılır.

Kullanım (PDF önce resmî adresten ayrı bir dizine indirilir; ``pdftotext`` gerekir):

    python -m scripts.curriculum_extract <program_id> <pdf> > çıktı.json

Bu betik ağ çağrısı yapmaz ve çalışma zamanında kullanılmaz. Çıktı, ``features/curriculum/data/programs``
altındaki program dosyasının ``units``/``outcomes`` alanlarını yeniden üretmek ve denetlemek içindir.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

TR = str.maketrans({"ç": "c", "ğ": "g", "ı": "i", "İ": "i", "ö": "o", "ş": "s", "ü": "u", "Ç": "c", "Ğ": "g",
                    "Ö": "o", "Ş": "s", "Ü": "u", "â": "a", "Â": "a", "î": "i", "û": "u"})


def slug(text: str) -> str:
    value = text.translate(TR).casefold()
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")[:96] or "konu"


def ascii_code(code: str) -> str:
    return code.translate(TR).upper()


@dataclass(frozen=True)
class Layout:
    """Kod düzeni. ``depth`` kazanım kodundaki sayı adedi; ``levels`` başlık seviyelerinin sayı adetleri."""

    prefix: str          # "M.", "F.", "" (2018 ortaöğretim), "MAT.", "FB.", "FİZ." …
    depth: int
    levels: tuple[int, ...]
    heading: str | None = None  # TYMM: "TEMA" veya "ÜNİTE" başlıkları
    grades: tuple[int, ...] = ()


LAYOUTS = {
    "meb-2018.matematik.1-8": Layout("M.", 4, (2, 3), grades=(5, 6, 7, 8)),
    "meb-2018.fen-bilimleri.3-8": Layout("F.", 4, (2, 3), grades=(5, 6, 7, 8)),
    "meb-2018.matematik.9-12": Layout("", 4, (2, 3), grades=(9, 10, 11, 12)),
    "meb-2018.fizik.9-12": Layout("", 4, (2, 3), grades=(9, 10, 11, 12)),
    "meb-2018.kimya.9-12": Layout("", 4, (2, 3), grades=(9, 10, 11, 12)),
    "meb-2018.biyoloji.9-12": Layout("", 4, (2, 3), grades=(9, 10, 11, 12)),
    "tymm-2026.matematik.5-8": Layout("MAT.", 3, (), "TEMA", (5, 6, 7, 8)),
    "tymm-2026.fen-bilimleri.3-8": Layout("FB.", 3, (), "ÜNİTE", (5, 6, 7, 8)),
    "tymm-2026.matematik.9-12": Layout("MAT.", 3, (), "TEMA", (9, 10, 11, 12)),
    "tymm-2026.fizik.9-12": Layout("FİZ.", 3, (), "ÜNİTE", (9, 10, 11, 12)),
    "tymm-2026.kimya.9-12": Layout("KİM.", 3, (), "TEMA", (9, 10, 11, 12)),
    "tymm-2026.biyoloji.9-12": Layout("BİY.", 3, (), "TEMA", (9, 10, 11, 12)),
}

# Başlık metni bu işaretlerden birinde biter (süre, kavram listesi, açıklama veya sonraki kod).
TITLE_END = re.compile(r"\s+(?:Önerilen Süre|Terimler (?:ve|veya) [Kk]avramlar|Konu ?/ ?Kavramlar|Sembol ve Gösterimler"
                       r"|Anahtar [Kk]avramlar|Bu ünitede|Bu bölümde|\d+\s*$|/ )")


NOISE = re.compile(r"\d|Kazanım|Süre|Ünite|Yüzde|Ders Saati|Toplam|Oran", re.IGNORECASE)


def pages_of(text: str) -> list[int]:
    """Her karakterin PDF sayfa numarası (1 tabanlı); pdftotext sayfaları form feed ile ayırır."""
    marks, page = [], 1
    for char in text:
        marks.append(page)
        if char == "\f":
            page += 1
    return marks


def _title(raw: str) -> str | None:
    raw = " ".join(raw.split())
    raw = TITLE_END.split(raw, maxsplit=1)[0]
    raw = re.split(r"\s+(?=[A-ZÇĞİÖŞÜ]\.\d|\d+\.\d+\.)", raw, maxsplit=1)[0].strip(" :-–")
    raw = re.split(r"\s+\d", raw, maxsplit=1)[0]  # tablo hücresindeki sayılar başlık değildir
    words = raw.split()
    if not words or len(words) > 12 or not words[0][:1].isupper():
        return None
    return raw[:160]


def extract(program_id: str, text: str) -> dict:
    layout = LAYOUTS[program_id]
    prefix = re.escape(layout.prefix)
    gap = r"\s?" if layout.prefix else ""  # 2018 PDF'inde "M. 8.1." yazım hatası var
    code = re.compile(rf"(?<![\w.]){prefix}{gap}((?:\d{{1,2}}\.)+\d{{1,2}})(?:\.(?=[^\s\d.])|\.?(?=\s))")
    marks = pages_of(text)
    outcomes: dict[str, dict] = {}
    headings: dict[str, dict] = {}
    pending: dict[int, tuple[str, int]] = {}
    candidates: dict[str, list[dict]] = {}
    events = [(m.start(), "code", m) for m in code.finditer(text)]
    if layout.heading:
        pattern = re.compile(rf"(?m)^\s*(\d{{1,2}})\s*\.\s*{layout.heading}\s*:\s*([^\n]+)")
        events += [(m.start(), "heading", m) for m in pattern.finditer(text)]
    for _, kind, match in sorted(events, key=lambda item: item[0]):
        if kind == "heading":
            title = re.sub(r"\s*\(\d\)\s*$", "", " ".join(match.group(2).split())).strip()
            pending[int(match.group(1))] = (title, marks[match.start()])
            continue
        numbers = [int(part) for part in match.group(1).split(".")]
        grade = numbers[0]
        if grade not in layout.grades:
            continue
        official = layout.prefix + match.group(1)
        following = text[match.end(): match.end() + 400]
        if len(numbers) == layout.depth:
            words = following.split()
            # İçindekiler aralıkları ("M.3.2.4.1. - M.3.2.4.3.") ve tablo hücreleri kazanım sayılmaz.
            if official in outcomes or len(words) < 3 or words[0][:1] in "-–" or code.match(following.lstrip()):
                continue
            parents = {level: layout.prefix + ".".join(map(str, numbers[:level])) for level in layout.levels}
            unit = layout.prefix + ".".join(map(str, numbers[:2])) if layout.heading else parents[layout.levels[0]]
            outcomes[official] = {"official_code": official, "grade": grade, "unit": unit,
                                  "topic": parents.get(layout.levels[-1]) if layout.levels else None,
                                  "page": marks[match.start()]}
            if layout.heading and unit not in headings and numbers[1] in pending:
                title, page = pending[numbers[1]]
                headings[unit] = {"code": unit, "grade": grade, "level": 1, "title": title, "page": page}
        elif len(numbers) in layout.levels:
            title = _title(following)
            if title:
                candidates.setdefault(official, []).append({"code": official, "grade": grade,
                                                            "level": layout.levels.index(len(numbers)) + 1,
                                                            "title": title, "page": marks[match.start()]})
    for official, found in candidates.items():
        # Ön sayfadaki sayı/süre tablosu hücreleri başlığa sayı ve tablo sözcükleri karıştırır; temiz aday seçilir.
        clean = [item for item in found if not NOISE.search(item["title"])] or found
        counts = {}
        for item in clean:
            counts[item["title"]] = counts.get(item["title"], 0) + 1
        best = max(counts.values())
        # Eşitlikte son aday: kazanım bölümündeki başlık ön sayfadaki tablodan sonra gelir.
        headings[official] = [item for item in clean if counts[item["title"]] == best][-1]
    units = sorted(headings.values(), key=lambda item: _key(item["code"]))
    return {"units": units, "outcomes": sorted(outcomes.values(), key=lambda item: _key(item["official_code"]))}


def _key(code: str):
    return [int(part) for part in re.findall(r"\d+", code)]


SUBJECTS = {"matematik": "mathematics", "fen-bilimleri": "science", "fizik": "physics", "kimya": "chemistry",
            "biyoloji": "biology"}
GEOMETRY = re.compile(r"geometri|üçgen|çember|dörtgen|çokgen|katı cisim|\bdönüşüm(?:ler)?\b|prizma|\baçılar\b"
                      r"|\buzay\b|daire|\beşlik\b|benzerlik|cisim", re.IGNORECASE)
NOT_GEOMETRY = re.compile(r"fonksiyon|formül|trigonometri", re.IGNORECASE)
SMALL = {"ve", "ile", "ya", "da", "de", "veya", "ya da", "için"}


def tr_title(text: str) -> str:
    """Tamamı büyük harfli başlığı Türkçe kurallarla başlık biçimine çevirir; diğerlerini korur."""
    text = re.sub(r"(\w)- (\w)", r"\1\2", " ".join(text.split()))  # satır sonu tirelemesi
    if text != text.upper():
        return text
    words = text.replace("I", "ı").replace("İ", "i").lower().split()
    return " ".join(word if index and word in SMALL else word[:1].replace("i", "İ").upper() + word[1:]
                    for index, word in enumerate(words))


def build_program_file(program_id: str, extraction: dict, descriptions: dict | None = None) -> dict:
    """Çıkarım sonucunu ``teacherai.curriculum_program`` biçimine çevirir. Aynı girdi aynı çıktıyı verir."""
    subject = SUBJECTS[program_id.split(".")[1]]
    terminology = "kazanim" if program_id.startswith("meb-2018") else "ogrenme_ciktisi"
    items = (descriptions or {}).get("items", {})
    review = (descriptions or {}).get("review", "unreviewed")
    titles = {heading["code"]: tr_title(heading["title"]) for heading in extraction["units"]}
    units = []
    for heading in extraction["units"]:
        title = titles[heading["code"]]
        parent_code = heading["code"].rsplit(".", 1)[0] if heading["level"] == 2 else None
        parent = f"{program_id}::{ascii_code(parent_code)}" if parent_code in titles else None
        context = f"{title} {titles.get(parent_code, '')}"
        geometry = subject == "mathematics" and bool(GEOMETRY.search(context)) and not NOT_GEOMETRY.search(context)
        units.append({"id": f"{program_id}::{ascii_code(heading['code'])}", "program_id": program_id,
                      "grade": heading["grade"], "official_code": heading["code"], "level": heading["level"],
                      "title_tr": title, "discipline": "geometry" if geometry else subject, "page": heading["page"],
                      "parent_id": parent})
    discipline = {unit["official_code"]: unit["discipline"] for unit in units}
    outcomes = []
    for item in extraction["outcomes"]:
        code = item["official_code"]
        topic = item.get("topic")
        heading = topic or item["unit"]
        described = items.get(code, {})
        record = {"id": f"{program_id}::{ascii_code(code)}", "program_id": program_id, "subject": subject,
                  "discipline": discipline.get(heading, discipline.get(item["unit"], subject)), "grade": item["grade"],
                  "unit_id": f"{program_id}::{ascii_code(item['unit'])}",
                  "topic_id": f"{program_id}::{ascii_code(topic)}" if topic else None,
                  "topic_key": slug(titles.get(heading, heading)), "official_code": code, "terminology": terminology,
                  "page": item["page"], "source_status": "sourced", "review_status": "unreviewed"}
        if described.get("description_tr"):
            record["description_tr"] = described["description_tr"]
            record["description_review"] = review
        if described.get("aliases"):
            record["aliases"] = sorted(described["aliases"])
        outcomes.append({key: value for key, value in record.items() if value is not None})
    return {"schema_name": "teacherai.curriculum_program", "version": "2.0.0", "program_id": program_id,
            "extraction_tool": "scripts.curriculum_extract (pdftotext + resmî kod deseni)", "units": units,
            "outcomes": outcomes}


def dump_program_file(document: dict) -> str:
    """Satır başına bir kayıt: incelemede fark okunur kalır."""
    head = {key: value for key, value in document.items() if key not in {"units", "outcomes"}}
    lines = ["{"] + [f"  {json.dumps(key)}: {json.dumps(value, ensure_ascii=False)}," for key, value in head.items()]
    for name in ("units", "outcomes"):
        rows = [f"    {json.dumps(row, ensure_ascii=False)}" for row in document[name]]
        lines.append(f'  "{name}": [')
        lines.append(",\n".join(rows))
        lines.append("  ]," if name == "units" else "  ]")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("program_id", choices=sorted(LAYOUTS))
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--program-file", action="store_true", help="kayıt biçiminde (data/programs) yaz")
    parser.add_argument("--descriptions", type=Path, help="data/descriptions/<program_id>.json")
    args = parser.parse_args(argv)
    digest = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    raw = subprocess.run(["pdftotext", "-enc", "UTF-8", str(args.pdf), "-"], check=True, capture_output=True)
    text = raw.stdout.decode("utf-8")
    extraction = extract(args.program_id, text)
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    if args.program_file:
        descriptions = json.loads(args.descriptions.read_text(encoding="utf-8")) if args.descriptions else None
        sys.stdout.write(dump_program_file(build_program_file(args.program_id, extraction, descriptions)))
        sys.stderr.write(f"sha256={digest} pages={text.count(chr(12))}\n")
        return
    result = {"program_id": args.program_id, "pdf_sha256": digest, "pdf_pages": text.count("\f") or None, **extraction}
    json.dump(result, sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
