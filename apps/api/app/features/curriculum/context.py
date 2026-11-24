"""Ders üretimi için belirlenimci, sınırlı eğitim bağlamı seçimi (TA-006, TA-007).

Girdi: öğrencinin beyan ettiği veya profildeki bağlam (sınıf, öğrenci/mezun durumu, sınav hedefleri, okul
izleği) ve sunucunun kaynaktan çıkardığı konu eşlemesi (``topics.map_question``). Sağlayıcı çağrısı, gömme veya
Firestore okuması yoktur. Sonuç:

- ``payload``: yalnız çözümleme ``resolved`` ve eşleşen kazanım varsa; en çok ``MAX_OUTCOMES`` kazanım,
  denetimli geri getirmeden (``knowledge.retrieval``, üretim kipi) gelen bütün kayıtlar ve yetkili onaylı yöntem
  politikaları. Bayt sınırı ``MAX_PAYLOAD_BYTES``; sığmayan bilgi kaydı kırpılmaz, dışarıda bırakılır.
- ``provenance``: dersle saklanan, bağlamı yeniden kurmaya yeten sürüm ve seçim kaydı.
- ``policy_set`` / ``mapping`` / ``matched``: sunucu yöntem ve müfredat denetimleri için aynı karar.

Taslak bilgi girdileri ve taslak politikalar isteme girmez; yalnız sayıları/nedenleri köken kaydına yazılır.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from ..education.base import Subject
from ..education.curriculum_v2 import (
    ContextOutcome,
    CurriculumContextPayload,
    CurriculumResolution,
    EducationalProvenance,
    ExcludedKnowledge,
)
from ..knowledge import registry as knowledge_registry
from ..knowledge import retrieval
from ..knowledge.capabilities import capability_check
from . import methods, registry_v2, topics

MAX_OUTCOMES = 4
MAX_PAYLOAD_BYTES = 2600
AUTHORITY_TR = ("Resmî öğretim programı kodu ve başlıkları sınıf düzeyini gösterir. Bilgi girdileri yetkili "
                "öğretmen onaylıdır; koşul ve istisnaları dışında genelleme yapılmaz. Bu bağlam doğrulama veya onay "
                "kararı değildir.")
EXAMS = {"lgs": ("LGS",), "tyt": ("TYT",), "ayt": ("AYT",), "yks": ("TYT", "AYT")}


@dataclass(frozen=True)
class SelectedContext:
    payload: CurriculumContextPayload | None
    provenance: EducationalProvenance
    outcome_ids: tuple[str, ...]
    program_id: str | None
    resolution: CurriculumResolution | None = None
    mapping: topics.TopicMapping | None = None
    policy_set: methods.PolicySet | None = None
    matched: tuple = ()


def _exam_token(token: str) -> tuple[str, ...]:
    for key, exams in EXAMS.items():
        if token == key or (token.startswith(key) and topics.SUFFIX.fullmatch(token[len(key):])):
            return exams
    return ()


def exam_goals(value: str | None) -> list[str]:
    """Serbest metinden sınav hedefleri, sırayla ve tekrarsız. Türkçe ekler tanınır ("LGS'ye", "YKS'ye").
    "YKS" iki oturumu (TYT ve AYT) birlikte kapsar. Tanınmayan metin boş liste verir; tahmin yapılmaz."""
    found: list[str] = []
    for token in topics.normalize(value or ""):
        for exam in _exam_token(token.replace("-", "")):
            if exam not in found:
                found.append(exam)
    return found


def canonical_exam(value: str | None) -> str | None:
    """Geriye dönük: tek hedef varsa o; birden çok hedefte None (bkz. ``exam_goals``)."""
    goals = exam_goals(value)
    return goals[0] if len(goals) == 1 else None


def declared_graduate(value: str | None) -> bool:
    """Öğrencinin kendi beyanında "mezunum/mezun oldum". Görselden çıkarılmaz."""
    for token in topics.normalize(value or ""):
        if token.startswith("mezun"):
            rest = token[len("mezun"):]
            if rest in {"", "um", "uz", "uyum", "uyuz"} or topics.SUFFIX.fullmatch(rest):
                return True
    return False


def _payload_bytes(payload: CurriculumContextPayload) -> int:
    return len(json.dumps(payload.model_dump(exclude_none=True, exclude_defaults=True), ensure_ascii=False,
                          separators=(",", ":")).encode("utf-8"))


def _code_order(outcome) -> list[int]:
    return [int(part) for part in outcome.official_code.split(".") if part.isdigit()]


def match_outcomes(curriculum, program_id: str, grade: int, mapping: topics.TopicMapping) -> list[tuple[object, str]]:
    """Önce kazanımın kendi konu anahtarı/takma adı (``topic_key``/``alias``), sonra taksonomi deseni."""
    if not mapping.keys:
        return []
    taxonomy = topics.default_taxonomy()
    rows = []
    for outcome in curriculum.outcomes_for(program_id, grade):
        how = None
        for key in mapping.keys:
            if outcome.topic_key == key:
                how = "topic_key"
                break
            if key in outcome.aliases:
                how = how or "alias"
            elif how is None and key in taxonomy.topics and topics.outcome_matches(taxonomy.topics[key], outcome,
                                                                                    curriculum.units):
                how = "taxonomy"
        if how:
            rows.append((outcome, how))
    rank = {"topic_key": 0, "alias": 1, "taxonomy": 2}
    rows.sort(key=lambda pair: (rank[pair[1]], _code_order(pair[0])))
    return rows


def _capabilities(entries) -> list[str]:
    names = set()
    for entry in entries:
        names.update(capability_check(entry).verifiers)
    return sorted(names)[:16]


def select(analysis, subject: Subject, grade: int | None, *, today: date, learner_status: str | None = None,
           exam_goal: str | None = None, academic_year: str | None = None, track: str | None = None,
           curriculum: registry_v2.CurriculumRegistryV2 | None = None,
           knowledge: knowledge_registry.KnowledgeRegistry | None = None,
           budget: retrieval.Budget = retrieval.DEFAULT_BUDGET) -> SelectedContext:
    curriculum = curriculum or registry_v2.default_registry()
    knowledge = knowledge or knowledge_registry.default_knowledge()
    goals = exam_goals(exam_goal)
    if learner_status is None and declared_graduate(exam_goal):
        learner_status = "graduate"
    resolution = registry_v2.resolve(curriculum, subject, grade, today=today, academic_year=academic_year,
                                     learner_status=learner_status, exams=goals, track=track)
    mapping = topics.map_question(analysis, subject)
    policy_set = methods.select(resolution, mapping, subject, grade, curriculum=curriculum) if grade else None
    topic = mapping.certain or (mapping.keys[0] if mapping.status == "single" else None)
    base = {"curriculum_version": curriculum.version, "knowledge_version": knowledge.version, "resolution": resolution,
            "topic_key": topic, "selection_mode": "deterministic_production", "topic_mapping": mapping.status,
            "topic_candidates": list(mapping.keys)[:4],
            "method_policy_ids": policy_set.ids if policy_set else [],
            "inactive_method_policies": len(policy_set.inactive) if policy_set else 0}
    extra = {"resolution": resolution, "mapping": mapping, "policy_set": policy_set}
    empty = {"match": "none", "payload_bytes": 0, "included_in_prompt": False}
    if resolution.status != "resolved" or not mapping.keys or resolution.grade is None:
        return SelectedContext(None, EducationalProvenance(**base, **empty, excluded_draft_knowledge=0), (), None,
                               **extra)
    program_id = resolution.program_ids[0]
    program = curriculum.programs[program_id]
    matched = match_outcomes(curriculum, program_id, resolution.grade, mapping)
    chosen = matched[:MAX_OUTCOMES]
    outcome_ids = [outcome.id for outcome, _ in chosen]
    unit_ids = sorted({ref for outcome, _ in chosen for ref in (outcome.unit_id, outcome.topic_id) if ref})
    found = retrieval.retrieve(knowledge, subject, topic_keys=sorted(topics.knowledge_topics(mapping.keys)),
                               outcome_ids=outcome_ids, unit_ids=unit_ids,
                               query=getattr(analysis, "question_text", "") or "", budget=budget)
    not_eligible = sum(1 for item in found.excluded if item.reason == "not_runtime_eligible")
    extra["matched"] = tuple(matched)
    if not chosen:
        return SelectedContext(None, EducationalProvenance(**base, **empty, excluded_draft_knowledge=not_eligible,
                                                           excluded_knowledge=list(found.excluded)[:32]),
                               (), program_id, **extra)
    payload = CurriculumContextPayload(
        program=program.label, framework=program.framework, academic_year=resolution.academic_year,
        grade=resolution.grade,
        outcomes=[ContextOutcome(code=outcome.official_code, unit_tr=curriculum.units[outcome.unit_id].title_tr,
                                 topic_tr=curriculum.units[outcome.topic_id].title_tr if outcome.topic_id else None,
                                 description_tr=outcome.description_tr if outcome.description_review == "approved" else None)
                  for outcome, _ in chosen],
        knowledge=retrieval.as_context(found), methods=methods.context_methods(policy_set), authority_tr=AUTHORITY_TR,
    )
    excluded = list(found.excluded)
    # Toplam bütçe: önce bilgi kaydı bütünüyle çıkarılır, sonra kazanım; kayıt içi kırpma yapılmaz.
    while _payload_bytes(payload) > MAX_PAYLOAD_BYTES and (payload.knowledge or len(payload.outcomes) > 1):
        if payload.knowledge:
            dropped = payload.knowledge[-1]
            excluded.append(ExcludedKnowledge(id=dropped.id, reason="exceeds_total_budget"))
            payload = payload.model_copy(update={"knowledge": payload.knowledge[:-1]})
        else:
            payload = payload.model_copy(update={"outcomes": payload.outcomes[:-1]})
    kept = {item.code for item in payload.outcomes}
    ids = tuple(outcome.id for outcome, _ in chosen if outcome.official_code in kept)
    knowledge_ids = [item.id for item in payload.knowledge]
    match_kind = chosen[0][1]
    provenance = EducationalProvenance(
        **base, match=match_kind, outcome_ids=list(ids),
        knowledge_ids=knowledge_ids, excluded_draft_knowledge=not_eligible, payload_bytes=_payload_bytes(payload),
        included_in_prompt=True,
        knowledge_refs=[ref for ref in found.refs if ref.id in knowledge_ids],
        excluded_knowledge=excluded[:32], compacted_knowledge=[ref for ref in found.compacted if ref in knowledge_ids],
        verification_capabilities=_capabilities(knowledge.entries[ref] for ref in knowledge_ids),
    )
    return SelectedContext(payload, provenance, ids, program_id, **extra)


def with_transmission(provenance: EducationalProvenance, levels: list[str | None]) -> EducationalProvenance:
    """Sağlayıcının bildirdiği gerçek gönderim düzeyini ders oluşturulurken bir kez ekler (sonradan değişmez)."""
    known = [level for level in levels if level is not None]
    if not known or len(known) != len(levels):
        return provenance
    state = "normal" if set(known) == {"normal"} else ("emergency" if set(known) == {"emergency"} else "mixed")
    sent = provenance.knowledge_ids if state == "normal" and provenance.included_in_prompt else []
    return provenance.model_copy(update={"transmission": state, "transmitted_knowledge_ids": list(sent)})
