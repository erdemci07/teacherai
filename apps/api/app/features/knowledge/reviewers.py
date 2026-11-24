"""Proje sahibinin yönettiği inceleyen yetki kaydı (TA-007).

Üretim kaydı (``data/reviewers.json``) boştur: TA-007'de hiçbir gerçek öğretmen yetkilendirilmedi. Sentetik
yetkiler yalnız yalıtılmış testlerde fikstürle verilir; üretim kaydına yazılmaz.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

from ..education.base import Subject
from ..education.knowledge import ReviewerAuthorization, ReviewerRegistryFile

DATA = Path(__file__).with_name("data") / "reviewers.json"


def load(path: Path = DATA) -> tuple[ReviewerAuthorization, ...]:
    return tuple(ReviewerRegistryFile.model_validate_json(path.read_bytes()).reviewers)


@lru_cache
def default_reviewers() -> tuple[ReviewerAuthorization, ...]:
    return load()


def authorized(reviewers, reviewer: str | None, stage: str, subject: Subject, role: str, on: date | None) -> bool:
    """İnceleyen, proje sahibinin kaydında bu aşama, alan, rol ve tarih için yetkili mi? Tarih yoksa hayır."""
    if reviewer is None or on is None:
        return False
    return any(item.reviewer == reviewer and item.allows(stage, subject, role, on) for item in reviewers)
