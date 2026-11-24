"""Öğretmen/uzman inceleme formlarının (CSV) dışa ve içe aktarımı (TA-007 §11–15).

    python -m scripts.review_import export <klasör>              # güncel sürümlerle boş inceleme CSV'leri
    python -m scripts.review_import validate <dosya.csv>         # bilgi girdisi veya yöntem politikası formu
    python -m scripts.review_import apply <dosya.csv> --write    # yalnız geçerli ve yetkili satırları kaydeder

Kurallar:

- Satır yalnız ``karar`` doluysa ve ``not_reviewed`` değilse işlenir. Boş satır karar sayılmaz.
- İnceleyen başvurusu (``teacher:…``/``expert:…``) proje sahibinin inceleyen kaydında, ilgili aşama, alan, rol ve
  tarih için yetkili olmalıdır. Üretim kaydı boştur; bugün hiçbir satır uygulanamaz.
- Formdaki sürüm güncel sürüm değilse (ör. TA-007'de düzeltilen 13 girdi) satır bayattır ve reddedilir.
- ``approve`` ancak girdi kaynaklıysa ve hak sınıflandırması ayrıca verilecekse kaydedilir; hak kararı bu formla
  verilmez. Düzeltme önerisi (``duzeltilmis_ifade_ve_kosullar``) içeriği değiştirmez; ``request_revision``
  olarak kaydedilir ve yeni sürüm ayrı yazılır.
- AI ön inceleme notu karar değildir ve hiçbir zaman içeri alınmaz.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import date
from pathlib import Path

from apps.api.app.features.curriculum import methods, registry_v2
from apps.api.app.features.curriculum import registry as legacy
from apps.api.app.features.education.base import Subject
from apps.api.app.features.education.knowledge import (
    KnowledgeFile,
    ReviewRecord,
    content_digest,
)
from apps.api.app.features.knowledge import registry as knowledge_registry
from apps.api.app.features.knowledge import reviewers as reviewer_registry

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_HEADER = ["kayit_id", "surum", "repo_durumu", "baslik", "mevcut_bilimsel_ifade", "kosullar", "istisnalar",
                    "repo_kaynak_bolumleri", "AI_on_inceleme_notu_onay_degildir", "inceleyen_takma_ad", "rol", "tarih",
                    "karar", "duzeltilmis_ifade_ve_kosullar", "gerekce_ve_kaynak", "duzeye_uygunluk_ve_not"]
POLICY_HEADER = ["politika_id", "sinif", "program", "mevcut_durum", "konu", "ozet_islemler", "inceleme_notu", "kazanim",
                 "inceleyen_takma_ad", "tarih", "karar", "duzeltme_ve_gerekce"]
DECISIONS = {"approve", "request_revision", "reject", "not_reviewed"}
ROLES = {"öğretmen": "teacher", "ogretmen": "teacher", "teacher": "teacher", "alan uzmanı": "subject_expert",
         "uzman": "subject_expert", "subject_expert": "subject_expert", "expert": "subject_expert"}
STATUS = {"approve": "approved", "request_revision": "revision_requested", "reject": "rejected"}


def read_rows(path: Path) -> tuple[list[str], list[dict]]:
    text = path.read_bytes().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    return list(reader.fieldnames or []), list(reader)


def _date(value: str) -> date | None:
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError:
        return None


def check_knowledge_row(row: dict, registry, reviewers) -> tuple[dict | None, list[str]]:
    decision = (row.get("karar") or "").strip()
    if not decision or decision == "not_reviewed":
        return None, []
    entry_id = (row.get("kayit_id") or "").strip()
    problems = []
    if decision not in DECISIONS:
        return None, [f"{entry_id}: tanımsız karar '{decision}'"]
    entry = registry.entries.get(entry_id)
    if entry is None:
        return None, [f"{entry_id}: kayıt yok"]
    if str(entry.version) != (row.get("surum") or "").strip():
        problems.append(f"{entry_id}: form sürümü {row.get('surum')} güncel sürüm {entry.version} değil (bayat)")
    reviewer, on = (row.get("inceleyen_takma_ad") or "").strip(), _date(row.get("tarih"))
    role = ROLES.get((row.get("rol") or "").strip().casefold())
    if role is None:
        problems.append(f"{entry_id}: rol tanımsız")
    if on is None:
        problems.append(f"{entry_id}: tarih YYYY-AA-GG değil")
    rationale = (row.get("gerekce_ve_kaynak") or "").strip()
    if not rationale:
        problems.append(f"{entry_id}: gerekçe ve doğrulanan kaynak boş")
    if role and on and not reviewer_registry.authorized(reviewers, reviewer, "scientific", entry.subject, role, on):
        problems.append(f"{entry_id}: inceleyen '{reviewer}' yetkili değil (proje sahibinin kaydında yok)")
    if decision == "approve" and (row.get("duzeltilmis_ifade_ve_kosullar") or "").strip():
        problems.append(f"{entry_id}: düzeltme önerisiyle birlikte onay verilemez (önce yeni sürüm)")
    if decision == "approve" and on and entry.reviews and on < entry.reviews[-1].reviewed_on:
        problems.append(f"{entry_id}: onay tarihi son incelemeden önce")
    if problems:
        return None, problems
    note = (row.get("duzeltilmis_ifade_ve_kosullar") or "").strip()
    review = ReviewRecord(reviewer=reviewer, role=role, reviewed_on=on, reviewed_version=entry.version,
                          decision=decision, stage="scientific", content_digest=content_digest(entry),
                          rationale_tr=(rationale + (f" Düzeltme önerisi: {note}" if note else ""))[:2000])
    return {"entry_id": entry_id, "review": review}, []


def check_policy_row(row: dict, reviewers) -> tuple[dict | None, list[str]]:
    decision = (row.get("karar") or "").strip()
    if not decision or decision == "not_reviewed":
        return None, []
    policy_id = (row.get("politika_id") or "").strip()
    if decision not in DECISIONS:
        return None, [f"{policy_id}: tanımsız karar '{decision}'"]
    current = {p.legacy_id: p for p in registry_v2.migrate_v1_policies(legacy.default_registry())}
    policy = current.get(policy_id)
    if policy is None:
        return None, [f"{policy_id}: politika yok"]
    reviewer, on = (row.get("inceleyen_takma_ad") or "").strip(), _date(row.get("tarih"))
    problems = []
    if on is None:
        problems.append(f"{policy_id}: tarih YYYY-AA-GG değil")
    elif not reviewer_registry.authorized(reviewers, reviewer, "pedagogical", Subject.MATHEMATICS, "teacher", on):
        problems.append(f"{policy_id}: inceleyen '{reviewer}' yetkili değil (proje sahibinin kaydında yok)")
    if decision == "approve" and (row.get("duzeltme_ve_gerekce") or "").strip().lower().startswith("düzelt"):
        problems.append(f"{policy_id}: düzeltme isteyen satır onay olamaz")
    if problems:
        return None, problems
    return {"policy_id": policy_id, "decision": decision, "reviewer": reviewer, "on": on,
            "digest": methods.policy_digest(policy)}, []


def validate(path: Path, reviewers=None) -> tuple[str, list[dict], list[str]]:
    reviewers = reviewer_registry.default_reviewers() if reviewers is None else reviewers
    header, rows = read_rows(path)
    if header == KNOWLEDGE_HEADER:
        registry = knowledge_registry.default_knowledge()
        kind, checker = "knowledge", (lambda row: check_knowledge_row(row, registry, reviewers))
    elif header == POLICY_HEADER:
        kind, checker = "policy", (lambda row: check_policy_row(row, reviewers))
    else:
        return "unknown", [], ["Başlık satırı tanınmadı; formun sütunları değiştirilmemelidir."]
    accepted, problems = [], []
    for row in rows:
        item, issues = checker(row)
        problems += issues
        if item:
            accepted.append(item)
    return kind, accepted, problems


def apply_knowledge(accepted: list[dict]) -> int:
    data_dir = knowledge_registry.DATA
    changed = 0
    for name in knowledge_registry.SUBJECT_FILES:
        path = data_dir / f"{name}.json"
        file = KnowledgeFile.model_validate_json(registry_v2._read(path))
        updates = {item["entry_id"]: item["review"] for item in accepted}
        entries, touched = [], False
        for entry in file.entries:
            review = updates.get(entry.id)
            if review is not None:
                status = STATUS[review.decision]
                entry = entry.model_validate({**entry.model_dump(mode="json"), "status": status,
                                              "reviews": [*[r.model_dump(mode="json") for r in entry.reviews],
                                                          review.model_dump(mode="json")]})
                changed += 1
                touched = True
            entries.append(entry)
        if touched:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["entries"] = [entry.model_dump(mode="json", exclude_none=True) for entry in entries]
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return changed


def apply_policies(accepted: list[dict]) -> int:
    data = json.loads(legacy.DATA.read_text(encoding="utf-8"))
    changed = 0
    for item in accepted:
        for policy in data["policies"]:
            if policy["id"] != item["policy_id"]:
                continue
            if item["decision"] == "approve":
                policy.update(status="approved", authored_by=policy["authored_by"], approved_by=item["reviewer"],
                              approved_on=item["on"].isoformat(), approval_digest=item["digest"])
            else:
                policy.update(status="draft", approved_by=None, approved_on=None, approval_digest=None)
            changed += 1
    legacy.CurriculumRegistry.model_validate(data)
    legacy.DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed


def export(folder: Path) -> list[Path]:
    """Güncel sürümlerle boş inceleme formları. AI ön inceleme notu yalnız uyarıdır."""
    registry = knowledge_registry.default_knowledge()
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for name in knowledge_registry.SUBJECT_FILES:
        rows = [entry for entry in registry.entries.values()
                if entry.subject.value == name or (name == "mathematics" and entry.subject == Subject.GEOMETRY)]
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";")
        writer.writerow(KNOWLEDGE_HEADER)
        for entry in sorted(rows, key=lambda item: item.id):
            writer.writerow([entry.id, entry.version, entry.status, entry.title_tr, entry.statement_tr,
                             " / ".join(entry.conditions_tr), " / ".join(entry.exceptions_tr),
                             " ".join(item.url or item.source_id for item in entry.provenance),
                             "Bilimsel doğruluk, koşullar, istisnalar, düzey ve kaynak desteğini ayrı kontrol edin.",
                             "", "", "", "", "", "", ""])
        path = folder / f"{name}_inceleme.csv"
        path.write_text("﻿" + buffer.getvalue(), encoding="utf-8")
        written.append(path)
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=["export", "validate", "apply"])
    parser.add_argument("path", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    if args.mode == "export":
        for path in export(args.path):
            print(f"Yazıldı: {path}")
        return 0
    kind, accepted, problems = validate(args.path)
    for problem in problems:
        print(f"SORUN: {problem}")
    print(f"Form türü: {kind}; uygulanabilir satır: {len(accepted)}; sorun: {len(problems)}")
    if args.mode == "validate" or not accepted:
        return 1 if problems else 0
    if not args.write:
        print("--write verilmedi; hiçbir şey yazılmadı.")
        return 0
    changed = apply_knowledge(accepted) if kind == "knowledge" else apply_policies(accepted)
    print(f"{changed} kayıt güncellendi. Hak kararı ve yayım ayrı kapılardır.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
