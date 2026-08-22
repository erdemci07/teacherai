from firebase_admin import firestore

from .schemas import FeedbackRecord


class FirestoreFeedbackRepository:
    def __init__(self):
        self.db = firestore.client()

    def get(self, feedback_id: str) -> FeedbackRecord | None:
        snap = self.db.collection("feedback").document(feedback_id).get()
        return FeedbackRecord.model_validate(snap.to_dict()) if snap.exists else None

    def save(self, record: FeedbackRecord) -> bool:
        ref = self.db.collection("feedback").document(record.feedback_id)
        created = not ref.get().exists
        ref.set(
            {
                **record.model_dump(mode="json"),
                "created_at": firestore.SERVER_TIMESTAMP if created else record.created_at,
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        return created
