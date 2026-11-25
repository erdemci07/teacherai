"""Öğretmen katkı dosyalarını doğrular ve yönetişim durumunu raporlar (TA-006, TA-007).

    python -m scripts.teacher_contributions validate data/contributions/<dosya>.json
    python -m scripts.teacher_contributions validate-all     # data/contributions altındaki bütün .json dosyaları
    python -m scripts.teacher_contributions status           # register.json aşamaları ve yayım engelleri

Katkı onay değildir. Yayım için şu aşamaların hepsi, sırasıyla ve katkının *bugünkü* içerik özetiyle geçilir:
normalized → source_verified → scientific_review → pedagogical_review → rights_approved → published. Her aşamayı
yapan proje sahibinin inceleyen kaydında o aşama, alan, rol ve tarih için yetkilidir. Bilimsel ve öğretimsel
inceleme katkı sahibinden bağımsızdır. Geri çekilen, reddedilen veya yerine başkası geçen katkı yayımlanmaz.
Uygulama içi kullanım izni model eğitimi izni değildir. Bu araç çevrimdışıdır; çalışma zamanı katkı okumaz.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from apps.api.app.features.curriculum import registry_v2
from apps.api.app.features.education.contribution import (
    TERMINAL_STAGES,
    ContributionRecord,
    ContributionRegister,
    TeacherContribution,
)
from apps.api.app.features.knowledge import registry as knowledge
from apps.api.app.features.knowledge import reviewers as reviewer_registry

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "data/contributions"
REGISTER = FOLDER / "register.json"
REQUIRED = ("normalized", "source_verified", "scientific_review", "pedagogical_review", "rights_approved", "published")
# Katkı aşaması → inceleyen kaydındaki yetki aşaması.
AUTHORITY = {"normalized": "publication", "source_verified": "source_verification", "scientific_review": "scientific",
             "pedagogical_review": "pedagogical", "rights_approved": "rights", "published": "publication",
             "revision_requested": "scientific", "rejected": "scientific", "superseded": "publication"}
INDEPENDENT = {"scientific_review", "pedagogical_review"}




def validate(path: Path) -> list[str]:
    contribution = TeacherContribution.model_validate_json(registry_v2._read(path))
    outcomes = set(registry_v2.default_registry().outcomes)
    entries = set(knowledge.default_knowledge().entries)
    problems = []
    for index, item in enumerate(contribution.items):
        problems += [f"öğe {index}: tanımsız kazanım {ref}" for ref in item.outcome_ids if ref not in outcomes]
        problems += [f"öğe {index}: tanımsız bilgi girdisi {ref}" for ref in item.knowledge_ids if ref not in entries]
    return problems


def contribution_digest(contribution: TeacherContribution) -> str:
    canonical = json.dumps(contribution.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_register(path: Path = REGISTER) -> ContributionRegister:
    if not path.exists():
        return ContributionRegister(schema_name="teacherai.contribution_register", version="1.0.0")
    return ContributionRegister.model_validate_json(path.read_bytes())


def publication_blockers(record: ContributionRecord, contribution: TeacherContribution, reviewers=None) -> list[str]:
    """Boş liste: katkı yayımlanmış ve bugünkü içerikle geçerli. Aksi halde engel nedenleri."""
    reviewers = reviewer_registry.default_reviewers() if reviewers is None else reviewers
    digest = contribution_digest(contribution)
    reasons = []
    last = record.events[-1].stage
    if last in TERMINAL_STAGES or last == "revision_requested":
        reasons.append(f"stage:{last}")
    # Son "revision_requested" sonrası aşamalar sayılır; öncekiler düzeltmeyle geçersizdir.
    cut = max((i for i, event in enumerate(record.events) if event.stage == "revision_requested"), default=-1)
    events = record.events[cut + 1:]
    position = -1
    for stage in REQUIRED:
        found = [(i, event) for i, event in enumerate(events) if event.stage == stage]
        if not found:
            reasons.append(f"missing:{stage}")
            continue
        index, event = found[-1]
        if index < position:
            reasons.append(f"out_of_order:{stage}")
        position = max(position, index)
        if event.content_digest != digest:
            reasons.append(f"stale:{stage}")
        if not reviewer_registry.authorized(reviewers, event.by, AUTHORITY[stage], contribution.subject, event.role,
                                            event.on):
            reasons.append(f"not_authorized:{stage}")
        if stage in INDEPENDENT and event.by == contribution.contributor:
            reasons.append(f"not_independent:{stage}")
    return sorted(set(reasons))


def training_allowed(record: ContributionRecord | None, contribution: TeacherContribution) -> bool:
    """Model eğitimi için ayrı, açık izin ve geri çekilmemiş katkı. TeacherAI bugün model eğitimi yapmaz."""
    withdrawn = record is not None and any(event.stage == "withdrawn" for event in record.events)
    return contribution.consent_model_training and not withdrawn


SNAPSHOT = ROOT / "apps/api/app/features/knowledge/data/contribution_publications.json"


def snapshot(register: ContributionRegister | None = None, reviewers=None) -> dict:
    """TA-008: çalışma zamanının okuduğu değişmez yayın anlık görüntüsü. Yalnız engelsiz yayımlanmış katkılar
    ``published`` olur; geri çekilen, reddedilen, yerine başkası geçen veya düzeltme istenen katkılar durumlarıyla
    yazılır ve çalışma zamanında uygunluğu düşürür. Süren (yayımlanmamış) katkılar yazılmaz."""
    register = register or load_register()
    records = []
    for record in sorted(register.records, key=lambda item: item.contribution_id):
        contribution = TeacherContribution.model_validate_json(registry_v2._read(FOLDER / record.path))
        last = record.events[-1]
        if last.stage in TERMINAL_STAGES or last.stage == "revision_requested":
            status, published_by = last.stage, None
        elif last.stage == "published" and not publication_blockers(record, contribution, reviewers):
            status, published_by = "published", last.by
        else:
            continue
        records.append({"contribution_id": record.contribution_id, "contributor": contribution.contributor,
                        "subject": contribution.subject.value, "content_digest": contribution_digest(contribution),
                        "status": status, "decided_on": last.on.isoformat(), "published_by": published_by,
                        "consent_use": contribution.consent_use,
                        "consent_model_training": contribution.consent_model_training and status == "published"})
    register_bytes = registry_v2._read(REGISTER) if REGISTER.exists() else b""
    dates = [item["decided_on"] for item in records]
    return {"schema_name": "teacherai.contribution_publications", "version": "1.0.0",
            "generated_on": max(dates) if dates else None,
            "register_digest": hashlib.sha256(register_bytes).hexdigest() if register_bytes else None,
            "records": records}


def _snapshot_text(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["validate", "validate-all", "status", "snapshot"])
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("path", nargs="?", type=Path)
    args = parser.parse_args(argv)
    if args.mode == "snapshot":
        text = _snapshot_text(snapshot())
        if args.check:
            current = SNAPSHOT.read_text(encoding="utf-8") if SNAPSHOT.exists() else ""
            if json.loads(current or "{}") != json.loads(text):
                raise SystemExit("Katkı yayın anlık görüntüsü güncel değil: python -m scripts.teacher_contributions snapshot --write")
            print("Katkı yayın anlık görüntüsü güncel.")
            return
        if args.write:
            SNAPSHOT.write_text(text, encoding="utf-8", newline="\n")
            print(f"Yazıldı: {SNAPSHOT.relative_to(ROOT)}")
        else:
            print(text)
        return
    if args.mode == "status":
        register = load_register()
        for record in register.records:
            contribution = TeacherContribution.model_validate_json(registry_v2._read(FOLDER / record.path))
            print(json.dumps({"contribution_id": record.contribution_id, "stage": record.events[-1].stage,
                              "publication_blockers": publication_blockers(record, contribution),
                              "training_allowed": training_allowed(record, contribution)}, ensure_ascii=False))
        if not register.records:
            print("Katkı kaydı yok (register.json boş veya yok). Onaylı/yayımlanmış katkı: 0.")
        return
    paths = sorted(p for p in FOLDER.glob("*.json") if p.name != "register.json") if args.mode == "validate-all" else [args.path]
    failed = False
    for path in paths:
        problems = validate(path)
        failed |= bool(problems)
        print(json.dumps({"file": str(path), "valid": not problems, "problems": problems}, ensure_ascii=False))
    if not paths:
        print("Katkı dosyası yok (data/contributions).")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
