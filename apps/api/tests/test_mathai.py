import pytest
from apps.api.app.features.mathai.service import MathAIService
from apps.api.app.features.lessons.schemas import Expression,LessonContent,LessonPlan,Step
from apps.api.app.features.vision.schemas import VisionAnalysis,VisualElements

def plan(original="3x + 7 = 19",final="x = 4",steps=None):
    analysis=VisionAnalysis(request_id="v1",image_status="valid_math_question",is_valid_question=True,rejection_reason=None,subject="mathematics",exam_context="TYT",topic="Denklem",subtopic="Doğrusal",question_type="open",language="tr",difficulty="easy",question_text=original,mathematical_expressions=[original],answer_choices=[],visual_elements=VisualElements(has_diagram=False,has_graph=False,has_table=False,has_geometry_figure=False,description=None),ocr_uncertainties=[],confidence=.99,provider="mock",model="mock",processing_time_ms=1)
    content=LessonContent(question_understanding="x'i bul",unknown="x",strategy="yalnız bırak",strategy_id="strategy_isolate",steps=steps or [Step(id="step_1",type="transformation",title="Düzenle",explanation="7 çıkar",expressions=[Expression(type="equation",latex="3x = 12")]),Step(id="step_2",type="result",title="Böl",explanation="3'e böl",expressions=[Expression(type="equation",latex=final)])],final_answer=final,final_answer_expressions=[Expression(type="equation",latex=value.strip()) for value in final.replace("veya",",").split(",")],takeaway="İki tarafa aynı işlem")
    return LessonPlan(lesson_plan_id="lesson_1",source_analysis=analysis,learning_objectives=["denklem"],concept_id="concept_linear_equation",content=content,provider="mock",model="mock",lesson_generation_ms=1)

def choice_plan(final="C) 3", final_expr="k = 3"):
    p=plan("x = 3",final_expr)
    p.source_analysis.question_text="k kaçtır?"
    p.source_analysis.mathematical_expressions=["x = 3"]
    p.source_analysis.answer_choices=["A) 1","B) 2","C) 3","D) 4"]
    p.content.final_answer=final
    p.content.final_answer_expressions=[Expression(type="equation",latex=final_expr)]
    p.content.steps=[Step(id="step_1",type="result",title="Sonucu bul",explanation="Sonuç 3'tür.",expressions=[Expression(type="equation",latex="x = 3")])]
    return p

def test_linear_equation_and_valid_substitution():
    result=MathAIService().verify(plan())
    assert result.status=="verified" and result.final_answer_verified

def test_wrong_final_answer_detected():
    result=MathAIService().verify(plan(final="x = 5"))
    assert result.status=="failed" and result.contradiction

def test_invalid_transformation_detected():
    steps=[Step(id="step_1",type="transformation",title="yanlış",explanation="yanlış",expressions=[Expression(type="equation",latex="3x = 11")])]
    assert MathAIService().verify(plan(steps=steps)).status=="failed"

def test_absolute_value_multiple_solutions():
    result=MathAIService().verify(plan("|x - 2| = 4","x = -2 veya x = 6",[Step(id="step_1",type="case",title="durum",explanation="iki durum",expressions=[Expression(type="equation",latex="x = -2"),Expression(type="equation",latex="x = 6")])]))
    assert result.status=="verified" and result.final_answer_verified

def test_expression_equivalence(): assert MathAIService().equivalent("(x+1)^2","x^2+2x+1")
def test_function_roots():
    graph=MathAIService().analyze_function("y = x^2 - 4")
    assert graph.roots==[-2.0,2.0] and graph.y_intercept==-4.0

def test_pythagorean(): assert MathAIService().pythagorean_hypotenuse(3,4)==5
def test_basic_geometry():
    service=MathAIService(); assert service.triangle_missing_angle(60,70)==50; assert service.rectangle_area(3,4)==12; assert service.circle_diameter(5)==10

def test_unsupported_case_is_honest():
    p=plan();p.source_analysis.mathematical_expressions=[]
    assert MathAIService().verify(p).status=="unsupported"
def test_function_question_produces_graph_foundation():
    result=MathAIService().verify(plan("y = x^2 - 4","x = 2"))
    assert result.status=="partially_verified" and result.graph and result.graph.roots==[-2.0,2.0]

def test_answer_choice_matches_computed_value():
    result=MathAIService().verify(choice_plan("C) 3","x = 3"))
    assert result.status=="verified"
    assert any(check.id=="answer_choice" and check.status=="passed" and "C" in (check.detail or "") for check in result.checks)

def test_wrong_answer_choice_label_is_detected():
    result=MathAIService().verify(choice_plan("B) 2","x = 3"))
    assert result.status=="failed"
    assert result.contradiction
    assert any(check.id=="answer_choice" and check.status=="failed" and "C" in (check.detail or "") for check in result.checks)

def test_answer_choice_label_can_be_reconciled_without_ai():
    fixed=MathAIService().reconcile_answer_choice(choice_plan("B) 2","x = 3"))
    assert fixed.content.final_answer=="C) 3"
    assert fixed.content.final_answer_expressions[0].latex=="x = 3"
