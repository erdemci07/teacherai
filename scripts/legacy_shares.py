"""TA-001 öncesi paylaşımlar için inceleme ve yayından kaldırma (TA-001B, G paketi).

Kullanım (depo kökünden):
    python -m scripts.legacy_shares                     # audit, salt okunur
    python -m scripts.legacy_shares audit --output tmp/legacy-shares/audit.csv
    python -m scripts.legacy_shares unpublish --ids-file ids.txt              # yalnız dry-run
    TEACHERAI_ALLOW_DESTRUCTIVE=1 python -m scripts.legacy_shares unpublish \\
        --ids-file ids.txt --execute --confirm-project <bağlı-proje>

Tespit ölçütü apps/api/app/features/shares/legacy.py içindedir: TA-001 sonrası her
paylaşım sabit özet, sabit öğrenme hedefi ve sabit soru anlayışı metni taşır; biri
farklıysa paylaşım eski biçimdedir.

Gizlilik: Betik hiçbir soru metnini veya anlatımı ekrana, CSV'ye ya da günlüğe yazmaz.
Yalnız alanların varlığı (true/false) raporlanır. Yedekler tam içerik taşır; Git
dışındaki tmp/ altına, yalnız sahibinin okuyabileceği izinle yazılır ve yetkili
işletmeci dışında paylaşılmamalıdır. Hard delete modu yoktur.

Bu betik bu görevde yalnız yerel emülatöre karşı test edildi; gerçek bir projede
çalıştırılmadı.
"""

import argparse
import csv
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from apps.api.app.features.shares.legacy import CURRENT_UNDERSTANDING, is_current_format

COLLECTION = "shared_solutions"
OUTPUT_DIR = Path("tmp/legacy-shares")
FIXED_EXPLANATIONS = {"Matematiksel işlem", "Sonuç ifadesi"}
# Yeni biçimin sabit strateji metni (ShareService._public_lesson_snapshot).
FIXED_STRATEGY = "Dönüşümleri sırayla izle."
NARRATION_FIELDS = ("common_mistake", "shortcut", "teacher_tip", "prerequisite_reminder", "key_rule")


def connect(project):
    from google.cloud.firestore import Client

    if os.environ.get("FIRESTORE_EMULATOR_HOST"):
        from google.auth.credentials import AnonymousCredentials

        return Client(project=project, credentials=AnonymousCredentials())
    return Client(project=project)


def describe(share_id, data):
    """Bir paylaşımın içerik taşımayan özeti."""
    content = (data.get("lesson_snapshot") or {}).get("content") or {}
    steps = content.get("steps") or []
    narration = (
        content.get("question_understanding") not in (None, CURRENT_UNDERSTANDING)
        or content.get("strategy") not in (None, FIXED_STRATEGY)
        or any(content.get(field) for field in NARRATION_FIELDS)
        or any(step.get("explanation") not in FIXED_EXPLANATIONS for step in steps)
    )
    created = data.get("created_at")
    return {
        "share_id": share_id,
        "created_at": created.isoformat() if hasattr(created, "isoformat") else str(created or ""),
        "has_question_text": bool(data.get("question_summary")),
        "has_free_narration": bool(narration),
        "has_owner": "owner_id" in data,
        "unpublished": bool(data.get("unpublished_at")),
    }


def audit(db, output):
    rows = [describe(snap.id, data) for snap in db.collection(COLLECTION).stream()
            if not is_current_format(data := snap.to_dict() or {})]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["share_id", "created_at", "has_question_text", "has_free_narration", "has_owner", "unpublished"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} eski biçimli paylaşım bulundu; içerik yazılmadı. CSV: {output}")
    return rows


def read_ids(path):
    ids = [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
    bad = [value for value in ids if "/" in value or len(value) > 64]
    if bad:
        raise SystemExit(f"Geçersiz paylaşım kimliği: {len(bad)} satır")
    return list(dict.fromkeys(ids))


def unpublish(db, args, env):
    ids = read_ids(args.ids_file)
    refs = [db.collection(COLLECTION).document(value) for value in ids]
    found = {snap.id: snap.to_dict() for snap in db.get_all(refs) if snap.exists}
    selected = [value for value in ids if value in found and not is_current_format(found[value]) and not found[value].get("unpublished_at")]
    skipped = len(ids) - len(selected)
    if not args.execute:
        print(f"Dry-run: {len(selected)} paylaşım yayından kaldırılacaktı, {skipped} kimlik atlandı (yok, yeni biçimli veya zaten kaldırılmış). Yazma yapılmadı.")
        return 0
    if args.confirm_project != db.project:
        print("Durduruldu: --confirm-project bağlı projeyle birebir eşleşmiyor. Yazma yapılmadı.", file=sys.stderr)
        return 2
    if env.get("TEACHERAI_ALLOW_DESTRUCTIVE") != "1":
        print("Durduruldu: TEACHERAI_ALLOW_DESTRUCTIVE=1 gerekli. Yazma yapılmadı.", file=sys.stderr)
        return 2
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    backup = Path(args.backup_dir) / f"unpublish-backup-{db.project}-{stamp}.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text(json.dumps({value: found[value] for value in selected}, ensure_ascii=False, default=str), encoding="utf-8")
    try:
        os.chmod(backup, 0o600)
    except OSError:
        pass
    now = datetime.now(UTC)
    for start in range(0, len(selected), 500):
        batch = db.batch()
        for value in selected[start:start + 500]:
            batch.update(db.collection(COLLECTION).document(value), {"unpublished_at": now})
        batch.commit()
    print(f"{len(selected)} paylaşım yayından kaldırıldı, {skipped} kimlik atlandı. Yedek: {backup}")
    return 0


def parser():
    root = argparse.ArgumentParser(description="TA-001 öncesi paylaşımlar için inceleme ve yayından kaldırma.")
    root.add_argument("--project", default=os.environ.get("TEACHERAI_FIREBASE_PROJECT_ID", "demo-teacherai"))
    commands = root.add_subparsers(dest="mode")
    audit_cmd = commands.add_parser("audit", help="Salt okunur inceleme (varsayılan).")
    audit_cmd.add_argument("--output", type=Path)
    remove = commands.add_parser("unpublish", help="Seçilen eski paylaşımları yayından kaldırır.")
    remove.add_argument("--ids-file", required=True)
    remove.add_argument("--execute", action="store_true")
    remove.add_argument("--confirm-project")
    remove.add_argument("--backup-dir", default=str(OUTPUT_DIR))
    return root


def main(argv=None, db=None, env=None):
    args = parser().parse_args(argv)
    db = db or connect(args.project)
    if args.mode in (None, "audit"):
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        audit(db, getattr(args, "output", None) or OUTPUT_DIR / f"audit-{stamp}.csv")
        return 0
    return unpublish(db, args, os.environ if env is None else env)


if __name__ == "__main__":
    raise SystemExit(main())
