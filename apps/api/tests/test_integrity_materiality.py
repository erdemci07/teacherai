"""TA-004 eski OCR notlarının önemliliği ve zorunlu görsel kuralı. Sağlayıcı çağrısı yoktur."""

import pytest
from apps.api.app.features.integrity.engine import EvaluationState, apply_recheck, evaluate, recheck_items
from apps.api.app.features.integrity.materiality import classify
from apps.api.tests.test_question_integrity import wire

RADICAL = {"question_text": "√(x + 5) = 3 ise x kaçtır?", "mathematical_expressions": ["\\sqrt{x + 5} = 3"]}
MISSING_VISUAL = {"has_diagram": False, "has_graph": False, "has_table": False, "has_geometry_figure": True, "description": None,
                  "visual_relevance": "essential", "relevant_visual_facts": [], "relationships": []}


@pytest.mark.parametrize(("note", "level"), [
    ("Kök işaretinin nerede bittiği net değil.", "material"),
    ("Kök ifadesi açıkça okundu.", "nonconsequential"),  # anahtar kelime var, şüphe yok
    ("Yazı tipi farklı, sayfada gölge var.", "harmless"),
    ("Bazı yerler biraz bulanık.", "insufficient"),
    ("Üst köşede sayfa numarası var.", "harmless"),  # "üst" kelimesi üs kategorisi sayılmaz
])
def test_legacy_note_classification_needs_doubt_category_and_context(note, level):
    assert classify(note, wire(**RADICAL)).level == level


def test_keyword_without_matching_source_structure_is_not_material():
    analysis = wire()  # 3x + 7 = 19: kök yok
    assert classify("Kök işaretinin kapsamı belirsiz.", analysis).level == "nonconsequential"
    report = evaluate(analysis.model_copy(update={"ocr_uncertainties": ["Kök işaretinin kapsamı belirsiz."]}))
    assert report.solvable and "legacy_uncertainty_context_absent" in report.uncertainties[0].evidence


def test_critical_uncertainty_written_only_in_legacy_text_is_not_passed_silently():
    analysis = wire(**RADICAL, ocr_uncertainties=["Kök işaretinin nerede bittiği net değil."])
    blocked = evaluate(analysis)
    assert blocked.decision == "retake_required" and blocked.pending()[0].origin == "legacy_text"
    state = EvaluationState(recheck_limit=1)
    report = evaluate(analysis, state)
    assert report.decision == "targeted_recheck"
    items = recheck_items(report)
    assert items[0].element == "expression:0" and items[0].recognized == "\\sqrt{x + 5} = 3"
    confirmed = apply_recheck(analysis, report, items, {1: (True, "\\sqrt{x + 5} = 3")}, state)
    assert confirmed.solvable and confirmed.uncertainties[0].resolution == "confirmed_by_recheck"


def test_legacy_records_are_not_blocked_retroactively():
    analysis = wire(**RADICAL, ocr_uncertainties=["Kök işaretinin nerede bittiği net değil."])
    report = evaluate(analysis, EvaluationState(origin="legacy"))
    assert report.solvable and report.uncertainties[0].impact == "noncritical"


def test_structured_and_legacy_duplicates_are_merged():
    structured = {"source": {"uncertainties": [{"category": "radical_scope", "element": "expression:0", "recognized": "\\sqrt{x + 5}",
                                                "alternatives": ["\\sqrt{x} + 5"], "affects_answer": True, "region_index": None}]}}
    analysis = wire(**RADICAL, **structured, ocr_uncertainties=["Kök kapsamı belirsiz."])
    report = evaluate(analysis)
    assert [item.id for item in report.uncertainties] == ["u1"]
    assert any(check.code == "legacy_uncertainty_merged" for check in report.checks)


def test_essential_visual_with_sufficient_text_continues_without_extra_call():
    analysis = wire(question_text="Şekildeki üçgende x + 40 = 90 olduğuna göre x kaçtır?", mathematical_expressions=["x + 40 = 90"],
                    visual_elements=MISSING_VISUAL)
    report = evaluate(analysis, EvaluationState(recheck_limit=1))
    assert report.decision == "ready_with_noncritical_uncertainty"
    assert {check.code for check in report.checks} >= {"essential_visual_without_facts", "essential_visual_text_sufficient"}


def test_essential_visual_without_information_is_not_solved_from_fabricated_facts():
    analysis = wire(question_text="Şekle göre x kaçtır?", mathematical_expressions=[], visual_elements=MISSING_VISUAL)
    assert evaluate(analysis, EvaluationState(recheck_limit=1)).decision == "targeted_recheck"
    report = evaluate(analysis)
    assert report.decision == "retake_required" and report.recovery == "retake"
    assert report.pending()[0].id == "d_visual_missing"
