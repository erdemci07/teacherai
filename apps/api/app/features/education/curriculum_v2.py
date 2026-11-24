"""Müfredat Kaydı v2 sözleşmeleri (TA-006).

v1 (``curriculum.CurriculumRegistry``) yalnız 8. sınıf matematiği taşır ve değişmeden çalışır. v2 şunları ayırır:

1. **Program sürümü** (``ProgramVersion``): belgenin kendisi (MEB 2018, Türkiye Yüzyılı Maarif Modeli 2026),
   kapsadığı sınıflar, resmî terim (kazanım / öğrenme çıktısı), belge özeti (sha256) ve hak durumu.
2. **Uygulama takvimi** (``ApplicationRule``): hangi öğretim yılında hangi sınıfta hangi çerçevenin uygulandığı.
   İçerikten ayrıdır; bir programın var olması o yıl okutulduğu anlamına gelmez.
3. **Sınav kapsamı** (``ExamScope``): LGS/TYT/AYT kapsamı okul programından bağımsız sürümlenir. Doğrulanmamış
   kapsam ``unverified`` kalır ve hiçbir kazanımı sınav kapsamına sokmaz.
4. **Kazanım** (``OutcomeRecord``): küresel olarak tekil kimlik ``<program_id>::<resmî kod (ASCII)>``. Aynı resmî
   kod farklı program sürümlerinde çakışmaz. Resmî metin yalnız izinli/eski (TA-005) kayıtta bulunur.

Sağlayıcı çıktısı bu kayıtların hiçbir alanını belirleyemez.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from .base import Contract, Identifier, Label, Subject, Text
from .curriculum import ForbiddenOperation, MethodOperation

Framework = Literal["meb_2018", "tymm"]
# TA-007: okul izleği. Fen lisesi programı hiçbir zaman sessizce genel lise programı yerine kullanılmaz.
Track = Literal["general", "science_high_school", "basic_level"]
Terminology = Literal["kazanim", "ogrenme_ciktisi"]
Exam = Literal["LGS", "TYT", "AYT"]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
AcademicYear = Annotated[str, StringConstraints(pattern=r"^20\d\d-20\d\d$")]
GradeValue = Annotated[int, Field(ge=1, le=12)]

PROGRAM_SUBJECTS = {Subject.MATHEMATICS, Subject.SCIENCE, Subject.PHYSICS, Subject.CHEMISTRY, Subject.BIOLOGY}


def academic_year_valid(value: str) -> bool:
    start, end = (int(part) for part in value.split("-"))
    return end == start + 1


class Citation(Contract):
    """Doğrulanmış bir resmî sayfa veya belge bölümü. ``excerpt_tr`` kısa, kelimesi kelimesine olmayan özettir."""

    url: Label
    title: Label
    accessed: date
    summary_tr: Text


class ProgramDocument(Contract):
    title: Label
    issuer: Label
    detail_url: Label
    file_url: Label
    sha256: Sha256 | None = None
    pdf_pages: int | None = Field(default=None, ge=1, le=2000)
    # Belgede yazılı resmî tarih veya karar. Doğrulanamadıysa None ve ``date_note`` nedenini taşır.
    stated_date: Label | None = None
    date_note: Text | None = None
    accessed: date
    # Belgede lisans/kullanım koşulu ifadesi yok: birebir metnin yeniden kullanımı doğrulanmadı.
    rights: Literal["no_license_statement_found", "license_stated"]
    text_policy: Literal["identifiers_and_headings_only", "legacy_verbatim_pending_review"]

    @model_validator(mode="after")
    def dated_or_explained(self):
        if self.stated_date is None and not self.date_note:
            raise ValueError("Tarihi doğrulanmamış belge nedenini açıklar.")
        return self


class ExpectedCount(Contract):
    grade: GradeValue
    count: int = Field(ge=0, le=500)
    # Sayının okunduğu yer (ör. "Kazanım sayısı ve süre tablosu"). Okunamayan sınıf burada yer almaz.
    location: Label


class ProgramVersion(Contract):
    id: Identifier
    subject: Subject
    framework: Framework
    label: Label
    stage: Literal["ortaokul", "ortaogretim", "ilkokul_ortaokul"]
    document_grades: list[GradeValue] = Field(min_length=1, max_length=13)
    # Kayıtta envanteri çıkarılan sınıflar (belge daha geniş olabilir: ör. 1-8 programının 5-8'i).
    covered_grades: list[GradeValue] = Field(min_length=1, max_length=13)
    terminology: Terminology
    status: Literal["final"]  # taslak yıllık planlar program sürümü olarak kaydedilmez
    document: ProgramDocument
    expected_counts: list[ExpectedCount] = Field(default_factory=list, max_length=13)
    extraction_note: Text
    track: Track = "general"

    @model_validator(mode="after")
    def coherent(self):
        if self.subject not in PROGRAM_SUBJECTS:
            raise ValueError("Program alanı desteklenen öğretim programlarından olmalı.")
        if not set(self.covered_grades) <= set(self.document_grades):
            raise ValueError("Kapsanan sınıf belgenin sınıfları içinde olmalı.")
        if {item.grade for item in self.expected_counts} - set(self.covered_grades):
            raise ValueError("Beklenen sayı yalnız kapsanan sınıf için yazılır.")
        expected = "kazanim" if self.framework == "meb_2018" else "ogrenme_ciktisi"
        if self.terminology != expected:
            raise ValueError("Resmî terim çerçeveyle uyuşmuyor.")
        return self


class ApplicationRule(Contract):
    """Bir öğretim yılında bir sınıfta uygulanan çerçeve. ``evidence`` kanıtın türünü saklar."""

    academic_year: AcademicYear
    stage: Literal["ortaokul", "ortaogretim"]
    grades: list[GradeValue] = Field(min_length=1, max_length=13)
    framework: Framework
    # Uygulanan belge kayıtta yoksa None: çerçeve bilinir ama içerik çözümlenemez.
    program_ids: list[Identifier] = Field(default_factory=list, max_length=16)
    # explicit: resmî metin sınıfı açıkça sayar. by_exclusion: resmî metin yeni programın sınıflarını sayar ve
    # bu sınıf listede yoktur; önceki programın sürdüğü açıkça yazmaz.
    evidence: Literal["explicit", "by_exclusion"]
    citation: Citation
    track: Track = "general"

    @model_validator(mode="after")
    def valid_year(self):
        if not academic_year_valid(self.academic_year):
            raise ValueError("Öğretim yılı ardışık iki yıl olmalı.")
        return self


ScopeStatus = Literal["verified", "derived", "unverified"]


class ExamScope(Contract):
    """Sınav kapsamı katmanlıdır: tarih, sınıf düzeyi, program sürümü ve kazanım düzeyi ayrı doğrulanır.

    ``status`` geriye dönük uyum içindir ve sınıf düzeyi kapsamının doğrulanıp doğrulanmadığını söyler. Program
    sürümü kapsamı ``derived`` ise uygulama takvimi kuralından türetilmiştir. Kazanım düzeyinde ayrıntılı liste
    resmî olarak yayımlanmadıkça ``unverified`` kalır ve kapsam tarihten türetilmez.
    """

    id: Identifier
    exam: Exam
    exam_year: int = Field(ge=2018, le=2100)
    academic_year: AcademicYear
    status: Literal["verified", "unverified"]
    # Kapsamın bağlandığı sınıflar (LGS 2026: "8'inci sınıf öğretim programlarındaki kazanımlar").
    grades: list[GradeValue] = Field(default_factory=list, max_length=13)
    citation: Citation | None = None
    note: Text
    exam_date: date | None = None
    date_status: Literal["verified", "unverified"] = "unverified"
    date_citation: Citation | None = None
    program_scope: ScopeStatus = "unverified"
    outcome_scope: ScopeStatus = "unverified"

    @model_validator(mode="after")
    def verified_has_source(self):
        if (self.status == "verified") != (self.citation is not None):
            raise ValueError("Doğrulanmış kapsam kaynak taşır; doğrulanmamış taşımaz.")
        if self.status == "verified" and not self.grades:
            raise ValueError("Doğrulanmış kapsam sınıf düzeyini belirtir.")
        if (self.date_status == "verified") != (self.date_citation is not None and self.exam_date is not None):
            raise ValueError("Doğrulanmış sınav tarihi tarih ve kaynak taşır.")
        if self.status != "verified" and self.program_scope != "unverified":
            raise ValueError("Sınıf kapsamı doğrulanmadan program kapsamı türetilemez.")
        if self.outcome_scope == "verified" and self.status != "verified":
            raise ValueError("Kazanım kapsamı sınıf kapsamı olmadan doğrulanamaz.")
        return self


class PendingProgram(Contract):
    """Resmî olarak var olduğu bilinen ama kayda alınamayan program belgesi. İçerik uydurulmaz."""

    id: Identifier
    title: Label
    url: Label
    subject: Subject
    framework: Framework
    grades: list[GradeValue] = Field(min_length=1, max_length=13)
    track: Track = "general"
    reason: Literal["http_error", "inconsistent_codes", "extraction_unreliable", "not_downloaded"]
    detail_tr: Text
    checked_on: date


class UnitRecord(Contract):
    id: Identifier
    program_id: Identifier
    grade: GradeValue
    official_code: Label
    level: Literal[1, 2]  # 1: ünite/tema/öğrenme alanı, 2: alt öğrenme alanı/konu
    title_tr: Label
    discipline: Subject
    page: int = Field(ge=1, le=2000)
    parent_id: Identifier | None = None


class OutcomeRecord(Contract):
    id: Identifier
    program_id: Identifier
    subject: Subject
    discipline: Subject
    grade: GradeValue
    track: Label | None = None
    unit_id: Identifier
    topic_id: Identifier | None = None
    # Kararlı konu anahtarı (başlıktan türetilir) ve eşleme takma adları (ör. v1 konu anahtarı).
    topic_key: Identifier
    aliases: list[Identifier] = Field(default_factory=list, max_length=16)
    official_code: Label
    terminology: Terminology
    page: int = Field(ge=1, le=2000)
    # Resmî metin yalnız TA-005'ten korunan birebir kayıtta (hak incelemesi bekliyor).
    official_text_tr: Text | None = None
    # Özgün kısa betimleme (resmî metin değildir). İncelenmeden çalışma zamanı yetkisi taşımaz.
    description_tr: Label | None = None
    description_review: Literal["unreviewed", "approved"] | None = None
    prerequisites: list[Identifier] = Field(default_factory=list, max_length=16)
    related: list[Identifier] = Field(default_factory=list, max_length=16)
    source_status: Literal["sourced", "pending"]
    review_status: Literal["source_verified", "unreviewed"]

    @model_validator(mode="after")
    def coherent(self):
        if not self.id.startswith(f"{self.program_id}::"):
            raise ValueError("Kimlik program sürümüyle başlar.")
        if (self.description_tr is None) != (self.description_review is None):
            raise ValueError("Betimleme inceleme durumunu taşır.")
        if self.source_status == "pending" and self.review_status == "source_verified":
            raise ValueError("Kaynaksız kayıt kaynakla doğrulanmış olamaz.")
        return self


def code_grade(code: str) -> int | None:
    """Resmî koddaki sınıf: ``M.8.1.1.1`` → 8, ``FİZ.9.1.1`` → 9, ``10.1.1.2`` → 10."""
    match = re.match(r"^(?:[^\W\d_]+\.\s?)?(\d{1,2})\.", code)
    return int(match.group(1)) if match else None


class MethodPolicyV2(Contract):
    """TA-006 yöntem politikası. v1 ``MethodPolicy`` buradan geriye dönük üretilmez; v1 kayıt belirlenimci olarak
    v2'ye taşınır. Yalnız ``approved`` ve onay kaydı taşıyan politika kesin kısıt uygular."""

    id: Identifier
    subject: Subject
    topic: Identifier
    framework: Framework | None = None
    program_ids: list[Identifier] = Field(default_factory=list, max_length=8)
    grades: list[GradeValue] = Field(min_length=1, max_length=12)
    prerequisites: list[Identifier] = Field(default_factory=list, max_length=16)
    applicable_when: list[Text] = Field(default_factory=list, max_length=16)
    allowed_operations: list[MethodOperation] = Field(default_factory=list, max_length=64)
    forbidden_operations: list[ForbiddenOperation] = Field(default_factory=list, max_length=32)
    # Bilimsel olarak yanlış değil, düzeye uygunsuz: ayrı tutulur. Bilimsel hata bu listede yer almaz.
    unsuitable_when: list[Text] = Field(default_factory=list, max_length=16)
    preferred_representations: list[Label] = Field(default_factory=list, max_length=16)
    alternatives: list[Identifier] = Field(default_factory=list, max_length=8)
    outcome_ids: list[Identifier] = Field(default_factory=list, max_length=32)
    status: Literal["draft", "approved"]
    authored_by: Literal["claude-draft", "teacher"]
    approved_by: Label | None = None
    legacy_id: Identifier | None = None
    # TA-007: yetkili onay kanıtı. Tarih veya içerik özeti eksik ya da güncel içerikle uyuşmuyorsa politika
    # çalışma zamanında etkin olmaz (``curriculum.methods``).
    approved_on: date | None = None
    approval_digest: Label | None = None

    @model_validator(mode="after")
    def approval_is_explicit(self):
        if (self.status == "approved") != (self.approved_by is not None):
            raise ValueError("Onaylı politika onaylayanı taşır; taslak taşımaz.")
        if self.status == "approved" and self.authored_by == "claude-draft" and self.approved_by.startswith("claude"):
            raise ValueError("AI taslağı kendini onaylayamaz.")
        if set(self.allowed_operations) & {item.operation for item in self.forbidden_operations}:
            raise ValueError("Bir işlem hem izinli hem yasak olamaz.")
        return self


class ProgramFile(Contract):
    """``data/programs/<program_id>.json``: tek programın ünite ve kazanım envanteri."""

    schema_name: Literal["teacherai.curriculum_program"]
    version: Literal["2.0.0"]
    program_id: Identifier
    extraction_tool: Label
    units: list[UnitRecord] = Field(default_factory=list, max_length=4000)
    outcomes: list[OutcomeRecord] = Field(default_factory=list, max_length=4000)


class CurriculumCatalog(Contract):
    """``data/catalog.json``: program sürümleri, uygulama takvimi, sınav kapsamları ve yöntem politikaları."""

    schema_name: Literal["teacherai.curriculum_catalog"]
    version: Literal["2.0.0"]
    programs: list[ProgramVersion] = Field(min_length=1, max_length=256)
    application: list[ApplicationRule] = Field(default_factory=list, max_length=512)
    exam_scopes: list[ExamScope] = Field(default_factory=list, max_length=256)
    policies: list[MethodPolicyV2] = Field(default_factory=list, max_length=1024)
    pending_programs: list[PendingProgram] = Field(default_factory=list, max_length=256)


ResolutionStatus = Literal["resolved", "ambiguous", "unresolved"]
ResolutionReason = Literal[
    "grade_unknown", "subject_unsupported", "schedule_unverified", "program_document_missing", "by_exclusion",
    "academic_year_transition", "graduate_exam_scope", "exam_scope_unverified", "exam_scope_verified",
    "explicit_program", "explicit_program_not_applicable", "multiple_programs", "no_program_for_grade",
    "track_unspecified_general_assumed", "track_specific_program", "track_rule_missing_general_used",
    "multiple_exam_goals",
]


class CurriculumResolution(Contract):
    """Öğrenci bağlamından belirlenimci program seçimi. Belirsizlik açıkça temsil edilir."""

    status: ResolutionStatus
    subject: Subject
    academic_year: AcademicYear
    academic_year_origin: Literal["declared", "server_clock"]
    grade: GradeValue | None = None
    learner_status: Literal["student", "graduate"] | None = None
    exam: Exam | None = None
    # TA-007: birden çok sınav hedefi (ör. TYT ve AYT) kaybolmaz; ``exam`` ilk hedeftir (geriye dönük uyum).
    exams: list[Exam] = Field(default_factory=list, max_length=3)
    exam_scope_ids: list[Identifier] = Field(default_factory=list, max_length=3)
    track: Track | None = None
    program_ids: list[Identifier] = Field(default_factory=list, max_length=8)
    candidate_program_ids: list[Identifier] = Field(default_factory=list, max_length=8)
    exam_scope_id: Identifier | None = None
    reasons: list[ResolutionReason] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def coherent(self):
        if (self.status == "resolved") != (len(self.program_ids) == 1):
            raise ValueError("Çözümlenmiş bağlam tek program taşır.")
        return self


class KnowledgeRef(Contract):
    id: Identifier
    version: int = Field(ge=1, le=1000)
    content_digest: Label


ExclusionReason = Literal["not_runtime_eligible", "exceeds_record_budget", "exceeds_total_budget", "limit_reached",
                          "subject_mismatch"]


class ExcludedKnowledge(Contract):
    id: Identifier
    reason: ExclusionReason


class ContextOutcome(Contract):
    """İsteme giden kazanım özeti: resmî kod ve başlıklar. Resmî metin ve incelenmemiş betimleme gönderilmez."""

    code: Label
    unit_tr: Label
    topic_tr: Label | None = None
    description_tr: Label | None = None


class ContextKnowledge(Contract):
    """Onaylı ve çalışma zamanına uygun bir bilgi girdisinin isteme giden biçimi. Koşul ve istisnalar kırpılmaz:
    sığmayan girdi bütünüyle dışarıda bırakılır (TA-007)."""

    id: Identifier
    version: int = Field(default=1, ge=1, le=1000)
    kind: Label | None = None
    title_tr: Label
    statement_tr: Text
    conditions_tr: list[Text] = Field(default_factory=list, max_length=12)
    assumptions_tr: list[Text] = Field(default_factory=list, max_length=12)
    exceptions_tr: list[Text] = Field(default_factory=list, max_length=12)
    # İsteğe bağlı; bütçe gerektirirse çıkarılır ve köken kaydında "compacted" olarak işaretlenir.
    misconceptions_tr: list[Text] = Field(default_factory=list, max_length=12)


class ContextMethod(Contract):
    """Yetkili öğretmen onaylı yöntem politikasının isteme giden özeti. Taslak politika gönderilmez."""

    policy_id: Identifier
    allowed_operations: list[MethodOperation] = Field(default_factory=list, max_length=64)
    forbidden_operations: list[MethodOperation] = Field(default_factory=list, max_length=32)
    preferred_representations: list[Label] = Field(default_factory=list, max_length=16)


class CurriculumContextPayload(Contract):
    """Ders sağlayıcısına giden sınırlı müfredat bağlamı. Model bu bağlamı kullanabilir; onay veya doğrulama
    durumu belirleyemez."""

    program: Label
    framework: Framework
    academic_year: AcademicYear
    grade: GradeValue
    outcomes: list[ContextOutcome] = Field(default_factory=list, max_length=6)
    knowledge: list[ContextKnowledge] = Field(default_factory=list, max_length=4)
    methods: list[ContextMethod] = Field(default_factory=list, max_length=4)
    authority_tr: Text


class EducationalProvenance(Contract):
    """Bir dersin üretildiği andaki eğitim bağlamının yeniden kurulabilir kaydı. Ders kaydıyla saklanır; kayıt
    veya profil sonradan değişse de eski ders yeniden hesaplanmaz."""

    curriculum_version: Label
    knowledge_version: Label
    resolution: CurriculumResolution
    topic_key: Identifier | None = None
    # "taxonomy" (TA-007): kazanım yalnız taksonomi deseniyle eşlendi (AI taslağı eşleme; incelenmedi).
    match: Literal["topic_key", "alias", "taxonomy", "none"]
    outcome_ids: list[Identifier] = Field(default_factory=list, max_length=6)
    knowledge_ids: list[Identifier] = Field(default_factory=list, max_length=4)
    excluded_draft_knowledge: int = Field(ge=0, le=1000)
    payload_bytes: int = Field(ge=0, le=8192)
    # Seçim anında isteme konması planlanan bağlam. Gerçekten gönderilen düzey ``transmission``'dadır.
    included_in_prompt: bool
    # TA-007 alanları. Eski derslerde yoktur ve geriye dönük doldurulmaz.
    selection_mode: Literal["deterministic_production"] | None = None
    topic_mapping: Literal["structural", "single", "ambiguous", "none"] | None = None
    topic_candidates: list[Identifier] = Field(default_factory=list, max_length=4)
    knowledge_refs: list[KnowledgeRef] = Field(default_factory=list, max_length=4)
    excluded_knowledge: list[ExcludedKnowledge] = Field(default_factory=list, max_length=32)
    compacted_knowledge: list[Identifier] = Field(default_factory=list, max_length=4)
    method_policy_ids: list[Identifier] = Field(default_factory=list, max_length=8)
    inactive_method_policies: int = Field(default=0, ge=0, le=1024)
    verification_capabilities: list[Identifier] = Field(default_factory=list, max_length=16)
    # "normal": seçilen bağlam gönderildi; "emergency": acil sıkıştırmada müfredat/bilgi bağlamı gönderilmedi;
    # "mixed": birden çok çağrıdan en az biri acil düzeydeydi. None: sağlayıcı düzey bildirmedi.
    transmission: Literal["normal", "emergency", "mixed"] | None = None
    transmitted_knowledge_ids: list[Identifier] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def transmitted_subset(self):
        if not set(self.transmitted_knowledge_ids) <= set(self.knowledge_ids):
            raise ValueError("Gönderilen bilgi girdileri seçilenlerin alt kümesidir.")
        if {item.id for item in self.knowledge_refs} - set(self.knowledge_ids):
            raise ValueError("Bilgi sürüm kaydı seçilen girdilerle tutarlı olmalı.")
        return self
