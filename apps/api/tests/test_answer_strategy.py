"""TA-005 şıkları gizleyerek çözme: strateji kararı, istemde şık yokluğu ve sağlayıcı çağrı sayısı.

Sahte OpenAI istemcisi kullanılır; ağ çağrısı yoktur. Sahte model bilinçli olarak çeldirici şıkka denk gelen
yanlış kapsamlı sonucu da önerir; bu model kalitesi ölçümü değildir.
"""

import json

import apps.api.app.features.lessons.openai_provider as provider_module
import pytest
from apps.api.app.features.board.planner import BoardPlanner
from apps.api.app.features.lessons.context import build_lesson_generation_context, strategy_decision
from apps.api.app.features.lessons.openai_provider import OpenAILessonProvider
from apps.api.app.features.lessons.schemas import LessonDraftResponse
from apps.api.app.features.lessons.service import LessonService
from apps.api.app.features.mathai.service import MathAIService
from apps.api.tests.fake_openai import raw_responses
from apps.api.tests.test_lesson_provider_errors import lesson_payload
from apps.api.tests.test_question_integrity import analysis

# (kimlik, tuzak, soru, ifade, şıklar, doğru şık, doğru değer, çeldirici değer)
TRAPS = [
    ("root_scope", "kök kapsamı", "İşleminin sonucu kaçtır?", r"\sqrt{16+9}",
     ["A) 13", "B) 5", "C) 7", "D) 25"], "B", "5", "13"),
    ("nested_root_scope", "iç içe kök kapsamı", "İşleminin sonucu kaçtır?", r"\sqrt{\sqrt{16}+5}",
     ["A) 7", "B) 9", "C) 3", "D) 4"], "C", "3", "7"),
    ("denested_root", "iç içe kök sadeleştirme", "İfadesinin eşiti kaçtır?", r"\sqrt{4+2\sqrt{3}}",
     ["A) 2+\\sqrt{3}", "B) 1+\\sqrt{3}", "C) \\sqrt{6}", "D) 3"], "B", "1+\\sqrt{3}", "2+\\sqrt{3}"),
    ("power_of_power", "üs önceliği", "İşleminin sonucu kaçtır?", r"2^{3^{2}}",
     ["A) 64", "B) 81", "C) 512", "D) 36"], "C", "512", "64"),
    ("negative_square", "üs önceliği (eksi)", "İşleminin sonucu kaçtır?", r"-2^{2}",
     ["A) 4", "B) -4", "C) 2", "D) -2"], "B", "-4", "4"),
    ("fraction_bar_scope", "kesir çizgisi kapsamı", "İşleminin sonucu kaçtır?", r"\frac{6+2}{2}",
     ["A) 7", "B) 8", "C) 4", "D) 3"], "C", "4", "7"),
    ("continued_fraction", "kesir çizgisi kapsamı (iç içe)", "İşleminin sonucu kaçtır?", r"\frac{1}{2+\frac{1}{2}}",
     ["A) 1", "B) \\frac{2}{5}", "C) \\frac{5}{2}", "D) \\frac{1}{4}"], "B", "\\frac{2}{5}", "1"),
]


def trap_analysis(question, expression, choices):
    return analysis(question_text=question, mathematical_expressions=[expression], answer_choices=choices)


class Capture:
    """İsteği kaydeder ve sıradaki taslağı döndürür; şıklara yalnızca istem üzerinden erişebilir."""

    def __init__(self, finals):
        self.finals = list(finals)
        self.user_messages: list[str] = []

    async def parse(self, **kwargs):
        self.user_messages.append(kwargs["input"][1]["content"])
        final = self.finals.pop(0)
        payload = lesson_payload()
        payload["content"].update(
            known_values=[], unknown="istenen değer", final_answer=final,
            final_answer_expressions=[{"type": "expression", "latex": final}],
            steps=[{"id": "step_1", "type": "result", "title": "Hesapla", "explanation": "İşlem önceliğine göre hesaplanır.",
                    "expressions": [{"type": "expression", "latex": final}], "visual_reference": None}])
        return type("Parsed", (), {"output_parsed": LessonDraftResponse.model_validate(payload)})()


class Client:
    def __init__(self, capture):
        self.responses = raw_responses(capture.parse)

    async def close(self):
        pass


def service(monkeypatch, capture):
    monkeypatch.setattr(provider_module, "AsyncOpenAI", lambda **kwargs: Client(capture))
    return LessonService(OpenAILessonProvider("fixture-key", "fixture", 5), MathAIService(), BoardPlanner())


@pytest.mark.parametrize("case", TRAPS, ids=[case[0] for case in TRAPS])
def test_trap_questions_choose_hidden_strategy_with_reason(case):
    _, _, question, expression, choices, *_ = case
    decision = strategy_decision(trap_analysis(question, expression, choices))
    assert decision.strategy == "solve_first_hidden"
    assert decision.reason.startswith("constant_expression:")


@pytest.mark.asyncio
@pytest.mark.parametrize("case", TRAPS, ids=[case[0] for case in TRAPS])
async def test_hidden_strategy_never_shows_choices_and_needs_one_call(monkeypatch, case):
    _, _, question, expression, choices, label, value, _ = case
    capture = Capture([value])
    result = await service(monkeypatch, capture).generate(trap_analysis(question, expression, choices))
    assert len(capture.user_messages) == 1
    problem = json.loads(capture.user_messages[0])["problem"]
    assert "answer_choices" not in problem and problem["answer_choice_count"] == 4
    for choice in choices:
        assert choice not in capture.user_messages[0]  # şık metni ve etiketi istemde hiç yok
    assert result.lesson.content.final_answer.startswith(f"{label})")
    assert result.verification.choice_match.status == "matched"


@pytest.mark.asyncio
@pytest.mark.parametrize("case", TRAPS, ids=[case[0] for case in TRAPS])
async def test_bait_value_is_caught_and_corrected_within_call_cap(monkeypatch, case):
    _, _, question, expression, choices, label, value, bait = case
    capture = Capture([bait, value])
    result = await service(monkeypatch, capture).generate(trap_analysis(question, expression, choices))
    assert len(capture.user_messages) == 2  # ilk ders + tek düzeltme; lesson_max_provider_calls (3) içinde
    assert all("answer_choices" not in json.loads(message)["problem"] for message in capture.user_messages)
    assert result.correction_attempted and result.lesson.content.final_answer.startswith(f"{label})")


@pytest.mark.parametrize(("question", "expressions", "choices", "strategy", "reason"), [
    ("Aşağıdakilerden hangisi yanlıştır?", [], ["A) √4 = 2", "B) √9 = 3", "C) √16 = 5", "D) √25 = 5"],
     "choice_dependent", "choice_dependent_intent"),
    ("2 < x < 6 ve x bir tam sayı ise x aşağıdakilerden hangisi olabilir?", ["2 < x < 6"],
     ["A) 1", "B) 2", "C) 4", "D) 6"], "choice_dependent", "choice_dependent_intent"),
    ("Buna göre I, II ve III ifadelerinden hangileri doğrudur?", [], ["A) Yalnız I", "B) I ve II", "C) II ve III", "D) I, II ve III"],
     "choice_dependent", "choice_dependent_intent"),
    ("İfadesinin sadeleştirilmiş hali hangisidir?", [r"\frac{x^2-1}{x-1}"], ["A) x+1", "B) x-1", "C) x", "D) 1"],
     "derive_then_select", "symbolic_expression"),
    ("x + y = 10 ise x·y en çok kaçtır?", ["x + y = 10"], ["A) 25", "B) 20", "C) 10", "D) 50"],
     "derive_then_select", "model_not_supported"),
    ("x² − 5x + 6 = 0 denkleminin kökler toplamı kaçtır?", ["x^2-5x+6=0"], ["A) 6", "B) 5", "C) -5", "D) 2"],
     "solve_first_hidden", "single_equation:root_sum"),
    ("2x − 3 < 7 eşitsizliğini sağlayan en büyük tam sayı kaçtır?", ["2x-3<7"], ["A) 5", "B) 4", "C) 3", "D) 6"],
     "solve_first_hidden", "single_inequality:maximum"),
])
def test_choice_part_of_question_keeps_choices_and_reason_is_explained(question, expressions, choices, strategy, reason):
    item = analysis(question_text=question, mathematical_expressions=expressions, answer_choices=choices)
    decision = strategy_decision(item)
    assert (decision.strategy, decision.reason) == (strategy, reason)
    built = build_lesson_generation_context(item)
    assert built.metrics.answer_strategy == strategy and built.metrics.answer_strategy_reason == reason
    assert ("answer_choices" in built.payload["problem"]) == (strategy != "solve_first_hidden")
