"""Müfredat gözatma ve bağlam çözümleme uçları (TA-006). Salt okunur; sağlayıcı çağrısı, kota veya Firestore yok.

Resmî kazanım metni öğrenciye dağıtılmaz (yeniden kullanım izni doğrulanmadı); yalnız resmî kod, başlık, sayfa
ve varsa özgün, inceleme durumu belirtilmiş betimleme döner.
"""

from datetime import date, datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from apps.api.app.features.auth.dependencies import require_user
from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.schemas.responses import ApiResponse

from ..education.base import Subject
from ..education.curriculum_v2 import CurriculumResolution
from ..education.domain import Capabilities, capabilities
from ..education.lesson_intent import MODE_PHASE, ModeSupport, mode_support
from ..knowledge import registry as knowledge_registry
from . import registry_v2

router = APIRouter(prefix="/curriculum", tags=["curriculum"])
User = Annotated[AuthenticatedUser, Depends(require_user)]
SUBJECTS = (Subject.MATHEMATICS, Subject.SCIENCE, Subject.PHYSICS, Subject.CHEMISTRY, Subject.BIOLOGY)
RIGHTS_NOTICE = ("Resmî kazanım metni gösterilmez: yeniden kullanım izni doğrulanmadı. Kod ve başlıklar resmî "
                 "programdan, betimlemeler özgün taslaktır.")


class ProgramSummary(BaseModel):
    id: str
    label: str
    subject: Subject
    framework: str
    terminology: str
    covered_grades: list[int]
    document_title: str
    document_url: str
    applies: dict[str, list[int]]
    outcome_count: int


class SubjectSummary(BaseModel):
    subject: Subject
    capabilities: Capabilities
    modes: list[ModeSupport]


class CatalogView(BaseModel):
    curriculum_version: str
    knowledge_version: str
    programs: list[ProgramSummary]
    subjects: list[SubjectSummary]
    rights_notice: str


class BrowseOutcome(BaseModel):
    id: str
    code: str
    description_tr: str | None
    description_review: str | None
    page: int


class BrowseTopic(BaseModel):
    id: str
    code: str
    title_tr: str
    discipline: Subject
    outcomes: list[BrowseOutcome]


class BrowseUnit(BaseModel):
    id: str
    code: str
    title_tr: str
    discipline: Subject
    topics: list[BrowseTopic]
    outcomes: list[BrowseOutcome]


class BrowseView(BaseModel):
    program: ProgramSummary
    grade: int
    units: list[BrowseUnit]
    knowledge_drafts: int
    rights_notice: str


def _summary(registry, program) -> ProgramSummary:
    return ProgramSummary(id=program.id, label=program.label, subject=program.subject, framework=program.framework,
                          terminology=program.terminology, covered_grades=program.covered_grades,
                          document_title=program.document.title, document_url=program.document.detail_url,
                          applies=registry_v2.applicability(registry, program.id),
                          outcome_count=len(registry.outcomes_for(program.id)))


def _cache(response: Response):
    response.headers["Cache-Control"] = "private, max-age=300"


@router.get("/catalog", response_model=ApiResponse[CatalogView])
def catalog(response: Response, user: User):
    registry = registry_v2.default_registry()
    knowledge = knowledge_registry.default_knowledge()
    _cache(response)
    return ApiResponse(data=CatalogView(
        curriculum_version=registry.version, knowledge_version=knowledge.version,
        programs=[_summary(registry, program) for program in registry.catalog.programs],
        subjects=[SubjectSummary(subject=subject, capabilities=capabilities(subject),
                                 modes=[mode_support(mode, subject) for mode in MODE_PHASE]) for subject in SUBJECTS],
        rights_notice=RIGHTS_NOTICE))


@router.get("/programs/{program_id}/grades/{grade}", response_model=ApiResponse[BrowseView])
def browse(program_id: str, grade: int, response: Response, user: User):
    registry = registry_v2.default_registry()
    program = registry.programs.get(program_id)
    if program is None or grade not in program.covered_grades:
        raise HTTPException(404, "Program veya sınıf bulunamadı.")
    knowledge = knowledge_registry.default_knowledge()
    outcome_ids = {item.id for item in registry.outcomes_for(program_id, grade)}
    drafts = sum(1 for entry in knowledge.entries.values() if outcome_ids & set(entry.outcome_refs))
    _cache(response)
    return ApiResponse(data=BrowseView(program=_summary(registry, program), grade=grade,
                                       units=registry_v2.browse(registry, program_id, grade),
                                       knowledge_drafts=drafts, rights_notice=RIGHTS_NOTICE))


@router.get("/resolve", response_model=ApiResponse[CurriculumResolution])
def resolve(user: User, subject: Subject = Subject.MATHEMATICS, grade: Annotated[int | None, Query(ge=5, le=12)] = None,
            academic_year: Annotated[str | None, Query(pattern=r"^20\d\d-20\d\d$")] = None,
            learner_status: Literal["student", "graduate"] | None = None,
            exam: Literal["LGS", "TYT", "AYT"] | None = None):
    """Yalnız istekte açıkça verilen bağlamla çözümler; sınıf veya mezuniyet tahmin edilmez."""
    today: date = datetime.now(timezone.utc).date()
    return ApiResponse(data=registry_v2.resolve(registry_v2.default_registry(), subject, grade, today=today,
                                                academic_year=academic_year, learner_status=learner_status, exam=exam))
