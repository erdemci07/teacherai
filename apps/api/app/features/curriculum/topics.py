"""Ortak konu taksonomisi ve belirlenimci soru → konu eşlemesi (TA-007). Saf Python; sağlayıcı çağırmaz.

Kanıt düzeyleri ayrı tutulur:

- **structure** (güçlü): kaynak ifadelerin AST'sinden ``registry.topic_of`` ile çıkan konu. Yalnız matematik.
- **alias** (zayıf): soru metninde (OCR) taksonomi takma adının Türkçe ekli biçimi. Sağlayıcının serbest
  ``topic`` etiketi kullanılmaz.

Eşleme birden çok aday döndürebilir; ``status`` belirsizliği açıkça söyler. Belirsiz eşleme müfredat
denetimini geçmiş saymaz ve yöntem politikasını tek konuya daraltmaz.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from ..education.base import Subject
from . import registry as legacy

DATA = Path(__file__).with_name("data") / "topics.json"
ASCII = str.maketrans("çğıöşüâîû", "cgiosuaiu")
# Türkçe çekim/iyelik ekleri (tam liste değildir). Ünsüz yumuşaması (kitap→kitabı) desteklenmez.
SUFFIX = re.compile(
    r"(?:l[ae]r)?(?:[iıuü]|s[iıuü]|n[iıuü]n|[iıuü]n|y?[ae]|[dt][ae]|[dt][ae]n|y?l[ae]|[dt][iıuü]r|n[iıuü])?"
    r"(?:n?[dt][ae]n?|n?[iıuü]n|y?[ae]|k[iı]|l[ae]r)?")
TOKEN = re.compile(r"[0-9a-zçğıöşüâîû]+")
SUBJECTS = {
    Subject.MATHEMATICS: {"mathematics", "geometry"}, Subject.GEOMETRY: {"mathematics", "geometry"},
    Subject.PHYSICS: {"physics"}, Subject.CHEMISTRY: {"chemistry"}, Subject.BIOLOGY: {"biology"},
    Subject.SCIENCE: {"science", "physics", "chemistry", "biology"},
}
Evidence = Literal["structure", "alias"]
Status = Literal["structural", "single", "ambiguous", "none"]


class TaxonomyError(ValueError):
    pass


@dataclass(frozen=True)
class Topic:
    key: str
    subject: str
    title_tr: str
    aliases: tuple[tuple[str, ...], ...]
    pattern: re.Pattern
    knowledge_topics: tuple[str, ...]
    structure: str | None
    prerequisites: tuple[str, ...]
    related: tuple[str, ...]


@dataclass(frozen=True)
class Candidate:
    key: str
    evidence: Evidence
    hits: tuple[str, ...]


@dataclass(frozen=True)
class TopicMapping:
    status: Status
    candidates: tuple[Candidate, ...]

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(item.key for item in self.candidates)

    @property
    def certain(self) -> str | None:
        """Yalnız yapısal tek konu kesin sayılır."""
        return self.candidates[0].key if self.status == "structural" else None


@dataclass(frozen=True)
class Taxonomy:
    version: str
    topics: dict[str, Topic]

    def for_subject(self, subject: Subject) -> list[Topic]:
        wanted = SUBJECTS.get(subject, {subject.value})
        return [item for item in self.topics.values() if item.subject in wanted]


def normalize(text: str) -> list[str]:
    """Türkçe büyük/küçük harf dönüşümü (İ→i, I→ı) ve kesme işaretinin kaldırılması."""
    lowered = (text or "").replace("İ", "i").replace("I", "ı").lower().replace("'", "").replace("’", "")
    return TOKEN.findall(lowered)


def slug(text: str) -> str:
    return "_".join(normalize(text)).translate(ASCII)


def _token_matches(token: str, alias: str, last: bool) -> bool:
    if token == alias:
        return True
    return last and token.startswith(alias) and SUFFIX.fullmatch(token[len(alias):]) is not None


def alias_hits(tokens: list[str], alias: tuple[str, ...]) -> bool:
    size = len(alias)
    for start in range(len(tokens) - size + 1):
        if all(_token_matches(tokens[start + i], alias[i], i == size - 1) for i in range(size)):
            return True
    return False


def load(path: Path = DATA) -> Taxonomy:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_name") != "teacherai.topic_taxonomy":
        raise TaxonomyError("Taksonomi şema adı geçersiz.")
    topics, problems = {}, []
    valid_subjects = {item.value for item in Subject}
    for raw in data["topics"]:
        key = raw["key"]
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
            problems.append(f"Geçersiz konu anahtarı: {key}")
        if key in topics:
            problems.append(f"Yinelenen konu: {key}")
        if raw["subject"] not in valid_subjects:
            problems.append(f"Tanımsız alan: {key} → {raw['subject']}")
        try:
            pattern = re.compile(raw["outcome_pattern"])
        except re.error:
            problems.append(f"Geçersiz kazanım deseni: {key}")
            continue
        aliases = tuple(tuple(normalize(alias)) for alias in raw.get("aliases", []))
        if any(not alias for alias in aliases):
            problems.append(f"Boş takma ad: {key}")
        topics[key] = Topic(key, raw["subject"], raw["title_tr"], aliases, pattern,
                            tuple(raw.get("knowledge_topics", [])), raw.get("structure"),
                            tuple(raw.get("prerequisites", [])), tuple(raw.get("related", [])))
    for item in topics.values():
        for ref in item.prerequisites + item.related:
            if ref not in topics:
                problems.append(f"Tanımsız konu bağı: {item.key} → {ref}")
    if problems:
        raise TaxonomyError("; ".join(problems))
    return Taxonomy(data["version"], topics)


@lru_cache
def default_taxonomy() -> Taxonomy:
    return load()


def map_question(analysis, subject: Subject, taxonomy: Taxonomy | None = None) -> TopicMapping:
    """Belirlenimci eşleme. Önce yapı (güçlü), yoksa soru metnindeki takma adlar (zayıf)."""
    taxonomy = taxonomy or default_taxonomy()
    allowed = {item.key for item in taxonomy.for_subject(subject)}
    structural = legacy.topic_of(analysis) if subject in {Subject.MATHEMATICS, Subject.GEOMETRY} else None
    if structural in allowed:
        return TopicMapping("structural", (Candidate(structural, "structure", ("ast",)),))
    tokens = normalize(getattr(analysis, "question_text", "") or "")
    found = []
    for item in taxonomy.for_subject(subject):
        hits = tuple(" ".join(alias) for alias in item.aliases if alias_hits(tokens, alias))
        if hits:
            found.append(Candidate(item.key, "alias", hits))
    found.sort(key=lambda item: (-len(item.hits), item.key))
    if not found:
        return TopicMapping("none", ())
    top = [item for item in found if len(item.hits) == len(found[0].hits)]
    return TopicMapping("single" if len(top) == 1 and len(found) == 1 else "ambiguous", tuple(found[:4]))


def outcome_matches(topic: Topic, outcome, units) -> bool:
    keys = {outcome.topic_key, *outcome.aliases}
    unit = units.get(outcome.unit_id)
    if unit is not None:
        keys.add(slug(unit.title_tr))
    return any(topic.pattern.search(key) for key in keys)


def outcomes_for(curriculum, program_id: str, grade: int, keys) -> list:
    taxonomy_topics = [default_taxonomy().topics[key] for key in keys if key in default_taxonomy().topics]
    return [outcome for outcome in curriculum.outcomes_for(program_id, grade)
            if any(outcome_matches(topic, outcome, curriculum.units) for topic in taxonomy_topics)]


def knowledge_topics(keys, taxonomy: Taxonomy | None = None) -> set[str]:
    taxonomy = taxonomy or default_taxonomy()
    return {name for key in keys if key in taxonomy.topics for name in (key, *taxonomy.topics[key].knowledge_topics)}


def coverage(curriculum, knowledge, taxonomy: Taxonomy | None = None) -> dict:
    """Dürüst kapsam: hangi kazanımlar hiçbir taksonomi konusuna düşmüyor, hangi bilgi konuları eşlenmemiş."""
    taxonomy = taxonomy or default_taxonomy()
    programs = []
    for program_id in sorted(curriculum.programs):
        outcomes = curriculum.outcomes_for(program_id)
        if not outcomes:
            continue
        topics = [item for item in taxonomy.topics.values()
                  if item.subject in SUBJECTS.get(curriculum.programs[program_id].subject, set())]
        mapped = [o for o in outcomes if any(outcome_matches(t, o, curriculum.units) for t in topics)]
        multi = [o for o in outcomes if sum(outcome_matches(t, o, curriculum.units) for t in topics) > 1]
        programs.append({"program_id": program_id, "outcomes": len(outcomes), "mapped": len(mapped),
                         "multiple_topics": len(multi)})
    mapped_names = {name for item in taxonomy.topics.values() for name in (item.key, *item.knowledge_topics)}
    unmapped = sorted({f"{entry.subject.value}:{entry.topic}" for entry in knowledge.entries.values()
                       if entry.topic not in mapped_names})
    return {"taxonomy_version": taxonomy.version, "topics": len(taxonomy.topics),
            "by_subject": {subject: sum(1 for t in taxonomy.topics.values() if t.subject == subject)
                           for subject in sorted({t.subject for t in taxonomy.topics.values()})},
            "programs": programs, "unmapped_knowledge_topics": unmapped}
