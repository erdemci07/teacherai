from pathlib import Path
from typing import Protocol
from uuid import uuid4


class TemporaryImageStorage(Protocol):
    async def save(self, content: bytes, suffix: str) -> Path: ...

    async def delete(self, path: Path) -> None: ...


class LocalTemporaryImageStorage:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    async def save(self, content: bytes, suffix: str) -> Path:
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._directory / f"{uuid4().hex}.{suffix}"
        path.write_bytes(content)
        return path

    async def delete(self, path: Path) -> None:
        path.unlink(missing_ok=True)
