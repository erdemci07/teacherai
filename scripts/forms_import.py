"""Google Forms / Sheets CSV dışa aktarımını öğretmen katkı *taslaklarına* çevirir (TA-008 §3.6).

    python -m scripts.forms_import inspect <yanıtlar.csv>                       # başlıkları listeler, eşleme önerir
    python -m scripts.forms_import convert <yanıtlar.csv> --mapping <eşleme.json>    # kuru çalıştırma (yazmaz)
    python -m scripts.forms_import convert <yanıtlar.csv> --mapping <eşleme.json> --write [--register]

İlkeler:

- Son CSV başlığı bilinmeden varsayım yapılmaz: sütunlar açık bir eşleme dosyasıyla bağlanır
  (örnek: ``docs/teachers/forms-mapping.example.json``). Eşlemede olmayan sütun okunmaz.
- Proje sahibinin Google hesabına erişilmez; yalnız proje sahibinin verdiği dışa aktarılmış dosya okunur.
- Kullanım izni açıkça "evet" değilse satır içeri alınmaz. Model eğitimi izni yalnız açık "evet" ile true.
- E-posta/telefon görülen satır alınmaz (formda kişisel bilgi istenmez).
- Konu belirtilmemiş genel pedagojik öneri ``general_pedagogy`` türüyle ve ``genel`` konusuyla alınır; kazanım
  veya konu uydurulmaz.
- Artımlı içe aktarma: her satırın normalleştirilmiş içerik özeti ``data/contributions/forms-ledger.json``
  defterine yazılır; aynı satır (veya aynı dosyadaki yinelenen satır) ikinci kez alınmaz.
- Çıktı yalnız taslaktır: onay, yayın veya bilgi girdisi değildir. ``--register`` yalnız ``submitted`` aşamasını
  ekler; diğer aşamalar insan incelemesiyle eklenir (bkz. docs/governance/TA-007-review-workflow.md).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

from apps.api.app.features.education.contribution import (
    ContributionRecord,
    ContributionRegister,
    TeacherContribution,
)

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "data/contributions"
LEDGER = FOLDER / "forms-ledger.json"
REGISTER = FOLDER / "register.json"
MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 2000
MAX_CELL = 4000
PERSONAL = [re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), re.compile(r"(?:\+?90|0)?\s?5\d{2}\s?\d{3}\s?\d{2}\s?\d{2}")]
REF = re.compile(r"^(teacher|expert):[a-z0-9][a-z0-9_-]{2,63}$")
# Eşleme anahtarı → katkı türü. Sırası çıktı sırasıdır.
TEXT_FIELDS = {"misconceptions": "common_error", "strategies": "preferred_strategy",
               "alternatives": "alternative_explanation", "visual": "visual_strategy",
               "curriculum": "class_level_method", "general": "general_pedagogy"}
META_FIELDS = ("timestamp", "alias", "role", "subject", "experience", "grades_exams", "topic", "consent_use",
               "consent_training")


class MappingError(ValueError):
    pass


def _norm(text: str) -> str:
    return " ".join((text or "").replace("İ", "i").replace("I", "ı").lower().split())


def read_csv(path: Path, delimiter: str | None = None) -> tuple[list[str], list[dict]]:
    if path.stat().st_size > MAX_BYTES:
        raise MappingError("CSV dosyası çok büyük.")
    text = path.read_bytes().decode("utf-8-sig")
    if delimiter is None:
        delimiter = ";" if text.split("\n", 1)[0].count(";") > text.split("\n", 1)[0].count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = []
    for index, row in enumerate(reader):
        if index >= MAX_ROWS:
            raise MappingError("Satır sınırı aşıldı.")
        rows.append({key: (value or "") for key, value in row.items() if key is not None})
    return list(reader.fieldnames or []), rows


def load_mapping(path: Path, headers: list[str]) -> dict:
    mapping = json.loads(path.read_text(encoding="utf-8"))
    columns = mapping.get("columns", {})
    unknown_keys = sorted(set(columns) - set(META_FIELDS) - set(TEXT_FIELDS))
    if unknown_keys:
        raise MappingError(f"Eşlemede tanımsız alan: {', '.join(unknown_keys)}")
    missing = sorted({column for column in columns.values() if column} - set(headers))
    if missing:
        raise MappingError(f"CSV'de olmayan sütun eşlendi: {', '.join(missing)}")
    for key in ("subject", "consent_use"):
        if not columns.get(key) and not mapping.get(f"default_{key}"):
            raise MappingError(f"'{key}' için sütun veya varsayılan değer gerekli.")
    if not any(columns.get(key) for key in TEXT_FIELDS):
        raise MappingError("En az bir katkı metni sütunu eşlenmeli.")
    return mapping


def _choice(value: str, mapping: dict) -> bool | None:
    text = _norm(value)
    yes = {_norm(item) for item in mapping.get("yes_values", ["evet"])}
    no = {_norm(item) for item in mapping.get("no_values", ["hayır"])}
    if text in yes:
        return True
    if text in no:
        return False
    return None  # boş veya tanınmayan yanıt: karar sayılmaz


def row_digest(row: dict, mapping: dict) -> str:
    """Zaman damgası dışındaki eşlenmiş içerik; boşluk ve büyük/küçük harf farkı yinelemeyi gizlemez."""
    columns = mapping["columns"]
    payload = {key: _norm(row.get(column, "")) for key, column in sorted(columns.items()) if column and key != "timestamp"}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def convert_row(row: dict, mapping: dict, digest: str) -> tuple[dict | None, list[str]]:
    columns = mapping["columns"]

    def cell(key: str) -> str:
        column = columns.get(key)
        return (row.get(column, "") if column else "").strip()[:MAX_CELL]

    problems = []
    for key in (*TEXT_FIELDS, "experience", "grades_exams", "topic"):
        if any(pattern.search(cell(key)) for pattern in PERSONAL):
            problems.append(f"kişisel bilgi olabilir ({key})")
    consent_cell = cell("consent_use") or mapping.get("default_consent_use", "")
    if _choice(consent_cell, mapping) is not True:
        problems.append("kullanım izni açıkça verilmedi")
    subject_raw = cell("subject") or mapping.get("default_subject", "")
    subject = mapping.get("subject_values", {}).get(subject_raw.strip()) or (
        subject_raw if subject_raw in {"mathematics", "physics", "chemistry", "biology", "science", "geometry"} else None)
    if subject is None:
        problems.append(f"alan eşlenemedi ({subject_raw[:40] or 'boş'})")
    alias = cell("alias").lower()
    if alias and not REF.match(alias):
        problems.append("takma ad 'teacher:…' veya 'expert:…' biçiminde değil")
    if problems:
        return None, problems
    contributor = alias or f"teacher:form-{digest[:10]}"  # takma başvuru; kimlik değildir, proje sahibi eşler
    role = "subject_expert" if contributor.startswith("expert:") or _norm(cell("role")) in {"uzman", "alan uzmanı"} else "teacher"
    topic = re.sub(r"[^a-z0-9_]", "", cell("topic").lower()) or "genel"
    items = []
    for key, kind in TEXT_FIELDS.items():
        text = cell(key)
        if text:
            items.append({"kind": kind, "topic": topic if kind != "general_pedagogy" else "genel", "text_tr": text})
    if not items:
        return None, ["doldurulmuş katkı alanı yok"]
    submitted = mapping.get("default_date") or date.today().isoformat()
    stamp = cell("timestamp")
    for pattern in ("%d.%m.%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S"):
        try:
            submitted = datetime.strptime(stamp, pattern).date().isoformat()
            break
        except ValueError:
            continue
    experience = " · ".join(part for part in (cell("experience"), cell("grades_exams")) if part) or None
    record = {"schema_name": "teacherai.teacher_contribution", "version": "1.0.0", "contributor": contributor,
              "role": role, "subject": subject, "submitted_on": submitted, "consent_use": True,
              "consent_model_training": _choice(cell("consent_training"), mapping) is True,
              "experience_tr": experience[:4000] if experience else None, "import_ref": f"google_forms:{digest[:16]}",
              "items": items}
    TeacherContribution.model_validate(record)
    return record, []


def load_ledger(path: Path = LEDGER) -> set[str]:
    if not path.exists():
        return set()
    return set(json.loads(path.read_text(encoding="utf-8")).get("digests", []))


def convert(path: Path, mapping_path: Path, ledger: set[str] | None = None) -> dict:
    headers, rows = read_csv(path)
    mapping = load_mapping(mapping_path, headers)
    seen = set(ledger if ledger is not None else load_ledger())
    report = {"rows": len(rows), "accepted": [], "skipped": []}
    for index, row in enumerate(rows, 2):
        digest = row_digest(row, mapping)
        if digest in seen:
            report["skipped"].append({"row": index, "reason": "yinelenen veya daha önce alınmış satır"})
            continue
        record, problems = convert_row(row, mapping, digest)
        if record is None:
            report["skipped"].append({"row": index, "reason": "; ".join(problems)})
            continue
        seen.add(digest)
        report["accepted"].append({"row": index, "digest": digest, "record": record})
    return report


def write(report: dict, register: bool = False) -> list[Path]:
    from scripts import teacher_contributions

    written = []
    ledger = load_ledger()
    current = teacher_contributions.load_register() if register else None
    records = list(current.records) if current else []
    for item in report["accepted"]:
        record = item["record"]
        name = f"forms-{item['digest'][:16]}.json"
        target = FOLDER / name
        if target.exists():
            continue
        target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(target)
        ledger.add(item["digest"])
        if register:
            contribution = TeacherContribution.model_validate(record)
            records.append(ContributionRecord(contribution_id=f"forms-{item['digest'][:16]}", path=name, events=[{
                "stage": "submitted", "on": record["submitted_on"], "by": record["contributor"], "role": record["role"],
                "content_digest": teacher_contributions.contribution_digest(contribution)}]))
    LEDGER.write_text(json.dumps({"schema_name": "teacherai.forms_ledger", "version": "1.0.0",
                                  "digests": sorted(ledger)}, indent=1) + "\n", encoding="utf-8")
    if register:
        data = ContributionRegister(schema_name="teacherai.contribution_register", version="1.0.0", records=records)
        REGISTER.write_text(data.model_dump_json(indent=1) + "\n", encoding="utf-8")
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=["inspect", "convert"])
    parser.add_argument("csv", type=Path)
    parser.add_argument("--mapping", type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--register", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.mode == "inspect":
            headers, rows = read_csv(args.csv)
            print(f"{len(rows)} satır, {len(headers)} sütun. Eşleme dosyasında bu başlıkları kullanın:")
            for header in headers:
                print(f"- {header}")
            return 0
        if args.mapping is None:
            raise MappingError("--mapping gerekli.")
        report = convert(args.csv, args.mapping)
    except (MappingError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"SORUN: {exc}")
        return 1
    print(f"Satır: {report['rows']}  alınabilir: {len(report['accepted'])}  atlanan: {len(report['skipped'])}")
    for item in report["skipped"]:
        print(f"ATLANDI satır {item['row']}: {item['reason']}")
    if args.write:
        for path in write(report, args.register):
            print(f"Taslak yazıldı: {path.relative_to(ROOT)}")
    elif report["accepted"]:
        print("--write verilmedi; hiçbir şey yazılmadı.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
