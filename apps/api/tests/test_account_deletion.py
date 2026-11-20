"""F paketi: uygulama içi hesap silme. Yalnız Firestore emülatörü ve sahte Auth kimliği kullanılır."""

import asyncio
import json
import threading
from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from google.cloud.firestore_v1.base_query import FieldFilter

import apps.api.app.features.lessons.openai_provider as lesson_module
from apps.api.app.core.settings import Settings
from apps.api.app.core.usage import UsageTracker
from apps.api.app.features.account.service import STEPS, AccountDeletionService
from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.feedback.email import NoopFeedbackEmailProvider
from apps.api.app.features.feedback.firestore_repository import FirestoreFeedbackRepository
from apps.api.app.features.feedback.service import FeedbackService
from apps.api.app.features.interactions.service import InteractionService
from apps.api.app.features.interactions.store import FirestorePracticeStore, PracticeRecord
from apps.api.app.features.lessons.openai_provider import OpenAILessonProvider
from apps.api.app.features.lessons.service import LessonService
from apps.api.app.features.mathai.isolated import IsolatedMathAI
from apps.api.app.features.memory.engine import MemoryEngine
from apps.api.app.features.shares.firestore_repository import FirestoreShareRepository
from apps.api.app.features.shares.service import ShareService
from apps.api.app.features.students.firestore_repository import FirestoreStudentRepository
from apps.api.app.features.students.service import StudentService
from apps.api.tests.fake_openai import FakeRaw, body, fake_client, usage
from apps.api.tests.test_feedback import generated_result
from apps.api.tests.test_firestore_integration import databases as databases_fixture
from apps.api.tests.test_interactions import Provider as InteractionProvider
from apps.api.tests.test_lesson_provider_errors import lesson_payload

databases = databases_fixture
PREFIX = "/api/v1"
OWNER_FIELDS = {
    "lessons": "student_id",
    "lesson_analyses": "owner",
    "practice_questions": "student_id",
    "interaction_events": "student_id",
    "practice_attempts": "student_id",
    "shared_solutions": "owner_id",
    "feedback": "user_id",
    "ai_daily_usage": "owner_hash",
    "ai_output_usage": "owner_hash",
}
SINGLE = ("student_profiles", "users", "student_memories")


class Clock:
    def __init__(self):
        self.now = datetime.now(UTC)

    def __call__(self):
        return self.now


class FakeIdentity:
    def __init__(self):
        self.deleted, self.revoked, self.fail_delete = set(), [], 0

    def revoke(self, uid):
        self.revoked.append(uid)

    def delete(self, uid):
        if self.fail_delete:
            self.fail_delete -= 1
            raise ConnectionError("bağlantı koptu")
        self.deleted.add(uid)

    def exists(self, uid):
        return uid not in self.deleted


class Verifier:
    """Belirteç = uid. Silinmiş Auth kullanıcısının belirteci reddedilir (check_revoked davranışı)."""

    def __init__(self, identity, clock):
        self.identity, self.clock, self.auth_age, self.accept_deleted = identity, clock, 10, False

    def verify(self, token):
        if not self.identity.exists(token) and not self.accept_deleted:
            raise ValueError("deleted")
        return AuthenticatedUser(uid=token, auth_time=int(self.clock().timestamp()) - self.auth_age)


@pytest.fixture
def stack(databases, monkeypatch):
    db = databases[0]
    settings = Settings(environment="test")
    clock, identity = Clock(), FakeIdentity()
    from apps.api.app.main import create_app

    app = create_app(settings)
    students = StudentService(FirestoreStudentRepository(db), MemoryEngine())
    deletion = AccountDeletionService(settings, db, identity, clock)
    verifier = Verifier(identity, clock)
    app.state.container = replace(
        app.state.container,
        token_verifier=verifier,
        student_service=students,
        share_service=ShareService(FirestoreShareRepository(db), settings),
        feedback_service=FeedbackService(FirestoreFeedbackRepository(db), NoopFeedbackEmailProvider(), settings),
        usage_tracker=UsageTracker(settings, db),
        interaction_service=InteractionService(InteractionProvider(), IsolatedMathAI(), FirestorePracticeStore(db)),
        account_deletion=deletion,
    )
    return SimpleNamespace(app=app, db=db, students=students, deletion=deletion, identity=identity, clock=clock, verifier=verifier, client=TestClient(app))


def headers(uid):
    return {"Authorization": f"Bearer {uid}"}


def seed(stack, uid):
    """Her koleksiyona hem gerçek yazma yollarıyla hem eski biçimde kayıt üretir."""
    db, user, client = stack.db, AuthenticatedUser(uid=uid), stack.client
    assert client.put(PREFIX + "/students/me/profile", headers=headers(uid), json={"display_name": "Öğrenci"}).status_code == 200
    result = generated_result()
    result.lesson.lesson_plan_id = "lesson_" + uuid4().hex
    analysis = result.lesson.source_analysis.model_copy(update={"request_id": "analysis_" + uuid4().hex})
    stack.students.save_analysis(user, analysis)
    stack.students.save_lesson(user, result)
    lesson_id = result.lesson.lesson_plan_id
    store = FirestorePracticeStore(db)
    pid = "practice_" + uuid4().hex
    store.save(PracticeRecord(pid, lesson_id, "x + 1 = 2", "1", "x", "İpucu", "Denklem", None, "concept", "easy", student_id=uid))
    answer = client.post(f"{PREFIX}/lessons/{lesson_id}/practice/{pid}/answer", headers=headers(uid), json={"answer": "1"})
    assert answer.status_code == 200, answer.text
    share = client.post(PREFIX + "/shares", headers=headers(uid), json={"lesson_id": lesson_id})
    assert share.status_code == 200, share.text
    assert client.post(PREFIX + "/feedback", headers=headers(uid), json={"lesson_id": lesson_id, "rating": "positive"}).status_code == 200
    stack.app.state.container.usage_tracker.reserve_output(uid, 100)
    # Eski biçimler: sahip alanı olmayan pratik ve TA-001 biçimli paylaşım, owner_hash alanı olmayan kota.
    db.collection("practice_questions").document("legacy_" + uuid4().hex).set({"lesson_id": lesson_id, "question": "x = 1"})
    current = db.collection("shared_solutions").document(share.json()["data"]["share_id"]).get().to_dict()
    legacy_current = {k: v for k, v in current.items() if k != "owner_id"}
    db.collection("shared_solutions").document("legacycur" + uuid4().hex[:6]).set({**legacy_current, "share_id": "x"})
    pre_ta001 = {**legacy_current, "question_summary": "Ham soru metni: 3x + 7 = 19", "share_id": "y"}
    pre_id = "pre" + uuid4().hex[:8]
    db.collection("shared_solutions").document(pre_id).set(pre_ta001)
    digest = sha256(uid.encode()).hexdigest()
    db.collection("ai_daily_usage").document(f"2026-11-19_{digest}").set({"total": 1})
    return {"lesson_id": lesson_id, "pre_ta001_share": pre_id, "digest": digest}


def owned(stack, uid, info):
    """Koleksiyon başına kullanıcının belge yolları (sahip alanı, ders bağı ve hesaplanan kimlikler)."""
    db, digest = stack.db, sha256(uid.encode()).hexdigest()
    found = {}
    for collection, field in OWNER_FIELDS.items():
        value = digest if field == "owner_hash" else uid
        found[collection] = {s.reference.path for s in db.collection(collection).where(filter=FieldFilter(field, "==", value)).stream()}
    for collection in ("practice_questions", "shared_solutions"):
        query = db.collection(collection).where(filter=FieldFilter("lesson_id" if collection == "practice_questions" else "source_lesson_plan_id", "==", info["lesson_id"]))
        found[collection] |= {s.reference.path for s in query.stream() if s.id != info["pre_ta001_share"]}
    legacy = db.collection("ai_daily_usage").document(f"2026-11-19_{digest}").get()
    if legacy.exists:
        found["ai_daily_usage"].add(legacy.reference.path)
    for collection in SINGLE:
        snap = db.collection(collection).document(uid).get()
        found[collection] = {snap.reference.path} if snap.exists else set()
    return found


def counts(found):
    return {collection: len(paths) for collection, paths in found.items()}


def delete(stack, uid):
    return stack.client.post(PREFIX + "/account/deletion", headers=headers(uid), json={"confirm": True})


def test_deleting_a_removes_every_collection_and_keeps_b(stack):
    a, b = "a_" + uuid4().hex, "b_" + uuid4().hex
    info_a, info_b = seed(stack, a), seed(stack, b)
    before_a, before_b = counts(owned(stack, a, info_a)), counts(owned(stack, b, info_b))
    assert all(before_a.values()) and all(before_b.values()), before_a
    response = delete(stack, a)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "completed"
    after_a = counts(owned(stack, a, info_a))
    for collection, count in after_a.items():
        assert count == 0, f"{collection}: A'ya ait {count} belge kaldı"
    assert counts(owned(stack, b, info_b)) == before_b
    # TA-001 öncesi biçimli, sahipsiz paylaşım tahminle silinmez; G betiğiyle ele alınır.
    assert stack.db.collection("shared_solutions").document(info_a["pre_ta001_share"]).get().exists
    assert a in stack.identity.deleted and stack.identity.revoked == [a]
    record = stack.db.collection("account_deletions").document(a).get().to_dict()
    assert set(record) >= {"status", "completed_steps", "attempts", "created_at", "expires_at"}
    assert record["expires_at"] - record["completed_at"] == timedelta(days=30)
    assert "email" not in str(record) and "Öğrenci" not in str(record)


@pytest.mark.parametrize("step", STEPS)
def test_failure_at_each_step_resumes_without_reprocessing(stack, step):
    uid = "u_" + uuid4().hex
    info = seed(stack, uid)
    fired, calls, deleted = [], Counter(), []

    def before(name):
        calls[name] += 1
        if name == step and not fired:
            fired.append(name)
            raise RuntimeError("yapay hata")

    stack.deletion.before_step = before
    stack.deletion.on_delete = deleted.append
    first = delete(stack, uid)
    assert first.status_code == 500 and first.json()["error"] == "account_deletion_incomplete"
    assert first.json()["data"]["status"] == "failed" and first.json()["data"]["failed_step"] == step
    assert uid not in stack.identity.deleted
    second = delete(stack, uid)
    assert second.status_code == 200 and second.json()["data"]["status"] == "completed"
    assert all(count == 1 for name, count in calls.items() if name != step), calls
    assert calls[step] == 2
    assert not [path for path, n in Counter(deleted).items() if n > 1], "bir belge iki kez işlendi"
    assert not any(counts(owned(stack, uid, info)).values())


def test_writes_are_rejected_while_deletion_is_in_progress(stack):
    uid = "u_" + uuid4().hex
    info = seed(stack, uid)
    stack.deletion.settings = stack.deletion.settings.model_copy(update={"account_deletion_time_budget_seconds": 0})
    response = delete(stack, uid)
    assert response.status_code == 202 and response.json()["data"]["status"] == "in_progress"
    before = counts(owned(stack, uid, info))
    lesson = info["lesson_id"]
    attempts = {
        "ücretli işlem": stack.client.post(PREFIX + "/lessons/generate", headers=headers(uid), json={"analysis_id": "x"}),
        "geçmiş kaydı": stack.client.post(PREFIX + "/students/me/lessons", headers=headers(uid), json={"lesson_id": lesson}),
        "paylaşım": stack.client.post(PREFIX + "/shares", headers=headers(uid), json={"lesson_id": lesson}),
        "geri bildirim": stack.client.post(PREFIX + "/feedback", headers=headers(uid), json={"lesson_id": lesson, "rating": "negative"}),
        "pratik yanıtı": stack.client.post(f"{PREFIX}/lessons/{lesson}/practice/p1/answer", headers=headers(uid), json={"answer": "2"}),
        "profil": stack.client.put(PREFIX + "/students/me/profile", headers=headers(uid), json={"display_name": "Yeni"}),
    }
    for name, result in attempts.items():
        assert (result.status_code, result.json()["error"]) == (409, "account_deletion_in_progress"), name
    assert counts(owned(stack, uid, info)) == before


@pytest.mark.parametrize(("age", "expected"), [(301, 401), (299, 200)])
def test_recent_login_is_required(stack, age, expected):
    uid = "u_" + uuid4().hex
    stack.verifier.auth_age = age
    response = delete(stack, uid)
    assert response.status_code == expected
    if expected == 401:
        assert response.json()["error"] == "reauthentication_required"
        assert not stack.db.collection("account_deletions").document(uid).get().exists


def test_auth_failure_is_failed_never_completed(stack):
    uid = "u_" + uuid4().hex
    seed(stack, uid)
    stack.identity.fail_delete = 5
    for _ in range(2):
        response = delete(stack, uid)
        assert response.status_code == 500 and response.json()["data"]["status"] == "failed"
        assert response.json()["data"]["failed_step"] == "auth"
    status = stack.client.get(PREFIX + "/account/deletion", headers=headers(uid)).json()["data"]
    assert status["status"] == "failed" and "auth" not in status["completed_steps"]
    assert stack.identity.exists(uid)


def test_other_users_deletion_record_is_not_reachable(stack):
    a, b = "a_" + uuid4().hex, "b_" + uuid4().hex
    receipt = delete(stack, a).json()["data"]["receipt"]
    assert stack.client.get(PREFIX + "/account/deletion", headers=headers(b)).status_code == 404
    wrong = stack.client.post(PREFIX + "/account/deletion/receipt", json={"uid": a, "receipt": "x" * 43})
    assert wrong.status_code == 404
    swapped = stack.client.post(PREFIX + "/account/deletion/receipt", json={"uid": b, "receipt": receipt})
    assert swapped.status_code == 404


# Bağlayıcı ek, zorunlu regresyonlar ----------------------------------------


def blocked_lesson(stack, monkeypatch):
    """Sağlayıcı yanıtını dışarıdan bırakılana kadar bekleten ders yolu."""
    gate, entered = threading.Event(), threading.Event()

    async def parse(**kwargs):
        entered.set()
        await asyncio.to_thread(gate.wait, 30)
        return FakeRaw(body(text=json.dumps(lesson_payload()), tokens=usage(output_tokens=50)))

    monkeypatch.setattr(lesson_module, "AsyncOpenAI", lambda **kwargs: SimpleNamespace(responses=fake_client(parse).responses, close=AsyncMock()))
    container = stack.app.state.container
    stack.app.state.container = replace(container, lesson_service=LessonService(OpenAILessonProvider("fixture-key", "fixture", 30), IsolatedMathAI(), BoardPlanner()))
    return gate, entered


@pytest.mark.parametrize("finish", [False, True], ids=["silme-sürerken", "silme-tamamlandıktan-sonra"])
def test_in_flight_ai_request_cannot_persist_after_deletion(stack, monkeypatch, finish):
    """Regresyon 1 ve 2: AI isteği başladıktan sonra silme; gecikmiş AI cevabı."""
    uid = "u_" + uuid4().hex
    gate, entered = blocked_lesson(stack, monkeypatch)
    analysis = generated_result().lesson.source_analysis.model_copy(update={"request_id": "analysis_" + uuid4().hex})
    stack.students.save_analysis(AuthenticatedUser(uid=uid), analysis)
    outcome = {}
    worker = threading.Thread(target=lambda: outcome.update(response=stack.client.post(
        PREFIX + "/lessons/generate", headers=headers(uid), json={"analysis_id": analysis.request_id})))
    worker.start()
    assert entered.wait(10)
    if not finish:
        stack.deletion.settings = stack.deletion.settings.model_copy(update={"account_deletion_time_budget_seconds": 0})
    response = delete(stack, uid)
    assert response.status_code == (200 if finish else 202), response.text
    gate.set()
    worker.join(30)
    late = outcome["response"]
    assert (late.status_code, late.json()["error"]) == (409, "account_deletion_in_progress")
    db = stack.db
    assert not list(db.collection("lessons").where(filter=FieldFilter("student_id", "==", uid)).stream())
    assert not list(db.collection("interaction_events").where(filter=FieldFilter("student_id", "==", uid)).stream())
    assert not db.collection("student_memories").document(uid).get().exists
    if finish:
        digest = sha256(uid.encode()).hexdigest()
        assert not list(db.collection("ai_output_usage").where(filter=FieldFilter("owner_hash", "==", digest)).stream())


def test_concurrent_deletions_run_each_step_once(stack):
    """Regresyon 3: aynı hesap için eşzamanlı iki silme isteği."""
    uid = "u_" + uuid4().hex
    seed(stack, uid)
    calls, barrier = Counter(), threading.Barrier(2)
    stack.deletion.before_step = lambda name: calls.update([name])
    results = []

    def run():
        barrier.wait()
        results.append(delete(stack, uid))

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(60)
    assert sorted(r.status_code for r in results) in ([200, 202], [200, 200])
    assert set(calls.values()) == {1} and set(calls) == set(STEPS)
    final = stack.db.collection("account_deletions").document(uid).get().to_dict()
    assert final["status"] == "completed" and final["attempts"] == 1


def test_auth_deleted_but_completion_record_failed_is_reconciled(stack, monkeypatch):
    """Regresyon 4: Auth silme başarılı, tamamlanma kaydı başarısız."""
    uid = "u_" + uuid4().hex
    seed(stack, uid)
    original = stack.deletion._update

    def failing(target, lease, changes):
        if changes.get("status") == "completed":
            raise ConnectionError("yazma başarısız")
        return original(target, lease, changes)

    monkeypatch.setattr(stack.deletion, "_update", failing)
    first = delete(stack, uid)
    receipt = first.json()["data"]["receipt"]
    assert first.status_code == 500 and first.json()["data"]["status"] != "completed"
    assert uid in stack.identity.deleted
    monkeypatch.setattr(stack.deletion, "_update", original)
    # Auth yok: normal oturum reddedilir; makbuzla, kira süresi dolduktan sonra uzlaştırılır.
    assert delete(stack, uid).status_code == 401
    assert stack.client.post(PREFIX + "/account/deletion/receipt", json={"uid": uid, "receipt": receipt}).status_code == 202
    stack.clock.now += timedelta(minutes=5)
    done = stack.client.post(PREFIX + "/account/deletion/receipt", json={"uid": uid, "receipt": receipt})
    assert done.status_code == 200 and done.json()["data"]["status"] == "completed"


def test_connection_drop_on_last_step_resumes_safely(stack):
    """Regresyon 5: son adımda bağlantı kesilmesi ve güvenli devam."""
    uid = "u_" + uuid4().hex
    info = seed(stack, uid)
    stack.identity.fail_delete = 1
    first = delete(stack, uid)
    receipt = first.json()["data"]["receipt"]
    assert first.status_code == 500 and first.json()["data"]["failed_step"] == "auth"
    assert not any(counts(owned(stack, uid, info)).values())
    second = delete(stack, uid)
    assert second.status_code == 200 and second.json()["data"]["status"] == "completed"
    # Yanıt istemciye ulaşmasa bile sonuç makbuzla okunabilir; tekrar silme çalışmaz.
    again = stack.client.post(PREFIX + "/account/deletion/receipt", json={"uid": uid, "receipt": receipt})
    assert again.status_code == 200 and again.json()["data"]["status"] == "completed"


def test_stale_session_cannot_write_after_deletion(stack):
    """Regresyon 6: silme sonrasında eski oturumla veri yazma girişimi."""
    uid = "u_" + uuid4().hex
    info = seed(stack, uid)
    assert delete(stack, uid).status_code == 200
    lesson = info["lesson_id"]
    # Silinmiş kullanıcının belirteci reddedilir.
    assert stack.client.put(PREFIX + "/students/me/profile", headers=headers(uid), json={"display_name": "X"}).status_code == 401
    # Doğrulaması önceden geçmiş bir istek olsa bile yazma engeli 409 verir.
    stack.verifier.accept_deleted = True
    writes = [
        stack.client.put(PREFIX + "/students/me/profile", headers=headers(uid), json={"display_name": "X"}),
        stack.client.post(PREFIX + "/shares", headers=headers(uid), json={"lesson_id": lesson}),
        stack.client.post(PREFIX + "/feedback", headers=headers(uid), json={"lesson_id": lesson, "rating": "positive"}),
        stack.client.post(PREFIX + "/lessons/generate", headers=headers(uid), json={"analysis_id": "x"}),
    ]
    assert [w.status_code for w in writes] == [409] * 4
    user = AuthenticatedUser(uid=uid)
    result = generated_result()
    result.lesson.lesson_plan_id = "lesson_" + uuid4().hex
    from apps.api.app.features.account.guard import AccountDeletionInProgress

    with pytest.raises(AccountDeletionInProgress):
        stack.students.save_lesson(user, result)
    with pytest.raises(AccountDeletionInProgress):
        stack.students.save_analysis(user, result.lesson.source_analysis.model_copy(update={"request_id": "analysis_" + uuid4().hex}))
    assert not any(counts(owned(stack, uid, info)).values())
