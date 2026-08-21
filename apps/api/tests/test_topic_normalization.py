import pytest

from apps.api.app.features.vision.topic_normalization import normalize_topic_name


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Algebra", "Cebir"),
        ("Geometry", "Geometri"),
        ("Functions", "Fonksiyonlar"),
        ("Probability", "Olasılık"),
        ("Statistics", "İstatistik"),
        ("Trigonometry", "Trigonometri"),
        ("Calculus", "Analiz"),
        ("Arithmetic", "Aritmetik"),
        ("Numbers", "Sayılar"),
        ("Equations", "Denklemler"),
        ("Inequalities", "Eşitsizlikler"),
        ("Ratios", "Oran ve Orantı"),
        ("Fractions", "Kesirler"),
        ("Polynomials", "Polinomlar"),
    ],
)
def test_common_english_topics_are_normalized_to_turkish(source, expected) -> None:
    assert normalize_topic_name(source) == expected


@pytest.mark.parametrize("source", ["Cebir", "Mutlak Değer", "Parabol"])
def test_turkish_topics_remain_unchanged(source) -> None:
    assert normalize_topic_name(source) == source


def test_unknown_topic_remains_unchanged() -> None:
    assert normalize_topic_name("Combinatorics") == "Combinatorics"


def test_subtopic_mapping_uses_same_controlled_map() -> None:
    assert normalize_topic_name("Linear equations") == "Denklemler"
