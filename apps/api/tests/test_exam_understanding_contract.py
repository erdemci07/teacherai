from pathlib import Path

from apps.api.app.features.vision.schemas import VisionProviderAnalysis, VisualElements


def analysis_with_visual(**visual_overrides) -> VisionProviderAnalysis:
    visual = {
        "has_diagram": False,
        "has_graph": False,
        "has_table": False,
        "has_geometry_figure": False,
        "description": None,
    }
    visual.update(visual_overrides)
    return VisionProviderAnalysis(
        image_status="valid_math_question",
        is_valid_question=True,
        rejection_reason=None,
        subject="mathematics",
        exam_context="TYT",
        topic="Cebir",
        subtopic="Denklemler",
        question_type="multiple_choice",
        language="tr",
        difficulty="medium",
        question_text="Bir matematik sorusu",
        mathematical_expressions=["x + 2 = 5"],
        answer_choices=["A) 1", "B) 2", "C) 3", "D) 4"],
        visual_elements=VisualElements(**visual),
        ocr_uncertainties=[],
        confidence=0.9,
    )


def test_ordinary_algebra_defaults_to_no_visual_dependency() -> None:
    analysis = analysis_with_visual()

    assert analysis.visual_elements.visual_relevance == "none"
    assert analysis.visual_elements.relevant_visual_facts == []
    assert analysis.visual_elements.relationships == []


def test_story_problem_contract_preserves_relevant_constraints_without_template_path() -> None:
    prompt = Path("apps/api/app/features/vision/prompts/question_analysis.txt").read_text(encoding="utf-8")

    for phrase in ("entities", "quantities", "units", "constraints", "relationships", "unknowns", "model clues"):
        assert phrase in prompt
    assert "do not repeat decorative narrative details" in prompt


def test_geometry_graph_table_number_line_and_set_relationships_fit_compact_schema() -> None:
    cases = [
        analysis_with_visual(has_geometry_figure=True, visual_relevance="essential", relevant_visual_facts=["AB = AC", "m(A) = 40"], relationships=["AB and AC have equal length markings", "40 belongs to angle A"]),
        analysis_with_visual(has_graph=True, visual_relevance="essential", relevant_visual_facts=["point P is (2, 3)"], relationships=["P lies on the graph", "3 belongs to y-axis value"]),
        analysis_with_visual(has_table=True, visual_relevance="essential", relevant_visual_facts=["Monday total is 12"], relationships=["12 is in Monday row and total column"]),
        analysis_with_visual(has_diagram=True, visual_relevance="supporting", relevant_visual_facts=["A is left of B on number line"], relationships=["labels keep left-to-right order"]),
        analysis_with_visual(has_diagram=True, visual_relevance="essential", relevant_visual_facts=["A shaded region belongs to set K"], relationships=["shading indicates membership in K"]),
    ]

    assert all(item.visual_elements.relationships for item in cases)
    assert {item.visual_elements.visual_relevance for item in cases} == {"supporting", "essential"}


def test_ambiguous_visual_uses_uncertainty_instead_of_invented_fact() -> None:
    analysis = analysis_with_visual(
        has_diagram=True,
        visual_relevance="essential",
        relevant_visual_facts=["number line labels A and B are visible"],
        relationships=[],
    ).model_copy(update={"ocr_uncertainties": ["B'nin yanındaki sayı net değil"]})

    assert analysis.ocr_uncertainties
    assert analysis.visual_elements.relationships == []


def test_invalid_image_cannot_carry_invented_visual_facts() -> None:
    try:
        VisionProviderAnalysis(
            image_status="not_math_question",
            is_valid_question=False,
            rejection_reason="Matematik sorusu yok.",
            subject="",
            exam_context=None,
            topic="",
            subtopic=None,
            question_type="",
            language="tr",
            difficulty="unknown",
            question_text="",
            mathematical_expressions=[],
            answer_choices=[],
            visual_elements=VisualElements(
                has_diagram=True,
                has_graph=False,
                has_table=False,
                has_geometry_figure=False,
                description="Bir şekil var.",
                visual_relevance="supporting",
                relevant_visual_facts=["A noktası var"],
                relationships=[],
            ),
            ocr_uncertainties=[],
            confidence=0.1,
        )
    except ValueError as exc:
        assert "invented visual facts" in str(exc)
    else:
        raise AssertionError("invalid image visual facts should fail validation")


def test_prompt_preserves_answer_choice_and_no_estimation_contracts() -> None:
    prompt = Path("apps/api/app/features/vision/prompts/question_analysis.txt").read_text(encoding="utf-8")
    lesson_prompt = Path("apps/api/app/features/lessons/prompts/lesson_plan.txt").read_text(encoding="utf-8")

    assert "answer choices" in prompt
    assert "Do not infer exact measurements or equal spacing" in prompt
    assert "Tablo değerlerini satır/sütun bağlamından koparma" in lesson_prompt
    assert "Grafik noktalarını eksen/ölçek/koordinatla" in lesson_prompt
    assert "Ölçekli olmadığı belirtilen veya belirsiz şekilden ölçü tahmin etme" in lesson_prompt


def test_representative_exam_categories_are_named_without_separate_code_paths() -> None:
    prompt = Path("apps/api/app/features/vision/prompts/question_analysis.txt").read_text(encoding="utf-8")

    for term in ("diagrams", "geometry", "graphs", "tables", "number lines", "sets", "shaded regions", "routes", "operation boxes", "patterns"):
        assert term in prompt


def test_visual_observability_is_compact_and_non_sensitive() -> None:
    service = Path("apps/api/app/features/vision/service.py").read_text(encoding="utf-8")

    assert "visual_relevance" in service
    assert "visual_relationship_count" in service
    assert "uncertainty_count" in service
    assert "question_text" not in service.split('"Vision processing succeeded"', 1)[1].split("return VisionAnalysis", 1)[0]
