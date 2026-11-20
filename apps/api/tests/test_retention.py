import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from apps.api.app.core.retention import ANALYSES, DAILY, OUTPUT, PRACTICE, TTL_DAYS
from apps.api.app.core.settings import Settings
from apps.api.app.core.usage import UsageTracker
from apps.api.app.features.interactions.store import FirestorePracticeStore, PracticeRecord
from apps.api.app.features.students.firestore_repository import FirestoreStudentRepository
from apps.api.tests.test_feedback import generated_result
from apps.api.tests.test_firestore_integration import databases as databases_fixture

databases = databases_fixture


def test_retention_configuration():
    overrides = json.loads(Path("firestore.indexes.json").read_text())["fieldOverrides"]
    assert {x["collectionGroup"] for x in overrides} == set(TTL_DAYS)
    assert all(x["ttl"] and x["fieldPath"] == "expires_at" and x["indexes"] == [] for x in overrides)


@pytest.mark.parametrize("collection", [ANALYSES, PRACTICE, DAILY, OUTPUT])
def test_new_records_have_timestamps(databases, collection):
    db = databases[0]
    uid = uuid4().hex
    tracker = UsageTracker(Settings(), db)
    repo = FirestoreStudentRepository(db)
    store = FirestorePracticeStore(db)
    if collection == ANALYSES:
        analysis = generated_result().lesson.source_analysis.model_copy(update={"request_id": uid})
        repo.save_analysis(uid, analysis)
        ref = db.collection(collection).document(uid)
    elif collection == PRACTICE:
        store.save(PracticeRecord(uid, uid, "x=1", "1", "x", "", "", None, "", ""))
        ref = db.collection(collection).document(uid)
    else:
        from hashlib import sha256
        tracker.record(uid, "generate")
        tracker.reserve_output(uid, 128)
        key = f"{datetime.now(UTC).date()}_{sha256(uid.encode()).hexdigest()}"
        ref = db.collection(collection).document(key)
    doc = ref.get().to_dict()
    assert isinstance(doc["expires_at"], datetime) and doc["created_at"].tzinfo
    assert abs(doc["expires_at"] - doc["created_at"] - timedelta(days=TTL_DAYS[collection])) < timedelta(minutes=1)
    if collection in {ANALYSES, PRACTICE}:
        ref.update({"expires_at": datetime.now(UTC) - timedelta(seconds=1)})
        assert (repo.analysis(uid, uid) if collection == ANALYSES else store.get(uid, uid)) is None


def test_global_usage_record_has_timestamps(databases):
    from apps.api.app.core.retention import GLOBAL

    db = databases[0]
    UsageTracker(Settings(), db).record(uuid4().hex, "generate")
    doc = db.collection(GLOBAL).document(datetime.now(UTC).date().isoformat()).get().to_dict()
    assert isinstance(doc["expires_at"], datetime) and doc["created_at"].tzinfo
    assert abs(doc["expires_at"] - doc["created_at"] - timedelta(days=TTL_DAYS[GLOBAL])) < timedelta(minutes=1)


def test_only_completed_deletion_record_expires(databases):
    from apps.api.app.core.retention import DELETIONS
    from apps.api.app.features.account.service import AccountDeletionService
    from apps.api.app.features.auth.schemas import AuthenticatedUser

    class Identity:
        def revoke(self, uid): ...
        def delete(self, uid): ...
        def exists(self, uid): return False

    db = databases[0]
    uid = uuid4().hex
    settings = Settings(account_deletion_time_budget_seconds=0)
    service = AccountDeletionService(settings, db, Identity())
    user = AuthenticatedUser(uid=uid, auth_time=int(datetime.now(UTC).timestamp()))
    assert service.start_or_resume(user)[0] == 202
    assert "expires_at" not in db.collection(DELETIONS).document(uid).get().to_dict()
    service.settings = Settings()
    assert service.start_or_resume(user)[0] == 200
    doc = db.collection(DELETIONS).document(uid).get().to_dict()
    assert isinstance(doc["expires_at"], datetime)
    assert abs(doc["expires_at"] - doc["completed_at"] - timedelta(days=TTL_DAYS[DELETIONS])) < timedelta(minutes=1)
