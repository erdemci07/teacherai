"""TA-004 fizik, kimya, biyoloji ve ortak kanıt denetimleri. Tamamen yerel; sağlayıcı çağrısı yoktur."""

import random
import re
from fractions import Fraction
from pathlib import Path

import pytest
from apps.api.app.features.education.domain import Subject, capabilities
from apps.api.app.features.education.lesson import DerivationStepBlock, EducationalDraft
from apps.api.app.features.education.science import Entity, Relation, ScientificProblemModel
from apps.api.app.features.reasoning import chemistry, formula, narrative, units
from pydantic import ValidationError
from scripts import science_matrix

REASONING = Path(__file__).parents[1] / "app/features/reasoning"


def test_science_matrix_meets_fixture_acceptance():
    summary = science_matrix.run()
    assert summary["mismatches"] == []
    assert summary["cases"] >= 60
    assert {"physics", "chemistry", "biology", "science"} <= set(summary["by_subject"])
    # Desteklenmeyen ve başarısız sonuçlar gerçek; her vaka "geçti" değildir.
    assert summary["by_outcome"]["failed"] >= 10 and summary["by_outcome"]["unsupported"] >= 10


def test_reasoning_modules_never_execute_text():
    for path in REASONING.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert not re.search(r"\beval\(|\bexec\(|sympify\(|ast\.parse\(|^\s*(?:import|from) sympy", source, re.MULTILINE), path.name


def test_fkb_generation_is_still_unavailable():
    for subject in (Subject.PHYSICS, Subject.CHEMISTRY, Subject.BIOLOGY, Subject.SCIENCE):
        assert capabilities(subject).generation is False and capabilities(subject).verification == "unsupported"


# --------------------------------------------------------------------------- birimler


@pytest.mark.parametrize(("left", "right", "equivalent"), [
    ("m/s", "m·s⁻¹", True), ("m/s", "m s^-1", True), ("m/s", "m/s²", False), ("N", "kg·m/s²", True),
    ("J", "N·m", True), ("W", "J/s", True), ("Pa", "N/m²", True), ("mol/L", "mmol/mL", True), ("km/h", "m/s", False),
])
def test_unit_equivalence(left, right, equivalent):
    assert units.equivalent_units(left, right) is equivalent


@pytest.mark.parametrize("text", ["C", "M", "l", "Co", "Na", "kgg", "m^9", "x" * 50, "J/(((m·s)))", "°C·m"])
def test_ambiguous_unknown_or_unbounded_units_are_not_guessed(text):
    with pytest.raises(units.UnitError):
        units.parse_unit(text)


def test_conversion_round_trip_property():
    rng = random.Random(4)
    pairs = [("km", "m"), ("cm", "mm"), ("h", "min"), ("g", "kg"), ("mL", "L"), ("km/h", "m/s"), ("kJ", "J"), ("kPa", "Pa")]
    for _ in range(200):
        a, b = rng.choice(pairs)
        value = Fraction(rng.randint(-10**6, 10**6), rng.choice([1, 2, 4, 5, 8, 10, 100]))
        text = f"{value.numerator / value.denominator}"
        if "e" in text or len(text.split(".")[-1]) == 3:
            continue
        forward = units.convert(f"{text} {a}", b)
        unit_a, unit_b = units.parse_unit(a), units.parse_unit(b)
        assert forward * unit_b.scale == units.parse_number(text)[0] * unit_a.scale


def test_temperature_offset_and_mass_weight_are_explicit():
    with pytest.raises(units.DimensionError):
        units.convert("25 °C", "K")
    with pytest.raises(units.DimensionError):
        units.convert("2 kg", "N")
    assert formula.add_quantities("10 °C", "5 °C").outcome == "unsupported"


def test_scientific_notation_signs_and_separators():
    assert units.parse_number("10⁻³")[0] == Fraction(1, 1000)
    assert units.parse_number("10³")[0] == 1000
    assert units.parse_number("3×10⁻³")[0] == Fraction(3, 1000)
    assert units.parse_number("2,5")[0] == Fraction(5, 2)
    for ambiguous in ("1,250", "1.000"):
        with pytest.raises(units.NumberError):
            units.parse_number(ambiguous)


def test_formula_dimension_property_wrong_dimensions_never_pass():
    rng = random.Random(7)
    good = {"v": "m/s", "a": "m/s²", "t": "s"}
    alternatives = ["m", "s", "kg", "N", "m/s", "m/s²", "J"]
    for _ in range(100):
        units_ = {key: rng.choice(alternatives) for key in good}
        result = formula.check_dimensions("v = a t", units_)
        consistent = units.parse_unit(units_["v"]).dim == tuple(
            a + b for a, b in zip(units.parse_unit(units_["a"]).dim, units.parse_unit(units_["t"]).dim))
        assert result.outcome == ("partially_checked" if consistent else "failed")


def test_formula_bindings_are_bounded_and_symbols_are_never_assumed():
    assert formula.check_formula("F = m a", {"m": "2 kg"}, "19,6 N").reason == "missing_quantity"
    many = {f"x_{i}": "1 m" for i in range(13)}
    assert formula.check_formula("y = x_1", many, "1 m").reason == "binding_budget"


# --------------------------------------------------------------------------- kimya


def test_formula_parser_composition_property():
    rng = random.Random(11)
    elements = ["H", "C", "N", "O", "Na", "Cl", "Ca", "Fe", "Co", "S", "Mg", "Al"]
    for _ in range(300):
        parts = rng.sample(elements, rng.randint(1, 4))
        counts = {element: rng.randint(1, 9) for element in parts}
        text = "".join(element + (str(count) if count > 1 else "") for element, count in counts.items())
        coefficient = rng.randint(1, 5)
        species = chemistry.parse_species((str(coefficient) if coefficient > 1 else "") + text)
        assert dict(species.composition) == counts and species.coefficient == coefficient


def test_balanced_reactions_stay_balanced_when_scaled_and_break_when_perturbed():
    reaction = chemistry.parse_reaction("2H₂ + O₂ → 2H₂O")
    for factor in range(1, 6):
        text = f"{2 * factor}H₂ + {factor}O₂ → {2 * factor}H₂O"
        assert chemistry.check_reaction(text)[0] == "passed"
    assert chemistry.check_reaction("2H₂ + O₂ → 3H₂O")[0] == "failed"
    assert reaction.reversible is False and chemistry.parse_reaction("N₂ + 3H₂ ⇌ 2NH₃").reversible is True


def test_case_coefficient_subscript_and_charge_are_never_conflated():
    assert dict(chemistry.parse_species("CO").composition) == {"C": 1, "O": 1}
    assert dict(chemistry.parse_species("Co").composition) == {"Co": 1}
    assert chemistry.parse_species("2H₂").coefficient == 2 and dict(chemistry.parse_species("H₂O").composition) == {"H": 2, "O": 1}
    assert chemistry.parse_species("Fe²⁺").charge == 2 and chemistry.parse_species("Fe³⁺").charge == 3
    assert chemistry.parse_species("SO₄²⁻").charge == -2
    with pytest.raises(chemistry.ChemistryError):
        chemistry.parse_species("Xy")
    with pytest.raises(chemistry.ChemistryError):
        chemistry.parse_species("((((H))))2")
    with pytest.raises(chemistry.ChemistryError):
        chemistry.parse_species("H" * 60)


# --------------------------------------------------------------------------- anlatı ve model


def test_long_narrative_keeps_late_condition_and_ignores_decorative_numbers():
    story = ("Bir sabah üç arkadaş parka gider. " * 30) + "Araç A 20 m/s, araç B 15 m/s hızla zıt yönde ilerler. Aradaki uzaklık kaç saniyede kapanır?"
    found = narrative.quantities(story)
    assert [q.magnitude for q in found] == ["20", "15"] and all(q.unit.canonical == "m·s^-1" for q in found)
    segments = narrative.segments(story)
    assert segments[-1].role == "requested" and segments[-1].end == len(story)


def test_problem_model_rejects_dangling_and_cross_panel_relations():
    entities = [Entity(id="a", kind="object", figure=None, provenance="visual_reading")]
    with pytest.raises(ValidationError):
        ScientificProblemModel(subject="physics", entities=entities,
                               relations=[Relation(id="r", type="points_to", subject="a", object="ghost", provenance="visual_reading")])
    with pytest.raises(ValidationError):
        ScientificProblemModel(subject="physics", entities=[Entity(id="a", kind="object", figure="missing", provenance="source_text")])


def test_derivation_step_cannot_reference_itself_or_invent_an_operation_origin():
    step = {"id": "s1", "kind": "derivation_step", "step_index": 1, "explanation": "Biyolojik süreç sırası çıkarılır.",
            "operation": "infer_sequence", "operation_origin": "fixture"}
    EducationalDraft(activity="topic_lesson", objectives=["a"], blocks=[step], takeaway="t")
    with pytest.raises(ValidationError):
        DerivationStepBlock.model_validate(step | {"operation": "unknown"})
    with pytest.raises(ValidationError):
        DerivationStepBlock.model_validate(step | {"operation_origin": "unknown"})
    with pytest.raises(ValidationError):
        EducationalDraft(activity="topic_lesson", objectives=["a"], takeaway="t",
                         blocks=[step | {"outputs": [{"kind": "block", "id": "s1"}]}])
