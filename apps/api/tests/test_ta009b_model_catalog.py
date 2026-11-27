"""TA-009B §2: model kataloğu, kademeli fiyat ve kapanış denetimi (çevrimdışı; sağlayıcı çağrısı yok)."""

from datetime import date

import pytest
from pydantic import ValidationError

from apps.api.app.core import gateway, model_catalog
from apps.api.app.core import settings as settings_module
from apps.api.app.core.operations import Operation
from apps.api.app.core.settings import Settings

PRODUCTION = {"_env_file": None, "environment": "production", "firebase_project_id": "p", "firebase_auth_project_id": "p"}


def _cost(model, prompt, cached=0, output=1000, settings=None):
    event = {"model": model, "input_tokens": prompt, "cached_tokens": cached, "output_tokens": output}
    gateway._price(event, settings or Settings(_env_file=None))
    return event.get("estimated_usd")


def test_new_openai_models_are_catalogued_with_verified_capabilities():
    entries = model_catalog.catalog()["models"]
    for name in ("gpt-6.1-terra", "gpt-6.2-sol"):
        assert entries[name]["provider"] == "openai"
        assert all(model_catalog.supports(name, op) is True for op in Operation)
    assert "none" not in model_catalog.reasoning_levels()["gpt-6.2-sol"]
    assert model_catalog.prices()["gpt-6.1-terra"] == (1.0, 0.05, 5.0)
    assert model_catalog.prices()["gpt-6-luna"] == (0.1, 0.01, 0.5)  # Standard; 0,05/0,25 Batch/Flex tablosudur


def test_haiku_tier_is_chosen_by_real_prompt_tokens():
    low = _cost("claude-haiku-5-5", 100_000, output=1_000)
    high = _cost("claude-haiku-5-5", 100_001, output=1_000)
    assert low == pytest.approx((100_000 * 0.1 + 1_000 * 0.5) / 1_000_000)
    assert high == pytest.approx((100_001 * 0.5 + 1_000 * 2.5) / 1_000_000)  # isteğin tamamı yüksek kademe
    cached = _cost("claude-haiku-5-5", 150_000, cached=120_000)
    assert cached == pytest.approx((30_000 * 0.5 + 120_000 * 0.05 + 1_000 * 2.5) / 1_000_000)


def test_openai_long_context_tier_and_unknown_prompt():
    assert _cost("gpt-6-luna", 272_001, output=0) == pytest.approx(272_001 * 0.2 / 1_000_000)
    assert _cost("gpt-6-luna", 272_000, output=0) == pytest.approx(272_000 * 0.1 / 1_000_000)
    assert _cost("claude-haiku-5-5", None) is None  # kademe seçilemez; maliyet uydurulmaz


def test_overridden_price_is_single_tier():
    settings = Settings(_env_file=None, model_prices={"claude-haiku-5-5": (1, 0.5, 2)})
    assert "claude-haiku-5-5" not in settings.model_price_tiers
    assert _cost("claude-haiku-5-5", 200_000, output=0, settings=settings) == pytest.approx(200_000 / 1_000_000)


def test_production_accepts_tier_priced_haiku():
    ok = Settings(**PRODUCTION, openai_api_key="k", provider_lesson="anthropic", anthropic_api_key="k",
                  anthropic_lesson_model="claude-haiku-5-5")
    assert ok.model_for(Operation.LESSONS) == "claude-haiku-5-5"


def test_shutdown_warns_within_30_days_and_blocks_after(monkeypatch, caplog):
    assert model_catalog.shutdown_problems(["gpt-4.1-mini"], date(2026, 11, 27)) == ([], [])
    warn, block = model_catalog.shutdown_problems(["gpt-4.1-mini"], date(2026, 12, 20))
    assert warn and not block and "25 gün" in warn[0]
    warn, block = model_catalog.shutdown_problems(["gpt-4.1-mini"], date(2027, 1, 15))
    assert block and not warn
    monkeypatch.setattr(settings_module, "_today", lambda: date(2026, 12, 20))
    Settings(_env_file=None)
    assert "Model kapanışı yaklaşıyor" in caplog.text
    monkeypatch.setattr(settings_module, "_today", lambda: date(2027, 1, 15))
    with pytest.raises(ValidationError, match="Kapanmış model"):
        Settings(_env_file=None)
    Settings(_env_file=None, openai_vision_model="gpt-6-luna", openai_interaction_model="gpt-6-luna")


def test_defaults_unchanged_until_measurement():
    settings = Settings(_env_file=None)
    assert settings.openai_lesson_model == "gpt-5.6-terra"
    assert settings.openai_interaction_model == "gpt-4.1-mini"
    assert settings.pricing_version == "catalog-2026-11-27"
