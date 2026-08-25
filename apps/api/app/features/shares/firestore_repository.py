from firebase_admin import firestore

from .schemas import PublicSolutionSnapshot


class FirestoreShareRepository:
    def __init__(self):
        self.db = firestore.client()

    def get(self, share_id: str) -> PublicSolutionSnapshot | None:
        snap = self.db.collection("shared_solutions").document(share_id).get()
        return PublicSolutionSnapshot.model_validate(snap.to_dict()) if snap.exists else None

    def find_by_lesson_plan_id(self, lesson_plan_id: str) -> PublicSolutionSnapshot | None:
        query = (
            self.db.collection("shared_solutions")
            .where("source_lesson_plan_id", "==", lesson_plan_id)
            .limit(5)
            .stream()
        )
        for snap in query:
            item = PublicSolutionSnapshot.model_validate(snap.to_dict())
            if item.status == "published":
                return item
        return None

    def save(self, snapshot: PublicSolutionSnapshot) -> bool:
        ref = self.db.collection("shared_solutions").document(snapshot.share_id)
        created = not ref.get().exists
        ref.set(
            {
                **snapshot.model_dump(mode="json"),
                "created_at": firestore.SERVER_TIMESTAMP if created else snapshot.created_at,
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        return created
