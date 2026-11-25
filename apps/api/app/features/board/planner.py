from uuid import uuid4
from ..education.lesson import LessonPlanV2, MathAnswer
from .schemas import BoardElement,BoardPlan
from ..lessons.schemas import LessonPlan
from ..mathai.schemas import VerificationResult
_KINDS = {"segment_length": "uzunluk", "angle_measure": "açı", "right_angle": "dik açı", "equal_segments": "eş kenar",
          "equal_angles": "eş açı", "parallel": "paralel", "perpendicular": "dik", "midpoint": "orta nokta",
          "triangle": "üçgen", "similar": "benzer", "congruent": "eş", "coordinate": "koordinat", "tangent": "teğet"}


def _number(value: str) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


class BoardPlanner:
    def create(self,lesson:LessonPlan,verification:VerificationResult, artifact:LessonPlanV2 | None = None)->BoardPlan:
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
        report = getattr(verification, "mathematics", None)
        if verification.graph:
            holes = [float(item) for item in (report.domain_exclusions if report else []) if _number(item)]
            add("graph", graph=verification.graph.model_copy(update={"discontinuities": holes}))
        # TA-008: sayı doğrusu yalnız kesin (exact) ve aralık biçimli çözüm kümesinden; sağlayıcı çizimi kullanılmaz.
        if report and report.solution_set and report.solution_set.kind == "intervals" and report.solution_set.exact:
            add("number_line", text=report.solution_set.variable or "x", intervals=report.solution_set.intervals,
                exclusions=report.solution_set.exclusions)
        model = getattr(c, "mathematical_model", None)
        if model is not None and model.geometry is not None and report is not None:
            labels = {"stated": "verilen", "marked": "şekilde işaretli", "derived": "türetilen", "construction": "yardımcı çizim",
                      "visual_uncertain": "yalnız görünüş — kullanılmadı"}
            facts = [f"{' '.join(f.points)}{(' ~ ' + ' '.join(f.other)) if f.other else ''}"
                     f"{(' = ' + f.value) if f.value else ''} ({_KINDS.get(f.kind, f.kind)}; {labels[f.origin]})"
                     for f in model.geometry.facts][:16]
            add("geometry_facts", text="Şekil ölçekli değildir; yalnız verilen ve işaretli olgular kullanılır.",
                facts=facts, schematic=model.geometry.schematic)
        answer = artifact.content.answer if artifact else None
        add("final_answer",text=answer.description if isinstance(answer, MathAnswer) else c.final_answer,latex=answer.expressions[0] if isinstance(answer, MathAnswer) else c.final_answer_expressions[0].latex,mark="check" if verification.final_answer_verified else "warning")
        return BoardPlan(board_id=f"board_{uuid4().hex}",lesson_plan_id=lesson.lesson_plan_id,title=lesson.source_analysis.topic,elements=elements)
