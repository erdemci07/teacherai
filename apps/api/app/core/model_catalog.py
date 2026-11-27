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


def tiers() -> dict[str, tuple[tuple[int, tuple[float, float, float]], ...]]:
    """TA-009B §2: model → ((istem eşiği, (girdi, önbellekli, çıktı)), ...). İstem token sayısı eşiği *aşarsa*
    isteğin tamamı o kademeden fiyatlanır (Haiku 5.5: 100.000; OpenAI uzun bağlam: 272.000)."""
    out = {}
    for name, m in catalog()["models"].items():
        rows = [(t["above_prompt_tokens"], (t["usd_per_million_tokens"]["input"], t["usd_per_million_tokens"]["cached_input"],
                                            t["usd_per_million_tokens"]["output"])) for t in m.get("tiers") or ()]
        if rows and m.get("usd_per_million_tokens"):
            out[name] = tuple(sorted(rows))
    return out


def rates_for(model: str, prompt_tokens: int | None, base: dict, tiered: dict) -> tuple[float, float, float] | None:
    """İsteğin gerçek istem token sayısına göre fiyat kademesi. Kademeli modelde istem sayısı bilinmiyorsa
    kademe seçilemez ve maliyet uydurulmaz (None)."""
    rates = base.get(model)
    steps = tiered.get(model) or ()
    if rates is None or not steps:
        return rates
    if prompt_tokens is None:
        return None
    for threshold, step in steps:
        if prompt_tokens > threshold:
            rates = step
    return rates


def shutdown_problems(models, today) -> tuple[list[str], list[str]]:
    """TA-009B §2: (uyarılar, engeller). Kapanışa 30 günden az kalan model uyarı; kapanış günü geçmiş model
    başlatmayı engeller. ``applies_to`` yalnız bilgi amaçlıdır; takma adın da kapanacağı varsayılır."""
    from datetime import date

    warnings, blockers = [], []
    for model in sorted(set(models)):
        life = (catalog()["models"].get(model) or {}).get("lifecycle") or {}
        if not life.get("shutdown"):
            continue
        left = (date.fromisoformat(life["shutdown"]) - today).days
        if left < 0:
            blockers.append(f"{model} kapanış tarihi {life['shutdown']} geçti; önerilen: {life.get('replacement') or 'yok'}.")
        elif left < 30:
            warnings.append(f"{model} için kapanışa {left} gün kaldı ({life['shutdown']}).")
    return warnings, blockers


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
