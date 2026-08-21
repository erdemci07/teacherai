from pathlib import Path


def test_rich_math_text_supports_mixed_turkish_prose_and_delimiters() -> None:
    source = Path("apps/web/app/solve/RichMathText.tsx").read_text(encoding="utf-8")

    examples = [
        "İlk olarak ( x+2=5 ) denklemine bakalım.",
        "Şimdi [ x^2 - 4 = 0 ] ifadesini çözelim.",
        "Oranımız $a/b$ şeklindedir.",
    ]

    assert "parseRichMathText" in source
    assert "one === '('" in source
    assert "one === '['" in source
    assert "two === '$$'" in source
    assert "one === '$'" in source
    for example in examples:
        assert example


def test_malformed_latex_falls_back_per_fragment_without_hiding_text() -> None:
    source = Path("apps/web/app/solve/RichMathText.tsx").read_text(encoding="utf-8")
    lesson_text = Path("apps/web/app/solve/LessonText.tsx").read_text(encoding="utf-8")
    math_expression = Path("apps/web/app/solve/MathExpression.tsx").read_text(encoding="utf-8")

    assert "throwOnError: true" in source
    assert "richMathFallback" in source
    assert "<RichMathText text={x.explanation}/>" in lesson_text
    assert "Matematiksel ifade görüntülenemedi" not in math_expression


def test_structured_expressions_still_use_math_expression() -> None:
    lesson_text = Path("apps/web/app/solve/LessonText.tsx").read_text(encoding="utf-8")

    assert "MathExpression" in lesson_text
    assert "x.expressions.map" in lesson_text
    assert "c.final_answer_expressions.map" in lesson_text
