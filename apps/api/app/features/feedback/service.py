import hashlib
import logging
from datetime import datetime, timezone

from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.core.settings import Settings

from .email import FeedbackEmailProvider
from .repository import FeedbackRepository
from .schemas import CRITICAL_REASONS, FeedbackRecord, SubmitFeedbackRequest, SubmitFeedbackResponse

logger = logging.getLogger(__name__)


class FeedbackService:
    def __init__(self, repository: FeedbackRepository, email_provider: FeedbackEmailProvider, settings: Settings):
        self.repository = repository
        self.email_provider = email_provider
        self.settings = settings

    def submit(self, body: SubmitFeedbackRequest, user: AuthenticatedUser | None = None) -> SubmitFeedbackResponse:
        result = body.result
        lesson = result.lesson
        source = lesson.source_analysis
        request_id = source.request_id
        solution_id = lesson.lesson_plan_id
        feedback_id = self._feedback_id(user.uid if user else None, request_id, solution_id)
        existing = self.repository.get(feedback_id)
        now = datetime.now(timezone.utc)
        critical = self._is_critical(body)
        record = FeedbackRecord(
            feedback_id=feedback_id,
            created_at=existing.created_at if existing else now,
            updated_at=now,
            rating=body.rating,
            reasons=body.reasons,
            comment=body.comment,
            critical=critical,
            attention_worthy=critical,
            request_id=request_id,
            solution_id=solution_id,
            user_id=user.uid if user else None,
            topic=source.topic or None,
            subtopic=source.subtopic,
            vision_model=source.model,
            lesson_model=lesson.model,
            verification_model=result.verification.engine,
            verification_status=result.verification.status,
            question_type=source.question_type or None,
            difficulty=source.difficulty,
            app_version=self.settings.version,
        )
        created = self.repository.save(record)
        notification_attempted = False
        if self._should_notify(record):
            notification_attempted = True
            try:
                self.email_provider.send_critical_feedback(record)
            except Exception:
                logger.warning("Feedback persisted but notification failed feedback_id=%s", record.feedback_id)
        return SubmitFeedbackResponse(feedback_id=record.feedback_id, created=created, critical=critical, notification_attempted=notification_attempted)

    @staticmethod
    def _feedback_id(user_id: str | None, request_id: str, solution_id: str) -> str:
        owner = user_id or "anonymous"
        digest = hashlib.sha256(f"{owner}:{request_id}:{solution_id}".encode("utf-8")).hexdigest()[:32]
        return f"feedback_{digest}"

    @staticmethod
    def _is_critical(body: SubmitFeedbackRequest) -> bool:
        if body.rating != "negative":
            return False
        if any(reason in CRITICAL_REASONS for reason in body.reasons):
            return True
        return bool(body.comment and len(body.comment.strip()) >= 8)

    @classmethod
    def _should_notify(cls, record: FeedbackRecord) -> bool:
        return record.rating == "negative" and record.attention_worthy
