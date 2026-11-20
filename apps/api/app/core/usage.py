"""UTC daily admission. Firestore retries conflicting transactions before a provider is called."""
from apps.api.app.core.transactions import commit as commit_transaction
from datetime import datetime, timezone
from .retention import DAILY, OUTPUT, retention
from hashlib import sha256
from threading import Lock
from fastapi import HTTPException
from firebase_admin import firestore


PAID_OPERATIONS = {"analyze", "generate", "interact"}


class UsageLimitExceeded(Exception):
    pass


class UsageTracker:
    def __init__(self, settings, db=None):
        self.settings = settings
        self.db = db
        self.output = {}
        self.days = {}
        self.lock = Lock()

    def record(self, uid, operation, key=None):
        day = datetime.now(timezone.utc).date().isoformat()
        identity = sha256(uid.encode()).hexdigest()
        doc_id = f"{day}_{identity}"
        fingerprint = sha256(f"{operation}:{key}".encode()).hexdigest() if key else None

        def reserve(data):
            counts = data.get("counts", {}).copy()
            keys = data.get("keys", [])
            total = data.get("total", 0)
            if fingerprint and fingerprint in keys:
                raise HTTPException(409, "Request already admitted.")
            paid = operation in PAID_OPERATIONS
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

        if self.db is None:
            with self.lock:
                self.days[doc_id] = reserve(self.days.get(doc_id, {}))
            return
        ref = self.db.collection(DAILY).document(doc_id)

        @firestore.transactional
        def update(tx):
            tx.set(ref, {**reserve(ref.get(transaction=tx).to_dict() or {}), **retention(DAILY, day)})

        commit_transaction(self.db, update)

    def reserve_output(self, uid, limit):
        key = (
            datetime.now(timezone.utc).date().isoformat()
            + "_"
            + sha256(uid.encode()).hexdigest()
        )
        self._adjust_output(key, limit)
        return key

    def release_output(self, key, unused):
        self._adjust_output(key, -unused)

    def _adjust_output(self, key, delta):
        def adjust(amount):
            total = amount + delta
            if delta > 0 and total > self.settings.daily_output_tokens:
                raise UsageLimitExceeded
            return total

        if self.db is None:
            with self.lock:
                self.output[key] = adjust(self.output.get(key, 0))
            return
        ref = self.db.collection(OUTPUT).document(key)

        @firestore.transactional
        def update(tx):
            current = ref.get(transaction=tx).to_dict() or {}
            tx.set(ref, {"output_tokens": adjust(current.get("output_tokens", 0)), **retention(OUTPUT, key[:10])})

        try:
            commit_transaction(self.db, update)
        except UsageLimitExceeded:
            raise
        except Exception:
            raise HTTPException(503, "Usage service unavailable.") from None
