from uuid import uuid4

from apps.api.app.features.interactions.schemas import InteractionEvent
from apps.api.app.features.memory.engine import MemoryEngine

from .repository import StudentRepository
from .schemas import DashboardSummary, LessonRecord, StudentProfile


class StudentService:
    def __init__(self, repository: StudentRepository, memory: MemoryEngine):
        self.repository = repository
        self.memory = memory

    def profile(self, user, body):
        value = StudentProfile(
            student_id=user.uid,
            display_name=body.display_name,
            exam_goal=body.exam_goal,
            email=user.email,
        )
        self.repository.save_profile(value)
        return value

    def save_lesson(self, user, result):
        lesson = result.lesson
        source = lesson.source_analysis
        record = LessonRecord(
            server_generated=True,
            lesson_id=lesson.lesson_plan_id,
            student_id=user.uid,
            subject=source.subject,
            exam_context=source.exam_context,
            topic=source.topic,
            subtopic=source.subtopic,
            difficulty=source.difficulty,
            question_summary=source.question_text[:500],
            final_answer=lesson.content.final_answer,
            verification_status=result.verification.status,
            lesson_data=result.model_dump(
                mode="json",
                by_alias=True,
                exclude={
                    "lesson": {"source_analysis": {"normalized_preview_url", "debug"}}
                },
            ),
        )
        completed = InteractionEvent(
            event_id=f"event_{uuid4().hex}",
            event="solution_completed",
            lesson_id=record.lesson_id,
            topic=record.topic,
            subtopic=record.subtopic,
            skill=lesson.concept_id,
            difficulty=record.difficulty,
            action="solution_completed",
        )
        self.repository.apply_event(
            user.uid, completed, None, self.memory, lesson=record
        )
        return record

    def save_analysis(self, user, analysis):
        clean = analysis.model_copy(
            update={"normalized_preview_url": None, "debug": None}
        )
        self.repository.save_analysis(user.uid, clean)

    def clarify(self, user, analysis_id, request):
        """Öğrenci seçimini yeni revizyon olarak işler. Sağlayıcı çağrısı yapmaz.

        Aynı isteğin ağ yeniden denemesi güncel revizyonu değiştirmeden döndürür; farklı bir seçimle
        gelen eski revizyon 409 alır.
        """
        from apps.api.app.features.integrity.engine import (
            ClarificationError,
            apply_clarification,
        )
        from apps.api.app.features.vision.exceptions import (
            AnalysisUnavailableError,
            ClarificationNotPendingError,
            InvalidClarificationError,
            StaleQuestionRevisionError,
        )

        if not analysis_id or len(analysis_id) > 128 or "/" in analysis_id:
            raise AnalysisUnavailableError

        def mutate(current):
            report = current.integrity
            if report is None:
                raise ClarificationNotPendingError
            last = report.clarifications[-1] if report.clarifications else None
            if (
                last is not None
                and current.revision == request.expected_revision + 1
                and last.from_revision == request.expected_revision
                and last.uncertainty_id == request.uncertainty_id
                and last.selection == request.selection
            ):
                return None
            if current.revision != request.expected_revision:
                raise StaleQuestionRevisionError
            try:
                return apply_clarification(current, request.uncertainty_id, request.selection)
            except ClarificationError as exc:
                if str(exc) == "not_pending":
                    raise ClarificationNotPendingError from exc
                raise InvalidClarificationError from exc

        updated = self.repository.update_analysis(user.uid, analysis_id, mutate)
        if updated is None:
            raise AnalysisUnavailableError
        return updated

    def source_analysis(self, user, analysis_id):
        from fastapi import HTTPException

        if not analysis_id or len(analysis_id) > 128 or "/" in analysis_id:
            raise HTTPException(404, "Analysis unavailable.")
        analysis = self.repository.analysis(user.uid, analysis_id)
        if not analysis:
            raise HTTPException(404, "Analysis unavailable.")
        return analysis

    def owned(self, user, lesson_id):
        from fastapi import HTTPException

        if "/" in lesson_id or len(lesson_id) > 128:
            raise HTTPException(404, "Lesson unavailable.")
        record = self.repository.get_lesson(lesson_id)
        if not record or not record.server_generated or record.student_id != user.uid:
            raise HTTPException(404, "Lesson unavailable.")
        return record

    def record_event(self, user, event, practice_id=None):
        self.repository.apply_event(user.uid, event, practice_id, self.memory)

    def context(self, user, topic):
        return self.memory.context(self.repository.get_memory(user.uid), topic)

    def history(self, user):
        return [
            record
            if record.server_generated
            else record.model_copy(update={"verification_status": "legacy_unverified"})
            for record in self.repository.lessons(user.uid)
        ]

    def memory_summary(self, user):
        return self.repository.get_memory(user.uid)

    def reset(self, user):
        self.repository.reset_memory(user.uid)

    def dashboard(self, user):
        m = self.repository.get_memory(user.uid)
        return DashboardSummary(
            questions_solved=self.repository.lesson_count(user.uid),
            recent_topics=m.recent_topics,
            practice_attempts=m.practice.attempts,
            practice_correct=m.practice.correct,
            frequent_mistakes=m.mistake_counts,
            last_activity=m.last_activity,
        )
