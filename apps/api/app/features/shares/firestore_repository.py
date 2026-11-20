from google.cloud.firestore_v1.base_query import FieldFilter
from firebase_admin import firestore

from apps.api.app.core.transactions import commit as commit_transaction
from apps.api.app.features.account.guard import ensure_active

from .schemas import PublicSolutionSnapshot

# Sunucu tarafı alanlar; genel görünüme hiçbir zaman çıkmaz.
PRIVATE_FIELDS = ("owner_id",)


def public_snapshot(data: dict) -> PublicSolutionSnapshot:
    return PublicSolutionSnapshot.model_validate({k: v for k, v in data.items() if k not in PRIVATE_FIELDS})


class FirestoreShareRepository:
    def __init__(self, db=None):
        self.db = db if db is not None else firestore.client()

    def get(self, share_id: str) -> PublicSolutionSnapshot | None:
        snap = self.db.collection("shared_solutions").document(share_id).get()
        return public_snapshot(snap.to_dict()) if snap.exists else None

    def find_by_lesson_plan_id(self, lesson_plan_id: str) -> PublicSolutionSnapshot | None:
        query = (
            self.db.collection("shared_solutions")
            .where(filter=FieldFilter("source_lesson_plan_id", "==", lesson_plan_id))
            .limit(5)
            .stream()
        )
        for snap in query:
            item = public_snapshot(snap.to_dict())
            if item.status == "published":
                return item
        return None

    def save(self, snapshot: PublicSolutionSnapshot, owner_id: str | None = None) -> bool:
        ref = self.db.collection("shared_solutions").document(snapshot.share_id)

        @firestore.transactional
        def update(tx):
            ensure_active(self.db, tx, owner_id)
            created = not ref.get(transaction=tx).exists
            payload = {
                **snapshot.model_dump(mode="json"),
                "created_at": firestore.SERVER_TIMESTAMP if created else snapshot.created_at,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
            if owner_id:
                payload["owner_id"] = owner_id
            tx.set(ref, payload, merge=True)
            return created

        return commit_transaction(self.db, update)
