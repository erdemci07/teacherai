from firebase_admin import firestore

from apps.api.app.core.transactions import commit as commit_transaction
from apps.api.app.features.account.guard import ensure_active

from .schemas import FeedbackRecord


class FirestoreFeedbackRepository:
    def __init__(self, db=None):
        self.db = db if db is not None else firestore.client()

    def get(self, feedback_id: str) -> FeedbackRecord | None:
        snap = self.db.collection("feedback").document(feedback_id).get()
        return FeedbackRecord.model_validate(snap.to_dict()) if snap.exists else None

    def save(self, record: FeedbackRecord) -> bool:
        ref = self.db.collection("feedback").document(record.feedback_id)

        @firestore.transactional
        def update(tx):
            ensure_active(self.db, tx, record.user_id)
            created = not ref.get(transaction=tx).exists
            tx.set(
                ref,
                {
                    **record.model_dump(mode="json"),
                    "created_at": firestore.SERVER_TIMESTAMP if created else record.created_at,
                    "updated_at": firestore.SERVER_TIMESTAMP,
                },
                merge=True,
            )
            return created

        return commit_transaction(self.db, update)
