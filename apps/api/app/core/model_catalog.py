"""Model fiyat ve yetenek kataloğu: tek kaynak ``model_catalog.json`` (TA-005B §7).

Uygulama (``Settings.model_prices``, reasoning düzeyleri) ve değerlendirme betikleri yalnız bu dosyayı
okur. Fiyatı olmayan modelin maliyeti hesaplanmaz; production'da böyle bir model reddedilir.
"""

import json
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).with_name("model_catalog.json")


@lru_cache
def catalog() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8"))


def prices() -> dict[str, tuple[float, float, float]]:
    """Model → (girdi, önbellekli girdi, çıktı) USD / milyon token."""
    return {name: (m["usd_per_million_tokens"]["input"], m["usd_per_million_tokens"]["cached_input"],
                   m["usd_per_million_tokens"]["output"])
            for name, m in catalog()["models"].items() if m.get("usd_per_million_tokens")}


def pricing_version() -> str:
    return catalog()["pricing_version"]


def reasoning_levels() -> dict[str, frozenset[str]]:
    return {name: frozenset(m.get("reasoning_efforts") or ()) for name, m in catalog()["models"].items()
            if m.get("reasoning_efforts")}


def provider_of(model: str) -> str | None:
    entry = catalog()["models"].get(model)
    return entry["provider"] if entry else None


# TA-005C: işlem → gereken yetenekler. Katalogda ``true`` doğrulanmış, ``false`` doğrulanmış yokluk,
# ``null``/eksik bilinmiyor demektir.
REQUIRED = {"vision": ("image_input", "structured_outputs"), "lessons": ("text_input", "structured_outputs"),
            "interaction": ("text_input", "structured_outputs")}


def supports(model: str | None, operation) -> bool | None:
    """True: doğrulanmış destek; False: doğrulanmış yokluk; None: katalogda yok veya bilinmiyor."""
    entry = catalog()["models"].get(model or "")
    if not entry:
        return None
    values = [(entry.get("capabilities") or {}).get(name) for name in REQUIRED[str(operation)]]
    if any(value is False for value in values):
        return False
    return True if all(value is True for value in values) else None


def incompatibility(model: str | None, provider: str, operation) -> str | None:
    """Başlangıçta reddedilecek model/sağlayıcı/işlem uyumsuzluğu; yoksa None."""
    owner = provider_of(model or "")
    if owner is not None and owner != provider:
        return f"{model} modeli {owner} sağlayıcısına ait; {provider} adaptörüne atanamaz."
    if supports(model, operation) is False:
        return f"{model} modeli {operation} işleminin gerektirdiği yeteneği ({', '.join(REQUIRED[str(operation)])}) desteklemiyor."
    return None


def lifecycle_notice(model: str) -> str | None:
    """Duyurulmuş kapanış veya kullanımdan kaldırma varsa görünür uyarı metni."""
    life = (catalog()["models"].get(model) or {}).get("lifecycle") or {}
    if not life.get("shutdown"):
        return None
    applies = f" ({life['applies_to']})" if life.get("applies_to") else ""
    replacement = f"; önerilen: {life['replacement']}" if life.get("replacement") else ""
    return f"{model}{applies} için kapanış {life['shutdown']}{replacement}. Kaynak: {life.get('source', 'katalog')}"


def lifecycle_report() -> list[dict]:
    return [{"model": name, **entry["lifecycle"]} for name, entry in sorted(catalog()["models"].items())
            if entry.get("lifecycle")]
