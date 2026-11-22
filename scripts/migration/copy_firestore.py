"""Firestore koleksiyonlarını projeler arasında uzlaştırır, kopyalar ve doğrular (TA-005 §6.2, TA-005B §2).

``--authority source|target`` her modda zorunludur ve varsayılanı yoktur. Geçişten önce eski proje,
geçişten sonra yeni proje yetkilidir; bayrak bu projenin betikteki rolünü (``--source``/``--target``) seçer.

Kuru koşu (varsayılan; hiçbir şey yazmaz):
    python -m scripts.migration.copy_firestore --source math-ai-07 --target teacherai-07 --authority source
Gerçek kopya:
    ... --execute --confirm-target teacherai-07
İki yönlü fark raporu (yalnız okur; ekrana yalnız sayı yazar):
    ... --verify [--auth-uids target] --report-out fark.json
Hedefte fazla belgeyi budama (yalnız ``--verify`` raporunda görülmüş ve o andan beri değişmemiş belgeler):
    ... --prune --confirm-prune teacherai-07 --prune-from fark.json [--execute]
Hedef eski proje ise yazma ve budama ayrıca ``--allow-reverse`` ister.

Uzlaştırma kuralları:
- Eşitlik yalnız kanonik içerik özetinin eşitliğiyle kanıtlanır (``updated_at`` kısayolu yok).
- Silme kaydı (iki taraftaki ``account_deletions``) bulunan UID'nin verisi hiçbir yöne yazılmaz.
- Kullanıcıya ait koleksiyonda sahibi yetkili tarafın Auth'unda bulunmayan belge yazılmaz (30 günlük
  TTL ile silme kaydı kaybolsa da hesap Auth'ta yoktur). Sahipsiz paylaşımlar ayrıca sayılır ve
  ``--copy-ownerless-shares`` verilmedikçe yazılmaz.
- Yetkili taraf kaynaksa: yalnız kaynakta olan yazılır; çakışmada kaynak değeri yazılır ve ezilen hedef
  içeriğinin özeti raporlanır. Yetkili taraf hedefse: hedef hiç ezilmez; yalnız kaynakta olan belge
  hedefte silinmiş olabileceği için (ör. hafıza sıfırlama, paylaşım kaldırma) yazılmaz, sayılır.
- Hedefte fazla belge hiçbir zaman otomatik silinmez.
- Çıktıda belge içeriği, UID veya e-posta yoktur; belge yolları sha256 ile özetlenir.
Kimlik: Application Default Credentials. Emülatörde ``FIRESTORE_EMULATOR_HOST`` kullanılır.
"""

from __future__ import annotations

import argparse
import base64
import calendar
import datetime as dt
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

LEGACY_PROJECT = "math-ai-07"  # eski proje; buraya yazmak yalnız --allow-reverse ile
REPORT_TOOL = "scripts.migration.copy_firestore/verify"
REPORT_MAX_AGE = dt.timedelta(hours=1)
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
DOC_ID, HASHED = "<doc-id>", "<owner-hash>"
# Kullanıcıya ait koleksiyonların sahip alanı. Listede olmayan koleksiyonlar (ai_global_usage,
# account_deletions) kullanıcıya ait değildir; silme kayıtları silmenin kendisini taşır.
OWNER_FIELDS = {"lessons": "student_id", "practice_questions": "student_id", "practice_attempts": "student_id",
                "interaction_events": "student_id", "shared_solutions": "owner_id", "feedback": "user_id",
                "lesson_analyses": "owner", "users": DOC_ID, "student_profiles": DOC_ID, "student_memories": DOC_ID,
                "ai_daily_usage": HASHED, "ai_output_usage": HASHED}
DELETIONS = "account_deletions"
BATCH = 400
BLOCKED = ("deleted_owner", "owner_not_in_auth", "no_owner", "ownerless_share")


def client(project):
    from google.cloud.firestore import Client

    if os.environ.get("FIRESTORE_EMULATOR_HOST"):
        from google.auth.credentials import AnonymousCredentials

        return Client(project=project, credentials=AnonymousCredentials())
    return Client(project=project)


def canonical(value):
    """Her Firestore değerini tip etiketiyle karşılaştırılabilir JSON'a çevirir.

    Firestore'da tamsayı ve ondalık ayrı tiplerdir: ``1`` (``i``) ile ``1.0`` (``d``) farklı sayılır, çünkü
    kopyada tipin değişmesi verinin değişmesidir. Ondalıklar ``repr`` ile yazılır (``-0.0`` ve ``nan``
    dahil). Zaman damgası epoch saniyesi + nanosaniyedir; saat dilimsiz değer UTC sayılır. Belge referansı
    yalnız göreli yoluyla karşılaştırılır (proje kimliği farkı fark sayılmaz). Bilinmeyen tip ``TypeError``
    verir; böylece desteklenmeyen bir alan hiçbir zaman "aynı" görünmez.
    """
    from google.cloud.firestore import DocumentReference, GeoPoint

    if value is None:
        return None
    if isinstance(value, bool):
        return {"b": value}
    if isinstance(value, int):
        return {"i": str(value)}
    if isinstance(value, float):
        return {"d": repr(value)}
    if isinstance(value, str):
        return {"s": value}
    if isinstance(value, bytes):
        return {"y": base64.b64encode(value).decode()}
    if isinstance(value, dt.datetime):
        moment = value if value.tzinfo else value.replace(tzinfo=dt.UTC)
        nanos = getattr(value, "nanosecond", None)
        return {"t": calendar.timegm(moment.utctimetuple()),
                "n": nanos if isinstance(nanos, int) else value.microsecond * 1000}
    if isinstance(value, GeoPoint):
        return {"g": [repr(float(value.latitude)), repr(float(value.longitude))]}
    if isinstance(value, DocumentReference):
        return {"r": value.path}
    if isinstance(value, dict):
        return {"m": {str(key): canonical(item) for key, item in value.items()}}
    if isinstance(value, list | tuple):
        return {"a": [canonical(item) for item in value]}
    raise TypeError(f"Desteklenmeyen Firestore tipi: {type(value).__name__}")


def digest(data) -> str:
    text = json.dumps(canonical(data), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def path_hash(path: str) -> str:
    return hashlib.sha256(path.encode()).hexdigest()


def owner_hash(uid: str) -> str:
    return hashlib.sha256(uid.encode()).hexdigest()  # core/usage.owner_hash ile aynı


def pattern(path: str) -> str:
    """``lessons/abc/notes/n1`` → ``lessons/*/notes``: rapor anahtarı; belge kimliği içermez."""
    parts = path.split("/")[:-1]
    return "/".join(part if index % 2 == 0 else "*" for index, part in enumerate(parts))


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


class Policy:
    """Sahiplik kararları. ``deleted``: iki taraftaki silme kayıtlarının birleşimi. ``auth``: Auth UID'leri
    (kopyada yetkili taraf; doğrulamada isteğe bağlı hedef). ``auth=None`` Auth denetimini kapatır ve
    yalnız doğrulamada kullanılır."""

    def __init__(self, authority, deleted, auth=None, copy_ownerless_shares=False):
        if authority not in ("source", "target"):
            raise ValueError("authority source veya target olmalı")
        self.authority, self.deleted, self.auth = authority, set(deleted), auth
        self.copy_ownerless_shares = copy_ownerless_shares
        self._deleted_hashes = {owner_hash(uid) for uid in self.deleted}
        self._auth_hashes = None if auth is None else {owner_hash(uid) for uid in auth}

    def status(self, path, data):
        top, doc_id = path.split("/")[0], path.split("/")[1]
        field = OWNER_FIELDS.get(top)
        if field is None:
            return "unowned"
        if field == HASHED:
            value = (data or {}).get("owner_hash") or (doc_id.split("_", 1)[1] if "_" in doc_id else None)
            deleted, known = self._deleted_hashes, self._auth_hashes
        else:
            value = doc_id if field == DOC_ID else (data or {}).get(field)
            deleted, known = self.deleted, self.auth
        if not value:
            if top == "shared_solutions":
                return "ok" if self.copy_ownerless_shares else "ownerless_share"
            return "no_owner"
        if value in deleted:
            return "deleted_owner"
        if known is not None and value not in known:
            return "owner_not_in_auth"
        return "ok"


def decide(policy, status, source_digest, target_digest):
    """Tek belge için eylem. Saf fonksiyon; yazma kararının tamamı buradadır."""
    if source_digest is not None and source_digest == target_digest:
        return "same"
    if source_digest is None:
        return "only_target"
    if status in BLOCKED:
        return f"blocked_{status}"
    if target_digest is None:
        return "write_new" if policy.authority == "source" else "held_source_only"
    return "conflict_overwrite" if policy.authority == "source" else "conflict_kept_target"


def pages(collection, size):
    query = collection.order_by("__name__").limit(size)
    last = None
    while True:
        batch = list((query.start_after(last) if last else query).stream())
        yield batch
        if len(batch) < size:
            return
        last = batch[-1]


def walk(source, target, collection_path, policy, visit, size, inherited=None):
    """Kaynak ve hedefteki bütün belgeleri (alt koleksiyonlar dahil) bir kez ziyaret eder.

    Alt koleksiyon belgesi, üst düzey atasının sahiplik durumunu devralır.
    """
    for page in pages(source.collection(collection_path), size):
        if not page:
            continue
        others = {snap.reference.path: snap for snap in target.get_all([target.document(s.reference.path) for s in page])}
        _visit_all([(s.reference.path, s, others[s.reference.path]) for s in page],
                   source, target, policy, visit, size, inherited)
    for page in pages(target.collection(collection_path), size):  # yalnız hedefte olanlar
        if not page:
            continue
        others = {snap.reference.path: snap for snap in source.get_all([source.document(s.reference.path) for s in page])}
        _visit_all([(s.reference.path, others[s.reference.path], s) for s in page if not others[s.reference.path].exists],
                   source, target, policy, visit, size, inherited)


def _visit_all(items, source, target, policy, visit, size, inherited):
    for path, src, dst in items:
        src_data = src.to_dict() if src.exists else None
        dst_data = dst.to_dict() if dst.exists else None
        status = inherited or policy.status(path, src_data if src_data is not None else dst_data)
        visit(path, status, src_data, dst_data)
        children = {c.id for c in source.document(path).collections()} | {c.id for c in target.document(path).collections()}
        for child in sorted(children):
            walk(source, target, f"{path}/{child}", policy, visit, size, inherited=status)


def deletion_uids(*clients):
    return {snap.id for db in clients for snap in db.collection(DELETIONS).stream()}


def copy(source_id, target_id, collections, execute, policy, size=300, source=None, target=None):
    if policy.auth is None:
        raise ValueError("Kopya için yetkili tarafın Auth UID listesi zorunludur.")
    source, target = source or client(source_id), target or client(target_id)
    report, conflicts = defaultdict(Counter), []
    state = {"batch": target.batch(), "pending": 0}

    def visit(path, status, src_data, dst_data):
        src_digest = None if src_data is None else digest(src_data)
        dst_digest = None if dst_data is None else digest(dst_data)
        action = decide(policy, status, src_digest, dst_digest)
        stats = report[pattern(path)]
        stats[action] += 1
        if action.startswith("conflict_"):
            kept = action == "conflict_kept_target"
            conflicts.append({"collection": pattern(path), "path_sha256": path_hash(path),
                              ("source_digest_not_written" if kept else "replaced_target_digest"):
                              src_digest if kept else dst_digest})
        if action in ("write_new", "conflict_overwrite"):
            stats["written" if execute else "would_write"] += 1
            if execute:
                state["batch"].set(target.document(path), rebind(src_data, target, stats))
                state["pending"] += 1
                if state["pending"] == BATCH:
                    state["batch"].commit()
                    state["batch"], state["pending"] = target.batch(), 0

    for name in collections:
        walk(source, target, name, policy, visit, size)
    if state["pending"]:
        state["batch"].commit()
    return {"collections": {key: dict(value) for key, value in report.items()}, "conflicts": conflicts}


def _diff(source, target, collections, policy, size):
    report, candidates = defaultdict(Counter), []

    def visit(path, status, src_data, dst_data):
        stats = report[pattern(path)]
        src_digest = None if src_data is None else digest(src_data)
        dst_digest = None if dst_data is None else digest(dst_data)
        if src_digest is None:
            stats["only_target"] += 1
        elif dst_digest is None:
            stats["only_source"] += 1
        else:
            stats["same" if src_digest == dst_digest else "different"] += 1
        if status in ("no_owner", "ownerless_share", "owner_not_in_auth"):
            stats[status] += 1
        if status == "deleted_owner":
            for side, data in (("source", src_data), ("target", dst_data)):
                if data is not None:
                    stats[f"deleted_owner_in_{side}"] += 1
        stale = dst_digest is not None and (
            (src_digest is None and policy.authority == "source") or status == "deleted_owner")
        if stale:
            candidates.append({"path_sha256": path_hash(path), "digest": dst_digest})

    for name in collections:
        walk(source, target, name, policy, visit, size)
    return {key: dict(value) for key, value in report.items()}, candidates


def verify(source_id, target_id, collections, policy, size=300, source=None, target=None, now=None):
    """İki yönlü fark raporu. ``prune_manifest`` yalnız rapor dosyasına yazılır; ekrana çıkmaz."""
    source, target = source or client(source_id), target or client(target_id)
    counts, candidates = _diff(source, target, collections, policy, size)
    stamp = (now or dt.datetime.now(dt.UTC)).isoformat()
    return {"collections": counts, "prune_manifest": {
        "tool": REPORT_TOOL, "format": 1, "source": source_id, "target": target_id, "authority": policy.authority,
        "collections": sorted(collections), "created_at": stamp, "candidates": candidates}}


def load_prune_report(path, source_id, target_id, now=None):
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))["prune_manifest"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"Budama raporu okunamadı ({type(error).__name__}). Silme yapılmadı.") from None
    if manifest.get("tool") != REPORT_TOOL or manifest.get("format") != 1:
        raise SystemExit("Budama raporu bu betiğin --verify çıktısı değil. Silme yapılmadı.")
    if manifest.get("target") != target_id or manifest.get("source") != source_id:
        raise SystemExit("Budama raporu başka bir kaynak/hedef çifti için üretilmiş. Silme yapılmadı.")
    try:
        created = dt.datetime.fromisoformat(manifest["created_at"])
    except (KeyError, TypeError, ValueError):
        raise SystemExit("Budama raporunun zamanı okunamadı. Silme yapılmadı.") from None
    age = (now or dt.datetime.now(dt.UTC)) - created
    if age > REPORT_MAX_AGE or age < -dt.timedelta(minutes=5):
        raise SystemExit("Budama raporunun süresi dolmuş (en çok 1 saat). --verify yeniden çalıştırın. Silme yapılmadı.")
    return manifest


def prune(source_id, target_id, manifest, execute, policy, size=300, source=None, target=None):
    """Yalnız raporda görülmüş ve özeti o andan beri değişmemiş hedef belgelerini siler."""
    if manifest.get("authority") != policy.authority:
        raise SystemExit("Budama raporu farklı bir --authority ile üretilmiş. Silme yapılmadı.")
    source, target = source or client(source_id), target or client(target_id)
    approved = {(item["path_sha256"], item["digest"]) for item in manifest["candidates"]}
    approved_paths = {item["path_sha256"] for item in manifest["candidates"]}
    stats, to_delete = Counter(), []

    def visit(path, status, src_data, dst_data):
        if dst_data is None:
            return
        stale = (src_data is None and policy.authority == "source") or status == "deleted_owner"
        if not stale:
            return
        key = (path_hash(path), digest(dst_data))
        if key in approved:
            stats["pruned" if execute else "would_prune"] += 1
            to_delete.append(path)
        else:
            stats["skipped_changed_since_report" if key[0] in approved_paths else "skipped_not_in_report"] += 1

    for name in manifest["collections"]:
        walk(source, target, name, policy, visit, size)
    if execute:  # en derin belge önce; alt koleksiyonu olan üst belge kendi kaydıyla silinir
        for start in range(0, len(to_delete), BATCH):
            batch = target.batch()
            for path in sorted(to_delete, key=lambda p: -p.count("/"))[start:start + BATCH]:
                batch.delete(target.document(path))
            batch.commit()
    return dict(stats)


def guard(args):
    if args.target == args.source:
        raise SystemExit("Kaynak ve hedef aynı olamaz.")
    if args.verify and args.prune:
        raise SystemExit("--verify ve --prune birlikte kullanılamaz.")
    if args.execute and not args.prune and args.confirm_target != args.target:
        raise SystemExit("--confirm-target, --target ile birebir aynı olmalı. Yazma yapılmadı.")
    if args.prune and (args.confirm_prune != args.target or not args.prune_from):
        raise SystemExit("Budama --prune --confirm-prune <hedef> --prune-from <rapor> ister. Silme yapılmadı.")
    if (args.execute or args.prune) and args.target == LEGACY_PROJECT and not args.allow_reverse:
        raise SystemExit(f"Hedef {LEGACY_PROJECT}: geri yönde yazma/silme yalnız --allow-reverse ile. Yazma yapılmadı.")
    unknown = sorted(set(args.collections) - set(ALLOWLIST))
    if unknown:
        raise SystemExit(f"İzin listesinde olmayan koleksiyon: {', '.join(unknown)}")


def _auth_uids(project):
    from scripts.migration.audit_projects import Rest, access_token, list_users

    summary, uids = list_users(project, Rest(access_token()[0]))
    if "error" in summary:
        raise SystemExit(f"{project} Auth okunamadı: {summary['error']}")
    return uids


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--authority", required=True, choices=["source", "target"],
                        help="yetkili taraf (zorunlu, varsayılan yok): geçişten önce eski, sonra yeni proje")
    parser.add_argument("--execute", action="store_true", help="gerçek yazma/silme (varsayılan kuru koşu)")
    parser.add_argument("--confirm-target")
    parser.add_argument("--allow-reverse", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--report-out", help="--verify: sayılar ve budama manifestiyle tam rapor dosyası")
    parser.add_argument("--auth-uids", choices=["target"], help="--verify: hedef Auth'ta olmayan sahipleri say")
    parser.add_argument("--prune", action="store_true")
    parser.add_argument("--confirm-prune")
    parser.add_argument("--prune-from")
    parser.add_argument("--copy-ownerless-shares", action="store_true", help="sahipsiz eski paylaşımları da yaz (Erdem kararı)")
    parser.add_argument("--collections", nargs="+", default=sorted(ALLOWLIST))
    parser.add_argument("--page-size", type=int, default=300)
    args = parser.parse_args(argv)
    guard(args)
    source, target = client(args.source), client(args.target)
    deleted = deletion_uids(source, target)
    if args.verify:
        policy = Policy(args.authority, deleted, _auth_uids(args.target) if args.auth_uids else None)
        result = verify(args.source, args.target, args.collections, policy, args.page_size, source, target)
        if args.report_out:
            Path(args.report_out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        output = {"mode": "verify", "collections": result["collections"],
                  "prune_candidates": len(result["prune_manifest"]["candidates"])}
    elif args.prune:
        manifest = load_prune_report(args.prune_from, args.source, args.target)
        policy = Policy(args.authority, deleted)
        output = {"mode": "prune" if args.execute else "prune_dry_run",
                  "result": prune(args.source, args.target, manifest, args.execute, policy, args.page_size, source, target)}
    else:
        authority_project = args.source if args.authority == "source" else args.target
        policy = Policy(args.authority, deleted, _auth_uids(authority_project), args.copy_ownerless_shares)
        output = {"mode": "execute" if args.execute else "dry_run",
                  **copy(args.source, args.target, args.collections, args.execute, policy, args.page_size, source, target)}
    print(json.dumps({"source": args.source, "target": args.target, "authority": args.authority, **output},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
