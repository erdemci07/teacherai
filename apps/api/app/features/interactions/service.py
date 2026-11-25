from starlette.concurrency import run_in_threadpool
from hashlib import sha256
from .store import PracticeRecord
from uuid import uuid4
from apps.api.app.features.board.schemas import BoardElement, BoardPlan
from apps.api.app.features.mathai.parser import MathParseError
from apps.api.app.features.mathai.priority import after_paid_call
from apps.api.app.features.mathai.service import MathAIService
from .exceptions import (
    InvalidInteractionError,
    InvalidPracticeError,
    PracticeNotFoundError,
)
from .provider import InteractionProvider
from .schemas import (
    InteractionRequest,
    InteractionResponse,
    InteractionEvent,
    PracticeAnswerRequest,
    PracticeFeedback,
    PracticePublic,
)
from .store import InMemoryPracticeStore

_EVENT = {
    "understood": "understood_clicked",
    "simplify": "simpler_explanation_requested",
    "alternative": "alternative_method_requested",
    "hint": "hint_requested",
    "similar_example": "similar_example_requested",
}


class InteractionService:
    def __init__(
        self,
        provider: InteractionProvider,
        mathai: MathAIService,
        store: InMemoryPracticeStore,
    ):
        self.provider = provider
        self.mathai = mathai
        self.store = store

    async def interact(
        self, lesson_id: str, request: InteractionRequest, teaching_context=None, uid: str | None = None
    ) -> InteractionResponse:
        lesson = request.lesson
        if lesson.lesson_plan_id != lesson_id:
            raise InvalidInteractionError
        interaction_id = f"interaction_{uuid4().hex}"
        event = self._event(
            _EVENT[request.action],
            lesson,
            request.action,
            explanation_mode=request.action,
        )
        if request.action == "understood":
            message = f"Güzel. Bu sorudaki ana fikir {lesson.content.strategy.lower()}. İstersen şimdi benzer bir soruyu sen deneyebilirsin."
            return InteractionResponse(
                interaction_id=interaction_id,
                action=request.action,
                message=message,
                event=event,
            )
        draft = await self.provider.adapt(
            request.action, lesson, request.hint_level, teaching_context
        )
        if (
            request.action == "hint"
            and lesson.content.final_answer.strip().lower()
            in draft.text.strip().lower()
        ):
            raise InvalidInteractionError
        verification = None
        if (
            request.action in ("similar_example", "alternative")
            and draft.question_expression
            and draft.expected_answer_expression
        ):
            try:
                verification = (
                    "verified"
                    if (
                        await run_in_threadpool(
                            after_paid_call(self.mathai.check_answer),
                            draft.question_expression,
                            draft.expected_answer_expression,
                            draft.answer_variable,
                        )
                    )[0]
                    else "failed"
                )
            except MathParseError:
                verification = "unsupported"
            if verification == "failed":
                raise InvalidPracticeError
        if (
            request.action == "similar_example"
            and draft.question_expression
            and verification != "verified"
        ):
            raise InvalidPracticeError
        practice = None
        if request.action == "similar_example" and verification == "verified":
            question = draft.question_expression
            pid = f"practice_{uuid4().hex}"
            source = lesson.source_analysis
            await run_in_threadpool(
                self.store.save,
                PracticeRecord(
                    pid,
                    lesson_id,
                    question,
                    draft.expected_answer_expression,
                    draft.answer_variable,
                    draft.feedback_hint or "Denklemin iki tarafını kontrol et.",
                    source.topic,
                    source.subtopic,
                    lesson.concept_id,
                    source.difficulty,
                    student_id=uid,
                ),
            )
            practice = PracticePublic(
                practice_question_id=pid,
                question=question,
                question_expression=question,
                topic=source.topic,
                subtopic=source.subtopic,
                skill_id=lesson.concept_id,
                difficulty=source.difficulty,
            )
        board = (
            None
            if practice
            else self._board(lesson_id, interaction_id, draft, request.action)
        )
        return InteractionResponse(
            interaction_id=interaction_id,
            action=request.action,
            message="Denklemi çöz. Bulduğun değeri aşağıya yaz."
            if practice
            else draft.text,
            practice=practice,
            board=board,
            event=event,
            next_hint_level=min(3, request.hint_level + 1)
            if request.action == "hint"
            else None,
            verification_status=verification,
        )

    def submit(
        self, lesson_id: str, practice_id: str, request: PracticeAnswerRequest, uid: str | None = None
    ) -> PracticeFeedback:
        item = self.store.get(practice_id, lesson_id)
        if not item:
            raise PracticeNotFoundError
        try:
            correct, mistake = self.mathai.check_answer(
                item.question, request.answer, item.variable
            )
        except MathParseError:
            from fastapi import HTTPException

            raise HTTPException(422, "Yanıt sayısal bir çözüm içermeli.") from None

        def feedback(attempt):
            if correct:
                message = "Evet, doğru. Sonucun denklemi sağlıyor; kullandığın işlem dengeli ilerlemiş."
            elif attempt < 3:
                message = (
                    f"Henüz değil. {item.hint} Cevabı vermeden bu adımı bir daha dene."
                )
            else:
                message = f"Çözüm {item.expected_answer}. Bu değeri denklemde yerine koyup iki tarafı karşılaştır."
            event_name = "practice_correct" if correct else "practice_incorrect"
            event = InteractionEvent(
                event_id=f"event_{uuid4().hex}",
                event=event_name,
                lesson_id=lesson_id,
                topic=item.topic,
                subtopic=item.subtopic,
                skill=item.skill,
                difficulty=item.difficulty,
                action="practice_answered",
                mistake_type=mistake,
                correctness=correct,
                attempt_count=attempt,
                explanation_mode="practice",
            )
            return PracticeFeedback(
                correct=correct,
                message=message,
                attempt_number=attempt,
                mistake_type=mistake,
                can_show_solution=False,
                event=event,
            )

        key = sha256(request.answer.strip().encode()).hexdigest()
        return self.store.answer(item, key, feedback, uid)

    def _board(self, lesson_id, interaction_id, draft, action):
        elements = [
            BoardElement(id=f"{interaction_id}_title", type="title", text=draft.title)
        ]
        elements.append(
            BoardElement(
                id=f"{interaction_id}_note", type="teacher_note", text=draft.text
            )
        )
        for i, step in enumerate(draft.steps):
            elements.append(
                BoardElement(
                    id=f"{interaction_id}_step_{i + 1}", type="teacher_note", text=step
                )
            )
        for i, expr in enumerate(draft.expressions):
            elements.append(
                BoardElement(
                    id=f"{interaction_id}_expr_{i + 1}",
                    type="equation",
                    latex=expr.latex,
                )
            )
        return BoardPlan(
            board_id=f"board_{uuid4().hex}",
            lesson_plan_id=lesson_id,
            title=draft.title,
            elements=elements,
        )

    def _event(self, name, lesson, action, **extra):
        return InteractionEvent(
            event_id=f"event_{uuid4().hex}",
            event=name,
            lesson_id=lesson.lesson_plan_id,
            topic=lesson.source_analysis.topic,
            subtopic=lesson.source_analysis.subtopic,
            skill=lesson.concept_id,
            difficulty=lesson.source_analysis.difficulty,
            action=action,
            **extra,
        )
