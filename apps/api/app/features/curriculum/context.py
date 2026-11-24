"""Ders üretimi için belirlenimci, sınırlı eğitim bağlamı seçimi (TA-006).

Girdi: öğrencinin beyan ettiği veya profildeki bağlam (sınıf, öğrenci/mezun durumu, sınav hedefi) ve
sunucunun kaynak ifadelerden çıkardığı yapısal konu anahtarı (``registry.topic_of``). Sağlayıcı çağrısı, gömme
veya Firestore okuması yoktur. Sonuç:

- ``payload``: yalnız çözümleme ``resolved`` ve eşleşen kazanım varsa; en çok ``MAX_OUTCOMES`` kazanım ve
  çalışma zamanına uygun (onaylı, kaynaklı, hak durumu açık) bilgi girdisi. Bayt sınırı ``MAX_PAYLOAD_BYTES``.
- ``provenance``: dersle saklanan, bağlamı yeniden kurmaya yeten sürüm ve seçim kaydı.

Taslak bilgi girdileri isteme girmez; yalnız sayıları köken kaydına yazılır.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from ..education.base import Subject
from ..education.curriculum_v2 import (
    ContextKnowledge,
    ContextOutcome,
    CurriculumContextPayload,
    EducationalProvenance,
)
from ..knowledge import registry as knowledge_registry
from . import registry as legacy
from . import registry_v2

MAX_OUTCOMES = 4
MAX_PAYLOAD_BYTES = 1500
AUTHORITY_TR = ("Resmî öğretim programı kodu ve başlıkları. Sınıf düzeyini gösterir; yöntem onayı, bilimsel "
                "doğrulama veya öğretmen onayı değildir.")
EXAMS = {"lgs": "LGS", "tyt": "TYT", "ayt": "AYT"}


@dataclass(frozen=True)
class SelectedContext:
    payload: CurriculumContextPayload | None
    provenance: EducationalProvenance
    outcome_ids: tuple[str, ...]
    program_id: str | None


def canonical_exam(value: str | None) -> str | None:
    """Profildeki serbest sınav hedefinden LGS/TYT/AYT. "YKS" tek başına TYT mi AYT mi belli olmadığından None."""
    if not value:
        return None
    words = " ".join(value.replace("İ", "i").casefold().replace("-", " ").split()).split()
    found = {EXAMS[word] for word in words if word in EXAMS}
    return found.pop() if len(found) == 1 else None


def _matches(outcome, topic: str) -> str | None:
    if outcome.topic_key == topic:
        return "topic_key"
    if topic in outcome.aliases:
        return "alias"
    return None


def _payload_bytes(payload: CurriculumContextPayload) -> int:
    return len(json.dumps(payload.model_dump(exclude_none=True), ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def select(analysis, subject: Subject, grade: int | None, *, today: date, learner_status: str | None = None,
           exam_goal: str | None = None, academic_year: str | None = None,
           curriculum: registry_v2.CurriculumRegistryV2 | None = None,
           knowledge: knowledge_registry.KnowledgeRegistry | None = None) -> SelectedContext:
    curriculum = curriculum or registry_v2.default_registry()
    knowledge = knowledge or knowledge_registry.default_knowledge()
    exam = canonical_exam(exam_goal)
    resolution = registry_v2.resolve(curriculum, subject, grade, today=today, academic_year=academic_year,
                                     learner_status=learner_status, exam=exam)
    topic = legacy.topic_of(analysis)
    base = {"curriculum_version": curriculum.version, "knowledge_version": knowledge.version, "resolution": resolution,
            "topic_key": topic}
    if resolution.status != "resolved" or topic is None or resolution.grade is None:
        return SelectedContext(None, EducationalProvenance(**base, match="none", excluded_draft_knowledge=0,
                                                           payload_bytes=0, included_in_prompt=False), (), None)
    program_id = resolution.program_ids[0]
    program = curriculum.programs[program_id]
    matched = [(outcome, how) for outcome in curriculum.outcomes_for(program_id, resolution.grade)
               if (how := _matches(outcome, topic))]
    matched.sort(key=lambda pair: [int(part) for part in pair[0].official_code.split(".") if part.isdigit()])
    matched = matched[:MAX_OUTCOMES]
    outcome_ids = {outcome.id for outcome, _ in matched}
    eligible = knowledge_registry.select(knowledge, subject, topic_keys={topic}, outcome_ids=outcome_ids)
    drafts = knowledge_registry.select(knowledge, subject, topic_keys={topic}, outcome_ids=outcome_ids,
                                       include_drafts=True, limit=1000)
    excluded = len({item.id for item in drafts} - {item.id for item in eligible})
    match = "topic_key" if any(how == "topic_key" for _, how in matched) else ("alias" if matched else "none")
    if not matched:
        return SelectedContext(None, EducationalProvenance(**base, match="none", excluded_draft_knowledge=excluded,
                                                           payload_bytes=0, included_in_prompt=False), (), program_id)
    payload = CurriculumContextPayload(
        program=program.label, framework=program.framework, academic_year=resolution.academic_year, grade=resolution.grade,
        outcomes=[ContextOutcome(code=outcome.official_code, unit_tr=curriculum.units[outcome.unit_id].title_tr,
                                 topic_tr=curriculum.units[outcome.topic_id].title_tr if outcome.topic_id else None,
                                 description_tr=outcome.description_tr if outcome.description_review == "approved" else None)
                  for outcome, _ in matched],
        knowledge=[ContextKnowledge(id=item.id, title_tr=item.title_tr, statement_tr=item.statement_tr,
                                    conditions_tr=item.conditions_tr[:6]) for item in eligible],
        authority_tr=AUTHORITY_TR,
    )
    while _payload_bytes(payload) > MAX_PAYLOAD_BYTES and (payload.knowledge or len(payload.outcomes) > 1):
        update = {"knowledge": payload.knowledge[:-1]} if payload.knowledge else {"outcomes": payload.outcomes[:-1]}
        payload = payload.model_copy(update=update)
    kept = {item.code for item in payload.outcomes}
    ids = tuple(outcome.id for outcome, _ in matched if outcome.official_code in kept)
    provenance = EducationalProvenance(**base, match=match, outcome_ids=list(ids),
                                       knowledge_ids=[item.id for item in payload.knowledge],
                                       excluded_draft_knowledge=excluded, payload_bytes=_payload_bytes(payload),
                                       included_in_prompt=True)
    return SelectedContext(payload, provenance, ids, program_id)
