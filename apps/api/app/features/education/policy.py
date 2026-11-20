"""Somut öğrenci sinyalleri ile henüz değerlendirilmemiş öğretim kurallarını ayırır."""

from typing import Literal
from pydantic import Field

from ..memory.schemas import TeachingContext
from .domain import Contract, ContextValue, Grade, Identifier, Label


class TeachingRule(Contract):
    source: Literal["scientific", "curriculum", "platform_policy", "teacher_preference"]
    allowed_methods: list[Identifier] = Field(default_factory=list, max_length=32)
    forbidden_methods: list[Identifier] = Field(default_factory=list, max_length=32)
    required_checks: list[Label] = Field(default_factory=list, max_length=16)


class TeachingPolicy(Contract):
    learner: TeachingContext | None = None
    grade: Grade | None = None
    rules: list[TeachingRule] = Field(default_factory=list, max_length=16)

    def exam_context(self, profile_excerpt: str | None, inferred: str | None) -> ContextValue | None:
        if self.learner and profile_excerpt:
            return ContextValue(value=profile_excerpt, origin="profile")
        return ContextValue(value=inferred, origin="inferred") if inferred else None
