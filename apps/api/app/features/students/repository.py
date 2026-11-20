from threading import Lock
from typing import Protocol
from apps.api.app.features.interactions.schemas import InteractionEvent
from apps.api.app.features.memory.schemas import StudentMemory
from .schemas import LessonRecord, StudentProfile


class StudentRepository(Protocol):
    def save_profile(self, profile: StudentProfile) -> None: ...
    def get_profile(self, uid: str) -> StudentProfile | None: ...
    def apply_event(self, uid, event, practice_id, engine, lesson=None) -> None: ...
    def save_analysis(self, uid, analysis) -> None: ...
    def analysis(self, uid, analysis_id): ...
    def get_lesson(self, lesson_id: str) -> LessonRecord | None: ...
    def lesson_count(self, uid: str) -> int: ...
    def lessons(self, uid: str, limit: int = 50) -> list[LessonRecord]: ...
    def save_event(self, uid: str, event: InteractionEvent) -> None: ...
    def save_attempt(
        self, uid: str, event: InteractionEvent, practice_id: str
    ) -> None: ...
    def get_memory(self, uid: str) -> StudentMemory: ...
    def save_memory(self, memory: StudentMemory) -> None: ...
    def reset_memory(self, uid: str) -> None: ...


class InMemoryStudentRepository:
    def __init__(self):
        self.lock = Lock()
        self.analyses = {}
        self.profiles = {}
        self.lesson_items = {}
        self.events = {}
        self.attempts = {}
        self.memories = {}

    def save_profile(self, p):
        self.profiles[p.student_id] = p

    def get_profile(self, uid):
        return self.profiles.get(uid)

    def save_lesson(self, x):
        self.lesson_items[x.lesson_id] = x

    def get_lesson(self, lesson_id):
        return self.lesson_items.get(lesson_id)

    def lesson_count(self, uid):
        return sum(lesson.student_id == uid for lesson in self.lesson_items.values())

    def lessons(self, uid, limit=50):
        return sorted(
            [x for x in self.lesson_items.values() if x.student_id == uid],
            key=lambda x: x.created_at,
            reverse=True,
        )[:limit]

    def save_event(self, uid, event):
        self.events[event.event_id] = (uid, event)

    def save_attempt(self, uid, event, practice_id):
        self.attempts[event.event_id] = {
            "uid": uid,
            "event": event,
            "practice_id": practice_id,
        }

    def get_memory(self, uid):
        return self.memories.get(uid) or StudentMemory(student_id=uid)

    def save_memory(self, memory):
        self.memories[memory.student_id] = memory

    def reset_memory(self, uid):
        self.memories.pop(uid, None)

    def apply_event(self, uid, event, practice_id, engine, lesson=None):
        with self.lock:
            if event.event_id in self.events:
                return
            if lesson:
                self.save_lesson(lesson)
            self.save_event(uid, event)
            if practice_id:
                self.save_attempt(uid, event, practice_id)
            memory = self.get_memory(uid)
            profile = self.get_profile(uid)
            if profile:
                memory.exam_goal = profile.exam_goal
            self.save_memory(engine.apply(memory, event))

    def save_analysis(self, uid, analysis):
        self.analyses[analysis.request_id] = (uid, analysis)

    def analysis(self, uid, analysis_id):
        item = self.analyses.get(analysis_id)
        return item[1] if item and item[0] == uid else None
