"""Bilimsel kaynak ve bilgi kaydı: yükleme, doğrulama, çalışma zamanı uygunluğu ve belirlenimci seçim (TA-006).

Saf Python; sağlayıcı, gömme (embedding) veya vektör veritabanı yoktur. Seçim yalnız kesin kimlik, konu anahtarı
ve kazanım bağıyla yapılır. Taslak, incelenmemiş veya hak durumu kısıtlı girdi çalışma zamanı yetkisi taşımaz;
taslaklar yalnız ``include_drafts=True`` ile çevrimdışı önizlemede görünür.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from ..curriculum import registry_v2
from ..education.base import Subject
from . import reviewers as reviewer_registry
from ..education.knowledge import (
    ContributionPublication,
    ContributionSnapshotFile,
    KnowledgeEntry,
    KnowledgeFile,
    ReviewerAuthorization,
    ReviewerRegistryFile,
    SourceRecord,
    SourceRegistryFile,
    content_digest,
    rights_digest,
)
from .capabilities import CAPABILITIES, capability_check

DATA = Path(__file__).with_name("data")
SCHEMA_VERSION = "1.0.0"
SUBJECT_FILES = ("mathematics", "physics", "chemistry", "biology", "science")
ALLOWED_SUBJECTS = {Subject.MATHEMATICS: {Subject.MATHEMATICS, Subject.GEOMETRY}}


class KnowledgeRegistryError(ValueError):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("Bilgi kaydı geçersiz:\n- " + "\n- ".join(problems[:50]))


@dataclass(frozen=True)
class KnowledgeRegistry:
    sources: dict[str, SourceRecord]
    entries: dict[str, KnowledgeEntry]
    digest: str
    reviewers: tuple[ReviewerAuthorization, ...] = ()
    # TA-008: çevrimdışı üretilen katkı yayın anlık görüntüsü (contribution_id → kayıt). Çalışma zamanı katkı
    # dosyası veya Firestore okumaz; geri çekilen katkı bir sonraki yüklemede uygunluğunu kaybeder.
    publications: dict[str, ContributionPublication] = field(default_factory=dict)

    @property
    def version(self) -> str:
        return f"{SCHEMA_VERSION}+{self.digest[:12]}"


def authorized(reviewers, reviewer: str, stage: str, subject: Subject, role: str, on) -> bool:
    """İnceleyen, proje sahibinin kaydında bu aşama, alan, rol ve tarih için yetkili mi? Tarih yoksa hayır."""
    return reviewer_registry.authorized(reviewers, reviewer, stage, subject, role, on)


def _rights_reasons(entry: KnowledgeEntry, sources: dict[str, SourceRecord], reviewers) -> list[str]:
    rights = entry.rights
    reasons = []
    if rights.source_use == "unresolved":
        reasons.append("rights_unresolved")
    if rights.source_use == "reference_citation":
        # TA-008: yalnız kaynak gösterimi izni, kaynaktan türetilmiş içeriğin sağlayıcıya gönderilmesine yetmez.
        reasons.append("reference_only_not_transmittable")
    if rights.decision == "approved":
        if rights.decision_digest is None:
            reasons.append("rights_decision_incomplete")
        elif rights.decision_digest != rights_digest(entry):
            reasons.append("rights_decision_stale")
    if rights.decision != "approved":
        reasons.append(f"rights_decision:{rights.decision}")
    elif not authorized(reviewers, rights.decided_by, "rights", entry.subject, "project_owner", rights.decided_on):
        reasons.append("rights_decider_not_authorized")
    cited = [sources.get(locator.source_id) for locator in entry.provenance]
    for source in cited:
        if source is None:
            continue
        perms = source.permissions
        # Başvuru izni yalnız özgün anlatımı ve kaynak gösterimini kapsar; kopyalama/uyarlama yetkisi vermez.
        if perms.academic_reference != "allowed" or source.access in {"access_restricted", "not_accessed"}:
            reasons.append(f"rights_restricted:{source.id}")
        if rights.source_use == "licensed_adaptation":
            if perms.ingestion not in {"allowed", "conditional"} or not source.license_verified:
                reasons.append(f"adaptation_not_licensed:{source.id}")
            if rights.commercial_use != "eligible":
                reasons.append(f"commercial_use:{rights.commercial_use}")
        if rights.source_use == "direct_quotation":
            if perms.redistribution not in {"allowed", "conditional"} or not source.license_verified:
                reasons.append(f"quotation_not_licensed:{source.id}")
            if rights.commercial_use != "eligible":
                reasons.append(f"commercial_use:{rights.commercial_use}")
        if rights.source_use in {"licensed_adaptation", "direct_quotation"} and source.license and \
                "NC" in source.license.upper().replace("-", " ").split() and rights.commercial_use == "eligible":
            reasons.append(f"noncommercial_license:{source.id}")
    return reasons


def _contribution_reasons(entry: KnowledgeEntry, publications: dict[str, ContributionPublication]) -> list[str]:
    """Öğretmen katkısından türetilmiş girdi: katkı yayımlanmış, izinli, aynı sürüm ve aynı yazar olmalı."""
    rights = entry.rights
    if rights.contribution_id is None:
        return ["contribution_missing"] if entry.authored_by == "teacher" else []
    publication = publications.get(rights.contribution_id)
    if publication is None:
        return ["contribution_unpublished"]
    reasons = []
    if publication.status != "published":
        reasons.append(f"contribution_{publication.status}")
    if not publication.consent_use:
        reasons.append("contribution_consent_missing")
    if rights.contribution_digest is None or rights.contribution_digest != publication.content_digest:
        reasons.append("contribution_digest_mismatch")
    if entry.authored_by == "teacher" and entry.author_ref != publication.contributor:
        reasons.append("contribution_author_mismatch")
    if publication.subject != entry.subject and not (
            {publication.subject, entry.subject} <= {Subject.MATHEMATICS, Subject.GEOMETRY}):
        reasons.append("contribution_subject_mismatch")
    return reasons


def _independence_reasons(entry: KnowledgeEntry, publications: dict[str, ContributionPublication]) -> list[str]:
    """TA-008: katkı sahibi ve içerik yazarı kendi içeriğine bağımsız bilimsel/öğretimsel onay veremez."""
    parties = {entry.author_ref}
    publication = publications.get(entry.rights.contribution_id or "")
    if publication is not None:
        parties.add(publication.contributor)
    parties.discard(None)
    reasons = []
    for review in entry.reviews:
        if review.decision == "approve" and review.reviewer in parties:
            reasons.append(f"not_independent:{review.stage}")
    if entry.rights.decided_by is not None and entry.rights.decided_by in parties:
        reasons.append("rights_decider_not_independent")
    return reasons


def runtime_eligibility(entry: KnowledgeEntry, sources: dict[str, SourceRecord], reviewers=(),
                        publications: dict[str, ContributionPublication] | None = None) -> list[str]:
    """Boş liste: yetkili çalışma zamanı bağlamına girebilir. Aksi halde engel nedenleri.

    Gerekenler: onaylı durum; onayın proje sahibince yetkilendirilmiş, içeriğin yazarından ve katkı sahibinden
    bağımsız bir öğretmen/uzmandan, aynı sürüm ve aynı içerik özeti için gelmesi (bayat onay geçersiz);
    doğrulanmış kaynak konumu; kaynak kullanım sınıfına uygun haklar ve yetkili proje sahibinin aynı hak kaydı
    için verdiği karar; öğretmen katkısından türetilmişse katkının yayımlanmış, izinli ve aynı sürüm olması.
    """
    publications = publications or {}
    reasons = []
    if entry.status != "approved":
        reasons.append(f"status:{entry.status}")
    else:
        approval = entry.reviews[-1]
        if not authorized(reviewers, approval.reviewer, approval.stage, entry.subject, approval.role, approval.reviewed_on):
            reasons.append("reviewer_not_authorized")
        if approval.content_digest != content_digest(entry):
            reasons.append("stale_approval")
    reasons += _independence_reasons(entry, publications)
    reasons += _contribution_reasons(entry, publications)
    if not entry.provenance and entry.rights.source_use != "teacher_original":
        reasons.append("unsourced")
    for locator in entry.provenance:
        if locator.source_id not in sources:
            reasons.append(f"unknown_source:{locator.source_id}")
        elif locator.verified_on is None:
            reasons.append(f"locator_unverified:{locator.source_id}")
    reasons += _rights_reasons(entry, sources, reviewers)
    return sorted(set(reasons))


def eligibility(registry: "KnowledgeRegistry", entry: KnowledgeEntry) -> list[str]:
    return runtime_eligibility(entry, registry.sources, registry.reviewers, registry.publications)


USES = ("academic_reference", "original_explanation", "licensed_adaptation", "direct_quotation",
        "commercial_redistribution", "teacher_contribution", "provider_transmission", "model_training")


def use_permissions(registry: "KnowledgeRegistry", entry: KnowledgeEntry) -> dict[str, str]:
    """TA-008: amaçlanan kullanımlar ayrı ayrı. "allowed" yalnız kanıt varken; aksi halde engel nedeni."""
    cited = [registry.sources.get(locator.source_id) for locator in entry.provenance]
    cited = [item for item in cited if item is not None]
    rights = entry.rights
    blockers = eligibility(registry, entry)

    def all_sources(check) -> bool:
        return bool(cited) and all(check(item) for item in cited)

    out = {
        "academic_reference": "allowed" if all_sources(lambda s: s.permissions.academic_reference == "allowed")
        else "source_reference_not_allowed",
        "original_explanation": "allowed" if rights.source_use in {"independent_fact", "teacher_original"}
        else f"source_use:{rights.source_use}",
        "licensed_adaptation": "allowed" if rights.source_use == "licensed_adaptation" and all_sources(
            lambda s: s.permissions.ingestion in {"allowed", "conditional"} and s.license_verified)
        else "not_licensed",
        "direct_quotation": "allowed" if rights.source_use == "direct_quotation" and all_sources(
            lambda s: s.permissions.redistribution in {"allowed", "conditional"} and s.license_verified)
        else "not_licensed",
        "commercial_redistribution": "allowed" if rights.commercial_use == "eligible" else f"commercial_use:{rights.commercial_use}",
        "teacher_contribution": "allowed" if rights.contribution_id and not _contribution_reasons(
            entry, registry.publications) else "no_published_contribution",
        "provider_transmission": "allowed" if not blockers else "blocked:" + ",".join(blockers[:4]),
        # Model eğitimi yapılmaz; izin hiçbir zaman çalışma zamanı kararı değildir.
        "model_training": "not_performed",
    }
    return out


def _cycles(edges: dict[str, list[str]]) -> list[list[str]]:
    return registry_v2._cycles(edges)


def validate(sources: list[SourceRecord], files: list[KnowledgeFile], outcome_ids: set[str], problems: list[str],
             unit_ids: set[str] | None = None) -> None:
    source_ids = Counter(item.id for item in sources)
    problems.extend(f"Yinelenen kaynak: {key}" for key, count in source_ids.items() if count > 1)
    entries = [entry for item in files for entry in item.entries]
    entry_ids = Counter(item.id for item in entries)
    problems.extend(f"Yinelenen bilgi girdisi: {key}" for key, count in entry_ids.items() if count > 1)
    known = set(entry_ids)
    for item in files:
        allowed = ALLOWED_SUBJECTS.get(item.subject, {item.subject})
        for entry in item.entries:
            if entry.subject not in allowed:
                problems.append(f"Girdi alanı dosyayla uyuşmuyor: {entry.id}")
    for entry in entries:
        for locator in entry.provenance:
            if locator.source_id not in source_ids:
                problems.append(f"Tanımsız kaynak: {entry.id} → {locator.source_id}")
        for ref in [*entry.prerequisites, *entry.related]:
            if ref not in known:
                problems.append(f"Tanımsız ön koşul/ilişki: {entry.id} → {ref}")
            elif ref == entry.id:
                problems.append(f"Girdi kendine bağlanamaz: {entry.id}")
        for ref in entry.outcome_refs:
            if ref not in outcome_ids:
                problems.append(f"Tanımsız kazanım: {entry.id} → {ref}")
        for ref in entry.curriculum_topic_refs:
            if unit_ids is not None and ref not in unit_ids:
                problems.append(f"Tanımsız müfredat başlığı: {entry.id} → {ref}")
        if entry.rights.contribution_id is not None and entry.rights.source_use != "teacher_original":
            problems.append(f"Katkı bağı yalnız öğretmen özgün içeriğinde olur: {entry.id}")
        for link in entry.verifiers:
            if link.verifier not in CAPABILITIES:
                problems.append(f"Tanımsız denetleyici: {entry.id} → {link.verifier}")
        if entry.supersedes is not None and entry.supersedes not in known:
            problems.append(f"Yerine geçilen girdi yok: {entry.id} → {entry.supersedes}")
    for cycle in _cycles({entry.id: list(entry.prerequisites) for entry in entries}):
        problems.append("Ön koşul döngüsü: " + " → ".join(cycle))


def load(data_dir: Path = DATA, outcome_ids: set[str] | None = None) -> KnowledgeRegistry:
    hasher = hashlib.sha256()
    source_bytes = registry_v2._read(data_dir / "sources.json")
    hasher.update(b"sources.json\0" + source_bytes)
    sources = SourceRegistryFile.model_validate_json(source_bytes).sources
    files = []
    for name in SUBJECT_FILES:
        path = data_dir / f"{name}.json"
        if not path.exists():
            continue
        payload = registry_v2._read(path)
        hasher.update(f"{name}.json".encode() + b"\0" + payload)
        files.append(KnowledgeFile.model_validate_json(payload))
    unit_ids = None
    if outcome_ids is None:
        curriculum = registry_v2.default_registry()
        outcome_ids, unit_ids = set(curriculum.outcomes), set(curriculum.units)
    reviewer_bytes = registry_v2._read(data_dir / "reviewers.json")
    hasher.update(b"reviewers.json\0" + reviewer_bytes)
    reviewers = tuple(ReviewerRegistryFile.model_validate_json(reviewer_bytes).reviewers)
    snapshot_path = data_dir / "contribution_publications.json"
    publications: dict[str, ContributionPublication] = {}
    if snapshot_path.exists():
        snapshot_bytes = registry_v2._read(snapshot_path)
        hasher.update(b"contribution_publications.json\0" + snapshot_bytes)
        publications = {item.contribution_id: item
                        for item in ContributionSnapshotFile.model_validate_json(snapshot_bytes).records}
    problems: list[str] = []
    validate(sources, files, outcome_ids, problems, unit_ids)
    if problems:
        raise KnowledgeRegistryError(problems)
    return KnowledgeRegistry(sources={item.id: item for item in sources},
                             entries={entry.id: entry for item in files for entry in item.entries},
                             digest=hasher.hexdigest(), reviewers=reviewers, publications=publications)


@lru_cache
def default_knowledge() -> KnowledgeRegistry:
    return load()


def select(registry: KnowledgeRegistry, subject: Subject, *, topic_keys: set[str] = frozenset(),
           outcome_ids: set[str] = frozenset(), limit: int = 3, include_drafts: bool = False) -> list[KnowledgeEntry]:
    """Belirlenimci seçim: önce kazanım bağı, sonra konu anahtarı; eşitlikte kimlik sırası.

    ``include_drafts=False`` (çalışma zamanı) yalnız ``runtime_eligibility`` boş olan girdileri döndürür.
    """
    wanted = {subject, Subject.GEOMETRY} if subject in {Subject.MATHEMATICS, Subject.GEOMETRY} else {subject}
    scored = []
    for entry in registry.entries.values():
        if entry.subject not in wanted:
            continue
        if not include_drafts and eligibility(registry, entry):
            continue
        score = (2 if outcome_ids & set(entry.outcome_refs) else 0) + (1 if entry.topic in topic_keys else 0)
        if score:
            scored.append((-score, entry.id, entry))
    return [entry for *_, entry in sorted(scored, key=lambda item: item[:2])[:limit]]


def coverage(registry: KnowledgeRegistry) -> list[dict]:
    rows = []
    for subject in SUBJECT_FILES:
        group = [entry for entry in registry.entries.values()
                 if entry.subject.value == subject or (subject == "mathematics" and entry.subject == Subject.GEOMETRY)]
        rows.append({
            "subject": subject, "total": len(group),
            "kinds": dict(sorted(Counter(entry.kind for entry in group).items())),
            "sourced": sum(1 for entry in group if entry.provenance),
            "unsourced": [entry.id for entry in group if not entry.provenance],
            "with_outcome": sum(1 for entry in group if entry.outcome_refs),
            "with_verifier": sum(1 for entry in group if entry.verifiers),
            "statuses": dict(sorted(Counter(entry.status for entry in group).items())),
            "reviewed": sum(1 for entry in group if entry.reviews),
            "runtime_eligible": sum(1 for entry in group if not eligibility(registry, entry)),
            "revised": sum(1 for entry in group if entry.revisions),
            "source_use": dict(sorted(Counter(entry.rights.source_use for entry in group).items())),
            "topic_linked": sum(1 for entry in group if entry.curriculum_topic_refs),
        })
    return rows


def preview(registry: KnowledgeRegistry, entry_id: str) -> dict:
    """Çevrimdışı önizleme: taslak girdi, uygunluk engelleri ve denetleyici kapsamıyla birlikte."""
    entry = registry.entries[entry_id]
    return {"entry": entry.model_dump(mode="json", exclude_none=True),
            "runtime_blockers": eligibility(registry, entry),
            "uses": use_permissions(registry, entry),
            "capability": capability_check(entry).model_dump(mode="json"),
            "notice_tr": "TASLAK ÖNİZLEME — öğretmen onayı olmadan öğrenciye veya modele yetkili bilgi olarak verilmez."}
