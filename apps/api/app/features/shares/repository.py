from typing import Protocol

from .schemas import PublicSolutionSnapshot


class ShareRepository(Protocol):
    def get(self, share_id: str) -> PublicSolutionSnapshot | None: ...
    def find_by_lesson_plan_id(self, lesson_plan_id: str) -> PublicSolutionSnapshot | None: ...
    def save(self, snapshot: PublicSolutionSnapshot, owner_id: str | None = None) -> bool: ...


class InMemoryShareRepository:
    def __init__(self):
        self.items: dict[str, PublicSolutionSnapshot] = {}

    def get(self, share_id: str) -> PublicSolutionSnapshot | None:
        return self.items.get(share_id)

    def find_by_lesson_plan_id(self, lesson_plan_id: str) -> PublicSolutionSnapshot | None:
        for item in self.items.values():
            if item.source_lesson_plan_id == lesson_plan_id and item.status == "published" and not item.unpublished_at:
                return item
        return None

    def save(self, snapshot: PublicSolutionSnapshot, owner_id: str | None = None) -> bool:
        # Bellek içi depo yalnız testler içindir; hesap silme kalıcı depolama gerektirir.
        created = snapshot.share_id not in self.items
        self.items[snapshot.share_id] = snapshot
        return created
