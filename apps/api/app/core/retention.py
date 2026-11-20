"""Firestore saklama süreleri ve UTC zaman damgaları."""

from datetime import UTC, datetime, timedelta

ANALYSES = "lesson_analyses"
PRACTICE = "practice_questions"
DAILY = "ai_daily_usage"
OUTPUT = "ai_output_usage"
GLOBAL = "ai_global_usage"
DELETIONS = "account_deletions"
TTL_DAYS = {ANALYSES: 1, PRACTICE: 7, DAILY: 30, OUTPUT: 30, GLOBAL: 30, DELETIONS: 30}


def timestamp(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def retention(collection, created=None):
    start = timestamp(created) if created is not None else datetime.now(UTC)
    return {"created_at": start, "expires_at": start + timedelta(days=TTL_DAYS[collection])}


def expired(document):
    deadline = document.get("expires_at")
    return deadline is not None and timestamp(deadline) <= datetime.now(UTC)
