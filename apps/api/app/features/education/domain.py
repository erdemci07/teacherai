"""Ders alanındaki kimlikler, bağlam kaynakları ve sunucunun sunduğu yetenekler."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8192)]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]
Identifier = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$")]
Labels = Annotated[list[Label], Field(max_length=64)]


class Subject(StrEnum):
    MATHEMATICS = "mathematics"
    GEOMETRY = "geometry"
    PHYSICS = "physics"
    CHEMISTRY = "chemistry"
    BIOLOGY = "biology"
    SCIENCE = "science"
    UNKNOWN = "unknown"


# Belgelenmiş etiket eşlemesi. Listede olmayan etiket "unknown" kalır; hiçbir etiket sessizce
# matematiğe çevrilmez. (Görsel analizdeki matematik kapısı istisnası math_adapter.understand içindedir.)
_SUBJECTS = {s.value: s for s in Subject} | dict(zip(
    ("matematik", "geometri", "fizik", "kimya", "biyoloji", "fen bilimleri", "fen bilgisi"),
    (Subject.MATHEMATICS, Subject.GEOMETRY, Subject.PHYSICS, Subject.CHEMISTRY, Subject.BIOLOGY, Subject.SCIENCE,
     Subject.SCIENCE),
))


def canonical_subject(value: str) -> Subject:
    key = " ".join(value.replace("İ", "i").casefold().split())
    return _SUBJECTS.get(key, Subject.UNKNOWN)


class Capabilities(Contract):
    representable: bool
    recognition: bool
    generation: bool
    verification: Literal["bounded_math", "unsupported"]
    practice: bool
    rendering: bool


def capabilities(subject: Subject) -> Capabilities:
    math = subject in (Subject.MATHEMATICS, Subject.GEOMETRY)
    known = subject != Subject.UNKNOWN
    return Capabilities(representable=known, recognition=math, generation=math,
                        verification="bounded_math" if math else "unsupported",
                        practice=math, rendering=known)


class Reference(Contract):
    kind: Literal["concept", "outcome", "method", "prerequisite", "curriculum", "source", "learner"]
    key: Identifier
    review: Literal["unreviewed"] = "unreviewed"


Origin = Literal["declared", "profile", "inferred"]


class ContextValue(Contract):
    value: Label
    origin: Origin


class Grade(Contract):
    value: int = Field(ge=5, le=12)
    origin: Literal["declared", "profile"]


class EducationContext(Contract):
    subject: Subject
    language: Label
    system: ContextValue | None = None
    stage: ContextValue | None = None
    grade: Grade | None = None
    academic_year: ContextValue | None = None
    exam: ContextValue | None = None
    references: list[Reference] = Field(default_factory=list, max_length=64)


Activity = Literal["question_solution", "topic_lesson", "worked_example", "guided_practice",
                   "independent_practice", "diagnostic_question", "review"]


class Quantity(Contract):
    value: float = Field(strict=True)
    unit: Label
    label: Label | None = None


class Table(Contract):
    headers: list[Label] = Field(min_length=1, max_length=12)
    rows: list[Annotated[list[Label], Field(min_length=1, max_length=12)]] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def rectangular(self):
        if any(len(row) != len(self.headers) for row in self.rows):
            raise ValueError("Tablo satırı başlık sayısıyla uyuşmuyor.")
        return self


class QuestionUnderstanding(Contract):
    source_id: Label
    status: Literal["educational", "unreadable", "incomplete", "non_educational",
                    "unsupported_subject", "unresolved_subject"]
    context: EducationContext
    secondary_subjects: list[Subject] = Field(default_factory=list, max_length=5)
    question: Text | None = None
    requested: Text | None = None
    facts: list[Text] = Field(default_factory=list, max_length=128)
    choices: list[Text] = Field(default_factory=list, max_length=64)
    expressions: list[Text] = Field(default_factory=list, max_length=128)
    quantities: list[Quantity] = Field(default_factory=list, max_length=64)
    visuals: list[Text] = Field(default_factory=list, max_length=64)
    tables: list[Table] = Field(default_factory=list, max_length=8)
    uncertainties: list[Text] = Field(default_factory=list, max_length=128)


    @model_validator(mode="after")
    def valid_recognition(self):
        if self.status in {"educational", "unsupported_subject"} and not self.question:
            raise ValueError("Tanınan soruda soru metni gereklidir.")
        if self.status == "educational" and self.context.subject == Subject.UNKNOWN:
            raise ValueError("Soru alanı belirlenmemiş.")
        if self.status == "unsupported_subject" and (
            self.context.subject == Subject.UNKNOWN or capabilities(self.context.subject).generation
        ):
            raise ValueError("Alan ve destek durumu çelişiyor.")
        return self
