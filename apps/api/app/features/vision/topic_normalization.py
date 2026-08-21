TOPIC_TRANSLATIONS = {
    "algebra": "Cebir",
    "geometry": "Geometri",
    "functions": "Fonksiyonlar",
    "function": "Fonksiyonlar",
    "probability": "Olasılık",
    "statistics": "İstatistik",
    "trigonometry": "Trigonometri",
    "calculus": "Analiz",
    "arithmetic": "Aritmetik",
    "numbers": "Sayılar",
    "number theory": "Sayılar",
    "equations": "Denklemler",
    "linear equations": "Denklemler",
    "inequalities": "Eşitsizlikler",
    "ratios": "Oran ve Orantı",
    "ratio and proportion": "Oran ve Orantı",
    "fractions": "Kesirler",
    "polynomials": "Polinomlar",
}


def normalize_topic_name(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return normalized
    return TOPIC_TRANSLATIONS.get(normalized.lower(), normalized)
