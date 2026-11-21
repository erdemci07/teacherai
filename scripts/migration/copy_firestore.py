"""Firestore koleksiyonlarını projeler arasında kopyalar ve doğrular (TA-005 §6.2).

Varsayılan kuru koşudur; hiçbir şey yazmaz:
    python -m scripts.migration.copy_firestore --source math-ai-07 --target teacherai-07
Gerçek kopya (her iki kimlik birebir yazılmalı):
    python -m scripts.migration.copy_firestore --execute --source math-ai-07 --target teacherai-07 \\
        --confirm-target teacherai-07
Doğrulama (yalnız okur, yalnız sayı yazar):
    python -m scripts.migration.copy_firestore --verify --source math-ai-07 --target teacherai-07 [--auth-uids target]
Geri alma (hedef eski proje ise zorunlu bayrak):
    python -m scripts.migration.copy_firestore --execute --source teacherai-07 --target math-ai-07 \\
        --confirm-target math-ai-07 --allow-reverse

- Belge kimlikleri, alt koleksiyonlar ve tipler (Timestamp, GeoPoint, bytes, referans) korunur. Kaynak
  projeye işaret eden belge referansı hedef istemcinin referansına dönüştürülür ve sayılır.
- Artımlıdır: hedefte aynı ``updated_at`` veya aynı kanonik içerik özeti varsa belge yazılmaz.
- Çıktı yalnız sayılardır; belge içeriği, UID veya e-posta yazılmaz.
Kimlik: Application Default Credentials. Emülatörde ``FIRESTORE_EMULATOR_HOST`` kullanılır.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import sys
from collections import Counter

LEGACY_PROJECT = "math-ai-07"  # eski proje; buraya yazmak yalnız --allow-reverse ile
# Koleksiyon izin listesi ve gerekçeleri (denetimdeki kod haritası; bkz. docs/migration/TA-005-runbook.md).
ALLOWLIST = {
    "users": "kalıcı kullanıcı kaydı",
    "student_profiles": "profil (sınıf, sınav hedefi)",
    "student_memories": "öğrenme hafızası",
    "lessons": "geçmiş dersler",
    "interaction_events": "ders sonrası etkileşim geçmişi",
    "practice_attempts": "pratik yanıtları",
    "practice_questions": "7 günlük TTL; açık pratiklerin yanıtlanabilmesi için",
    "shared_solutions": "paylaşım bağlantıları",
    "feedback": "geri bildirim",
    "account_deletions": "süren silmeler ve 30 günlük makbuzlar; kopyalanmazsa silme sonucu sorgulanamaz",
    "lesson_analyses": "24 saatlik TTL; yeni yüklenen sorudan ders üretimi kesilmesin diye",
    "ai_daily_usage": "kota ve Idempotency-Key kaydı; kopyalanmazsa bugünkü kota sıfırlanır",
    "ai_output_usage": "çıktı token kotası; kopyalanmazsa bugünkü kota sıfırlanır",
    "ai_global_usage": "küresel günlük bütçe; kopyalanmazsa bugünkü bütçe sıfırlanır",
}
OWNER_FIELDS = {"lessons": "student_id", "practice_questions": "student_id", "practice_attempts": "student_id",
                "interaction_events": "student_id", "shared_solutions": "owner_id", "feedback": "user_id",
                "lesson_analyses": "owner", "users": None, "student_profiles": None, "student_memories": None}
BATCH = 400


def client(project):
    from google.cloud.firestore import Client

    if os.environ.get("FIRESTORE_EMULATOR_HOST"):
        from google.auth.credentials import AnonymousCredentials

        return Client(project=project, credentials=AnonymousCredentials())
    return Client(project=project)


def canonical(value):
    """Tip korunarak karşılaştırılabilir JSON değeri; referans yalnız göreli yoluyla."""
    from google.cloud.firestore import DocumentReference, GeoPoint

    if isinstance(value, dict):
        return {key: canonical(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [canonical(item) for item in value]
    if isinstance(value, dt.datetime):
        nanos = getattr(value, "nanosecond", 0)
        return {"__ts": value.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M:%S.%f"), "ns": nanos}
    if isinstance(value, GeoPoint):
        return {"__geo": [value.latitude, value.longitude]}
    if isinstance(value, DocumentReference):
        return {"__ref": value.path}
    if isinstance(value, bytes):
        return {"__bytes": base64.b64encode(value).decode()}
    return value


def digest(data) -> str:
    return hashlib.sha256(json.dumps(canonical(data), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def rebind(value, target, stats):
    """Kaynak istemciye bağlı referansları hedef istemciye taşır."""
    from google.cloud.firestore import DocumentReference

    if isinstance(value, dict):
        return {key: rebind(item, target, stats) for key, item in value.items()}
    if isinstance(value, list):
        return [rebind(item, target, stats) for item in value]
    if isinstance(value, DocumentReference):
        stats["references_rebound"] += 1
        return target.document(value.path)
    return value


def pages(collection, size):
    query = collection.order_by("__name__").limit(size)
    last = None
    while True:
        batch = list((query.start_after(last) if last else query).stream())
        yield batch
        if len(batch) < size:
            return
        last = batch[-1]


def _same(source_data, target_snap) -> bool:
    if not target_snap.exists:
        return False
    target_data = target_snap.to_dict()
    stamp = source_data.get("updated_at")
    if stamp is not None and target_data.get("updated_at") is not None and canonical(stamp) == canonical(target_data["updated_at"]):
        return True
    return digest(source_data) == digest(target_data)


def copy_collection(source, target, collection_ref, execute, stats, size):
    """Bir koleksiyonu (ve alt koleksiyonlarını) sayfa sayfa kopyalar; yalnız farklı belgeleri yazar."""
    for page in pages(collection_ref, size):
        refs = [target.document(snap.reference.path) for snap in page]
        existing = {snap.reference.path: snap for snap in target.get_all(refs)}
        batch, pending = target.batch(), 0
        for snap in page:
            data = snap.to_dict()
            stats["read"] += 1
            if _same(data, existing[snap.reference.path]):
                stats["unchanged"] += 1
            else:
                stats["written" if execute else "would_write"] += 1
                if execute:
                    batch.set(target.document(snap.reference.path), rebind(data, target, stats))
                    pending += 1
                    if pending == BATCH:
                        batch.commit()
                        batch, pending = target.batch(), 0
            for child in snap.reference.collections():
                stats["subcollections"] += 1
                copy_collection(source, target, child, execute, stats, size)
        if pending:
            batch.commit()


def copy(source_id, target_id, collections, execute, size=300, source=None, target=None):
    source, target = source or client(source_id), target or client(target_id)
    report = {}
    for name in collections:
        stats = Counter()
        copy_collection(source, target, source.collection(name), execute, stats, size)
        report[name] = dict(stats)
    return report


def verify(source_id, target_id, collections, auth_uids=None, size=300, source=None, target=None):
    """Sayı, belge özeti ve sahiplik bütünlüğü. Yalnız sayı döner."""
    source, target = source or client(source_id), target or client(target_id)
    report = {}
    for name in collections:
        stats = Counter()
        for page in pages(source.collection(name), size):
            refs = [target.document(snap.reference.path) for snap in page]
            existing = {snap.reference.path: snap for snap in target.get_all(refs)}
            for snap in page:
                stats["source"] += 1
                other = existing[snap.reference.path]
                stats["missing" if not other.exists else "same" if digest(snap.to_dict()) == digest(other.to_dict()) else "different"] += 1
                if auth_uids is not None and name in OWNER_FIELDS:
                    field = OWNER_FIELDS[name]
                    owner = snap.id if field is None else (snap.to_dict() or {}).get(field)
                    stats["owner_in_target_auth" if owner in auth_uids else "owner_missing" if owner else "no_owner"] += 1
        stats["target"] = target.collection(name).count().get()[0][0].value
        report[name] = dict(stats)
    return report


def guard(args):
    if args.target == args.source:
        raise SystemExit("Kaynak ve hedef aynı olamaz.")
    if args.execute and args.confirm_target != args.target:
        raise SystemExit("--confirm-target, --target ile birebir aynı olmalı. Yazma yapılmadı.")
    if args.execute and args.target == LEGACY_PROJECT and not args.allow_reverse:
        raise SystemExit(f"Hedef {LEGACY_PROJECT}: geri alma yalnız --allow-reverse ile yapılır. Yazma yapılmadı.")
    unknown = sorted(set(args.collections) - set(ALLOWLIST))
    if unknown:
        raise SystemExit(f"İzin listesinde olmayan koleksiyon: {', '.join(unknown)}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--execute", action="store_true", help="gerçek yazma (varsayılan kuru koşu)")
    parser.add_argument("--confirm-target")
    parser.add_argument("--allow-reverse", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--auth-uids", choices=["target"], help="sahiplik denetimi için hedef Auth UID'leri (alan maskeli)")
    parser.add_argument("--collections", nargs="+", default=sorted(ALLOWLIST))
    parser.add_argument("--page-size", type=int, default=300)
    args = parser.parse_args(argv)
    guard(args)
    if args.verify:
        uids = None
        if args.auth_uids:
            from scripts.migration.audit_projects import Rest, access_token, list_users

            summary, uids = list_users(args.target, Rest(access_token()[0]))
            if "error" in summary:
                raise SystemExit(f"Hedef Auth okunamadı: {summary['error']}")
        report = verify(args.source, args.target, args.collections, uids, args.page_size)
    else:
        report = copy(args.source, args.target, args.collections, args.execute, args.page_size)
    print(json.dumps({"mode": "verify" if args.verify else "execute" if args.execute else "dry_run",
                      "source": args.source, "target": args.target, "collections": report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
