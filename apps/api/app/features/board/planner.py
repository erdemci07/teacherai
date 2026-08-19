from uuid import uuid4
from .schemas import BoardElement,BoardPlan
from ..lessons.schemas import LessonPlan
from ..mathai.schemas import VerificationResult
class BoardPlanner:
    def create(self,lesson:LessonPlan,verification:VerificationResult)->BoardPlan:
        c=lesson.content; elements=[]
        def add(kind,**values): elements.append(BoardElement(id=f"board_{len(elements)+1}",type=kind,**values))
        add("title",text=lesson.source_analysis.topic)
        add("teacher_note",text=f"Ne arıyoruz? {c.unknown}" if c.unknown else c.question_understanding)
        if c.known_values: add("known_values",text="\n".join(c.known_values))
        if c.key_rule: add("rule",text=c.key_rule)
        for example in c.mini_example: add("mini_example",latex=example.latex)
        for step in c.steps:
            add("teacher_note",text=step.explanation,source_step_id=step.id)
            for expr in step.expressions: add("equation",latex=expr.latex,source_step_id=step.id)
            add("arrow",text="Sonraki adım",source_step_id=step.id)
        if c.common_mistake: add("warning",text=c.common_mistake,mark="cross")
        if c.shortcut: add("tip",text=f"Pratik yol: {c.shortcut}")
        if verification.graph: add("graph",graph=verification.graph)
        add("final_answer",text=c.final_answer,latex=c.final_answer_expressions[0].latex,mark="check" if verification.final_answer_verified else "warning")
        return BoardPlan(board_id=f"board_{uuid4().hex}",lesson_plan_id=lesson.lesson_plan_id,title=lesson.source_analysis.topic,elements=elements)
