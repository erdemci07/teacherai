from pathlib import Path


def test_lesson_prompt_prefers_structured_expressions_and_consistent_delimiters() -> None:
    prompt = Path("apps/api/app/features/lessons/prompts/lesson_plan.txt").read_text(encoding="utf-8")

    assert "structured expressions[].latex" in prompt
    assert r"inline ifade için yalnızca \( ... \)" in prompt
    assert r"display ifade için yalnızca \[ ... \]" in prompt
    assert r"\frac veya \sqrt gibi ham komutları delimiter dışında prose içine yazma" in prompt
    assert "Matematik token'larını Türkçe prose ile bitiştirme" in prompt
    assert "KaTeX uyumlu" in prompt
    assert "normal Türkçe metni matematik delimiter" in prompt
    assert "Markdown code fence" in prompt
    assert "HTML üretme" in prompt


def test_lesson_prompt_requires_student_facing_teacher_tip() -> None:
    prompt = Path("apps/api/app/features/lessons/prompts/lesson_plan.txt").read_text(encoding="utf-8")

    assert "teacher_tip varsa tek bir öğrenciye doğrudan seslenen" in prompt
    assert "sıcak, doğal ve kısa Türkçe" in prompt
    assert "bu soruyla ilgili somut bir ayrıntıyı" in prompt


def test_lesson_prompt_rejects_teacher_to_teacher_teacher_tip_language() -> None:
    prompt = Path("apps/api/app/features/lessons/prompts/lesson_plan.txt").read_text(encoding="utf-8")

    for phrase in ("öğrencilere", "öğrencilerin", "kavratılmalıdır", "sorgulatın", "öğretmenler"):
        assert phrase in prompt
    assert "öğretmenden öğretmene yönergeler kullanma" in prompt
