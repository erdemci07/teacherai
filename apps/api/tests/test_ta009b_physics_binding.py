"""TA-009B §1: birim sınırı, değer bağı ve g uzlaşımı (çevrimdışı; sağlayıcı çağrısı yok)."""

import copy
import json

import pytest

from apps.api.app.features.reasoning import quotes
from scripts import physics_matrix

CASES = {c["id"]: c for c in json.loads(physics_matrix.CASES.read_text(encoding="utf-8"))["cases"]}


@pytest.mark.parametrize(("source", "quote", "expected"), [
    ("yatay 20 m/s hızla", "20 m", False),
    ("20 mm uzunluk", "20 m", False),
    ("kenarı 3 cm² alan", "3 cm", False),
    ("10 N·m tork", "10 N", False),
    ("B cismi 4 kg'dır", "4 kg", True),
    ("5 m yükseklikten", "5 m", True),
    ("B açısı 40 derecedir", "B açısı 40 derece", True),
])
def test_unit_token_boundary(source, quote, expected):
    assert quotes.contains(source, quote) is expected


@pytest.mark.parametrize("case_id", sorted(c for c in CASES if c.startswith(("bind_", "gravity_choice_"))))
def test_binding_trap_cases(case_id):
    report = physics_matrix.run_case(CASES[case_id])
    assert physics_matrix.matches(report, CASES[case_id]["expect"]) == []


def test_swapped_masses_never_verified_and_ask_targeted_question():
    report = physics_matrix.run_case(CASES["bind_masses_swapped"])
    assert report.capability == "partially_checked"
    assert report.clarification_needed and "belirsiz" in report.clarification_tr
    assert any(v.origin == "unbound" for v in report.values_used)


def test_figure_only_binding_is_at_most_partial():
    """Görsel gözlem kaydı bağ kanıtıdır ama sağlayıcı okumasıdır: sonuç ``verified`` olamaz."""
    case = copy.deepcopy(CASES["bind_masses_correct"])
    case["text"] = ("Şekildeki cisimlerin kütleleri 4 kg ve 6 kg'dır. A masada, B asılıdır; sürtünme yoktur. "
                    "g = 10 m/s² alınız. Sistemin ivmesi kaç m/s²'dir?")
    unbound = physics_matrix.run_case(case)
    assert unbound.capability == "partially_checked" and unbound.clarification_needed is True
    case["observations"] = ["A cismi 4 kg", "B cismi 6 kg"]
    seen = physics_matrix.run_case(case)
    assert seen.capability == "partially_checked" and seen.answer == "matched" and seen.clarification_needed is False
    assert not any(c.reason == "value_binding_unproven" for c in seen.checks)


def test_student_confirmation_binds_value():
    case = copy.deepcopy(CASES["bind_masses_swapped"])
    case["text"] = "İki cismin kütleleri 4 kg ve 6 kg'dır. g = 10 m/s² alınız. Sistemin ivmesi kaç m/s²'dir?"
    from apps.api.app.features.education.science import ScientificProblemModel
    from apps.api.app.features.physics import verify

    problem = ScientificProblemModel.model_validate(physics_matrix._units(case["problem"]))
    report = verify.verify(problem, case["text"], case["claims"], confirmed=("A cismi 6 kg", "B cismi 4 kg"))
    assert not any(c.reason == "value_binding_unproven" for c in report.checks)


def test_gravity_not_given_without_choices_keeps_standard_constant():
    case = copy.deepcopy(CASES["gravity_choice_changes"])
    case.pop("choices")
    report = physics_matrix.run_case(case)
    assert not any(c.reason.startswith("convention_") for c in report.checks)
    assert any(v.origin == "standard_constant" for v in report.values_used)
