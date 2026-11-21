"""TA-005 kimya ayrıştırıcısı regresyonları ve özellik tabanlı bileşim testi. Sağlayıcı çağrısı yoktur."""

import random
from collections import Counter

import pytest

from apps.api.app.features.reasoning import chemistry as chem


def _reason(func, *args):
    with pytest.raises(chem.ChemistryError) as exc:
        func(*args)
    return exc.value.reason


@pytest.mark.parametrize("text", ["Ca(OH]2", "Ca[OH)2", "K2[Fe(CN)6)", "Al2(SO4]3"])
def test_mismatched_brackets_are_rejected(text):
    assert _reason(chem.parse_species, text) == "mismatched_bracket"


@pytest.mark.parametrize("text", ["Ca()2", "Ca[]", "()", "Fe(())2"])
def test_empty_groups_are_rejected(text):
    assert _reason(chem.parse_species, text) in {"empty_group", "empty_formula"}
    if text != "()":
        assert _reason(chem.parse_species, text) == "empty_group"


def test_matching_brackets_of_both_kinds_still_parse():
    assert dict(chem.parse_species("K3[Fe(CN)6]").composition) == {"K": 3, "Fe": 1, "C": 6, "N": 6}
    assert dict(chem.parse_species("Ca(OH)2").composition) == {"Ca": 1, "O": 2, "H": 2}


def test_states_written_on_both_sides_must_match():
    assert chem.same_species("H2O(l)", "H2O(g)") is False
    assert chem.same_species("H₂O(l)", "H₂O(l)") is True
    assert chem.same_species("NaCl(s)", "NaCl(aq)") is False


def test_missing_state_on_one_side_is_unknown_not_different():
    assert chem.same_species("H2O", "H2O(l)") is True
    assert chem.same_species("Fe^{3+}(aq)", "Fe³⁺") is True


def test_coefficient_is_amount_not_identity():
    assert chem.same_species("2H₂O", "H₂O") is True
    assert chem.same_species("2H₂", "H₂O") is False
    assert chem.same_species("Fe²⁺", "Fe³⁺") is False and chem.same_species("CO", "Co") is False


@pytest.mark.parametrize("text", ["2H₂+O₂→2H₂O", "2H2+O2->2H2O", "2H₂ +O₂ → 2H₂O".replace(" +", " + "),
                                  "2H_2+O_2\\rightarrow 2H_2O", "2H_{2} + O_{2} \\to 2H_{2}O",
                                  "2\\mathrm{H_2}+\\mathrm{O_2}\\longrightarrow 2\\mathrm{H_2O}"])
def test_reactions_without_spaces_or_in_latex_parse(text):
    assert chem.check_reaction(text)[:2] == ("passed", "atoms_and_charge_conserved")


@pytest.mark.parametrize("text", ["Fe^{3+}+e^- -> Fe^{2+}", "Fe^{3+}+e^{-}\\rightarrow Fe^{2+}", "Fe^3++e^-→Fe^2+",
                                  "Fe³⁺+e⁻→Fe²⁺", "e^-+Fe^{3+} -> Fe^{2+}"])
def test_latex_and_unicode_charges_next_to_separator_plus(text):
    reaction = chem.parse_reaction(text)
    assert len(reaction.reactants) == 2
    assert chem.check_reaction(text)[:2] == ("passed", "atoms_and_charge_conserved")


@pytest.mark.parametrize("text", ["Na++Cl- -> NaCl", "Na+ +Cl- -> NaCl", "Ag++Cl-→AgCl"])
def test_truly_ambiguous_ascii_plus_is_not_guessed(text):
    assert _reason(chem.parse_reaction, text) == "ambiguous_charge_notation"


def test_spaced_ascii_charges_and_separators_still_work():
    reaction = chem.parse_reaction("Na+ + Cl- -> NaCl")
    assert [s.charge for s in reaction.reactants] == [1, -1]
    assert chem.check_reaction("Ag⁺(aq) + Cl⁻(aq) ⇌ AgCl(s)")[0] == "passed"
    assert chem.check_reaction("N_2 + 3H_2 \\rightleftharpoons 2NH_3")[0] == "passed"


def test_empty_species_between_separators_is_invalid():
    assert _reason(chem.parse_reaction, "H2 + + O2 -> H2O") in {"ambiguous_charge_notation", "empty_species"}
    assert _reason(chem.parse_reaction, "H2 + -> H2") == "empty_species"


# --------------------------------------------------------------------------- özellik tabanlı

ELEMENTS = ["H", "C", "N", "O", "Na", "Mg", "Al", "S", "Cl", "Ca", "Fe", "Cu", "Co"]
SUB = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def _formula(rng, depth=0):
    """(yazım, bileşim) üretir; ayraç türü ve alt simge yazımı rastgeledir."""
    text, counts = "", Counter()
    for _ in range(rng.randint(1, 3)):
        if depth < 2 and rng.random() < 0.3:
            inner, inner_counts = _formula(rng, depth + 1)
            n = rng.randint(1, 4)
            opening, closing = rng.choice([("(", ")"), ("[", "]")])
            text += f"{opening}{inner}{closing}{_count(rng, n)}"
            for element, count in inner_counts.items():
                counts[element] += count * n
        else:
            element, n = rng.choice(ELEMENTS), rng.randint(1, 5)
            text += element + _count(rng, n)
            counts[element] += n
    return text, counts


def _count(rng, n):
    if n == 1 and rng.random() < 0.8:
        return ""
    style = rng.choice(["ascii", "unicode", "latex", "latex_brace"])
    return {"ascii": str(n), "unicode": str(n).translate(SUB), "latex": f"_{n}" if n < 10 else f"_{{{n}}}",
            "latex_brace": f"_{{{n}}}"}[style]


def test_generated_formulas_keep_composition_under_random_spacing_and_brackets():
    rng = random.Random(20261121)
    for _ in range(400):
        species = [_formula(rng) for _ in range(rng.randint(1, 4))]
        expected = Counter()
        for _, counts in species:
            expected.update(counts)
        for text, counts in species:
            assert Counter(dict(chem.parse_species(text).composition)) == +counts, text
        # Ayraç ya boşluksuz "+" ya da iki yanı boşluklu " + "; tek yanı boşluklu "+" belirsizdir (ayrı test).
        side = species[0][0] + "".join(rng.choice(["+", " + ", "  +  "]) + text for text, _ in species[1:])
        arrow = rng.choice(["→", " -> ", "\\rightarrow ", " ⟶ ", "->"])
        reaction = chem.parse_reaction(f"{rng.choice(['', ' '])}{side}{arrow}{species[0][0]}")
        total = Counter()
        for item in reaction.reactants:
            total.update(item.atoms)
        assert total == expected, side
