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
