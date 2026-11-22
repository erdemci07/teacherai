"""Sağlayıcıların gerçekte desteklediği işlemler (TA-005B §7–8).

Bir işlem yalnız adaptörü o işlemin şemasını ve girdisini gerçekten destekliyorsa listelenir. Listede
olmayan bir işleme sağlayıcı atanırsa ``Settings`` uygulamayı başlatmaz. Fallback yoktur.
"""

from .operations import Operation

SUPPORTED_OPERATIONS: dict[str, frozenset[Operation]] = {
    "openai": frozenset(Operation),
    # TA-005B P3 tamamlanmadı: Anthropic adaptörü yok; hiçbir işlem atanamaz (TA-005C).
    "anthropic": frozenset(),
}


def adapter_classes():
    """Kayıtlı adaptör sınıfları; geçiş belgesi testi her birini sınar."""
    from .openai_adapter import OpenAIAdapter

    return {"openai": OpenAIAdapter}
