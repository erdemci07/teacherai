"""Eski serbest metin OCR belirsizlikleri için önemlilik köprüsü (TA-004).

TA-003 serbest metin notlarını her zaman önemsiz sayıyordu; sağlayıcı kritik bir belirsizliği yanlış
alana yazarsa engel oluşmuyordu. Bu modül notu sınırlı kalıplarla sınıflandırır:

- ``harmless``: biçim, yazı tipi, renk, gölge, filigran gibi cevapla ilgisiz notlar.
- ``nonconsequential``: konu kategorisi var ama ilgili yapı kaynakta yok (ör. kökten söz ediliyor, ifadede kök yok).
- ``material``: şüphe ifadesi + kategori + kaynakta o yapının bulunması (ör. kök kapsamı belirsiz ve ifadede kök var).
- ``insufficient``: şüphe var ama kategori tanınmadı; tek başına engel oluşturmaz.

Anahtar kelime tek başına reddetmez: şüphe ifadesi ve kaynak bağlamı birlikte gerekir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .language import casefold_tr

_DOUBT = (
    "belirsiz", "emin değil", "emin olunamadı", "okunamadı", "okunamıyor", "net değil", "net seçilemi", "seçilemedi",
    "ayırt edilemedi", "ayırt edilemiyor", "silik", "bulanık", "karışabilir", "karıştırılabilir", "anlaşılamadı",
    "tam görünmüyor", "görünmüyor", "eksik olabilir", "kesik", "olabilir", "ya da", "mi yoksa", "muhtemelen",
)
_HARMLESS = ("yazı tipi", "font", "renk", "gölge", "hizalama", "kenar boşluğu", "sayfa numarası", "filigran", "logo",
             "satır aralığı", "el yazısı okunaklı", "kağıt", "arka plan")

# (anahtar sözcükler, kategori, kaynakta yapının varlığını sınayan kural)
_CATEGORIES: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("kök", "karekök", "radikal", "√"), "radical_scope", "radical"),
    (("üs ", "üssü", "üssün", "kuvvet", "üstel"), "exponent_scope", "exponent"),
    (("kesir", "pay ", "payı", "payda", "kesir çizgisi"), "fraction_scope", "fraction"),
    (("eksi", "negatif", "işaret"), "sign", "minus"),
    (("ondalık", "virgül"), "decimal", "decimal"),
    (("alt simge", "indis", "molekül alt", "alt indis"), "subscript", "subscript"),
    (("birim", "m/s", "ivme birimi"), "unit", "unit"),
    (("değil", "olumsuz", "olumsuzluk"), "negation", "negation"),
    (("seçenek", "şık"), "answer_choice", "choices"),
    (("tepkime ok", "tepkime yön", "ok yönü", "çift yönlü ok"), "symbol", "arrow"),
    (("organel", "etiket", "yapı adı"), "diagram", "visual"),
    (("şekil", "çizim", "diyagram", "kuvvet ok"), "diagram", "visual"),
    (("grafik", "eksen"), "graph", "visual"),
    (("tablo", "sütun", "satır"), "table", "visual"),
    (("parantez", "ayraç"), "grouping", "grouping"),
)


@dataclass(frozen=True)
class Materiality:
    level: str  # harmless | nonconsequential | material | insufficient
    category: str
    element: str | None
    recognized: str | None


def _has(structure: str, analysis, expressions: list[str], intent) -> list[int] | bool:
    """Yapının kaynakta bulunduğu ifade sıraları (ifade yapıları için) veya True/False."""
    def where(pattern: str) -> list[int]:
        return [i for i, text in enumerate(expressions) if re.search(pattern, text)]

    if structure == "radical":
        return where(r"\\sqrt|√|∛|sqrt\(")
    if structure == "exponent":
        return where(r"\^|[²³⁴⁵⁶⁷⁸⁹⁰¹]")
    if structure == "fraction":
        return where(r"\\[dt]?frac|/")
    if structure == "minus":
        return where(r"-|−|–")
    if structure == "decimal":
        return where(r"\d[.,]\d")
    if structure == "subscript":
        return where(r"_|[₀₁₂₃₄₅₆₇₈₉]")
    if structure == "grouping":
        return where(r"[()\[\]]")
    text = (analysis.question_text or "")
    if structure == "unit":
        return bool(re.search(r"\d\s*(?:m|s|kg|N|J|mol|L|km|cm|g|°C|K)\b", text))
    if structure == "negation":
        return intent is not None and any(marker.category in {"negation", "polarity"} for marker in intent.markers)
    if structure == "choices":
        return bool(analysis.answer_choices) and intent is not None and intent.choice_dependent
    if structure == "arrow":
        return bool(re.search(r"→|⇌|->|<=>|⟶", text + " ".join(expressions)))
    if structure == "visual":
        return analysis.visual_elements.visual_relevance == "essential"
    return False


def classify(note: str, analysis, intent=None) -> Materiality:
    folded = casefold_tr(note) + " "
    expressions = list(analysis.mathematical_expressions)
    doubt = any(word in folded for word in _DOUBT)
    for words, category, structure in _CATEGORIES:
        if not any(re.search(r"(?<!\w)" + re.escape(word), folded) for word in words):
            continue
        present = _has(structure, analysis, expressions, intent)
        if not doubt or not present:
            return Materiality("nonconsequential", category, None, None)
        if isinstance(present, list):
            if len(present) == 1:
                index = present[0]
                return Materiality("material", category, f"expression:{index}", expressions[index][:400])
            return Materiality("material", category, None, None)
        element = "visual" if structure == "visual" else "stem" if structure in {"negation", "unit", "arrow"} else None
        return Materiality("material", category, element, None)
    if any(word in folded for word in _HARMLESS):
        return Materiality("harmless", "text", None, None)
    return Materiality("insufficient" if doubt else "harmless", "text", None, None)
