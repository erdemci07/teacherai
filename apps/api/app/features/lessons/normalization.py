import re
import unicodedata
from typing import Any

from pydantic import ValidationError

from apps.api.app.features.mathai.parser import MathParseError, equation

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


def normalize_lesson_draft_response(response: LessonDraftResponse) -> LessonDraft:
    data = _trim(response.model_dump())
    data["concept_id"] = _normalize_prefixed_slug(data.get("concept_id"), "concept")
    content = data.get("content", {})
    content["strategy_id"] = _normalize_prefixed_slug(content.get("strategy_id"), "strategy")
    content["steps"] = [_normalize_step(step, index) for index, step in enumerate(content.get("steps", []), start=1)]
    if not content.get("final_answer_expressions"):
        extracted = _extract_exact_equation(content.get("final_answer"))
        if extracted:
            content["final_answer_expressions"] = [{"type": "equation", "latex": extracted}]
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
