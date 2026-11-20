"""UTC günlük kabul, çıktı rezervasyonu ve küresel AI bütçesi.

Kullanıcı sayaçları ile küresel gün belgesi (ai_global_usage/{YYYY-MM-DD}) aynı
Firestore işleminde okunup yazılır. Böylece birden fazla Cloud Run örneğinde de
sınır kontrolü ile rezervasyon arasında yarış olmaz; sınır aşılamaz.
Firestore'a ulaşılamazsa istek reddedilir ve sağlayıcı çağrılmaz (fail closed).

Küresel belge alanları:
- http_operations: kabul edilen ücretli HTTP işlemi (analyze, generate, interact)
- provider_calls: gerçek sağlayıcı çağrısı (düzeltme ve bağlam tekrarları dahil)
- reserved_output_tokens: ayrılmış ve iade sonrası kalan çıktı tokenları
- estimated_usd: yalnız raporlama; zorlama işlem, çağrı ve token sayısıyla yapılır
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from threading import Lock

from fastapi import HTTPException
from firebase_admin import firestore

from apps.api.app.core.transactions import commit as commit_transaction

from .retention import DAILY, GLOBAL, OUTPUT, retention

PAID_OPERATIONS = {"analyze", "generate", "interact"}


# Aynı süreçte aynı belge için yarışan işlemleri sıraya alır. Ücretli işlemler tek
# küresel kilidi kullanır; işlem başına yalnızca bir kilit alındığından kilitlenme olmaz.
# Farklı süreçler arasındaki tutarlılığı Firestore işlemi sağlar.
_local_locks = [Lock() for _ in range(64)]


def usage_lock(key):
    return _local_locks[hash(key) % len(_local_locks)]


class UsageLimitExceeded(Exception):
    pass


class GlobalBudgetExhausted(UsageLimitExceeded):
    """Günlük küresel bütçe doldu; 503 / ai_global_budget_exhausted."""


@dataclass
class Reservation:
    key: str
    day: str
    amount: int
    released: bool = False
    _lock: Lock = field(default_factory=Lock, repr=False, compare=False)


def _utc_now():
    return datetime.now(timezone.utc)


class UsageTracker:
    def __init__(self, settings, db=None, clock=_utc_now):
        self.settings = settings
        self.db = db
        self.clock = clock
        self.output = {}
        self.days = {}
        self.globals = {}
        self.lock = Lock()

    def _day(self):
        return self.clock().astimezone(timezone.utc).date().isoformat()

    def _get(self, ref, tx):
        return ref.get(transaction=tx, timeout=self.settings.usage_timeout_seconds).to_dict() or {}

    def _commit(self, lock_key, update):
        with usage_lock(lock_key):
            commit_transaction(self.db, update, self.settings.usage_transaction_attempts)

    # Kabul -----------------------------------------------------------------

    def record(self, uid, operation, key=None):
        day = self._day()
        doc_id = f"{day}_{sha256(uid.encode()).hexdigest()}"
        fingerprint = sha256(f"{operation}:{key}".encode()).hexdigest() if key else None
        paid = operation in PAID_OPERATIONS

        def reserve(data):
            counts = data.get("counts", {}).copy()
            keys = data.get("keys", [])
            total = data.get("total", 0)
            if fingerprint and fingerprint in keys:
                raise HTTPException(409, "Request already admitted.")
            if (paid and total >= self.settings.authenticated_daily_ai_limit) or counts.get(
                operation, 0
            ) >= self.settings.operation_limits.get(operation, 0):
                raise UsageLimitExceeded
            counts[operation] = counts.get(operation, 0) + 1
            return {
                "total": total + int(paid),
                "counts": counts,
                "keys": keys + ([fingerprint] if fingerprint else []),
            }

        def admit_global(data):
            used = data.get("http_operations", 0)
            if used + 1 > self.settings.global_daily_paid_operations:
                raise GlobalBudgetExhausted
            return {**data, "http_operations": used + 1}

        if self.db is None:
            with self.lock:
                user = reserve(self.days.get(doc_id, {}))
                if paid:
                    self.globals[day] = admit_global(self.globals.get(day, {}))
                self.days[doc_id] = user
            return
        ref = self.db.collection(DAILY).document(doc_id)
        global_ref = self.db.collection(GLOBAL).document(day)

        @firestore.transactional
        def update(tx):
            user = reserve(self._get(ref, tx))
            if paid:
                shared = admit_global(self._get(global_ref, tx))
                tx.set(global_ref, {**shared, **retention(GLOBAL, day)})
            tx.set(ref, {**user, **retention(DAILY, day)})

        self._commit(f"global:{day}" if paid else doc_id, update)

    # Çıktı rezervasyonu ----------------------------------------------------

    def reserve_output(self, uid, limit):
        """Her gerçek sağlayıcı çağrısından önce kullanıcı ve küresel bütçeyi birlikte ayırır."""
        day = self._day()
        key = f"{day}_{sha256(uid.encode()).hexdigest()}"

        def user_reserve(data):
            total = data.get("output_tokens", 0) + limit
            if total > self.settings.daily_output_tokens:
                raise UsageLimitExceeded
            return {**data, "output_tokens": total}

        def global_reserve(data):
            calls = data.get("provider_calls", 0) + 1
            tokens = data.get("reserved_output_tokens", 0) + limit
            if calls > self.settings.global_daily_provider_calls or tokens > self.settings.global_daily_output_tokens:
                raise GlobalBudgetExhausted
            return {**data, "provider_calls": calls, "reserved_output_tokens": tokens}

        if self.db is None:
            with self.lock:
                user = user_reserve({"output_tokens": self.output.get(key, 0)})
                self.globals[day] = global_reserve(self.globals.get(day, {}))
                self.output[key] = user["output_tokens"]
            return Reservation(key, day, limit)

        def build():
            ref = self.db.collection(OUTPUT).document(key)
            global_ref = self.db.collection(GLOBAL).document(day)

            @firestore.transactional
            def update(tx):
                user = user_reserve(self._get(ref, tx))
                shared = global_reserve(self._get(global_ref, tx))
                tx.set(ref, {"output_tokens": user["output_tokens"], **retention(OUTPUT, day)})
                tx.set(global_ref, {**shared, **retention(GLOBAL, day)})

            return update

        self._guarded(f"global:{day}", build)
        return Reservation(key, day, limit)

    def release_output(self, reservation, unused, usd=None):
        """Kullanılmayan kısmı bir kez iade eder; sayaçlar sıfırın altına inmez."""
        unused = max(0, min(int(unused), reservation.amount))
        with reservation._lock:
            if reservation.released:
                return False

            def shrink(value):
                return max(0, value - unused)

            if self.db is None:
                with self.lock:
                    self.output[reservation.key] = shrink(self.output.get(reservation.key, 0))
                    shared = self.globals.setdefault(reservation.day, {})
                    shared["reserved_output_tokens"] = shrink(shared.get("reserved_output_tokens", 0))
                    if usd is not None:
                        shared["estimated_usd"] = shared.get("estimated_usd", 0) + usd
            else:

                def build():
                    ref = self.db.collection(OUTPUT).document(reservation.key)
                    global_ref = self.db.collection(GLOBAL).document(reservation.day)

                    @firestore.transactional
                    def update(tx):
                        user = self._get(ref, tx)
                        shared = self._get(global_ref, tx)
                        tx.set(ref, {"output_tokens": shrink(user.get("output_tokens", 0)), **retention(OUTPUT, reservation.day)})
                        shared["reserved_output_tokens"] = shrink(shared.get("reserved_output_tokens", 0))
                        if usd is not None:
                            shared["estimated_usd"] = shared.get("estimated_usd", 0) + usd
                        tx.set(global_ref, {**shared, **retention(GLOBAL, reservation.day)})

                    return update

                self._guarded(f"global:{reservation.day}", build)
            reservation.released = True
            return True

    def _guarded(self, lock_key, build):
        """Firestore hatası 503'e dönüşür; sınır hatası olduğu gibi yükselir."""
        try:
            self._commit(lock_key, build())
        except UsageLimitExceeded:
            raise
        except Exception:
            raise HTTPException(503, "Usage service unavailable.") from None
