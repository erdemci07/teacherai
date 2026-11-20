"""Requires a local emulator. Never construct clients pointed at production."""

import os
import re
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from apps.api.app.core.settings import Settings
from apps.api.app.core.usage import UsageLimitExceeded, UsageTracker
from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.features.interactions.schemas import (
    InteractionRequest,
    PracticeAnswerRequest,
)
from apps.api.app.features.interactions.service import InteractionService
from apps.api.app.features.interactions.store import FirestorePracticeStore
from apps.api.app.features.mathai.service import MathAIService
from apps.api.app.features.memory.engine import MemoryEngine
from apps.api.app.features.students.firestore_repository import (
    FirestoreStudentRepository,
)
from apps.api.app.features.students.service import StudentService
from apps.api.tests.test_feedback import generated_result
from apps.api.tests.test_interactions import Provider
from google.auth.credentials import AnonymousCredentials
from google.cloud.firestore import Client


@pytest.fixture
def databases():
    host = os.environ.get("FIRESTORE_EMULATOR_HOST")
    if not host:
        pytest.skip("local Firestore emulator required")
    assert re.fullmatch(r"(127\.0\.0\.1|localhost):\d+", host)
    clients = [
        Client(project="demo-teacherai", credentials=AnonymousCredentials())
        for _ in range(2)
    ]
    yield clients
    for client in clients:
        client.close()


def test_atomic_quota_across_clients(databases):
    settings = Settings(
        authenticated_daily_ai_limit=2, operation_limits={"generate": 2}
    )
    uid = uuid4().hex
    trackers = [UsageTracker(settings, client) for client in databases]

    def reserve(i):
        try:
            trackers[i % 2].record(uid, "generate")
            return 1
        except UsageLimitExceeded:
            return 0

    with ThreadPoolExecutor(2) as pool:
        assert sum(pool.map(reserve, range(4))) == 2
    with pytest.raises(UsageLimitExceeded):
        UsageTracker(settings, databases[0]).record(uid, "generate")
    settings.daily_output_tokens = 200
    key = trackers[0].reserve_output(uid, 150)
    with pytest.raises(UsageLimitExceeded):
        trackers[1].reserve_output(uid, 60)
    trackers[1].release_output(key, 50)
    # Rezervasyon nesnesi kullanıcı ve küresel payı taşır (TA-001B, C); anahtar aynı kalır.
    assert trackers[0].reserve_output(uid, 100).key == key.key


@pytest.mark.asyncio
async def test_practice_and_stats_survive_new_client(databases):
    user = AuthenticatedUser(uid=uuid4().hex)
    result = generated_result()
    lesson = result.lesson
    lesson.lesson_plan_id = "lesson_" + uuid4().hex
    students = [
        StudentService(FirestoreStudentRepository(client), MemoryEngine())
        for client in databases
    ]
    students[0].save_lesson(user, result)
    assert students[1].owned(user, lesson.lesson_plan_id).server_generated
    services = [
        InteractionService(Provider(), MathAIService(), FirestorePracticeStore(db))
        for db in databases
    ]
    created = await services[0].interact(
        lesson.lesson_plan_id,
        InteractionRequest(action="similar_example", lesson=lesson),
    )
    pid = created.practice.practice_question_id

    def submit(i):
        feedback = services[i].submit(
            lesson.lesson_plan_id, pid, PracticeAnswerRequest(answer="4")
        )
        students[i].record_event(user, feedback.event, pid)
        return feedback.event.event_id

    with ThreadPoolExecutor(2) as pool:
        assert len(set(pool.map(submit, range(2)))) == 1
    stats = students[1].dashboard(user)
    assert (
        stats.questions_solved,
        stats.practice_attempts,
        stats.practice_correct,
    ) == (1, 1, 1)


def test_question_revision_is_owned_serialized_and_blocked_after_deletion(databases):
    """TA-003: açıklama aynı analiz belgesinde tek işlemde yeni revizyon yazar; TTL uzamaz."""
    from apps.api.app.core.retention import ANALYSES
    from apps.api.app.features.account.guard import AccountDeletionInProgress
    from apps.api.app.features.education.source import ClarificationRequest
    from apps.api.app.features.vision.exceptions import (
        AnalysisUnavailableError,
        StaleQuestionRevisionError,
    )
    from apps.api.tests.test_question_integrity import SIGN, analysis

    uid = uuid4().hex
    user = AuthenticatedUser(uid=uid)
    students = [StudentService(FirestoreStudentRepository(client), MemoryEngine()) for client in databases]
    current = analysis(request_id=f"analysis_{uid}", **SIGN)
    students[0].save_analysis(user, current)
    ref = databases[0].collection(ANALYSES).document(current.request_id)
    expires = ref.get().to_dict()["expires_at"]
    pending = current.integrity.pending()[0]
    requests = [ClarificationRequest(expected_revision=1, uncertainty_id=pending.id, selection=selection)
                for selection in ("recognized", pending.alternatives[0].id)]
    with pytest.raises(AnalysisUnavailableError):
        students[1].clarify(AuthenticatedUser(uid="other"), current.request_id, requests[0])

    def clarify(i):
        try:
            return students[i].clarify(user, current.request_id, requests[i]).revision
        except StaleQuestionRevisionError:
            return "stale"

    with ThreadPoolExecutor(2) as pool:
        outcomes = sorted(map(str, pool.map(clarify, range(2))))
    assert outcomes == ["2", "stale"]
    stored = students[1].source_analysis(user, current.request_id)
    assert stored.revision == 2 and stored.integrity.revision == 2
    assert ref.get().to_dict()["expires_at"] == expires
    databases[0].collection("account_deletions").document(uid).set({"status": "in_progress"})
    with pytest.raises(AccountDeletionInProgress):
        students[0].clarify(user, current.request_id, ClarificationRequest(expected_revision=2, uncertainty_id=pending.id, selection="none"))
    assert students[1].source_analysis(user, current.request_id).revision == 2
