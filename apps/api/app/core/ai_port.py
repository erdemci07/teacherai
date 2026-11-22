"""Sağlayıcıdan bağımsız dar AI portu (TA-005B §7).

Adaptörün işi yalnızca şudur: kanonik isteği sağlayıcı gövdesine çevirmek, çağrıyı yapmak ve ham yanıtı
tek bir sonuca (``Outcome``) ve normalize kullanıma indirmek. Kota, küresel bütçe, çağrı tavanı, token
rezervasyonu, idempotency, hesap silme, sahiplik, şema doğrulaması ve günlükleme ortak katmandadır
(``core/gateway.py``, ``core/admission.py``, ``core/usage.py``).

Adaptör ortak katmanı atlayamaz: ``ProviderAdapter.send`` yalnız geçidin o istek için bir kez verdiği
``Admission`` ile çalışır. Geçit bu belgeyi çağrı tavanı denetimi ve token rezervasyonundan sonra üretir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from .ai_outcomes import Outcome
from .operations import Operation


@dataclass(frozen=True)
class TextPart:
    text: str


@dataclass(frozen=True)
class ImagePart:
    data: bytes = field(repr=False)
    media_type: str
    detail: str = "high"


@dataclass(frozen=True)
class ProviderRequest:
    """Kanonik istek. ``max_output_tokens`` ve ``reasoning`` ortak katmanda işleme göre doldurulur."""

    operation: Operation
    model: str
    user: str | tuple[TextPart | ImagePart, ...] | None = None
    system: str | None = None
    schema: type[BaseModel] | None = None
    timeout: float | None = None
    max_output_tokens: int | None = None
    reasoning: str | None = None

    @property
    def has_images(self) -> bool:
        return isinstance(self.user, tuple) and any(isinstance(part, ImagePart) for part in self.user)


@dataclass(frozen=True)
class Usage:
    """Normalize kullanım. Sağlayıcının vermediği alan ``None`` kalır; tahmin edilmez."""

    input: int | None = None
    cached_input: int | None = None
    output: int | None = None
    reasoning: int | None = None


@dataclass
class AdapterResult:
    outcome: Outcome
    text: str | None = None  # yalnız COMPLETED: şemaya göre doğrulanacak JSON metni
    reason: str | None = None
    usage: Usage = field(default_factory=Usage)
    model: str | None = None
    status: str | None = None
    response_id: str | None = None
    provider_request_id: str | None = None
    raw_usage: dict[str, Any] = field(default_factory=dict)


class AdmissionRequired(RuntimeError):
    """Adaptör ortak katmandan (geçit) geçmeden çağrıldı."""


class Admission:
    """Geçidin tek istek için verdiği tek kullanımlık geçiş belgesi."""

    __slots__ = ("_request", "_used")

    def __init__(self, request: ProviderRequest, *, _issuer: object):
        if _issuer is not _ISSUER:
            raise AdmissionRequired("Admission yalnız geçit tarafından üretilir.")
        self._request, self._used = request, False

    def consume(self, request: ProviderRequest) -> None:
        if self._used or self._request is not request:
            raise AdmissionRequired("Admission bu istek için değil ya da kullanıldı.")
        self._used = True


_ISSUER = object()


def issue(request: ProviderRequest) -> Admission:
    """Yalnız ``core/gateway.py`` çağırır."""
    return Admission(request, _issuer=_ISSUER)


class ProviderAdapter:
    """Adaptör tabanı. Alt sınıf ``_send``'i uygular; ``send`` geçiş belgesini denetler."""

    name = "abstract"
    operations: frozenset[Operation] = frozenset()

    async def send(self, request: ProviderRequest, admission: Admission) -> AdapterResult:
        if not isinstance(admission, Admission):
            raise AdmissionRequired("Sağlayıcı çağrısı yalnız geçitten yapılır.")
        admission.consume(request)
        if request.operation not in self.operations:
            raise AdmissionRequired(f"{self.name} {request.operation} işlemini desteklemiyor.")
        return await self._send(request)

    async def _send(self, request: ProviderRequest) -> AdapterResult:
        raise NotImplementedError
