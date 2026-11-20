"""Soru amacı ve seçenek yapısı için belirlenimci Türkçe desenler (TA-003).

Bu modül tam bir doğal dil ayrıştırıcısı değildir. Olumsuzluk, kutupluluk, uç değer ve öncül
etiketleri gibi cevabı etkileyen işaretleri kanıt olarak çıkarır ve özgün metni değiştirmez.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..education.source import AnswerChoice, IntentMarker, QuestionIntent
from .expression import exact_value, parse, same_structure

ROMAN = ("I", "II", "III", "IV", "V", "VI")


def casefold_tr(value: str) -> str:
    return value.replace("İ", "i").replace("I", "ı").lower()


_MARKERS: tuple[tuple[str, str], ...] = (
    ("doğru değildir", "negation"),
    ("değildir", "negation"),
    ("olamaz", "possibility"),
    ("yanlıştır", "polarity"),
    ("yanlış olan", "polarity"),
    ("doğrudur", "polarity"),
    ("doğru olan", "polarity"),
    ("bulunmaz", "negation"),
    ("en az", "extremum"),
    ("en çok", "extremum"),
    ("en küçük", "extremum"),
    ("en büyük", "extremum"),
    ("yalnızca", "quantifier"),
    ("kesinlikle", "quantifier"),
    ("olabilir", "possibility"),
    ("farklı", "quantifier"),
    ("eşit", "quantifier"),
    ("toplamı", "operation"),
    ("farkı", "operation"),
    ("çarpımı", "operation"),
    ("kaç tanedir", "count"),
    ("kaç tane", "count"),
    ("kaç farklı", "count"),
)


def markers(text: str) -> list[IntentMarker]:
    folded = casefold_tr(text)
    found: list[IntentMarker] = []
    consumed: list[tuple[int, int]] = []
    for phrase, category in _MARKERS:
        for match in re.finditer(r"(?<!\w)" + re.escape(phrase), folded):
            span = match.span()
            if any(start <= span[0] < end for start, end in consumed):
                continue
            consumed.append(span)
            found.append(IntentMarker(marker=phrase, category=category))  # type: ignore[arg-type]
    unique: dict[str, IntentMarker] = {}
    for item in found:
        unique.setdefault(item.marker, item)
    return list(unique.values())[:24]


_STATEMENT = re.compile(r"(?:^|[\s\n])(VI|IV|V|III|II|I)\s*[.)]\s+\S")


def statement_labels(text: str, extra: list[str] | None = None) -> list[str]:
    """Metindeki öncül etiketleri sırasıyla; metinde yoksa sağlayıcının ayrıca aktardığı öncüller.

    Yinelenen etiket kontrolü için metindeki tekrarlar korunur; iki kaynak birbirine eklenmez.
    """
    labels = [match.group(1) for match in _STATEMENT.finditer(text)]
    if not labels:
        for item in extra or []:
            match = re.match(r"^\s*(VI|IV|V|III|II|I)\s*[.)]", item)
            if match:
                labels.append(match.group(1))
    return labels[:6]


def _last_question_sentence(text: str) -> str:
    folded = casefold_tr(text)
    end = folded.rfind("?")
    segment = folded[: end + 1] if end >= 0 else folded
    for separator in (".", "\n"):
        position = segment.rstrip("?").rfind(separator)
        if position > 0:
            segment = segment[position + 1:]
    return segment[-400:]


@dataclass(frozen=True)
class IntentEvidence:
    intent: QuestionIntent
    polarity_conflict: bool
    duplicate_statements: bool


def detect_intent(question_text: str, choices: list[AnswerChoice], statements: list[str] | None = None) -> IntentEvidence:
    folded = casefold_tr(question_text)
    ask = _last_question_sentence(question_text)
    found = markers(question_text)
    labels = statement_labels(question_text, statements)
    has = lambda *phrases: any(phrase in folded for phrase in phrases)  # noqa: E731
    asks = lambda *phrases: any(phrase in ask for phrase in phrases)  # noqa: E731

    negative = asks("yanlıştır", "yanlış olan", "değildir", "doğru değildir")
    positive = asks("doğrudur", "doğru olan") and not asks("doğru değildir")
    if asks("hangileri") or (labels and asks("hangileri", "hangisi") and (positive or negative)):
        kind = "find_all_valid"
    elif negative and asks("hangisi", "hangileri", "aşağıdaki"):
        kind = "identify_false"
    elif positive:
        kind = "identify_true"
    elif asks("olamaz", "alamaz"):
        kind = "determine_impossible"
    elif asks("olabilir", "alabilir"):
        kind = "determine_possible"
    elif asks("en az", "en küçük"):
        kind = "find_minimum"
    elif asks("en çok", "en büyük"):
        kind = "find_maximum"
    elif asks("kaç tane", "kaç farklı", "kaç tanedir"):
        kind = "count"
    elif asks("aralığı", "aralığında", "hangi aralık"):
        kind = "determine_range"
    elif has("grafik") and asks("hangisi", "göre"):
        kind = "interpret_graph"
    elif has("tablo") and asks("hangisi", "göre"):
        kind = "interpret_table"
    elif asks("hangi şekil", "şekillerden hangisi"):
        kind = "identify_shape"
    elif asks("sıralaması", "sıralanışı", "karşılaştır"):
        kind = "compare"
    elif asks("sadeleştir", "en sade", "eşittir", "eşitidir"):
        kind = "simplify"
    elif re.search(r"(?<!\w)[a-zçğıöşü]\s*(?:kaçtır|değeri|nedir)", ask) or asks("çözüm kümesi", "denklemini sağlayan", "kökü"):
        kind = "find_variable"
    elif asks("kaçtır", "nedir", "değeri", "bulunuz", "hesaplayınız", "kaç olur", "kaç"):
        kind = "find_value"
    else:
        kind = "unknown"

    nonsolvable_choices = any(choice.kind in {"text", "statement_combination", "visual", "empty"} for choice in choices)
    choice_dependent = bool(choices) and (
        kind in {"identify_true", "identify_false", "find_all_valid", "determine_possible", "determine_impossible",
                 "interpret_graph", "interpret_table", "identify_shape", "compare"}
        or bool(labels)
        or nonsolvable_choices
    )
    if not choices:
        strategy = "open"
    elif choice_dependent:
        strategy = "choice_dependent"
    elif kind in {"find_value", "find_variable", "find_minimum", "find_maximum", "count"} and all(
        choice.kind in {"number", "expression"} for choice in choices
    ):
        strategy = "solve_first_hidden"
    else:
        strategy = "derive_then_select"
    intent = QuestionIntent(kind=kind, markers=found, statement_labels=labels, choice_dependent=choice_dependent,
                            answer_strategy=strategy)  # type: ignore[arg-type]
    return IntentEvidence(intent, polarity_conflict=negative and positive, duplicate_statements=len(set(labels)) != len(labels))


# --------------------------------------------------------------------------- seçenekler

_LABEL = re.compile(r"^\s*\(?\s*([A-Ja-j])\s*[)\].:\-]\s*(.*)$", re.DOTALL)
_CONNECTIVES = {"ve", "ile", "yalnız", "yalnızca", "hem", "de", "da"}


def _statement_combination(content: str) -> list[str] | None:
    """"I ve III", "Yalnız II", "I, II ve III" gibi öncül birleşimlerini tanır."""
    tokens = [token for token in re.split(r"[\s,.]+", content) if token]
    refs = [token for token in tokens if token in ROMAN]
    if refs and all(token in ROMAN or casefold_tr(token) in _CONNECTIVES for token in tokens):
        return refs[:6]
    return None
_VISUAL_WORDS = ("grafik", "şekil", "görsel", "resim")


@dataclass(frozen=True)
class ChoiceEvidence:
    choices: list[AnswerChoice]
    duplicate_labels: bool
    missing_labels: bool
    unlabeled: bool
    equivalent_values: bool
    invalid: list[str]


def parse_choices(raw: list[str]) -> ChoiceEvidence:
    choices: list[AnswerChoice] = []
    invalid: list[str] = []
    parsed_values = []
    for order, item in enumerate(raw[:12]):
        text = item.strip()
        match = _LABEL.match(text)
        label = match.group(1).upper() if match else None
        content = (match.group(2).strip() if match else text) or None
        kind, canonical, latex, refs = "empty", None, None, []
        if content:
            folded = casefold_tr(content)
            combination = _statement_combination(content)
            if combination:
                kind = "statement_combination"
                refs = combination
            elif any(word in folded for word in _VISUAL_WORDS) and len(content) < 40:
                kind = "visual"
            else:
                result = parse(content[:400])
                if result.parsed:
                    kind = "number" if exact_value(result.tree) is not None else "expression"
                    canonical, latex = result.canonical(), result.latex()
                    parsed_values.append((label or str(order), result))
                elif result.status == "invalid" and not re.search(r"[a-zçğıöşü]{3,}", folded):
                    kind = "expression"
                    invalid.append(label or str(order))
                else:
                    kind = "text"
        choices.append(AnswerChoice(
            id=f"choice_{order + 1}", order=order, label=label, label_origin="printed" if label else "none",
            content=content[:400] if content else None, kind=kind, canonical=canonical, latex=latex,
            statement_refs=refs,
        ))
    labels = [choice.label for choice in choices if choice.label]
    duplicate = len(set(labels)) != len(labels)
    unlabeled = bool(labels) and len(labels) != len(choices)
    missing = False
    if labels and not duplicate:
        expected = [chr(ord("A") + index) for index in range(len(labels))]
        missing = sorted(labels) != expected
    equivalent = False
    for i, (_, left) in enumerate(parsed_values):
        for _, right in parsed_values[i + 1:]:
            if same_structure(left.tree, right.tree) or (
                exact_value(left.tree) is not None and exact_value(left.tree) == exact_value(right.tree)
            ):
                equivalent = True
    return ChoiceEvidence(choices, duplicate, missing, unlabeled, equivalent, invalid)
