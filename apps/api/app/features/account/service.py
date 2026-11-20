"""Uygulama içi hesap silme (TA-001B, F paketi).

Akış:
1. account_deletions/{uid} işareti bir işlemle oluşturulur (pending). Bu andan sonra
   kullanıcıya bağlı hiçbir kalıcı yazma commit edilemez (guard.ensure_active).
2. Yenileme belirteçleri iptal edilir; eski oturumlar check_revoked=True ile reddedilir.
3. Eşzamanlı istekler arasında yalnız biri, işlemle alınan süreli kira (lease) ile
   adımları çalıştırır. Diğerleri 202 / in_progress alır.
4. Her adım idempotenttir; 500'lük toplu silmelerle ilerler ve tamamlanınca kayda
   işlenir. Süre bütçesi dolarsa 202 döner, istemci POST'u tekrarlar.
5. Firebase Auth kullanıcısı en son silinir. Ancak ondan sonra durum completed olur.

Auth silindikten sonra tamamlanma kaydı yazılamazsa kullanıcı artık oturum açamaz.
Bu durum için ilk yanıtta verilen tek kullanımlık olmayan makbuz (receipt) vardır:
yalnız SHA-256 özeti saklanır, yalnız kendi kaydını gösterir ve Auth kullanıcısının
gerçekten bulunmadığını ve önceki adımların tamamlandığını doğrulayarak kaydı
idempotent biçimde tamamlar.

İşaret belgesinde uid (belge kimliği) dışında kişisel veri yoktur. Tamamlanınca
expires_at = tamamlanma + 30 gün yazılır. Bu süre uçuştaki her isteğin azami
süresinden (Cloud Run 300 sn) çok uzundur; Auth kullanıcısı silindiği için bu
sürenin sonunda eski belirteçlerle yeni istek kabul edilemez.
"""

import hmac
import secrets
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from time import monotonic

from google.cloud.firestore_v1.base_query import FieldFilter
from firebase_admin import firestore

from apps.api.app.core.retention import DAILY, DELETIONS, OUTPUT, TTL_DAYS
from apps.api.app.core.transactions import commit as commit_transaction
from apps.api.app.features.shares.legacy import is_current_format

BATCH = 500
# TA-001'in kota koleksiyonlarını ilk oluşturduğu gün. Kota belgeleri yalnız uid özeti
# kimliğiyle adlandırıldığından eski belgeler bu günden bugüne kadar hesaplanarak bulunur.
USAGE_HISTORY_START = date(2026, 11, 19)
STEPS = (
    "revoke_tokens",
    "shared_solutions",
    "practice_questions",
    "practice_attempts",
    "interaction_events",
    "feedback",
    "lesson_analyses",
    "usage",
    "lessons",
    "student_memories",
    "student_profiles",
    "users",
    "auth",
)


class ReauthenticationRequired(Exception):
    """401 / reauthentication_required."""


class DeletionUnavailable(Exception):
    """Silme kalıcı depolama gerektirir; test belleğinde 503 döner."""


class LostLease(Exception):
    pass


def _hash(value):
    return sha256(value.encode()).hexdigest()


class AccountDeletionService:
    def __init__(self, settings, db, identity, clock=lambda: datetime.now(UTC)):
        self.settings = settings
        self.db = db
        self.identity = identity
        self.clock = clock
        # Test kancaları: adım öncesi hata enjeksiyonu ve silinen belge yolları.
        self.before_step = lambda step: None
        self.on_delete = lambda path: None

    # Genel API -------------------------------------------------------------

    def ensure_recent_login(self, user):
        limit = self.settings.account_deletion_max_auth_age_seconds
        if user.auth_time is None or self.clock().timestamp() - user.auth_time > limit:
            raise ReauthenticationRequired

    def status(self, uid):
        self._require_db()
        data = self._ref(uid).get().to_dict()
        return self._public(data) if data else None

    def start_or_resume(self, user):
        """(HTTP durumu, genel kayıt) döndürür: 200 completed, 202 in_progress, 500 failed."""
        self._require_db()
        self.ensure_recent_login(user)
        receipt, _ = self._create(user.uid)
        return self._run(user.uid, receipt)

    def reconcile_with_receipt(self, uid, receipt):
        """Oturumsuz, yalnız kendi kaydına erişen sonuç sorgusu ve uzlaştırma."""
        self._require_db()
        data = self._ref(uid).get().to_dict() if uid and receipt else None
        if not data or not hmac.compare_digest(data.get("receipt_hash", ""), _hash(receipt)):
            return None
        if data["status"] != "completed" and not self.identity.exists(uid):
            # Auth yoksa normal oturumla devam edilemez; kalan adımlar sunucuda tamamlanır.
            return self._run(uid, None, auth_missing=True)
        return (200 if data["status"] == "completed" else 202), self._public(data)

    # İşaret ve kira --------------------------------------------------------

    def _ref(self, uid):
        return self.db.collection(DELETIONS).document(uid)

    def _require_db(self):
        if self.db is None:
            raise DeletionUnavailable

    def _create(self, uid):
        ref = self._ref(uid)
        receipt = secrets.token_urlsafe(32)
        now = self.clock()

        @firestore.transactional
        def create(tx):
            if ref.get(transaction=tx).exists:
                return False
            tx.create(ref, {"status": "pending", "completed_steps": [], "attempts": 0, "failed_step": None,
                            "receipt_hash": _hash(receipt), "created_at": now, "updated_at": now,
                            "lease_id": None, "lease_until": None})
            return True

        created = commit_transaction(self.db, create)
        return (receipt if created else None), created

    def _claim(self, uid):
        ref = self._ref(uid)
        lease = secrets.token_hex(8)
        now = self.clock()
        until = now + timedelta(seconds=self.settings.account_deletion_time_budget_seconds + 30)

        @firestore.transactional
        def claim(tx):
            data = ref.get(transaction=tx).to_dict()
            if data["status"] == "completed":
                return None, data
            if data.get("lease_until") and data["lease_until"] > now:
                return None, data
            update = {"status": "in_progress", "attempts": data["attempts"] + 1, "failed_step": None,
                      "lease_id": lease, "lease_until": until, "updated_at": now}
            tx.update(ref, update)
            return lease, {**data, **update}

        return commit_transaction(self.db, claim)

    def _update(self, uid, lease, changes):
        ref = self._ref(uid)

        @firestore.transactional
        def write(tx):
            data = ref.get(transaction=tx).to_dict()
            if data.get("lease_id") != lease:
                raise LostLease
            tx.update(ref, {**changes, "updated_at": self.clock()})
            return {**data, **changes}

        return commit_transaction(self.db, write)

    # Çalıştırma ------------------------------------------------------------

    def _run(self, uid, receipt, auth_missing=False):
        lease, data = self._claim(uid)
        if lease is None:
            code = 200 if data["status"] == "completed" else 202
            return code, self._public(data, receipt)
        started = monotonic()
        done = list(data["completed_steps"])
        step = None
        try:
            for step in STEPS:
                if step in done:
                    continue
                if monotonic() - started > self.settings.account_deletion_time_budget_seconds:
                    data = self._update(uid, lease, {"lease_id": None, "lease_until": None})
                    return 202, self._public(data, receipt)
                self.before_step(step)
                if step == "auth":
                    if not auth_missing:
                        self.identity.delete(uid)
                    break
                complete = getattr(self, f"_step_{step}")(uid, started)
                if not complete:
                    data = self._update(uid, lease, {"lease_id": None, "lease_until": None})
                    return 202, self._public(data, receipt)
                done.append(step)
                data = self._update(uid, lease, {"completed_steps": done})
        except LostLease:
            return 202, self._public(self._ref(uid).get().to_dict(), receipt)
        except Exception:
            data = self._update(uid, lease, {"status": "failed", "failed_step": step, "lease_id": None, "lease_until": None})
            return 500, self._public(data, receipt)
        # Auth silindi. Tamamlanma kaydı ancak şimdi yazılır; yazılamazsa durum completed
        # gösterilmez, kira süresi dolunca makbuzla uzlaştırılır.
        now = self.clock()
        try:
            data = self._update(uid, lease, {
                "status": "completed", "completed_steps": [*done, "auth"], "completed_at": now,
                "expires_at": now + timedelta(days=TTL_DAYS[DELETIONS]), "lease_id": None, "lease_until": None,
            })
        except Exception:
            pending = {**data, "status": "in_progress", "completed_steps": done, "failed_step": "completion_record"}
            return 500, self._public(pending, receipt)
        return 200, self._public(data, receipt)

    @staticmethod
    def _public(data, receipt=None):
        body = {key: data.get(key) for key in ("status", "completed_steps", "failed_step", "attempts")}
        body["updated_at"] = data.get("updated_at")
        if receipt:
            body["receipt"] = receipt
        return body

    # Adımlar ---------------------------------------------------------------

    def _deadline(self, started):
        return monotonic() - started > self.settings.account_deletion_time_budget_seconds

    def _delete_query(self, query, started):
        """Sorgu boşalana kadar 500'lük gruplarla siler. Süre dolarsa False döner."""
        while True:
            snaps = list(query.limit(BATCH).stream())
            if not snaps:
                return True
            self._delete_refs([snap.reference for snap in snaps])
            if self._deadline(started):
                return False

    def _delete_refs(self, refs):
        for start in range(0, len(refs), BATCH):
            batch = self.db.batch()
            for ref in refs[start:start + BATCH]:
                batch.delete(ref)
                self.on_delete(ref.path)
            batch.commit()

    def _where(self, collection, field, value):
        return self.db.collection(collection).where(filter=FieldFilter(field, "==", value))

    def _lesson_ids(self, uid):
        query = self._where("lessons", "student_id", uid).select(["student_id"])
        return [snap.id for snap in query.stream()]

    def _step_revoke_tokens(self, uid, started):
        self.identity.revoke(uid)
        return True

    def _step_shared_solutions(self, uid, started):
        if not self._delete_query(self._where("shared_solutions", "owner_id", uid), started):
            return False
        # TA-001 biçimindeki paylaşım yalnız sahip olunan dersten oluşturulabildiğinden, sahip
        # alanı olmasa da kaynak ders bu kullanıcıya aitse sahiplik kesindir. TA-001 öncesi
        # biçimdekiler tahminle silinmez; G paketindeki işletmeci betiğiyle ele alınır.
        refs = []
        lessons = self._lesson_ids(uid)
        for start in range(0, len(lessons), 30):
            query = self.db.collection("shared_solutions").where(
                filter=FieldFilter("source_lesson_plan_id", "in", lessons[start:start + 30]))
            refs += [snap.reference for snap in query.stream()
                     if "owner_id" not in (data := snap.to_dict()) and is_current_format(data)]
        self._delete_refs(refs)
        return True

    def _step_practice_questions(self, uid, started):
        if not self._delete_query(self._where("practice_questions", "student_id", uid), started):
            return False
        # Sahip alanı olmayan eski pratik soruları yalnız sahip olunan derse bağlıysa silinir.
        lessons = self._lesson_ids(uid)
        for start in range(0, len(lessons), 30):
            query = self.db.collection("practice_questions").where(
                filter=FieldFilter("lesson_id", "in", lessons[start:start + 30]))
            self._delete_refs([snap.reference for snap in query.stream()])
        return True

    def _step_practice_attempts(self, uid, started):
        return self._delete_query(self._where("practice_attempts", "student_id", uid), started)

    def _step_interaction_events(self, uid, started):
        return self._delete_query(self._where("interaction_events", "student_id", uid), started)

    def _step_feedback(self, uid, started):
        return self._delete_query(self._where("feedback", "user_id", uid), started)

    def _step_lesson_analyses(self, uid, started):
        return self._delete_query(self._where("lesson_analyses", "owner", uid), started)

    def _step_usage(self, uid, started):
        identity = _hash(uid)
        for collection in (DAILY, OUTPUT):
            if not self._delete_query(self._where(collection, "owner_hash", identity), started):
                return False
            # owner_hash alanı TA-001B ile geldi; daha eski belgeler kimlikten hesaplanır.
            first, last = USAGE_HISTORY_START, self.clock().date() + timedelta(days=1)
            refs = [self.db.collection(collection).document(f"{first + timedelta(days=i)}_{identity}")
                    for i in range((last - first).days + 1)]
            self._delete_refs([snap.reference for snap in self.db.get_all(refs) if snap.exists])
        return True

    def _step_lessons(self, uid, started):
        return self._delete_query(self._where("lessons", "student_id", uid), started)

    def _single(self, collection, uid):
        snap = self.db.collection(collection).document(uid).get()
        if snap.exists:
            self._delete_refs([snap.reference])
        return True

    def _step_student_memories(self, uid, started):
        return self._single("student_memories", uid)

    def _step_student_profiles(self, uid, started):
        return self._single("student_profiles", uid)

    def _step_users(self, uid, started):
        return self._single("users", uid)


class FirebaseIdentity:
    """Firebase Admin Auth üzerindeki dar arayüz; testlerde sahte uygulamayla değiştirilir."""

    def __init__(self, app=None):
        self.app = app

    def revoke(self, uid):
        from firebase_admin import auth

        try:
            auth.revoke_refresh_tokens(uid, app=self.app)
        except auth.UserNotFoundError:
            pass

    def delete(self, uid):
        from firebase_admin import auth

        try:
            auth.delete_user(uid, app=self.app)
        except auth.UserNotFoundError:
            pass

    def exists(self, uid):
        from firebase_admin import auth

        try:
            auth.get_user(uid, app=self.app)
            return True
        except auth.UserNotFoundError:
            return False
