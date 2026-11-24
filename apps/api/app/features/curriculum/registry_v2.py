"""Müfredat Kaydı v2: modüler veri dosyalarını yükler, doğrular, v1'i göç ettirir ve programı çözümler (TA-006).

Saf Python; sağlayıcı ve Firestore çağrısı yoktur. Kayıt süreç başına bir kez yüklenir (``default_registry``).

- **Göç (v1 → v2):** TA-005'in 29 kaynaklı 8. sınıf kazanımı ``meb-2018.matematik.1-8`` program dosyasındaki aynı
  resmî kodlu kayda bindirilir (birebir metin, v1 konu anahtarı takma ad olarak). 5 taslak yöntem politikası
  ``MethodPolicyV2`` olur. Göç belirlenimcidir; v1 dosyası ve ``registry.default_registry`` değişmez.
- **Doğrulama:** bütün sorunlar toplanır ve tek ``RegistryError`` ile raporlanır.
- **Çözümleme:** öğrencinin beyan ettiği bağlamdan program seçer; belirsizliği ``ambiguous`` olarak döndürür.
  Sınıf veya mezuniyet fotoğraftan çıkarılmaz; bu modül görsel almaz.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

from ..education.base import Subject
from ..education.curriculum import CurriculumRegistry
from ..education.curriculum_v2 import (
    PROGRAM_SUBJECTS,
    CurriculumCatalog,
    CurriculumResolution,
    MethodPolicyV2,
    OutcomeRecord,
    ProgramFile,
    ProgramVersion,
    UnitRecord,
    code_grade,
)
from . import registry as legacy

DATA = Path(__file__).with_name("data")
LEGACY_PROGRAM = "meb-2018.matematik.1-8"
SCHEMA_VERSION = "2.0.0"


class RegistryError(ValueError):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("Müfredat kaydı geçersiz:\n- " + "\n- ".join(problems[:50]))


@dataclass(frozen=True)
class CurriculumRegistryV2:
    catalog: CurriculumCatalog
    programs: dict[str, ProgramVersion]
    units: dict[str, UnitRecord]
    outcomes: dict[str, OutcomeRecord]
    policies: tuple[MethodPolicyV2, ...]
    digest: str
    by_code: dict[tuple[str, str], str] = field(default_factory=dict)

    @property
    def version(self) -> str:
        return f"{SCHEMA_VERSION}+{self.digest[:12]}"

    def outcomes_for(self, program_id: str, grade: int | None = None) -> list[OutcomeRecord]:
        return [item for item in self.outcomes.values()
                if item.program_id == program_id and (grade is None or item.grade == grade)]


def legacy_global_id(code: str) -> str:
    return f"{LEGACY_PROGRAM}::{code}"


def migrate_v1_policies(registry: CurriculumRegistry) -> list[MethodPolicyV2]:
    """v1 politikalarını alan, program ve küresel kazanım kimlikleriyle v2'ye taşır. Durum ve onay aynen kalır."""
    return [MethodPolicyV2(
        id=f"{LEGACY_PROGRAM}.{policy.id}", subject=Subject.MATHEMATICS, topic=policy.topic, framework="meb_2018",
        program_ids=[LEGACY_PROGRAM], grades=[policy.grade], allowed_operations=list(policy.allowed_operations),
        forbidden_operations=list(policy.forbidden_operations),
        preferred_representations=list(policy.preferred_representations),
        outcome_ids=[legacy_global_id(ref) for ref in policy.outcome_ids], status=policy.status,
        authored_by=policy.authored_by, approved_by=policy.approved_by, legacy_id=policy.id,
        approved_on=policy.approved_on, approval_digest=policy.approval_digest,
    ) for policy in registry.policies]


def overlay_v1_outcomes(outcomes: dict[str, OutcomeRecord], registry: CurriculumRegistry, problems: list[str]) -> None:
    """v1 kazanımlarının birebir metnini ve v1 konu anahtarını aynı resmî kodlu v2 kaydına taşır."""
    for item in registry.outcomes:
        key = legacy_global_id(item.outcome_id)
        target = outcomes.get(key)
        if target is None:
            problems.append(f"v1 kazanımı v2'de yok: {item.outcome_id}")
            continue
        if target.grade != item.grade:
            problems.append(f"v1 kazanımı sınıf uyuşmazlığı: {item.outcome_id}")
            continue
        aliases = sorted(set(target.aliases) | ({item.topic} - {target.topic_key}))
        outcomes[key] = target.model_copy(update={"official_text_tr": item.outcome_text_tr, "aliases": aliases})


def _read(path: Path) -> bytes:
    """Satır sonu normalize edilir: Windows (autocrlf) ile CI aynı özeti üretir."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def _cycles(edges: dict[str, list[str]]) -> list[list[str]]:
    """Ön koşul grafiğindeki döngüler (yinelemesiz DFS, belirlenimci sıra)."""
    state: dict[str, int] = {}
    found: list[list[str]] = []
    for root in sorted(edges):
        if state.get(root):
            continue
        stack = [(root, iter(sorted(edges.get(root, []))))]
        path = [root]
        state[root] = 1
        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:
                state[node] = 2
                stack.pop()
                path.pop()
                continue
            if state.get(child) == 1:
                found.append(path[path.index(child):] + [child])
            elif not state.get(child):
                state[child] = 1
                path.append(child)
                stack.append((child, iter(sorted(edges.get(child, [])))))
    return found


def validate(catalog: CurriculumCatalog, units: list[UnitRecord], outcomes: list[OutcomeRecord],
             policies: list[MethodPolicyV2], problems: list[str]) -> None:
    programs = {item.id: item for item in catalog.programs}
    if len(programs) != len(catalog.programs):
        problems.append("Yinelenen program kimliği")
    for kind, records in (("ünite", units), ("kazanım", outcomes), ("politika", policies)):
        seen: set[str] = set()
        for record in records:
            if record.id in seen:
                problems.append(f"Yinelenen {kind} kimliği: {record.id}")
            seen.add(record.id)
    unit_ids = {item.id: item for item in units}
    outcome_ids = {item.id: item for item in outcomes}
    codes: dict[tuple[str, str], str] = {}
    for unit in units:
        program = programs.get(unit.program_id)
        if program is None:
            problems.append(f"Ünite tanımsız programa bağlı: {unit.id}")
            continue
        if unit.parent_id and unit.parent_id not in unit_ids:
            problems.append(f"Üst başlık yok: {unit.id}")
        if code_grade(unit.official_code) != unit.grade:
            problems.append(f"Ünite kodu sınıfla uyuşmuyor: {unit.id}")
    for item in outcomes:
        program = programs.get(item.program_id)
        if program is None:
            problems.append(f"Kazanım tanımsız programa bağlı: {item.id}")
            continue
        if item.subject != program.subject:
            problems.append(f"Kazanım alanı programla uyuşmuyor: {item.id}")
        if item.terminology != program.terminology:
            problems.append(f"Kazanım terimi programla uyuşmuyor: {item.id}")
        if item.grade not in program.covered_grades:
            problems.append(f"Kazanım sınıfı program kapsamında değil: {item.id}")
        if code_grade(item.official_code) != item.grade:
            problems.append(f"Resmî kod sınıfla uyuşmuyor: {item.id}")
        key = (item.program_id, item.official_code)
        if key in codes:
            problems.append(f"Aynı programda yinelenen resmî kod: {item.official_code}")
        codes[key] = item.id
        for ref in (item.unit_id, item.topic_id):
            if ref is not None and (ref not in unit_ids or unit_ids[ref].program_id != item.program_id):
                problems.append(f"Kazanım başlığı çözümlenmedi: {item.id} → {ref}")
        for ref in [*item.prerequisites, *item.related]:
            other = outcome_ids.get(ref)
            if other is None:
                problems.append(f"Tanımsız ön koşul/ilişki: {item.id} → {ref}")
            elif programs[other.program_id].framework != program.framework:
                problems.append(f"Sürüm uyuşmazlığı (farklı çerçeve): {item.id} → {ref}")
            elif ref == item.id:
                problems.append(f"Kazanım kendine bağlanamaz: {item.id}")
    for cycle in _cycles({item.id: list(item.prerequisites) for item in outcomes}):
        problems.append("Ön koşul döngüsü: " + " → ".join(cycle))
    seen_rules: dict[tuple[str, int, Subject, str], str] = {}
    for rule in catalog.application:
        for ref in rule.program_ids:
            program = programs.get(ref)
            if program is None:
                problems.append(f"Uygulama kuralı tanımsız programa bağlı: {ref}")
                continue
            if program.framework != rule.framework:
                problems.append(f"Uygulama kuralı çerçeve uyuşmazlığı: {rule.academic_year} {ref}")
            if program.track != "general" and program.track != rule.track:
                problems.append(f"İzleğe özgü program başka izleğin kuralında: {rule.academic_year} {ref}")
            if not set(rule.grades) <= set(program.document_grades):
                problems.append(f"Uygulama kuralı belgenin sınıfları dışında: {rule.academic_year} {ref}")
            for grade in rule.grades:
                key = (rule.academic_year, grade, program.subject, rule.track)
                if key in seen_rules and seen_rules[key] != ref:
                    problems.append(f"Aynı yıl/sınıf/alan için iki program: {key}")
                seen_rules[key] = ref
    for policy in policies:
        for ref in policy.outcome_ids:
            if ref not in outcome_ids:
                problems.append(f"Politika tanımsız kazanıma bağlı: {policy.id} → {ref}")
        for ref in policy.program_ids:
            if ref not in programs:
                problems.append(f"Politika tanımsız programa bağlı: {policy.id} → {ref}")


def build(catalog: CurriculumCatalog, files: list[ProgramFile], v1: CurriculumRegistry, digest: str) -> CurriculumRegistryV2:
    problems: list[str] = []
    units = [unit for item in files for unit in item.units]
    outcomes: dict[str, OutcomeRecord] = {}
    ordered: list[OutcomeRecord] = []
    for item in files:
        if item.program_id not in {program.id for program in catalog.programs}:
            problems.append(f"Program dosyası katalogda yok: {item.program_id}")
        for outcome in item.outcomes:
            if outcome.program_id != item.program_id:
                problems.append(f"Kazanım başka programın dosyasında: {outcome.id}")
            ordered.append(outcome)
            outcomes.setdefault(outcome.id, outcome)
    overlay_v1_outcomes(outcomes, v1, problems)
    ordered = [outcomes.get(item.id, item) for item in ordered]
    policies = [*migrate_v1_policies(v1), *catalog.policies]
    validate(catalog, units, ordered, policies, problems)
    if problems:
        raise RegistryError(problems)
    return CurriculumRegistryV2(
        catalog=catalog, programs={item.id: item for item in catalog.programs},
        units={unit.id: unit for unit in units}, outcomes=outcomes, policies=tuple(policies), digest=digest,
        by_code={(item.program_id, item.official_code): item.id for item in outcomes.values()},
    )


def load(data_dir: Path = DATA, v1: CurriculumRegistry | None = None) -> CurriculumRegistryV2:
    catalog_bytes = _read(data_dir / "catalog.json")
    catalog = CurriculumCatalog.model_validate_json(catalog_bytes)
    paths = sorted((data_dir / "programs").glob("*.json"))
    legacy_path = legacy.DATA
    hasher = hashlib.sha256()
    for name, payload in [("catalog.json", catalog_bytes), *((f"programs/{p.name}", _read(p)) for p in paths),
                          (f"legacy/{legacy_path.name}", _read(legacy_path))]:
        hasher.update(name.encode() + b"\0" + payload + b"\0")
    files = [ProgramFile.model_validate_json(_read(path)) for path in paths]
    return build(catalog, files, v1 or legacy.default_registry(), hasher.hexdigest())


@lru_cache
def default_registry() -> CurriculumRegistryV2:
    return load()


# --- Çözümleme -------------------------------------------------------------------------------------------------

def academic_year_for(today: date) -> str:
    """Sunucu saatinden öğretim yılı: Eylül–Aralık → y-(y+1), Ocak–Ağustos → (y-1)-y."""
    start = today.year if today.month >= 9 else today.year - 1
    return f"{start}-{start + 1}"


def in_transition(today: date) -> bool:
    """Temmuz–Ağustos: biten yılın sınıfı ile başlayacak yılın sınıfı karışabilir."""
    return today.month in {7, 8}


def program_subject(subject: Subject) -> Subject:
    return Subject.MATHEMATICS if subject == Subject.GEOMETRY else subject


def scheduled(registry: CurriculumRegistryV2, subject: Subject, academic_year: str, grade: int, track: str = "general"):
    """(kurallar, programlar) — o yıl o sınıfta o alanda ve izlekte uygulanan."""
    rules = [rule for rule in registry.catalog.application
             if rule.academic_year == academic_year and grade in rule.grades and rule.track == track]
    programs = sorted({ref for rule in rules for ref in rule.program_ids if registry.programs[ref].subject == subject})
    return rules, programs


def exam_scope(registry: CurriculumRegistryV2, exam: str | None, academic_year: str):
    if exam is None:
        return None
    return next((scope for scope in registry.catalog.exam_scopes
                 if scope.exam == exam and scope.academic_year == academic_year), None)


def _track_choice(registry, subject, year, grades, track):
    """İzlek kararı. Fen lisesi/temel düzey programı yalnız açık beyanla seçilir; beyan yoksa genel program
    kullanılır ve izleğe özgü farklı program varsa bu açıkça gerekçe olarak yazılır."""
    general = [scheduled(registry, subject, year, value) for value in grades]
    general_rules = [rule for rules, _ in general for rule in rules]
    general_programs = sorted({ref for _, programs in general for ref in programs})
    if track in {"science_high_school", "basic_level"}:
        specific = [scheduled(registry, subject, year, value, track) for value in grades]
        programs = sorted({ref for _, items in specific for ref in items})
        if programs:
            return [rule for rules, _ in specific for rule in rules], programs, ["track_specific_program"]
        return general_rules, general_programs, ["track_rule_missing_general_used"] if general_programs else []
    others = sorted({ref for value in grades for other in ("science_high_school", "basic_level")
                     for ref in scheduled(registry, subject, year, value, other)[1]})
    differs = bool(set(others) - set(general_programs))
    return general_rules, general_programs, ["track_unspecified_general_assumed"] if differs and general_programs else []


def resolve(registry: CurriculumRegistryV2, subject: Subject, grade: int | None, *, today: date,
            academic_year: str | None = None, learner_status: str | None = None, exam: str | None = None,
            program_id: str | None = None, exams: list[str] | None = None, track: str | None = None) -> CurriculumResolution:
    year = academic_year or academic_year_for(today)
    goals = list(dict.fromkeys([*(exams or []), *([exam] if exam else [])]))
    base = {"subject": subject, "academic_year": year, "academic_year_origin": "declared" if academic_year else "server_clock",
            "grade": grade if learner_status != "graduate" else None, "learner_status": learner_status,
            "exam": goals[0] if goals else None, "exams": goals, "track": track}
    subject = program_subject(subject)
    if subject not in PROGRAM_SUBJECTS:
        return CurriculumResolution(status="unresolved", reasons=["subject_unsupported"], **base)
    scopes = [exam_scope(registry, goal, year) for goal in goals]
    scope_ids = [item.id for item in scopes if item is not None]
    verified = [item for item in scopes if item is not None and item.status == "verified"]
    scope_reason = []
    if goals:
        scope_reason.append("exam_scope_verified" if len(verified) == len(goals) else "exam_scope_unverified")
    if len(goals) > 1:
        scope_reason.append("multiple_exam_goals")
    scope_id = scope_ids[0] if scope_ids else None
    base |= {"exam_scope_ids": scope_ids}
    if learner_status == "graduate":
        # Mezun öğrenci 12. sınıf öğrencisi sayılmaz: yalnız bütün hedefleri doğrulanmış sınav kapsamı programı belirler.
        if not goals or len(verified) != len(goals):
            candidates = sorted(item.id for item in registry.programs.values()
                                if item.subject == subject and item.stage == "ortaogretim" and item.track == "general")
            return CurriculumResolution(status="ambiguous" if goals else "unresolved", exam_scope_id=scope_id,
                                        candidate_program_ids=candidates if goals else [],
                                        reasons=["graduate_exam_scope", *scope_reason] if goals else ["graduate_exam_scope", "grade_unknown"],
                                        **base)
    if grade is None and learner_status != "graduate":
        return CurriculumResolution(status="unresolved", reasons=["grade_unknown", *scope_reason], exam_scope_id=scope_id, **base)
    grades = sorted({value for item in verified for value in item.grades}) if learner_status == "graduate" else [grade]
    rules, programs, track_reasons = _track_choice(registry, subject, year, grades, track)
    reasons = [*scope_reason, *track_reasons]
    if any(rule.evidence == "by_exclusion" for rule in rules if set(rule.program_ids) & set(programs)):
        reasons.append("by_exclusion")
    if program_id is not None:
        if program_id in registry.programs and registry.programs[program_id].subject == subject:
            if not programs or program_id in programs:
                return CurriculumResolution(status="resolved", program_ids=[program_id], exam_scope_id=scope_id,
                                            reasons=[*reasons, "explicit_program"], **base)
            return CurriculumResolution(status="ambiguous", candidate_program_ids=sorted({program_id, *programs}),
                                        exam_scope_id=scope_id, reasons=[*reasons, "explicit_program_not_applicable"], **base)
    if not academic_year and in_transition(today) and learner_status != "graduate":
        return CurriculumResolution(status="ambiguous", candidate_program_ids=programs, exam_scope_id=scope_id,
                                    reasons=[*reasons, "academic_year_transition"], **base)
    if not rules:
        return CurriculumResolution(status="unresolved", exam_scope_id=scope_id, reasons=[*reasons, "schedule_unverified"], **base)
    if not programs:
        missing = any(not rule.program_ids for rule in rules)
        return CurriculumResolution(status="unresolved", exam_scope_id=scope_id,
                                    reasons=[*reasons, "program_document_missing" if missing else "no_program_for_grade"], **base)
    if len(programs) > 1:
        return CurriculumResolution(status="ambiguous", candidate_program_ids=programs, exam_scope_id=scope_id,
                                    reasons=[*reasons, "multiple_programs"], **base)
    return CurriculumResolution(status="resolved", program_ids=programs, candidate_program_ids=programs,
                                exam_scope_id=scope_id, reasons=reasons, **base)


# --- Gözatma ve kapsam -------------------------------------------------------------------------------------------

def applicability(registry: CurriculumRegistryV2, program_id: str) -> dict[str, list[int]]:
    """Programın doğrulanmış uygulama takvimi: öğretim yılı → sınıflar."""
    years: dict[str, set[int]] = defaultdict(set)
    for rule in registry.catalog.application:
        if program_id in rule.program_ids:
            years[rule.academic_year].update(rule.grades)
    return {year: sorted(grades) for year, grades in sorted(years.items())}


def exam_relevance(registry: CurriculumRegistryV2, outcome: OutcomeRecord) -> list[dict]:
    """Doğrulanmış sınav kapsamlarından bu kazanıma bağlananlar. Program sürümü o yıl için doğrulanmadıysa
    ``basis`` yalnız sınıf düzeyidir; kazanımın sınavda soru olarak yer alacağı anlamına gelmez."""
    result = []
    for scope in registry.catalog.exam_scopes:
        if scope.status != "verified" or outcome.grade not in scope.grades:
            continue
        _, programs = scheduled(registry, outcome.subject, scope.academic_year, outcome.grade)
        if programs and outcome.program_id not in programs:
            continue
        result.append({"scope_id": scope.id, "basis": "grade_and_program" if programs else "grade_only_program_unverified"})
    return result


def browse(registry: CurriculumRegistryV2, program_id: str, grade: int) -> list[dict]:
    """Ünite → konu → kazanım ağacı. Resmî kazanım metni öğrenciye dağıtılmaz (hak incelemesi bekliyor)."""
    units = sorted((unit for unit in registry.units.values() if unit.program_id == program_id and unit.grade == grade),
                   key=lambda unit: [int(part) for part in unit.official_code.split(".") if part.isdigit()])
    outcomes = registry.outcomes_for(program_id, grade)
    tree = []
    for unit in (item for item in units if item.level == 1):
        children = [item for item in units if item.parent_id == unit.id]
        def entries(parent_id, attribute):
            return [{"id": item.id, "code": item.official_code, "description_tr": item.description_tr,
                     "description_review": item.description_review, "page": item.page}
                    for item in outcomes if getattr(item, attribute) == parent_id]
        tree.append({"id": unit.id, "code": unit.official_code, "title_tr": unit.title_tr, "discipline": unit.discipline,
                     "topics": [{"id": child.id, "code": child.official_code, "title_tr": child.title_tr,
                                 "discipline": child.discipline, "outcomes": entries(child.id, "topic_id")}
                                for child in children],
                     "outcomes": [] if children else entries(unit.id, "unit_id")})
    return tree


def coverage(registry: CurriculumRegistryV2) -> list[dict]:
    rows = []
    for program in registry.catalog.programs:
        expected = {item.grade: item.count for item in program.expected_counts}
        years = applicability(registry, program.id)
        for grade in program.covered_grades:
            items = registry.outcomes_for(program.id, grade)
            count = len(items)
            rows.append({
                "program_id": program.id, "subject": program.subject.value, "framework": program.framework, "grade": grade,
                "expected": expected.get(grade), "actual": count,
                "missing": None if grade not in expected else max(expected[grade] - count, 0),
                "with_official_text": sum(1 for item in items if item.official_text_tr),
                "with_description": sum(1 for item in items if item.description_tr),
                "reviewed": sum(1 for item in items if item.review_status == "source_verified"),
                "source": "accessed" if program.document.sha256 else "missing",
                "applies": [year for year, grades in years.items() if grade in grades],
            })
    return rows


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
