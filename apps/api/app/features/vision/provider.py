from dataclasses import dataclass
from typing import Protocol

from apps.api.app.features.vision.schemas import VisionProviderAnalysis


@dataclass(frozen=True)
class ProviderResult:
    analysis: VisionProviderAnalysis
    provider: str
    model: str
    response_id: str | None = None


class VisionProvider(Protocol):
    name: str
    model: str

    async def analyze_image(self, image: bytes, media_type: str, request_id: str | None = None) -> ProviderResult: ...

    async def health(self) -> bool: ...

    def diagnostics(self) -> dict[str, str | bool]: ...
