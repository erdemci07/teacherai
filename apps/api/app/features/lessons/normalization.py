import re
import unicodedata
from typing import Any

from pydantic import ValidationError

from apps.api.app.features.mathai.parser import MathParseError, equation, expression

from .exceptions import InvalidLessonPlanError
from .schemas import LessonDraft, LessonDraftResponse


_TURKISH_ASCII = str.maketrans(
    {
        "ç": "c",
        "Ç": "c",
        "ğ": "g",
        "Ğ": "g",
        "ı": "i",
        "I": "i",
        "İ": "i",
        "ö": "o",
        "Ö": "o",
        "ş": "s",
        "Ş": "s",
        "ü": "u",
        "Ü": "u",
    }
)
_OPTIONAL_TEXT_FIELDS = {"prerequisite_reminder", "key_rule", "common_mistake", "mistake_type", "shortcut", "teacher_tip", "visual_reference"}
_REQUIRED_CONTENT_TEXT_FIELDS = {"question_understanding", "strategy", "final_answer", "takeaway"}
_REQUIRED_STEP_TEXT_FIELDS = {"title", "explanation"}
_PLACEHOLDER_PATTERNS = (
    re.compile(r"^\s*[\{\[\(<]*\s*metin\s+buraya\s*[\}\]\)>]*\s*\.?\s*$", re.IGNORECASE),
    re.compile(r"^\s*[\{\[\(<]*\s*(?:placeholder|todo|tbd|insert_text)\s*[\}\]\)>]*\s*\.?\s*$", re.IGNORECASE),
    re.compile(r"\bburaya\b.{0,40}\byaz\b", re.IGNORECASE),
)


def normalize_lesson_draft_response(response: LessonDraftResponse) -> LessonDraft:
    data = _trim(response.model_dump())
    data["concept_id"] = _normalize_prefixed_slug(data.get("concept_id"), "concept")
    content = data.get("content", {})
    content["strategy_id"] = _normalize_prefixed_slug(content.get("strategy_id"), "strategy")
    content["steps"] = [_normalize_step(step, index) for index, step in enumerate(content.get("steps", []), start=1)]
    _sanitize_student_facing_text(data)
    if not content.get("final_answer_expressions"):
        extracted = _extract_final_answer_expression(content.get("final_answer"))
        if extracted:
            content["final_answer_expressions"] = [extracted]
    try:
        return LessonDraft.model_validate(data)
    except (ValidationError, ValueError) as exc:
        raise InvalidLessonPlanError from exc


def _trim(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return [_trim(item) for item in value]
    if isinstance(value, dict):
        return {key: _trim(item) for key, item in value.items()}
    return value


def _normalize_step(step: dict[str, Any], index: int) -> dict[str, Any]:
    normalized = dict(step)
    normalized["id"] = f"step_{index}"
    return normalized


def _normalize_prefixed_slug(value: object, prefix: str) -> object:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if re.fullmatch(rf"{prefix}_[a-z0-9_]+", text):
        return text
    base = re.sub(rf"^{prefix}[_\s-]*", "", text, flags=re.IGNORECASE)
    slug = _slugify(base)
    return f"{prefix}_{slug}" if slug else value


def _sanitize_student_facing_text(data: dict[str, Any]) -> None:
    objectives = data.get("learning_objectives", [])
    if isinstance(objectives, list):
        for objective in objectives:
            _reject_placeholder_contamination(objective)

    content = data.get("content", {})
    if not isinstance(content, dict):
        return
    for field in _REQUIRED_CONTENT_TEXT_FIELDS:
        _reject_placeholder_contamination(content.get(field))
    for field in _OPTIONAL_TEXT_FIELDS:
        value = content.get(field)
        if _is_primary_placeholder(value):
            content[field] = None
        else:
            _reject_placeholder_contamination(value)

    known_values = content.get("known_values", [])
    if isinstance(known_values, list):
        content["known_values"] = [value for value in known_values if not _is_primary_placeholder(value)]
        for value in content["known_values"]:
            _reject_placeholder_contamination(value)

    for step in content.get("steps", []):
        if not isinstance(step, dict):
            continue
        for field in _REQUIRED_STEP_TEXT_FIELDS:
            _reject_placeholder_contamination(step.get(field))
        value = step.get("visual_reference")
        if _is_primary_placeholder(value):
            step["visual_reference"] = None
        else:
            _reject_placeholder_contamination(value)


def _reject_placeholder_contamination(value: object) -> None:
    if isinstance(value, str) and _contains_placeholder_artifact(value):
        raise InvalidLessonPlanError


def _is_primary_placeholder(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    return any(pattern.search(text) for pattern in _PLACEHOLDER_PATTERNS)


def _contains_placeholder_artifact(value: str) -> bool:
    text = value.strip()
    if _is_primary_placeholder(text):
        return True
    return bool(re.search(r"[\{\[\(<]\s*metin\s+buraya\s*[\}\]\)>]|<\s*placeholder\s*>|\b(?:TODO|TBD|INSERT_TEXT|PLACEHOLDER)\b|\bburaya\b.{0,40}\byaz\b", text, re.IGNORECASE))


def _slugify(value: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", value.translate(_TURKISH_ASCII)).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")
    return re.sub(r"_+", "_", slug)


def _extract_exact_equation(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*\s*=\s*-?\d+(?:\.\d+)?", text):
        return None
    try:
        equation(text)
    except MathParseError:
        return None
    return text


def _extract_final_answer_expression(value: object) -> dict[str, str] | None:
    text = _strip_answer_choice_prefix(value)
    if text is None:
        return None
    equation_text = _extract_exact_equation(text)
    if equation_text:
        return {"type": "equation", "latex": equation_text}
    numeric_text = _extract_exact_numeric_expression(text)
    if numeric_text:
        return {"type": "expression", "latex": numeric_text}
    return None


def _strip_answer_choice_prefix(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    match = re.fullmatch(r"[A-Ea-e]\s*[\)\].:\-]\s*(.+)", text)
    if match:
        return match.group(1).strip()
    return text


def _extract_exact_numeric_expression(value: str) -> str | None:
    text = value.strip().replace(",", ".")
    if not re.fullmatch(r"-?(?:\d+(?:\.\d+)?|\d+\s*/\s*\d+|\\frac\{\d+\}\{\d+\})", text):
        return None
    try:
        parsed = expression(text)
    except MathParseError:
        return None
    if parsed.free_symbols:
        return None
    return text
