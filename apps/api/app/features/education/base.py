"""Eğitim sözleşmelerinin ortak temel tipleri. domain ve source modülleri bunları paylaşır."""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


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
