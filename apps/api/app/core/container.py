from dataclasses import dataclass
from threading import BoundedSemaphore

from apps.api.app.core.settings import Settings, get_settings
from apps.api.app.core.usage import UsageTracker
from apps.api.app.features.account.service import (
    AccountDeletionService,
    FirebaseIdentity,
)
from apps.api.app.features.auth.verifier import FirebaseTokenVerifier
from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.feedback.email import (
    NoopFeedbackEmailProvider,
    ResendFeedbackEmailProvider,
)
from apps.api.app.features.feedback.repository import InMemoryFeedbackRepository
from apps.api.app.features.feedback.service import FeedbackService
from apps.api.app.features.interactions.openai_provider import OpenAIInteractionProvider
from apps.api.app.features.interactions.service import InteractionService
from apps.api.app.features.interactions.store import InMemoryPracticeStore
from apps.api.app.features.lessons.openai_provider import OpenAILessonProvider
from apps.api.app.features.lessons.service import LessonService
from apps.api.app.features.mathai.isolated import IsolatedMathAI
from apps.api.app.features.memory.engine import MemoryEngine
from apps.api.app.features.shares.repository import InMemoryShareRepository
from apps.api.app.features.shares.service import ShareService
from apps.api.app.features.students.repository import InMemoryStudentRepository
from apps.api.app.features.students.service import StudentService
from apps.api.app.features.vision.openai_provider import OpenAIVisionProvider
from apps.api.app.features.vision.service import VisionService
from apps.api.app.features.vision.storage import LocalTemporaryImageStorage
from apps.api.app.services.health_service import HealthService
from apps.api.app.services.version_service import VersionService


@dataclass(frozen=True)
class Container:
    settings: Settings
    health_service: HealthService
    version_service: VersionService
    vision_service: VisionService
    lesson_service: LessonService
    interaction_service: InteractionService
    token_verifier: FirebaseTokenVerifier
    student_service: StudentService
    feedback_service: FeedbackService
    share_service: ShareService
    slots: BoundedSemaphore
    usage_tracker: UsageTracker
    account_deletion: AccountDeletionService


def build_container(settings: Settings | None = None) -> Container:
    resolved_settings = settings or get_settings()
    import os
    if resolved_settings.environment == "test" and os.getenv("K_SERVICE"):
        raise RuntimeError("Test storage is unavailable on Cloud Run.")
    student_repository = InMemoryStudentRepository()
    feedback_repository = InMemoryFeedbackRepository()
    share_repository = InMemoryShareRepository()
    db = None
    identity_app = None
    practice_store = InMemoryPracticeStore()
    if resolved_settings.environment != "test" or resolved_settings.firebase_enabled:
        from apps.api.app.features.auth.firebase import (
            FirestoreConnection,
            initialize_firebase,
        )
        from apps.api.app.features.feedback.firestore_repository import (
            FirestoreFeedbackRepository,
        )
        from apps.api.app.features.shares.firestore_repository import (
            FirestoreShareRepository,
        )
        from apps.api.app.features.students.firestore_repository import (
            FirestoreStudentRepository,
        )
        initialize_firebase(resolved_settings.firebase_project_id, resolved_settings.firebase_service_account_json)
        if resolved_settings.firebase_auth_project_id and resolved_settings.firebase_auth_project_id != resolved_settings.firebase_project_id:
            identity_app = initialize_firebase(resolved_settings.firebase_auth_project_id, resolved_settings.firebase_service_account_json, name="identity")
        db = FirestoreConnection()
        student_repository = FirestoreStudentRepository(db)
        from apps.api.app.features.interactions.store import FirestorePracticeStore
        practice_store = FirestorePracticeStore(db)
        feedback_repository = FirestoreFeedbackRepository(db)
        share_repository = FirestoreShareRepository(db)
    feedback_email_provider = NoopFeedbackEmailProvider()
    if (
        resolved_settings.feedback_email_notifications
        and resolved_settings.feedback_notification_email
        and resolved_settings.feedback_email_sender
        and resolved_settings.resend_api_key
    ):
        feedback_email_provider = ResendFeedbackEmailProvider(
            api_key=resolved_settings.resend_api_key,
            recipient=resolved_settings.feedback_notification_email,
            sender=resolved_settings.feedback_email_sender,
        )
    vision_provider = OpenAIVisionProvider(
        api_key=resolved_settings.openai_api_key,
        model=resolved_settings.openai_vision_model,
        timeout_seconds=resolved_settings.vision_provider_timeout_seconds,
    )
    return Container(
        settings=resolved_settings,
        token_verifier=FirebaseTokenVerifier(identity_app),
        student_service=StudentService(student_repository, MemoryEngine()),
        feedback_service=FeedbackService(feedback_repository, feedback_email_provider, resolved_settings),
        share_service=ShareService(share_repository, resolved_settings),
        slots=BoundedSemaphore(resolved_settings.ai_concurrency),
        usage_tracker=UsageTracker(resolved_settings, db),
        account_deletion=AccountDeletionService(resolved_settings, db, FirebaseIdentity(identity_app)),
        health_service=HealthService(settings=resolved_settings),
        version_service=VersionService(settings=resolved_settings),
        interaction_service=InteractionService(OpenAIInteractionProvider(resolved_settings.openai_api_key, resolved_settings.openai_interaction_model, resolved_settings.interaction_provider_timeout_seconds), IsolatedMathAI(), practice_store),
        lesson_service=LessonService(OpenAILessonProvider(resolved_settings.openai_api_key, resolved_settings.openai_lesson_model, resolved_settings.lesson_provider_timeout_seconds, resolved_settings.lesson_context_max_bytes), IsolatedMathAI(), BoardPlanner()),
        vision_service=VisionService(
            provider=vision_provider,
            storage=LocalTemporaryImageStorage(resolved_settings.upload_temp_directory),
            max_upload_size_bytes=resolved_settings.max_upload_size_bytes,
            debug=resolved_settings.debug,
            recheck_limit=resolved_settings.vision_max_rechecks,
        ),
    )
