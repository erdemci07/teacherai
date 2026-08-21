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
