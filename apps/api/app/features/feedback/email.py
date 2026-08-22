import json
import logging
from dataclasses import dataclass
from typing import Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen

from .schemas import FeedbackRecord

logger = logging.getLogger(__name__)

RESEND_EMAILS_URL = "https://api.resend.com/emails"


class FeedbackEmailProvider(Protocol):
    def send_critical_feedback(self, record: FeedbackRecord) -> None: ...


class NoopFeedbackEmailProvider:
    def send_critical_feedback(self, record: FeedbackRecord) -> None:
        return None


@dataclass(frozen=True)
class ResendFeedbackEmailProvider:
    api_key: str
    recipient: str
    sender: str
    timeout_seconds: float = 8.0

    def send_critical_feedback(self, record: FeedbackRecord) -> None:
        payload = json.dumps(
            {
                "from": self.sender,
                "to": [self.recipient],
                "subject": "TeacherAI — Yeni kritik geri bildirim",
                "text": _email_body(record),
            }
        ).encode("utf-8")
        request = Request(
            RESEND_EMAILS_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                if response.status >= 400:
                    raise RuntimeError(f"Resend returned HTTP {response.status}")
        except (OSError, URLError, RuntimeError) as exc:
            logger.warning(
                "Feedback email notification failed exception_type=%s feedback_id=%s",
                type(exc).__name__,
                record.feedback_id,
            )
            raise


def _email_body(record: FeedbackRecord) -> str:
    lines = [
        "TeacherAI — Yeni kritik geri bildirim",
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
        lines.append(f"Doğrulama: {record.verification_status}")
    if record.comment:
        lines.extend(["", "Kullanıcı notu:", record.comment])
    lines.extend(["", f"Request ID: {record.request_id}", f"Solution ID: {record.solution_id}", f"Tarih: {record.updated_at.isoformat()}"])
    return "\n".join(lines)
