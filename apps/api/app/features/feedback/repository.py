from typing import Protocol

from .schemas import FeedbackRecord


class FeedbackRepository(Protocol):
    def get(self, feedback_id: str) -> FeedbackRecord | None: ...
    def save(self, record: FeedbackRecord) -> bool: ...


class InMemoryFeedbackRepository:
    def __init__(self):
        self.items: dict[str, FeedbackRecord] = {}

    def get(self, feedback_id: str) -> FeedbackRecord | None:
        return self.items.get(feedback_id)

    def save(self, record: FeedbackRecord) -> bool:
        created = record.feedback_id not in self.items
        self.items[record.feedback_id] = record
        return created
