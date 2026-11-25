from uuid import uuid4
from ..education.lesson import LessonPlanV2, MathAnswer
from .schemas import BoardElement,BoardPlan
from ..lessons.schemas import LessonPlan
from ..mathai.schemas import GraphData, VerificationResult
_KINDS = {"segment_length": "uzunluk", "angle_measure": "açı", "right_angle": "dik açı", "equal_segments": "eş kenar",
          "equal_angles": "eş açı", "parallel": "paralel", "perpendicular": "dik", "midpoint": "orta nokta",
          "triangle": "üçgen", "similar": "benzer", "congruent": "eş", "coordinate": "koordinat", "tangent": "teğet"}


_ACCEPTED = {"source_text": "metinde verilen", "diagram_observation": "şekilde işaretli (görselden AI ile okundu)",
             "student_confirmed": "öğrencinin onayladığı", "validated_derivation": "doğrulanmış türetme",
             "construction_defined": "yardımcı çizimin tanımından"}
_REJECTED = {"visual_fact_not_given": "yalnız görünüş", "provider_proposed": "kaynakta bulunamadı",
             "unsupported_derivation": "türetme kanıtsız", "circular_derivation": "döngüsel türetme",
             "missing_premise": "öncül eksik", "rule_not_applicable": "kural uygulanamaz",
             "construction_overreach": "çizim bunu kurmaz", "tangent_preconditions_unmet": "teğet ön koşulu yok",
             "degenerate_object": "yozlaşmış nesne", "quote_does_not_assert_fact": "alıntı bunu ileri sürmüyor",
             "quote_mentions_without_asserting": "yalnız soruda anılıyor", "negated_in_source": "kaynak olumsuzluyor",
             "diagram_marking_unlinked": "işaret gözleme bağlanamadı (yorum)"}


def _fact_label(verdict) -> str:
    if verdict is None:
        return "doğrulanmadı — kullanılmadı"
    if verdict.status == "accepted":
        return _ACCEPTED.get(verdict.basis, "doğrulandı")
    return f"kullanılmadı: {_REJECTED.get(verdict.basis, verdict.basis)}"


def _number(value: str) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _graph(verification: VerificationResult, report) -> GraphData | None:
    """TA-008B §18: grafik yalnız doğrulanmış fonksiyon analizinden. Uzmanlık raporu parçaları varsa onlar esastır:
    örnek noktalar parçaların içinden, tanımsız noktalar dışlanarak alınmıştır; delik ve asimptot ayrı taşınır."""
    base = verification.graph
    if report is None or not report.graph_segments:
        if base is None:
            return None
        # Yedek (TA-008 davranışı): parça analizi yoksa bilinen tanımsız noktalarda yine bölünür.
        holes = [float(item) for item in (report.domain_exclusions if report else []) if _number(item)]
        return base.model_copy(update={"discontinuities": holes})
    holes = [x for x, _ in report.graph_holes]
    update = {"segments": report.graph_segments, "holes": report.graph_holes, "asymptotes": report.graph_asymptotes,
              "discontinuities": sorted({*holes, *report.graph_asymptotes}), "sample_points": report.graph_points}
    if base is not None:
        return base.model_copy(update=update)
    return GraphData(expression=report.graph_expression or "", **update)


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
        graph = _graph(verification, report)
        if graph is not None:
            add("graph", graph=graph)
        # TA-008: sayı doğrusu yalnız kesin (exact) ve aralık biçimli çözüm kümesinden; sağlayıcı çizimi kullanılmaz.
        if report and report.solution_set and report.solution_set.kind == "intervals" and report.solution_set.exact:
            add("number_line", text=report.solution_set.variable or "x", intervals=report.solution_set.intervals,
                exclusions=report.solution_set.exclusions)
        model = getattr(c, "mathematical_model", None)
        if model is not None and model.geometry is not None and report is not None:
            # TA-008B §19: etiket sağlayıcının iddia ettiği kökenden değil, sunucunun olgu kararından gelir.
            verdicts = {item.id: item for item in report.geometry_facts}
            facts = [f"{' '.join(f.points)}{(' ~ ' + ' '.join(f.other)) if f.other else ''}"
                     f"{(' = ' + f.value) if f.value else ''} ({_KINDS.get(f.kind, f.kind)}; {_fact_label(verdicts.get(f.id))})"
                     for f in model.geometry.facts][:16]
            add("geometry_facts", text="Şekil ölçekli değildir; yalnız doğrulanmış olgular hesapta kullanılır. "
                                       "Şekil ve metin görselden AI ile okunmuş olabilir.",
                facts=facts, schematic=model.geometry.schematic)
        answer = artifact.content.answer if artifact else None
        add("final_answer",text=answer.description if isinstance(answer, MathAnswer) else c.final_answer,latex=answer.expressions[0] if isinstance(answer, MathAnswer) else c.final_answer_expressions[0].latex,mark="check" if verification.final_answer_verified else "warning")
        return BoardPlan(board_id=f"board_{uuid4().hex}",lesson_plan_id=lesson.lesson_plan_id,title=lesson.source_analysis.topic,elements=elements)
