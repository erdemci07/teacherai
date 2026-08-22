from dataclasses import replace

from fastapi.testclient import TestClient

from apps.api.app.core.settings import Settings
from apps.api.app.core.container import build_container
from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.feedback.email import GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, GmailSmtpFeedbackEmailProvider, NoopFeedbackEmailProvider, _email_body
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


def test_critical_feedback_triggers_gmail_smtp_notification_attempt(monkeypatch):
    sent = {}

    class FakeSmtp:
        def __init__(self, host, port, timeout):
            sent["host"] = host
            sent["port"] = port
            sent["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self, context):
            sent["starttls"] = True

        def login(self, username, password):
            sent["username"] = username
            sent["password"] = password

        def send_message(self, message):
            sent["to"] = message["To"]
            sent["from"] = message["From"]
            sent["subject"] = message["Subject"]
            sent["body"] = message.get_content()

    monkeypatch.setattr("apps.api.app.features.feedback.email.smtplib.SMTP", FakeSmtp)
    provider = GmailSmtpFeedbackEmailProvider(
        username="farukerdemci07@gmail.com",
        app_password="app-secret",
        recipient="farukerdemci07@gmail.com",
        sender="farukerdemci07@gmail.com",
    )
    client, repo, _ = client_with_feedback(provider)

    response = client.post("/api/v1/feedback", json=payload(rating="negative", reasons=["wrong_solution"], comment="Son cevap hatalı."))

    assert response.status_code == 200
    assert sent["host"] == GMAIL_SMTP_HOST
    assert sent["port"] == GMAIL_SMTP_PORT
    assert sent["starttls"] is True
    assert sent["username"] == "farukerdemci07@gmail.com"
    assert sent["password"] == "app-secret"
    assert sent["to"] == "farukerdemci07@gmail.com"
    assert "TeacherAI - Yeni kritik geri bildirim" in sent["subject"]
    assert "Son cevap hatalı." in sent["body"]
    assert len(repo.items) == 1


def test_smtp_failure_does_not_log_credentials_or_rollback(caplog, monkeypatch):
    class FailingSmtp:
        def __init__(self, host, port, timeout):
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self, context):
            return None

        def login(self, username, password):
            raise OSError("smtp unavailable")

    monkeypatch.setattr("apps.api.app.features.feedback.email.smtplib.SMTP", FailingSmtp)
    provider = GmailSmtpFeedbackEmailProvider(
        username="farukerdemci07@gmail.com",
        app_password="super-secret-app-password",
        recipient="farukerdemci07@gmail.com",
        sender="farukerdemci07@gmail.com",
    )
    client, repo, _ = client_with_feedback(provider)

    response = client.post("/api/v1/feedback", json=payload(rating="negative", reasons=["step_error"]))

    assert response.status_code == 200
    assert len(repo.items) == 1
    logs = caplog.text
    assert "super-secret-app-password" not in logs
    assert "farukerdemci07@gmail.com" not in logs


def test_missing_smtp_config_falls_back_to_noop_provider():
    container = build_container(
        Settings(
            environment="test",
            firebase_enabled=False,
            feedback_email_notifications=True,
            feedback_notification_email="farukerdemci07@gmail.com",
            feedback_email_sender="farukerdemci07@gmail.com",
            gmail_smtp_username=None,
            gmail_smtp_app_password=None,
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
