from pathlib import Path


def test_rich_math_text_supports_mixed_turkish_prose_and_delimiters() -> None:
    source = Path("apps/web/app/solve/RichMathText.tsx").read_text(encoding="utf-8")

    examples = [
        "İlk olarak ( x+2=5 ) denklemine bakalım.",
        "Şimdi [ x^2 - 4 = 0 ] ifadesini çözelim.",
        "Oranımız $a/b$ şeklindedir.",
    ]

    assert "parseRichMathText" in source
    assert "scanRawMath" in source
    assert "scanCommand" in source
    assert "one === '('" in source
    assert "one === '['" in source
    assert "two === '$$'" in source
    assert "one === '$'" in source
    assert "two === '\\\\('" in source
    assert "two === '\\\\['" in source
    for example in examples:
        assert example


def test_rich_math_text_detects_raw_latex_and_boundary_safety() -> None:
    source = Path("apps/web/app/solve/RichMathText.tsx").read_text(encoding="utf-8")
    styles = Path("apps/web/app/globals.css").read_text(encoding="utf-8")

    for fragment in (r"frac", r"sqrt", r"sin", r"cos", r"tan", r"cot", r"log", r"ln", r"circ", r"pi", r"theta", r"alpha", r"beta", r"cdot", r"times", r"le", r"ge", r"neq", r"pm"):
        assert fragment in source
    assert "scanSimpleAtom" in source
    assert "data-math-boundary" in source
    assert ".richMath{display:inline-block" in styles
    assert "margin:0 .08em" in styles


def test_malformed_latex_falls_back_per_fragment_without_hiding_text() -> None:
    source = Path("apps/web/app/solve/RichMathText.tsx").read_text(encoding="utf-8")
    lesson_text = Path("apps/web/app/solve/LessonText.tsx").read_text(encoding="utf-8")
    math_expression = Path("apps/web/app/solve/MathExpression.tsx").read_text(encoding="utf-8")

    assert "throwOnError: true" in source
    assert "richMathFallback" in source
    assert "<RichMathText text={x.explanation}/>" in lesson_text
    assert "Matematiksel ifade görüntülenemedi" not in math_expression
    assert "readableMathFallback" in source
    assert "√($1)" in source
    assert "°" in source


def test_structured_expressions_still_use_math_expression() -> None:
    lesson_text = Path("apps/web/app/solve/LessonText.tsx").read_text(encoding="utf-8")

    assert "MathExpression" in lesson_text
    assert "x.expressions.map" in lesson_text
    assert "c.final_answer_expressions.map" in lesson_text


def test_embedded_trig_and_fraction_latex_are_high_confidence_math() -> None:
    source = Path("apps/web/app/solve/RichMathText.tsx").read_text(encoding="utf-8")

    for fragment in (r"\cos 200^\circ", r"\sin 20^\circ", r"\frac{190^\circ}{2}"):
        assert fragment
    assert "RAW_COMMANDS = new Set" in source
    assert "'cos'" in source
    assert "'sin'" in source
    assert "'circ'" in source
    assert "scanRawMath" in source


def test_ordinary_turkish_prose_requires_math_signal_before_conversion() -> None:
    source = Path("apps/web/app/solve/RichMathText.tsx").read_text(encoding="utf-8")

    assert "candidateNeedsSignal" in source
    assert "looksLikeMath(latex)" in source
    assert "Do NOT" not in source
