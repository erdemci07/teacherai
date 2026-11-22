"""Sağlayıcıların gerçekte desteklediği işlemler (TA-005B §7–8).

Bir işlem yalnız adaptörü o işlemin şemasını ve girdisini gerçekten destekliyorsa listelenir. Listede
olmayan bir işleme sağlayıcı atanırsa ``Settings`` uygulamayı başlatmaz. Fallback yoktur.
"""

from .operations import Operation

SUPPORTED_OPERATIONS: dict[str, frozenset[Operation]] = {
    "openai": frozenset(Operation),
    # Yalnız şeması Anthropic kısıtlarına uyan işlem (scripts/anthropic_schema_compat.py --check).
    # Vision (minimum/maximum) ve etkileşim (minLength) şemaları uyumsuzdur; kısıtlar sessizce atılmaz.
    "anthropic": frozenset({Operation.LESSONS}),
}


def adapter_classes():
    """Kayıtlı adaptör sınıfları; geçiş belgesi testi her birini sınar."""
    from .anthropic_adapter import AnthropicAdapter
    from .openai_adapter import OpenAIAdapter

    return {"openai": OpenAIAdapter, "anthropic": AnthropicAdapter}
