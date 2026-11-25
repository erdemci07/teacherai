"""Denetimli, belirlenimci bilgi geri getirme (TA-007). Vektör veritabanı, gömme veya ek model çağrısı yoktur.

Sıra: kazanım bağı > konu anahtarı (taksonomi) > müfredat başlığı bağı > önkoşul/ilişki (tek adım) > hafif
sözcük örtüşmesi. Eşitlikte kimlik sırası. İki kip vardır:

- ``production``: yalnız ``runtime_eligibility`` boş girdiler. Ders akışı yalnız bu kipi kullanır.
- ``preview``: taslaklar dahil, engelleriyle birlikte; çevrimdışı inceleme içindir ve isteme giremez
  (``as_context`` önizleme sonucunu reddeder).

Paketleme bütün kayıt üzerindendir: ifade, koşul, varsayım ve istisnalar kırpılmaz. Kayıt sığmazsa dışarıda
bırakılır ve nedeni kaydedilir. Yalnız isteğe bağlı yanılgı listesi bütçe için çıkarılabilir ("compacted").
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Literal

from ..curriculum.topics import normalize
from ..education.base import Subject
from ..education.curriculum_v2 import ContextKnowledge, ExcludedKnowledge, KnowledgeRef
from ..education.knowledge import KnowledgeEntry, content_digest
from .registry import KnowledgeRegistry, eligibility

Mode = Literal["production", "preview"]
SCORES = {"outcome": 16, "topic": 8, "curriculum_topic": 4, "relationship": 2, "lexical": 1}
STOPWORDS = {"ve", "ile", "bir", "bu", "da", "de", "için", "olan", "veya", "ya", "ki", "en", "çok", "kaç", "nedir"}


@dataclass(frozen=True)
class Budget:
    max_entries: int = 3
    max_record_bytes: int = 700
    max_total_bytes: int = 1400


DEFAULT_BUDGET = Budget()


@dataclass(frozen=True)
class Learner:
    """TA-008: öğrenci düzeyi yalnız beyandan (sınıf, sınav hedefleri) gelir; görselden çıkarılmaz.
    ``advanced_requested``: öğrenci düzey üstü anlatımı açıkça istedi."""

    grade: int | None
    exams: tuple[str, ...] = ()
    advanced_requested: bool = False


LEVEL = re.compile(r"(\d{1,2})(?:\s*-\s*(\d{1,2}))?\s*\.\s*sınıf")
EXAM_LEVELS = {"LGS", "TYT", "AYT"}


def level_profile(entry: KnowledgeEntry) -> tuple[set[int], set[str], bool]:
    """(sınıflar, sınav etiketleri, bütün düzeyler mi). Etiketler girdinin ``levels`` alanından belirlenimci okunur."""
    grades: set[int] = set()
    exams: set[str] = set()
    every = False
    for label in entry.levels:
        text = label.strip()
        if text.casefold() in {"tüm düzeyler", "bütün düzeyler"}:
            every = True
        if text.upper() in EXAM_LEVELS:
            exams.add(text.upper())
        for match in LEVEL.finditer(text):
            low = int(match.group(1))
            high = int(match.group(2) or low)
            grades.update(range(low, high + 1))
    return grades, exams, every


def level_reason(entry: KnowledgeEntry, learner: Learner | None) -> str | None:
    """None: düzeye uygun. Sınav hedefi sınıf düzeyi sayılmaz; düzey üstü kayıt yalnız açık istekle gelir."""
    if learner is None:
        return None
    grades, exams, every = level_profile(entry)
    if every:
        return None
    if not grades and not exams:
        return "level_unspecified"
    if learner.grade is None:
        return None if exams & set(learner.exams) else "learner_level_unknown"
    if grades:
        if learner.grade in grades or max(grades) < learner.grade:
            return None  # aynı veya alt düzey (ön koşul) bilgisi
        return None if learner.advanced_requested else "above_learner_level"
    return None if exams & set(learner.exams) else "exam_level_mismatch"


@dataclass(frozen=True)
class Retrieved:
    entry: KnowledgeEntry
    score: int
    reasons: tuple[str, ...]
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class RetrievalResult:
    mode: Mode
    selected: tuple[Retrieved, ...]
    context: tuple[ContextKnowledge, ...]
    excluded: tuple[ExcludedKnowledge, ...]
    compacted: tuple[str, ...]
    considered: int
    payload_bytes: int = 0
    notice_tr: str | None = None

    @property
    def refs(self) -> list[KnowledgeRef]:
        chosen = {item.id for item in self.context}
        return [KnowledgeRef(id=item.entry.id, version=item.entry.version, content_digest=content_digest(item.entry))
                for item in self.selected if item.entry.id in chosen]


@dataclass(frozen=True)
class Index:
    by_outcome: dict[str, tuple[str, ...]]
    by_topic: dict[str, tuple[str, ...]]
    by_unit: dict[str, tuple[str, ...]]
    tokens: dict[str, frozenset[str]] = field(default_factory=dict)


def _group(pairs) -> dict[str, tuple[str, ...]]:
    out: dict[str, list[str]] = {}
    for key, value in pairs:
        out.setdefault(key, []).append(value)
    return {key: tuple(sorted(set(values))) for key, values in out.items()}


def _words(text: str) -> frozenset[str]:
    return frozenset(word for word in normalize(text) if len(word) > 2 and word not in STOPWORDS)


def _build_index(registry: KnowledgeRegistry) -> Index:
    entries = registry.entries.values()
    return Index(
        by_outcome=_group((ref, entry.id) for entry in entries for ref in entry.outcome_refs),
        by_topic=_group((entry.topic, entry.id) for entry in entries),
        by_unit=_group((ref, entry.id) for entry in entries for ref in entry.curriculum_topic_refs),
        tokens={entry.id: _words(f"{entry.title_tr} {entry.statement_tr}") for entry in entries},
    )


_CACHE: dict[int, tuple[KnowledgeRegistry, Index]] = {}


def index_for(registry: KnowledgeRegistry) -> Index:
    """Kayıt nesnesi başına bir kez kurulan dizin (kimlik denetimli küçük önbellek)."""
    cached = _CACHE.get(id(registry))
    if cached is not None and cached[0] is registry:
        return cached[1]
    if len(_CACHE) >= 8:
        _CACHE.clear()
    index = _build_index(registry)
    _CACHE[id(registry)] = (registry, index)
    return index


def _subjects(subject: Subject) -> set[Subject]:
    if subject in {Subject.MATHEMATICS, Subject.GEOMETRY}:
        return {Subject.MATHEMATICS, Subject.GEOMETRY}
    return {subject}


def candidates(registry: KnowledgeRegistry, subject: Subject, *, topic_keys=(), outcome_ids=(), unit_ids=(),
               query: str = "") -> list[tuple[KnowledgeEntry, int, tuple[str, ...]]]:
    index = index_for(registry)
    scores: dict[str, int] = {}
    reasons: dict[str, set[str]] = {}

    def add(entry_id: str, kind: str):
        scores[entry_id] = scores.get(entry_id, 0) + SCORES[kind]
        reasons.setdefault(entry_id, set()).add(kind)

    for ref in outcome_ids:
        for entry_id in index.by_outcome.get(ref, ()):
            add(entry_id, "outcome")
    for key in topic_keys:
        for entry_id in index.by_topic.get(key, ()):
            add(entry_id, "topic")
    for ref in unit_ids:
        for entry_id in index.by_unit.get(ref, ()):
            add(entry_id, "curriculum_topic")
    for entry_id in list(scores):
        entry = registry.entries[entry_id]
        for ref in (*entry.prerequisites, *entry.related):
            if ref in registry.entries and ref not in scores:
                add(ref, "relationship")
    words = _words(query)
    if words and scores:  # sözcük örtüşmesi yalnız sıralamayı etkiler; tek başına girdi getirmez
        for entry_id in scores:
            if len(words & index.tokens.get(entry_id, frozenset())) >= 2:
                add(entry_id, "lexical")
    wanted = _subjects(subject)
    rows = [(registry.entries[entry_id], score, tuple(sorted(reasons[entry_id])))
            for entry_id, score in scores.items() if registry.entries[entry_id].subject in wanted]
    rows.sort(key=lambda row: (-row[1], row[0].id))
    return rows


def _size(item: ContextKnowledge) -> int:
    # TA-008: isteme giden serileştirmeyle aynı (lessons.context: exclude_none, sıkı ayırıcı).
    return len(json.dumps(item.model_dump(exclude_none=True), ensure_ascii=False,
                          separators=(",", ":")).encode("utf-8"))


def to_context(entry: KnowledgeEntry) -> ContextKnowledge:
    return ContextKnowledge(id=entry.id, version=entry.version, kind=entry.kind, title_tr=entry.title_tr,
                            statement_tr=entry.statement_tr, conditions_tr=list(entry.conditions_tr),
                            assumptions_tr=list(entry.assumptions_tr), exceptions_tr=list(entry.exceptions_tr),
                            misconceptions_tr=list(entry.misconceptions_tr[:3]))


def retrieve(registry: KnowledgeRegistry, subject: Subject, *, topic_keys=(), outcome_ids=(), unit_ids=(),
             query: str = "", mode: Mode = "production", budget: Budget = DEFAULT_BUDGET,
             learner: Learner | None = None) -> RetrievalResult:
    rows = candidates(registry, subject, topic_keys=topic_keys, outcome_ids=outcome_ids, unit_ids=unit_ids, query=query)
    selected, context, excluded, compacted, total = [], [], [], [], 0
    for entry, score, reasons in rows:
        blockers = tuple(eligibility(registry, entry))
        if mode == "production" and blockers:
            excluded.append(ExcludedKnowledge(id=entry.id, reason="not_runtime_eligible"))
            continue
        unsuitable = level_reason(entry, learner)
        if unsuitable is not None:
            excluded.append(ExcludedKnowledge(id=entry.id, reason=unsuitable))
            continue
        if len(context) >= budget.max_entries:
            excluded.append(ExcludedKnowledge(id=entry.id, reason="limit_reached"))
            continue
        item = to_context(entry)
        if _size(item) > budget.max_record_bytes and item.misconceptions_tr:
            item = item.model_copy(update={"misconceptions_tr": []})
            compacted_now = True
        else:
            compacted_now = False
        size = _size(item)
        if size > budget.max_record_bytes:
            excluded.append(ExcludedKnowledge(id=entry.id, reason="exceeds_record_budget"))
            continue
        if total + size > budget.max_total_bytes:
            excluded.append(ExcludedKnowledge(id=entry.id, reason="exceeds_total_budget"))
            continue
        total += size
        context.append(item)
        selected.append(Retrieved(entry, score, reasons, blockers))
        if compacted_now:
            compacted.append(entry.id)
    notice = ("TASLAK ÖNİZLEME — öğretmen onayı olmadan öğrenciye veya modele yetkili bilgi olarak verilmez."
              if mode == "preview" else None)
    return RetrievalResult(mode, tuple(selected), tuple(context), tuple(excluded[:32]), tuple(compacted), len(rows),
                           total, notice)


def as_context(result: RetrievalResult) -> list[ContextKnowledge]:
    """İsteme yalnız üretim kipi sonucu girer."""
    if result.mode != "production":
        raise ValueError("Önizleme sonucu çalışma zamanı bağlamına giremez.")
    return list(result.context)
