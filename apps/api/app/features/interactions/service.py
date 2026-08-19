from uuid import uuid4
from apps.api.app.features.board.schemas import BoardElement,BoardPlan
from apps.api.app.features.mathai.parser import MathParseError
from apps.api.app.features.mathai.service import MathAIService
from .exceptions import InvalidInteractionError,InvalidPracticeError,PracticeNotFoundError
from .provider import InteractionProvider
from .schemas import *
from .store import InMemoryPracticeStore,PracticeRecord
_EVENT={"understood":"understood_clicked","simplify":"simpler_explanation_requested","alternative":"alternative_method_requested","hint":"hint_requested","similar_example":"similar_example_requested","practice":"practice_started"}
class InteractionService:
    def __init__(self,provider:InteractionProvider,mathai:MathAIService,store:InMemoryPracticeStore):self.provider=provider;self.mathai=mathai;self.store=store
    async def interact(self,lesson_id:str,request:InteractionRequest,teaching_context=None)->InteractionResponse:
        lesson=request.lesson
        if lesson.lesson_plan_id!=lesson_id:raise InvalidInteractionError
        interaction_id=f"interaction_{uuid4().hex}"
        event=self._event(_EVENT[request.action],lesson,request.action,explanation_mode=request.action)
        if request.action=="understood":
            message=f"Güzel. Bu sorudaki ana fikir {lesson.content.strategy.lower()}. İstersen şimdi benzer bir soruyu sen deneyebilirsin."
            return InteractionResponse(interaction_id=interaction_id,action=request.action,message=message,event=event)
        draft=await self.provider.adapt(request.action,lesson,request.hint_level,teaching_context)
        if request.action == "hint" and lesson.content.final_answer.strip().lower() in draft.text.strip().lower():
            raise InvalidInteractionError
        if request.action=="practice":
            practice=self._create_practice(lesson,draft)
            return InteractionResponse(interaction_id=interaction_id,action=request.action,message=draft.text,practice=practice,event=event)
        verification=None
        if request.action in ("similar_example", "alternative") and draft.question_expression and draft.expected_answer_expression:
            try:verification="verified" if self.mathai.check_answer(draft.question_expression,draft.expected_answer_expression,draft.answer_variable)[0] else "failed"
            except MathParseError:verification="unsupported"
            if verification=="failed":raise InvalidPracticeError
        board=self._board(lesson_id,interaction_id,draft,request.action)
        return InteractionResponse(interaction_id=interaction_id,action=request.action,message=draft.text,board=board,event=event,next_hint_level=min(3,request.hint_level+1) if request.action=="hint" else None,verification_status=verification)
    def submit(self,lesson_id:str,practice_id:str,request:PracticeAnswerRequest)->PracticeFeedback:
        item=self.store.get(practice_id,lesson_id)
        if not item:raise PracticeNotFoundError
        attempt=self.store.increment(item)
        try:correct,mistake=self.mathai.check_answer(item.question,request.answer,item.variable)
        except MathParseError:correct,mistake=False,"unknown"
        if correct:message="Evet, doğru. Sonucun denklemi sağlıyor; kullandığın işlem dengeli ilerlemiş."
        elif attempt<3:message=f"Henüz değil. {item.hint} Cevabı vermeden bu adımı bir daha dene."
        else:message=f"Birlikte ilk adıma dönelim: {item.hint} İstersen artık çözümü göster seçeneğini kullanabilirsin."
        event_name="practice_correct" if correct else "practice_incorrect"
        event=InteractionEvent(event_id=f"event_{uuid4().hex}",event=event_name,lesson_id=lesson_id,topic=item.topic,subtopic=item.subtopic,skill=item.skill,difficulty=item.difficulty,action="practice_answered",mistake_type=mistake,correctness=correct,attempt_count=attempt,explanation_mode="practice")
        return PracticeFeedback(correct=correct,message=message,attempt_number=attempt,mistake_type=mistake,can_show_solution=attempt>=3 and not correct,event=event)
    def _create_practice(self,lesson,draft):
        if not draft.question_expression or not draft.expected_answer_expression:raise InvalidPracticeError
        try:
            correct,_=self.mathai.check_answer(draft.question_expression,draft.expected_answer_expression,draft.answer_variable)
        except MathParseError as exc:raise InvalidPracticeError from exc
        if not correct:raise InvalidPracticeError
        pid=f"practice_{uuid4().hex}";item=PracticeRecord(pid,lesson.lesson_plan_id,draft.question_expression,draft.expected_answer_expression,draft.answer_variable,draft.feedback_hint or "İlk olarak hangi terimi kaldırman gerektiğine bak.",lesson.source_analysis.topic,lesson.source_analysis.subtopic,lesson.concept_id,lesson.source_analysis.difficulty)
        self.store.save(item)
        return PracticePublic(practice_question_id=pid,question=draft.title,question_expression=draft.question_expression,topic=item.topic,subtopic=item.subtopic,skill_id=item.skill,difficulty=item.difficulty)
    def _board(self,lesson_id,interaction_id,draft,action):
        elements=[BoardElement(id=f"{interaction_id}_title",type="title",text=draft.title)]
        elements.append(BoardElement(id=f"{interaction_id}_note",type="teacher_note",text=draft.text))
        for i,step in enumerate(draft.steps):elements.append(BoardElement(id=f"{interaction_id}_step_{i+1}",type="teacher_note",text=step))
        for i,expr in enumerate(draft.expressions):elements.append(BoardElement(id=f"{interaction_id}_expr_{i+1}",type="equation",latex=expr.latex))
        return BoardPlan(board_id=f"board_{uuid4().hex}",lesson_plan_id=lesson_id,title=draft.title,elements=elements)
    def _event(self,name,lesson,action,**extra):
        return InteractionEvent(event_id=f"event_{uuid4().hex}",event=name,lesson_id=lesson.lesson_plan_id,topic=lesson.source_analysis.topic,subtopic=lesson.source_analysis.subtopic,skill=lesson.concept_id,difficulty=lesson.source_analysis.difficulty,action=action,**extra)
