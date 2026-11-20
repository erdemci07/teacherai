from apps.api.app.core.transactions import commit as commit_transaction
from apps.api.app.core.retention import ANALYSES, expired, retention
import json
from google.cloud.firestore_v1.base_query import FieldFilter
from apps.api.app.features.vision.schemas import VisionAnalysis
from firebase_admin import firestore
from apps.api.app.features.memory.schemas import StudentMemory
from .schemas import LessonRecord, StudentProfile


class FirestoreStudentRepository:
    def __init__(self, db=None):
        self.db = db if db is not None else firestore.client()

    def save_profile(self, p):
        self.db.collection("student_profiles").document(p.student_id).set(
            p.model_dump(mode="json"), merge=True
        )
        self.db.collection("users").document(p.student_id).set(
            {"student_id": p.student_id, "email": p.email}, merge=True
        )

    def get_profile(self, uid):
        snap = self.db.collection("student_profiles").document(uid).get()
        return StudentProfile.model_validate(snap.to_dict()) if snap.exists else None

    @staticmethod
    def _payload(x):
        data = x.model_dump(mode="json", exclude={"lesson_data"})
        # Firestore rejects nested arrays, e.g. graph.sample_points.
        data["lesson_json"] = json.dumps(
            x.lesson_data, ensure_ascii=False, separators=(",", ":")
        )
        return data

    @staticmethod
    def _record(data):
        if "lesson_json" in data:
            data["lesson_data"] = json.loads(data.pop("lesson_json"))
        return LessonRecord.model_validate(data)

    def get_lesson(self, lesson_id):
        data = self.db.collection("lessons").document(lesson_id).get().to_dict()
        return self._record(data) if data else None

    def lesson_count(self, uid):
        query = self.db.collection('lessons').where(filter=FieldFilter('student_id', '==', uid))
        return query.count().get()[0][0].value

    def lessons(self, uid, limit=50):
        return [
            self._record(x.to_dict())
            for x in self.db.collection("lessons")
            .where(filter=FieldFilter("student_id", "==", uid))
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        ]

    def save_event(self, uid, event):
        self.db.collection("interaction_events").document(event.event_id).set(
            {**event.model_dump(mode="json"), "student_id": uid}
        )

    def save_attempt(self, uid, event, practice_id):
        self.db.collection("practice_attempts").document(event.event_id).set(
            {
                **event.model_dump(mode="json"),
                "student_id": uid,
                "practice_question_id": practice_id,
            }
        )

    def get_memory(self, uid):
        snap = self.db.collection("student_memories").document(uid).get()
        return (
            StudentMemory.model_validate(snap.to_dict())
            if snap.exists
            else StudentMemory(student_id=uid)
        )

    def save_memory(self, memory):
        self.db.collection("student_memories").document(memory.student_id).set(
            memory.model_dump(mode="json")
        )

    def reset_memory(self, uid):
        self.db.collection("student_memories").document(uid).delete()

    def apply_event(self, uid, event, practice_id, engine, lesson=None):
        events = self.db.collection("interaction_events").document(event.event_id)
        memory_ref = self.db.collection("student_memories").document(uid)
        profile_ref = self.db.collection("student_profiles").document(uid)

        @firestore.transactional
        def update(tx):
            if events.get(transaction=tx).exists:
                return
            data = memory_ref.get(transaction=tx).to_dict() or {"student_id": uid}
            profile = profile_ref.get(transaction=tx).to_dict()
            memory = StudentMemory.model_validate(data)
            if profile:
                memory.exam_goal = profile.get("exam_goal")
            payload = {**event.model_dump(mode="json"), "student_id": uid}
            if lesson:
                tx.create(
                    self.db.collection("lessons").document(lesson.lesson_id),
                    self._payload(lesson),
                )
            tx.set(events, payload)
            if practice_id:
                ref = self.db.collection("practice_attempts").document(event.event_id)
                tx.set(ref, {**payload, "practice_question_id": practice_id})
            tx.set(memory_ref, engine.apply(memory, event).model_dump(mode="json"))

        commit_transaction(self.db, update)

    def save_analysis(self, uid, analysis):
        self.db.collection(ANALYSES).document(analysis.request_id).create(
            {
                "owner": uid,
                **retention(ANALYSES),
                "analysis": analysis.model_dump_json(
                    exclude={"debug", "normalized_preview_url"}
                ),
            }
        )

    def analysis(self, uid, analysis_id):
        data = (
            self.db.collection(ANALYSES).document(analysis_id).get().to_dict()
        )
        if data and data["owner"] == uid and not expired(data):
            return VisionAnalysis.model_validate_json(data["analysis"])
        return None
