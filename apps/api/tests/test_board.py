from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.mathai.service import MathAIService
from apps.api.tests.test_mathai import plan

def test_board_has_semantic_marks_equations_notes_and_box():
    lesson=plan();board=BoardPlanner().create(lesson,MathAIService().verify(lesson))
    types={x.type for x in board.elements}
    assert {"title","teacher_note","equation","arrow","final_answer"}<=types
    final=board.elements[-1]
    assert final.type=="final_answer" and final.mark=="check"

def test_warning_generates_cross():
    lesson=plan();lesson.content.common_mistake="İşaret hatası";lesson.content.mistake_type="sign"
    board=BoardPlanner().create(lesson,MathAIService().verify(lesson))
    assert any(x.type=="warning" and x.mark=="cross" for x in board.elements)

def test_long_teacher_note_is_valid():
    lesson=plan();lesson.content.steps[0].explanation="uzun "*1000
    board=BoardPlanner().create(lesson,MathAIService().verify(lesson))
    assert len(board.elements)>1
