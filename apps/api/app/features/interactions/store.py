from apps.api.app.core.transactions import commit as commit_transaction
from apps.api.app.core.retention import PRACTICE, expired, retention, timestamp
from dataclasses import asdict
from firebase_admin import firestore
from fastapi import HTTPException
from .schemas import PracticeFeedback
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from threading import Lock


@dataclass
class PracticeRecord:
    practice_id: str
    lesson_id: str
    question: str
    expected_answer: str
    variable: str | None
    hint: str
    topic: str
    subtopic: str | None
    skill: str
    difficulty: str
    attempts: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    answers: dict = field(default_factory=dict)
    closed: bool = False


class InMemoryPracticeStore:
    def __init__(self, ttl_minutes: int = 60):
        self._items = {}
        self._lock = Lock()
        self._ttl = timedelta(minutes=ttl_minutes)

    def save(self, item: PracticeRecord):
        with self._lock:
            self._items[item.practice_id] = item

    def get(self, practice_id: str, lesson_id: str) -> PracticeRecord | None:
        with self._lock:
            item = self._items.get(practice_id)
            if not item or item.lesson_id != lesson_id:
                return None
            if datetime.now(timezone.utc) - item.created_at > self._ttl:
                self._items.pop(practice_id, None)
                return None
            return item

    def answer(self, item, key, make_feedback):
        with self._lock:
            saved = item.answers
            if key in saved:
                return PracticeFeedback.model_validate(saved[key])
            if item.closed or item.attempts >= 3:
                raise HTTPException(409, "Practice complete.")
            result = make_feedback(item.attempts + 1)
            saved[key] = result.model_dump(mode="json")
            item.attempts += 1
            item.closed = result.correct
            return result


class FirestorePracticeStore:
    def __init__(self, db):
        self.db = db

    def save(self, item):
        self.db.collection(PRACTICE).document(item.practice_id).create(
            {**asdict(item), **retention(PRACTICE, item.created_at)}
        )

    def get(self, practice_id, lesson_id):
        if len(practice_id) > 128 or "/" in practice_id:
            return None
        data = (
            self.db.collection(PRACTICE)
            .document(practice_id)
            .get()
            .to_dict()
        )
        if not data or data["lesson_id"] != lesson_id:
            return None
        data["created_at"] = timestamp(data["created_at"])
        if expired(data) or datetime.now(timezone.utc) - data["created_at"] > timedelta(minutes=60):
            return None
        data.pop("expires_at", None)
        return PracticeRecord(**data)

    def answer(self, item, key, make_feedback):
        ref = self.db.collection(PRACTICE).document(item.practice_id)

        @firestore.transactional
        def commit(tx):
            data = ref.get(transaction=tx).to_dict()
            if not data or expired(data) or datetime.now(timezone.utc) - timestamp(data["created_at"]) >= timedelta(hours=1):
                raise HTTPException(404, "Pratik sorusunun süresi doldu.")
            if key in data["answers"]:
                return PracticeFeedback.model_validate(data["answers"][key])
            if data["closed"] or data["attempts"] >= 3:
                raise HTTPException(409, "Practice complete.")
            result = make_feedback(data["attempts"] + 1)
            tx.update(
                ref,
                {
                    "attempts": result.attempt_number,
                    "closed": result.correct,
                    f"answers.{key}": result.model_dump(mode="json"),
                },
            )
            return result

        return commit_transaction(self.db, commit)
