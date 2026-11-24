"""Sağlayıcıların gerçekte desteklediği işlemler (TA-005B §7–8, TA-005C §1).

Bir işlem yalnız adaptörü o işlemin şemasını ve girdisini gerçekten destekliyorsa listelenir. Listede
olmayan bir işleme sağlayıcı atanırsa ``Settings`` uygulamayı başlatmaz. Fallback yoktur.
"""

from .operations import Operation

SUPPORTED_OPERATIONS: dict[str, frozenset[Operation]] = {
    "openai": frozenset(Operation),
    # TA-005C: üç işlem de Anthropic'te desteklenir. Vision (minimum/maximum) ve etkileşim (minLength)
    # şemaları onaylı izdüşümle gönderilir; sınırlar geçitte özgün Pydantic modeliyle uygulanır
    # (core/schema_compat.APPROVED_PROJECTIONS, scripts/anthropic_schema_compat.py --check).
    # Vision için ayrıca TEACHERAI_ALLOW_STUDENT_IMAGES_TO_ANTHROPIC gerekir (Settings.providers).
    "anthropic": frozenset(Operation),
}


def adapter_classes():
    """Kayıtlı adaptör sınıfları; geçiş belgesi testi her birini sınar."""
    from .anthropic_adapter import AnthropicAdapter
    from .openai_adapter import OpenAIAdapter

    return {"openai": OpenAIAdapter, "anthropic": AnthropicAdapter}
