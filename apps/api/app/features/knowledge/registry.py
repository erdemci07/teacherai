"""Bilimsel kaynak ve bilgi kaydı: yükleme, doğrulama, çalışma zamanı uygunluğu ve belirlenimci seçim (TA-006).

Saf Python; sağlayıcı, gömme (embedding) veya vektör veritabanı yoktur. Seçim yalnız kesin kimlik, konu anahtarı
ve kazanım bağıyla yapılır. Taslak, incelenmemiş veya hak durumu kısıtlı girdi çalışma zamanı yetkisi taşımaz;
taslaklar yalnız ``include_drafts=True`` ile çevrimdışı önizlemede görünür.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..curriculum import registry_v2
from ..education.base import Subject
from ..education.knowledge import KnowledgeEntry, KnowledgeFile, SourceRecord, SourceRegistryFile
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

    @property
    def version(self) -> str:
        return f"{SCHEMA_VERSION}+{self.digest[:12]}"


def runtime_eligibility(entry: KnowledgeEntry, sources: dict[str, SourceRecord]) -> list[str]:
    """Boş liste: çalışma zamanında yetkili bağlam olarak kullanılabilir. Aksi halde engel nedenleri."""
    reasons = []
    if entry.status != "approved":
        reasons.append(f"status:{entry.status}")
    if not entry.provenance:
        reasons.append("unsourced")
    for locator in entry.provenance:
        source = sources.get(locator.source_id)
        if source is None:
            reasons.append(f"unknown_source:{locator.source_id}")
            continue
        if locator.verified_on is None:
            reasons.append(f"locator_unverified:{locator.source_id}")
        if source.permissions.academic_reference != "allowed" or source.access in {"access_restricted", "not_accessed"}:
            reasons.append(f"rights_restricted:{source.id}")
    return sorted(set(reasons))


def _cycles(edges: dict[str, list[str]]) -> list[list[str]]:
    return registry_v2._cycles(edges)


def validate(sources: list[SourceRecord], files: list[KnowledgeFile], outcome_ids: set[str], problems: list[str]) -> None:
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
    if outcome_ids is None:
        outcome_ids = set(registry_v2.default_registry().outcomes)
    problems: list[str] = []
    validate(sources, files, outcome_ids, problems)
    if problems:
        raise KnowledgeRegistryError(problems)
    return KnowledgeRegistry(sources={item.id: item for item in sources},
                             entries={entry.id: entry for item in files for entry in item.entries},
                             digest=hasher.hexdigest())


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
        if not include_drafts and runtime_eligibility(entry, registry.sources):
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
            "runtime_eligible": sum(1 for entry in group if not runtime_eligibility(entry, registry.sources)),
        })
    return rows


def preview(registry: KnowledgeRegistry, entry_id: str) -> dict:
    """Çevrimdışı önizleme: taslak girdi, uygunluk engelleri ve denetleyici kapsamıyla birlikte."""
    entry = registry.entries[entry_id]
    return {"entry": entry.model_dump(mode="json", exclude_none=True),
            "runtime_blockers": runtime_eligibility(entry, registry.sources),
            "capability": capability_check(entry).model_dump(mode="json"),
            "notice_tr": "TASLAK ÖNİZLEME — öğretmen onayı olmadan öğrenciye veya modele yetkili bilgi olarak verilmez."}
