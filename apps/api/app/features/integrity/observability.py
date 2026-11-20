"""İçerik sızdırmayan bütünlük metrikleri ve hedefli yeniden okuma talimatı (TA-003).

Günlüğe yalnızca karar, kategori, sayı ve neden kodu yazılır; soru metni, ifade veya seçenek yazılmaz.
"""

from __future__ import annotations

import json

from ..education.source import IntegrityReport, SourceUncertainty

_QUESTIONS = {
    "radical_scope": "Where exactly does the radical bar end, and what is inside it?",
    "fraction_scope": "What exactly is in the numerator and what is in the denominator?",
    "exponent_scope": "What is the exponent and which base does it belong to?",
    "sign": "Is there a minus sign, and where exactly is it?",
    "decimal": "Where exactly is the decimal separator?",
    "grouping": "Where exactly do the parentheses or grouping symbols open and close?",
    "subscript": "Is this character a subscript, a superscript or on the baseline?",
    "symbol": "Which symbol is written here?",
    "negation": "Does the question sentence contain a negation such as değildir, olamaz or yanlıştır?",
    "answer_choice": "What exactly are this answer choice's printed label and value?",
    "diagram": "What exactly does this label or measurement on the figure say?",
    "graph": "What exactly does this axis label, scale or point say?",
    "table": "What exactly does this table cell say, in which row and column?",
    "quantity": "What exactly is this quantity, including its sign and decimal position?",
    "unit": "Which unit is written here?",
    "text": "What exactly is written in this part of the question text?",
}


def _location(element: str | None) -> str:
    if not element:
        return "the uncertain part of the question"
    kind, _, key = element.partition(":")
    return {
        "stem": "the question sentence",
        "visual": "the figure, graph or table",
        "expression": f"mathematical expression number {int(key) + 1}" if key.isdigit() else "a mathematical expression",
        "choice": f"answer choice {key}",
        "statement": f"statement {key}",
    }.get(kind, "the uncertain part of the question")


def recheck_prompt_items(items: list[SourceUncertainty]) -> str:
    lines = []
    for number, item in enumerate(items, start=1):
        recognized = json.dumps(item.recognized, ensure_ascii=False) if item.recognized else "(not readable in the first reading)"
        lines.append(
            f"{number}. Location: {_location(item.element)}. First reading of the fragment: {recognized}. "
            f"Check: {_QUESTIONS.get(item.category, _QUESTIONS['text'])}"
        )
    return "Items:\n" + "\n".join(lines)


def integrity_metrics(report: IntegrityReport | None) -> dict:
    if report is None:
        return {}
    categories = sorted({item.category for item in report.uncertainties if item.impact != "noncritical"})
    return {
        "integrity_decision": report.decision,
        "integrity_recovery": report.recovery,
        "integrity_revision": report.revision,
        "integrity_material_count": sum(item.impact != "noncritical" for item in report.uncertainties),
        "integrity_pending_count": len(report.pending()),
        "integrity_local_resolutions": sum(item.resolution == "resolved_locally" for item in report.uncertainties)
        + sum(check.code in {"normalized_notation", "decimal_comma_resolved"} for check in report.checks),
        "integrity_rechecks": report.rechecks_used,
        "integrity_categories": ",".join(categories),
        "integrity_reasons": ",".join(sorted({check.code for check in report.checks}))[:400],
        "integrity_unsupported_expressions": sum(item.status == "unsupported" for item in report.expressions),
        "integrity_intent": report.intent.kind,
        "integrity_answer_strategy": report.intent.answer_strategy,
        "image_advisories": ",".join(report.image),
    }
