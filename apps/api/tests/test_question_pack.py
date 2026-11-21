"""TeacherAI 24 özgün soru paketi regresyonu. Sağlayıcı çağrısı yoktur; model başarısı ölçülmez."""

import json

from apps.api.app.features.lessons.context import build_lesson_generation_context
from scripts import question_pack


def test_pack_answers_are_never_wrong_and_unsupported_science_abstains():
    summary = question_pack.run()
    assert summary["mismatches"] == []
    assert summary["questions"] == 24 and summary["wrong"] == 0
    assert set(summary["abstained"]) == {"M05", "B01", "B02", "B05"}
    assert summary["extra_vision_calls_on_clean_reading"] == 0 and summary["clarification_on_clean_reading"] == 0


def test_answer_key_never_reaches_provider_context():
    pack = json.loads(question_pack.PACK.read_text(encoding="utf-8"))
    for question in pack["questions"]:
        assert set(question["reading"]) <= {"subject", "question_text", "answer_choices", "mathematical_expressions",
                                            "visual_elements", "source"}
        if question["subject"] != "mathematics":
            continue
        payload = build_lesson_generation_context(question_pack.analysis(question["reading"])).payload
        serialized = json.dumps(payload, ensure_ascii=False)
        assert "evaluation" not in serialized and "answer_origin" not in serialized
        integrity = payload["problem"].get("question_integrity", {})
        if integrity.get("answer_strategy") == "solve_first_hidden":
            assert "answer_choices" not in payload["problem"]  # önce çöz: seçenek değerleri gönderilmez


def test_fkb_pack_questions_are_not_routed_to_generation():
    pack = json.loads(question_pack.PACK.read_text(encoding="utf-8"))
    for question in pack["questions"]:
        decision = question_pack.analysis(question["reading"]).integrity.decision
        assert (decision == "unsupported_subject") == (question["subject"] != "mathematics")
