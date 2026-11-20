"""A paketi: işleme özel çıktı sınırları, reasoning ayarı ve çıktı rezervasyonu."""

import asyncio
import json
import threading
from datetime import UTC, datetime
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsError

from apps.api.app.core.gateway import begin_accounting, end_accounting, parse_response
from apps.api.app.core.operations import DEFAULT_LIMITS, Operation
from apps.api.app.core.settings import Settings
from apps.api.app.core.usage import UsageLimitExceeded, UsageTracker
from apps.api.tests.test_firestore_integration import databases as databases_fixture
from apps.api.tests.fake_openai import raw_responses

databases = databases_fixture


def _client(parse):
    return SimpleNamespace(responses=raw_responses(parse))


@pytest.mark.parametrize("operation", DEFAULT_LIMITS)
@pytest.mark.parametrize("custom", [False, True])
@pytest.mark.asyncio
async def test_operation_reserves_exact_provider_limit(monkeypatch, operation, custom):
    if custom:
        monkeypatch.setenv("TEACHERAI_MAX_OUTPUT_TOKENS_BY_OPERATION", json.dumps({operation: 1800}))
    settings = Settings()
    tracker = Mock()
    parse = AsyncMock(return_value=SimpleNamespace(status="completed", usage=None, output_parsed={"ok": True}))
    token = begin_accounting("req", settings, tracker, "uid")
    try:
        await parse_response(_client(parse), operation, model="fixture")
    finally:
        end_accounting(token)
    expected = 1800 if custom else DEFAULT_LIMITS[operation]
    tracker.reserve_output.assert_called_once_with("uid", expected)
    assert parse.call_args.kwargs["max_output_tokens"] == expected


@pytest.mark.parametrize("value", ['{"vision":127}', '{"lessons":32001}', '{"lesson":512}', '{'])
def test_invalid_operation_config(monkeypatch, value):
    monkeypatch.setenv("TEACHERAI_MAX_OUTPUT_TOKENS_BY_OPERATION", value)
    with pytest.raises((ValidationError, SettingsError)):
        Settings()


def test_legacy_fallback(monkeypatch, caplog):
    monkeypatch.setenv("TEACHERAI_MAX_OUTPUT_TOKENS", "1500")
    monkeypatch.setenv("TEACHERAI_MAX_OUTPUT_TOKENS_BY_OPERATION", '{"vision":256}')
    assert Settings().max_output_tokens_by_operation == {"vision": 256, "interaction": 1500, "lessons": 1500}
    assert "kullanımdan kaldırılıyor" in caplog.text


def test_default_daily_budget_covers_eight_full_lessons():
    settings = Settings()
    assert settings.daily_output_tokens >= 8 * settings.max_output_tokens_by_operation[Operation.LESSONS]


@pytest.mark.parametrize(
    "value",
    [{"vision": "low"}, {"interaction": "none"}, {"lessons": "extreme"}, {"lesson": "low"}],
)
def test_unsupported_effort_rejected(value):
    # Mevcut gpt-4.1-mini reasoning almaz; bilinmeyen seviye ve işlem adı da reddedilir.
    with pytest.raises(ValidationError):
        Settings(reasoning_effort_by_operation=value)


@pytest.mark.asyncio
async def test_reasoning_effort_reaches_provider_only_when_configured():
    settings = Settings(reasoning_effort_by_operation={"lessons": "low"})
    parse = AsyncMock(return_value=SimpleNamespace(status="completed", usage=None, output_parsed={"ok": True}))
    token = begin_accounting("req", settings, Mock(), "uid")
    try:
        await parse_response(_client(parse), "lessons", model=settings.openai_lesson_model)
        assert parse.call_args.kwargs["reasoning"] == {"effort": "low"}
        await parse_response(_client(parse), "vision", model=settings.openai_vision_model)
        assert "reasoning" not in parse.call_args.kwargs
    finally:
        end_accounting(token)


@pytest.mark.asyncio
async def test_effort_for_unsupported_model_never_reserves_or_calls():
    settings = Settings(reasoning_effort_by_operation={"lessons": "low"})
    tracker = Mock()
    parse = AsyncMock()
    token = begin_accounting("req", settings, tracker, "uid")
    try:
        with pytest.raises(ValueError):
            await parse_response(_client(parse), "lessons", model="gpt-4.1-mini")
    finally:
        end_accounting(token)
    tracker.reserve_output.assert_not_called()
    parse.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_operation_name_has_no_silent_fallback():
    with pytest.raises(ValueError):
        await parse_response(_client(AsyncMock()), "interactions", model="fixture")


def test_release_never_drops_counter_below_zero():
    tracker = UsageTracker(Settings(daily_output_tokens=1000))
    key = tracker.reserve_output("uid", 300)
    tracker.release_output(key, 5000)
    assert tracker.output[key] == 0


@pytest.mark.asyncio
async def test_parallel_lesson_requests_never_exceed_daily_output(databases):
    """10 eşzamanlı ders isteği gateway üzerinden, iki ayrı Firestore istemcisiyle."""
    uid = uuid4().hex
    limit = DEFAULT_LIMITS[Operation.LESSONS]
    settings = Settings(daily_output_tokens=limit * 3)
    trackers = [UsageTracker(settings, db) for db in databases]
    key = f"{datetime.now(UTC).date()}_{sha256(uid.encode()).hexdigest()}"
    ref = databases[0].collection("ai_output_usage").document(key)

    samples, stop = [], threading.Event()

    def monitor():
        while not stop.is_set():
            snap = ref.get()
            if snap.exists:
                samples.append(snap.get("output_tokens"))

    watcher = threading.Thread(target=monitor)
    watcher.start()
    release, waiting, rejected = asyncio.Event(), [], []

    async def provider(**params):
        waiting.append(params["max_output_tokens"])
        await release.wait()
        return SimpleNamespace(status="completed", usage=SimpleNamespace(output_tokens=1000), output_parsed={"ok": True})

    async def lesson_request(index):
        token = begin_accounting(f"req-{index}", settings, trackers[index % 2], uid)
        try:
            await parse_response(_client(provider), "lessons", model="fixture")
            return True
        except UsageLimitExceeded:
            rejected.append(index)
            return False
        finally:
            end_accounting(token)

    try:
        tasks = [asyncio.create_task(lesson_request(i)) for i in range(10)]
        for _ in range(600):
            if len(waiting) + len(rejected) == 10:
                break
            await asyncio.sleep(0.05)
        peak = ref.get().get("output_tokens")
        release.set()
        accepted = sum(await asyncio.wait_for(asyncio.gather(*tasks), 30))
    finally:
        release.set()
        stop.set()
        watcher.join()

    assert accepted == 3 and len(rejected) == 7
    assert peak == settings.daily_output_tokens
    assert waiting == [limit] * 3
    assert samples and max(samples) <= settings.daily_output_tokens and min(samples) >= 0
    assert ref.get().get("output_tokens") == 3 * 1000
