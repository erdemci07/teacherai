from dataclasses import replace

from fastapi.testclient import TestClient

from apps.api.app.core.settings import Settings
from apps.api.app.core.container import build_container
from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.feedback.email import RESEND_EMAILS_URL, NoopFeedbackEmailProvider, ResendFeedbackEmailProvider, _email_body
from apps.api.app.features.feedback.repository import InMemoryFeedbackRepository
from apps.api.app.features.feedback.service import FeedbackService
from apps.api.app.features.lessons.service import GeneratedLesson
from apps.api.app.features.mathai.service import MathAIService
from apps.api.app.main import create_app
from apps.api.tests.test_mathai import plan


class RecordingEmailProvider:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.records = []

    def send_critical_feedback(self, record):
        self.records.append(record)
        if self.fail:
            raise RuntimeError("email failed")


def generated_result() -> GeneratedLesson:
    lesson = plan()
    verification = MathAIService().verify(lesson)
    board = BoardPlanner().create(lesson, verification)
    return GeneratedLesson(lesson=lesson, verification=verification, board=board, correction_attempted=False, total_processing_ms=3)


def client_with_feedback(email_provider=None):
    app = create_app(Settings(environment="test", firebase_enabled=False))
    repo = InMemoryFeedbackRepository()
    provider = email_provider or RecordingEmailProvider()
    service = FeedbackService(repo, provider, Settings(environment="test", firebase_enabled=False))
    app.state.container = replace(app.state.container, feedback_service=service)
    return TestClient(app, raise_server_exceptions=False), repo, provider


def payload(**overrides):
    value = {"rating": "positive", "reasons": ["clear"], "comment": "", "result": generated_result().model_dump(mode="json")}
    value.update(overrides)
    return value


def test_positive_feedback_can_be_submitted():
    client, repo, email = client_with_feedback()

    response = client.post("/api/v1/feedback", json=payload())

    assert response.status_code == 200
    assert response.json()["data"]["created"] is True
    assert len(repo.items) == 1
    assert email.records == []


def test_negative_feedback_with_multiple_reasons_can_be_submitted():
    client, repo, _ = client_with_feedback()

    response = client.post("/api/v1/feedback", json=payload(rating="negative", reasons=["wrong_solution", "step_error"]))

    assert response.status_code == 200
    record = next(iter(repo.items.values()))
    assert record.rating == "negative"
    assert record.reasons == ["wrong_solution", "step_error"]


def test_invalid_rating_reason_and_oversized_comment_are_rejected():
    client, repo, _ = client_with_feedback()

    assert client.post("/api/v1/feedback", json=payload(rating="meh")).status_code == 422
    assert client.post("/api/v1/feedback", json=payload(rating="positive", reasons=["wrong_solution"])).status_code == 422
    assert client.post("/api/v1/feedback", json=payload(comment="x" * 1001)).status_code == 422
    assert repo.items == {}


def test_trusted_metadata_is_enriched_server_side_and_spoof_fields_are_rejected():
    client, repo, _ = client_with_feedback()
    body = payload(lesson_model="spoof-model")

    response = client.post("/api/v1/feedback", json=body)

    assert response.status_code == 422
    assert repo.items == {}
    assert client.post("/api/v1/feedback", json=payload()).status_code == 200
    record = next(iter(repo.items.values()))
    assert record.lesson_model == "mock"
    assert record.vision_model == "mock"
    assert record.topic == "Denklem"


def test_duplicate_submission_updates_current_feedback_without_uncontrolled_duplicates():
    client, repo, _ = client_with_feedback()

    first = client.post("/api/v1/feedback", json=payload(rating="positive", reasons=["clear"]))
    second = client.post("/api/v1/feedback", json=payload(rating="negative", reasons=["unclear_explanation"], comment="Anlatım çok karışık geldi."))

    assert first.json()["data"]["created"] is True
    assert second.json()["data"]["created"] is False
    assert len(repo.items) == 1
    record = next(iter(repo.items.values()))
    assert record.rating == "negative"
    assert record.reasons == ["unclear_explanation"]


def test_critical_reason_and_meaningful_negative_comment_trigger_notification():
    email = RecordingEmailProvider()
    client, repo, _ = client_with_feedback(email)

    critical = client.post("/api/v1/feedback", json=payload(rating="negative", reasons=["formula_rendering_error"]))
    commented = client.post("/api/v1/feedback", json=payload(rating="negative", reasons=["other"], comment="Son şık yanlış çıktı."))

    assert critical.json()["data"]["critical"] is True
    assert commented.json()["data"]["critical"] is True
    assert len(email.records) == 2
    assert len(repo.items) == 1


def test_positive_feedback_does_not_trigger_developer_email():
    email = RecordingEmailProvider()
    client, _, _ = client_with_feedback(email)

    response = client.post("/api/v1/feedback", json=payload(rating="positive", reasons=["useful"], comment="Çok iyi."))

    assert response.status_code == 200
    assert response.json()["data"]["notification_attempted"] is False
    assert email.records == []


def test_email_failure_does_not_rollback_persisted_feedback():
    email = RecordingEmailProvider(fail=True)
    client, repo, _ = client_with_feedback(email)

    response = client.post("/api/v1/feedback", json=payload(rating="negative", reasons=["wrong_solution"]))

    assert response.status_code == 200
    assert response.json()["data"]["notification_attempted"] is True
    assert len(repo.items) == 1
    assert len(email.records) == 1


def test_feedback_record_and_email_do_not_include_uploaded_image_bytes():
    client, repo, _ = client_with_feedback()

    client.post("/api/v1/feedback", json=payload(rating="negative", reasons=["misread_question"]))
    record = next(iter(repo.items.values()))
    body = _email_body(record)

    dumped = record.model_dump(mode="json")
    assert "image" not in dumped
    assert "bytes" not in dumped
    assert "question_text" not in dumped
    assert "image" not in body.lower()
    assert "api key" not in body.lower()


def test_critical_feedback_triggers_resend_notification_attempt(monkeypatch):
    sent = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(request, timeout):
        sent["url"] = request.full_url
        sent["timeout"] = timeout
        sent["authorization"] = request.headers["Authorization"]
        sent["content_type"] = request.headers["Content-type"]
        sent["payload"] = request.data.decode("utf-8")
        return FakeResponse()

    monkeypatch.setattr("apps.api.app.features.feedback.email.urlopen", fake_urlopen)
    provider = ResendFeedbackEmailProvider(
        api_key="resend-secret",
        recipient="farukerdemci07@gmail.com",
        sender="TeacherAI <feedback@example.com>",
    )
    client, repo, _ = client_with_feedback(provider)

    response = client.post("/api/v1/feedback", json=payload(rating="negative", reasons=["wrong_solution"], comment="Son cevap hatalı."))

    assert response.status_code == 200
    assert sent["url"] == RESEND_EMAILS_URL
    assert sent["authorization"] == "Bearer resend-secret"
    assert sent["content_type"] == "application/json"
    assert '"to": ["farukerdemci07@gmail.com"]' in sent["payload"]
    assert '"from": "TeacherAI <feedback@example.com>"' in sent["payload"]
    assert "TeacherAI \\u2014 Yeni kritik geri bildirim" in sent["payload"]
    assert "Son cevap hatal" in sent["payload"]
    assert len(repo.items) == 1


def test_resend_failure_does_not_log_credentials_or_rollback(caplog, monkeypatch):
    def failing_urlopen(request, timeout):
        raise OSError("resend unavailable")

    monkeypatch.setattr("apps.api.app.features.feedback.email.urlopen", failing_urlopen)
    provider = ResendFeedbackEmailProvider(
        api_key="super-secret-resend-key",
        recipient="farukerdemci07@gmail.com",
        sender="TeacherAI <feedback@example.com>",
    )
    client, repo, _ = client_with_feedback(provider)

    response = client.post("/api/v1/feedback", json=payload(rating="negative", reasons=["step_error"]))

    assert response.status_code == 200
    assert len(repo.items) == 1
    logs = caplog.text
    assert "super-secret-resend-key" not in logs
    assert "farukerdemci07@gmail.com" not in logs


def test_missing_resend_api_key_falls_back_to_noop_provider():
    container = build_container(
        Settings(
            environment="test",
            firebase_enabled=False,
            feedback_email_notifications=True,
            feedback_notification_email="farukerdemci07@gmail.com",
            feedback_email_sender="TeacherAI <feedback@example.com>",
            resend_api_key=None,
        )
    )

    assert isinstance(container.feedback_service.email_provider, NoopFeedbackEmailProvider)


def test_email_body_contains_only_allowed_feedback_metadata():
    result = generated_result()
    client, repo, _ = client_with_feedback()
    client.post("/api/v1/feedback", json=payload(rating="negative", reasons=["misread_question"], comment="Soruyu farklı okudu."))
    record = next(iter(repo.items.values()))

    body = _email_body(record)

    assert "misread_question" in body
    assert result.lesson.source_analysis.topic in body
    assert result.lesson.model in body
    assert result.lesson.source_analysis.request_id in body
    assert "Soruyu farklı okudu." in body
    assert result.lesson.source_analysis.question_text not in body
    assert "lesson_data" not in body
