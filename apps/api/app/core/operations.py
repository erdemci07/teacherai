"""Sağlayıcı çağrılarının tek ve tip güvenli işlem tanımı.

Ayarlardaki anahtarlar ile gateway'e verilen işlem adları bu enum'dan gelir;
bilinmeyen bir ad sessizce varsayılana düşmez, ValueError fırlatır.
"""

from enum import StrEnum


class Operation(StrEnum):
    VISION = "vision"
    LESSONS = "lessons"
    INTERACTION = "interaction"


DEFAULT_LIMITS = {Operation.VISION: 4096, Operation.INTERACTION: 4096, Operation.LESSONS: 16384}

# Model başına desteklenen reasoning.effort değerleri. Kaynak: OpenAI model
# sayfaları (developers.openai.com/api/docs/models/<model>), 20 Kasım 2026'da
# okundu. Listede olmayan model reasoning parametresi almaz (ör. gpt-4.1-mini).
# Yeni bir sağlayıcı veya model eklendiğinde yalnızca bu tablo genişletilir.
_OPENAI_REASONING = frozenset({"none", "low", "medium", "high", "xhigh", "max"})
REASONING_LEVELS = {
    "gpt-6-luna": _OPENAI_REASONING,
    "gpt-5.6-terra": _OPENAI_REASONING,
}


def validate_effort(model, effort):
    if effort is not None and effort not in REASONING_LEVELS.get(model, frozenset()):
        raise ValueError(f"{model} için desteklenmeyen reasoning effort: {effort}")
