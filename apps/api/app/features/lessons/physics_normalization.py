"""TA-009 §17: sağlayıcının fizik yanıtını kanonik sözleşmeye çevirir. OpenAI ve Anthropic aynı kanonik nesneyi
üretir; geçersiz fiziksel model dersi düşürmez, yalnız model atılır (sunucu modelsiz denetler: ``unsupported``).

Birim ve büyüklük yalnız yerel ayrıştırıcıdan kurulur; kökenler sağlayıcı iddiasıdır ve ``physics.values`` sunucuda
yeniden doğrular.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from pydantic import ValidationError

from ..education.base import Subject
from ..education.science import ScientificProblemModel
from ..reasoning.units import unit_spec
from .exceptions import InvalidLessonPlanError
from .normalization import normalize_lesson_draft_response
from .schemas import LessonDraft, LessonDraftResponse, PhysicsLessonDraftResponse, PhysicsModelResponse


def normalize_physics_lesson_draft_response(response: PhysicsLessonDraftResponse) -> LessonDraft:
    data = response.model_dump()
    physics = data["content"].pop("physics_model", None)
    draft = normalize_lesson_draft_response(LessonDraftResponse.model_validate(data))
    problem = physics_problem(PhysicsModelResponse.model_validate(physics)) if physics else None
    try:
        return draft.model_copy(update={"content": draft.content.model_copy(update={"physics_model": problem})})
    except (ValidationError, ValueError) as exc:  # pragma: no cover - model_copy doğrulamaz
        raise InvalidLessonPlanError from exc


def _magnitude(text: str | None) -> str | None:
    if text is None:
        return None
    cleaned = text.strip().replace(" ", "").replace("−", "-").replace(",", ".")
    try:
        value = Fraction(cleaned)
    except (ValueError, ZeroDivisionError):
        return None
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def physics_problem(model: PhysicsModelResponse) -> ScientificProblemModel | None:
    entity_ids: list[str] = []

    def entity(name: str | None):
        if name and name not in entity_ids:
            entity_ids.append(name)

    for body in model.bodies:
        entity(body.entity)
    for force in model.forces:
        entity(force.on)
        entity(force.by)
    for link in model.strings:
        for name in link.bodies:
            entity(name)
    for phase in model.phases:
        entity(phase.entity)
    for collision in model.collisions:
        for name in collision.bodies:
            entity(name)
    known, unknown = [], []
    for item in model.quantities:
        value: dict[str, Any] = {"id": item.id, "symbol": item.symbol, "kind": item.kind, "original": item.original,
                                 "provenance": item.provenance, "entity": item.entity, "state": item.state,
                                 "representation": item.representation}
        if item.unit:
            value["unit"] = unit_spec(item.unit).model_dump()
        magnitude = _magnitude(item.magnitude)
        if item.magnitude is not None and magnitude is None:
            return None
        (known if magnitude is not None else unknown).append({**value, "magnitude": magnitude})
    physics = model.model_dump(exclude={"quantities"})
    physics["laws"] = [{"law": law.law, "system": law.system} for law in model.laws]
    for phase in physics["phases"]:
        phase["acceleration_basis"] = "provider_proposed" if phase["acceleration_kind"] != "unknown" else None
    if physics["target"] is not None:
        unit = physics["target"].pop("unit")
        physics["target"]["unit"] = unit_spec(unit).model_dump() if unit else None
    for surface in physics["surfaces"]:
        surface["angle_deg"] = _magnitude(surface["angle_deg"]) if surface["angle_deg"] else None
    for force in physics["forces"]:
        force["angle_deg"] = _magnitude(force["angle_deg"]) if force["angle_deg"] else None
    try:
        return ScientificProblemModel.model_validate({
            "subject": Subject.PHYSICS, "entities": [{"id": e, "kind": "body", "provenance": "provider_proposed"}
                                                     for e in entity_ids],
            "known": known, "unknown": unknown, "physics": physics})
    except (ValidationError, ValueError):
        return None
