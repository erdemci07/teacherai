import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from .schemas import FeedbackRecord

logger = logging.getLogger(__name__)

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587


class FeedbackEmailProvider(Protocol):
    def send_critical_feedback(self, record: FeedbackRecord) -> None: ...


class NoopFeedbackEmailProvider:
    def send_critical_feedback(self, record: FeedbackRecord) -> None:
        return None


@dataclass(frozen=True)
class GmailSmtpFeedbackEmailProvider:
    username: str
    app_password: str
    recipient: str
    sender: str
    timeout_seconds: float = 8.0

    def send_critical_feedback(self, record: FeedbackRecord) -> None:
        message = EmailMessage()
        message["Subject"] = "TeacherAI - Yeni kritik geri bildirim"
        message["From"] = self.sender
        message["To"] = self.recipient
        message.set_content(_email_body(record))
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, timeout=self.timeout_seconds) as smtp:
                smtp.starttls(context=context)
                smtp.login(self.username, self.app_password)
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            logger.warning(
                "Feedback email notification failed exception_type=%s feedback_id=%s",
                type(exc).__name__,
                record.feedback_id,
            )
            raise


def _email_body(record: FeedbackRecord) -> str:
    lines = [
        "TeacherAI - Yeni kritik geri bildirim",
        "",
        f"Tur: {record.rating}",
        f"Nedenler: {', '.join(record.reasons) if record.reasons else '-'}",
    ]
    if record.topic:
        lines.append(f"Konu: {record.topic}")
    if record.subtopic:
        lines.append(f"Alt konu: {record.subtopic}")
    model = record.lesson_model or record.vision_model
    if model:
        lines.append(f"Model: {model}")
    if record.verification_status:
        lines.append(f"Dogrulama: {record.verification_status}")
    if record.comment:
        lines.extend(["", "Kullanici notu:", record.comment])
    lines.extend(["", f"Request ID: {record.request_id}", f"Solution ID: {record.solution_id}", f"Tarih: {record.updated_at.isoformat()}"])
    return "\n".join(lines)
