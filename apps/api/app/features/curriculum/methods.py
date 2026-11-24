"""MethodPolicy v2 çalışma zamanı (TA-007). Saf Python; sağlayıcı çağırmaz. v1 ``method_check`` ve
``curriculum_check``'in ders akışındaki yerini alır; aynı adım kanıtı sınıflandırmasını (``registry``) kullanır.

Politika seçimi: alan + çözümlenmiş program + sınıf + konu. Kaynaklar: v1 kayıttan çağrı anında taşınan
politikalar ve katalogdaki v2 politikaları. Bir politika yalnız şu durumda **etkindir**:

1. ``status == "approved"``;
2. ``approved_by`` proje sahibinin inceleyen kaydında ``pedagogical`` aşaması, bu alan ve ``teacher`` rolü için
   ``approved_on`` tarihinde yetkili;
3. ``approval_digest`` politikanın bugünkü içerik özetine eşit (bayat onay etkin olmaz).

Belirsizlik kuralları:

- Program belirsizse (birden çok aday) yasak işlem yalnız *bütün* adaylarda yasaksa ``failed`` üretir.
- Konu yalnız yapısal kanıtla kesindir. Sözcük eşlemesinde konu politikaları ``passed`` üretmez; yasak işlem
  yalnız bütün aday konularda yasaksa uygulanır. "genel" politikalar her durumda geçerlidir.
- Öğrenci açıkça ileri yöntem isterse yasak işlem ``failed`` değil ``partially_checked``
  (``advanced_method_requested``) olur; düzeltme turu tetiklenmez.

Bilimsel geçersizlik bu denetimin konusu değildir (MathAI/FKB); burada yalnız öğretimsel uygunluk değerlendirilir.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from ..education.base import Subject
from ..education.curriculum import MethodEvidence, PolicyCheck
from ..education.curriculum_v2 import ContextMethod, CurriculumResolution, MethodPolicyV2
from ..integrity import expression as tree
from ..knowledge import reviewers as reviewer_registry
from . import registry as legacy
from . import registry_v2, topics

DIGEST_FIELDS = ("subject", "topic", "framework", "program_ids", "grades", "prerequisites", "applicable_when",
                 "allowed_operations", "forbidden_operations", "unsuitable_when", "preferred_representations",
                 "alternatives", "outcome_ids")


def policy_digest(policy: MethodPolicyV2) -> str:
    """Onaylanan içeriğin özeti: durum ve onay alanları hariç."""
    data = policy.model_dump(mode="json", include=set(DIGEST_FIELDS))
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def all_policies(curriculum: registry_v2.CurriculumRegistryV2 | None = None) -> list[MethodPolicyV2]:
    """v1 politikaları çağrı anında taşınır (v1 kayıt değişirse v2 görünümü de değişir) + katalog politikaları."""
    curriculum = curriculum or registry_v2.default_registry()
    return [*registry_v2.migrate_v1_policies(legacy.default_registry()), *curriculum.catalog.policies]


def inactive_reason(policy: MethodPolicyV2, reviewers) -> str | None:
    if policy.status != "approved":
        return "draft"
    if policy.approved_on is None or policy.approval_digest is None:
        return "approval_incomplete"
    if not reviewer_registry.authorized(reviewers, policy.approved_by, "pedagogical", policy.subject, "teacher",
                                        policy.approved_on):
        return "reviewer_not_authorized"
    if policy.approval_digest != policy_digest(policy):
        return "stale_approval"
    return None


def _subject_matches(policy: MethodPolicyV2, subject: Subject) -> bool:
    group = {Subject.MATHEMATICS, Subject.GEOMETRY}
    return policy.subject == subject or (policy.subject in group and subject in group)


def applicable(policies, *, subject: Subject, program_id: str | None, grade: int, topic_keys) -> list[MethodPolicyV2]:
    wanted = {"genel", *topic_keys}
    return [p for p in policies if _subject_matches(p, subject) and grade in p.grades and p.topic in wanted
            and (not p.program_ids or (program_id is not None and program_id in p.program_ids))]


@dataclass(frozen=True)
class PolicySet:
    programs: tuple[str | None, ...]
    active: tuple[MethodPolicyV2, ...]
    inactive: tuple[tuple[str, str], ...]
    topic: str | None
    topic_candidates: tuple[str, ...]
    forbidden: dict[str, str]
    allowed: frozenset[str]
    topical: bool

    @property
    def ids(self) -> list[str]:
        return [p.id for p in self.active][:8]


def program_candidates(resolution: CurriculumResolution | None) -> tuple[str | None, ...]:
    if resolution is None:
        return (None,)
    if resolution.status == "resolved":
        return (resolution.program_ids[0],)
    return tuple(resolution.candidate_program_ids) or (None,)


def select(resolution: CurriculumResolution | None, mapping: topics.TopicMapping, subject: Subject, grade: int, *,
           curriculum=None, reviewers=None) -> PolicySet:
    reviewers = reviewer_registry.default_reviewers() if reviewers is None else reviewers
    policies = all_policies(curriculum)
    certain = mapping.certain
    candidates = mapping.keys
    programs = program_candidates(resolution)
    per_program, inactive, active_all = [], {}, {}
    for program_id in programs:
        rows = applicable(policies, subject=subject, program_id=program_id, grade=grade, topic_keys=candidates)
        active = []
        for policy in rows:
            reason = inactive_reason(policy, reviewers)
            if reason is None:
                active.append(policy)
                active_all[policy.id] = policy
            else:
                inactive[policy.id] = reason
        per_program.append(active)

    def forbidden_of(group, topic):
        return {item.operation: item.reason for p in group if p.topic == topic for item in p.forbidden_operations}

    forbidden_sets = []
    for active in per_program:
        found = forbidden_of(active, "genel")
        if certain:
            found.update(forbidden_of(active, certain))
        elif candidates:  # konu belirsiz: yalnız bütün aday konularda yasak olan
            common = None
            for key in candidates:
                ops = forbidden_of(active, key)
                common = dict(ops) if common is None else {op: why for op, why in common.items() if op in ops}
            found.update(common or {})
        forbidden_sets.append(found)
    forbidden = dict(forbidden_sets[0]) if forbidden_sets else {}
    for other in forbidden_sets[1:]:  # program belirsiz: bütün adaylarda yasak olan
        forbidden = {op: why for op, why in forbidden.items() if op in other}
    topical_groups = [[p for p in active if certain and p.topic == certain] for active in per_program]
    topical = bool(topical_groups) and all(topical_groups)
    allowed = None
    for group in topical_groups:
        ops = {op for p in group for op in p.allowed_operations}
        allowed = ops if allowed is None else allowed & ops
    return PolicySet(programs, tuple(active_all.values()), tuple(sorted(inactive.items())), certain, candidates,
                     forbidden, frozenset(allowed or ()), topical)


def rejected_constructs(text: str) -> set[str]:
    """Olumsuzlanmış tümcelerde geçen konu sözcükleri: "düşünüldü, kullanılmadı"."""
    return {name for clause in legacy.CLAUSE.split(text or "") if legacy.NEGATION.search(clause)
            for name, pattern in legacy.PROSE.items() if pattern.search(clause)}


def evidence(plan, verification) -> list[MethodEvidence]:
    rows = legacy.step_operations(plan, verification)
    steps = {step.id: step for step in plan.content.steps}
    out = []
    for step_id, operations, weak, classified in rows:
        step = steps[step_id]
        prose = f"{step.title or ''}. {step.explanation or ''}"
        unparsed = sum(1 for item in step.expressions if not tree.parse(item.latex, constructs=True).parsed)
        out.append(MethodEvidence(step=step_id, used=operations[:16], mentioned=sorted(weak)[:8],
                                  rejected=sorted(rejected_constructs(prose) - set(operations))[:8],
                                  identifiable=classified, unparsed=unparsed))
    return out[:64]


def method_check(plan, verification, grade: int | None, policy_set: PolicySet | None, *,
                 advanced_requested: bool = False) -> PolicyCheck:
    if grade is None or policy_set is None:
        return PolicyCheck(dimension="method", state="not_checked", reason="grade_unknown")
    base = {"grade": grade, "topic": policy_set.topic, "topic_candidates": list(policy_set.topic_candidates),
            "inactive_policy_ids": [pid for pid, _ in policy_set.inactive][:16]}
    if not policy_set.active:
        return PolicyCheck(dimension="method", state="not_checked", reason="no_approved_policy", **base)
    items = evidence(plan, verification)
    ids = policy_set.ids
    forbidden = policy_set.forbidden
    for item in items:
        hit = next((op for op in item.used if op in forbidden), None)
        if hit:  # yalnız güçlü kanıt
            if advanced_requested:
                return PolicyCheck(dimension="method", state="partially_checked", reason="advanced_method_requested",
                                   step=item.step, operations=[hit], policy_ids=ids, evidence=items, **base)
            return PolicyCheck(dimension="method", state="failed", reason="forbidden_operation", step=item.step,
                               operations=[hit], policy_ids=ids, detail=forbidden[hit][:400], evidence=items, **base)
    used = sorted({op for item in items for op in item.used})
    for item in items:
        mention = next((op for op in item.mentioned if op in forbidden), None)
        if mention:  # zayıf kanıt: yasak sayılmaz, doğrulanmış da sayılmaz
            return PolicyCheck(dimension="method", state="partially_checked", reason="prose_mention_unverified",
                               step=item.step, operations=[mention], policy_ids=ids, evidence=items, **base)
    if len(policy_set.programs) > 1:
        reason = "program_ambiguous"
    elif policy_set.topic is None:
        reason = "topic_uncertain" if policy_set.topic_candidates else "topic_policy_missing"
    elif not policy_set.topical:
        reason = "topic_policy_missing"
    elif all(item.identifiable and not item.unparsed for item in items) and set(used) <= policy_set.allowed:
        return PolicyCheck(dimension="method", state="passed", reason="allowed_operations_only", operations=used,
                           policy_ids=ids, evidence=items, **base)
    else:
        reason = "no_forbidden_operation"
    return PolicyCheck(dimension="method", state="partially_checked", reason=reason, operations=used,
                       policy_ids=ids, evidence=items, **base)


def correction_feedback(check: PolicyCheck, policy_set: PolicySet) -> str:
    """Hedefli düzeltme istemi: yalnız izinli işlemler ve yasaklanan adım verilir."""
    allowed = sorted(policy_set.allowed)
    return (f"Yöntem denetimi: {check.grade}. sınıf düzeyine uygun olmayan işlem ({', '.join(check.operations)}) "
            f"{check.step} adımında kullanıldı. Bu adımı ve çözümü yalnızca şu işlemlerle yeniden yaz: "
            f"{', '.join(allowed) or 'temel cebirsel işlemler'}.")[:1200]


def context_methods(policy_set: PolicySet | None) -> list[ContextMethod]:
    if policy_set is None:
        return []
    return [ContextMethod(policy_id=p.id, allowed_operations=list(p.allowed_operations)[:64],
                          forbidden_operations=[item.operation for item in p.forbidden_operations][:32],
                          preferred_representations=list(p.preferred_representations)[:16])
            for p in policy_set.active][:4]


def curriculum_check(resolution: CurriculumResolution | None, mapping: topics.TopicMapping, grade: int | None,
                     matched: list[tuple[object, str]]) -> PolicyCheck:
    """Program uygunluğu. ``passed`` yalnız: çözümlenmiş program, yapısal kesin konu ve kazanımın kendi konu
    anahtarı/takma adıyla eşleşme. Taksonomi deseni (AI taslağı) veya sözcük eşlemesi ``partially_checked`` kalır.
    Konu programda bulunamazsa ``failed`` değil ``partially_checked`` (eşleme incelenmedi)."""
    if grade is None and (resolution is None or resolution.learner_status != "graduate"):
        return PolicyCheck(dimension="curriculum", state="not_checked", reason="grade_unknown")
    base = {"grade": grade, "topic": mapping.certain, "topic_candidates": list(mapping.keys)}
    if resolution is None or resolution.status != "resolved":
        reason = resolution.reasons[0] if resolution is not None and resolution.reasons else "program_unresolved"
        return PolicyCheck(dimension="curriculum", state="not_checked", reason=reason, **base)
    if mapping.status == "none":
        return PolicyCheck(dimension="curriculum", state="not_checked", reason="topic_unresolved", **base)
    ids = [outcome.id for outcome, _ in matched][:32]
    if not matched:
        return PolicyCheck(dimension="curriculum", state="partially_checked", reason="topic_not_found_in_program", **base)
    exact = [outcome.id for outcome, how in matched if how in {"topic_key", "alias"}]
    if mapping.status == "structural" and exact:
        return PolicyCheck(dimension="curriculum", state="passed", reason="program_outcome_matched",
                           outcome_ids=exact[:32], **base)
    reason = "topic_lexical_only" if mapping.status != "structural" else "taxonomy_mapping_unreviewed"
    return PolicyCheck(dimension="curriculum", state="partially_checked", reason=reason, outcome_ids=ids, **base)
