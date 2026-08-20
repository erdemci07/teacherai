import logging

import httpx
import pytest
from openai import APIConnectionError, AuthenticationError, RateLimitError

import apps.api.app.features.vision.openai_provider as provider_module
from apps.api.app.features.vision.exceptions import (
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)
from apps.api.app.features.vision.openai_provider import OpenAIVisionProvider


class RaisingResponses:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def parse(self, **kwargs):
        raise self.error


class RaisingClient:
    def __init__(self, error: Exception) -> None:
        self.responses = RaisingResponses(error)


def status_error(error_class, status: int, body: dict):
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    response = httpx.Response(status, request=request)
    return error_class("sensitive upstream message", response=response, body=body)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("upstream", "mapped"),
    [
        (status_error(AuthenticationError, 401, {"error": {"type": "invalid_request_error", "code": "invalid_api_key"}}), ProviderAuthenticationError),
        (status_error(RateLimitError, 429, {"error": {"type": "tokens", "code": "insufficient_quota"}}), ProviderRateLimitError),
        (APIConnectionError(request=httpx.Request("POST", "https://api.openai.com/v1/responses")), ProviderUnavailableError),
    ],
)
async def test_openai_errors_are_mapped_and_logged_safely(monkeypatch, caplog, upstream, mapped) -> None:
    api_key = "secret-test-key-that-must-never-appear"
    monkeypatch.setattr(provider_module, "AsyncOpenAI", lambda **kwargs: RaisingClient(upstream))
    provider = OpenAIVisionProvider(api_key=api_key, model="gpt-test-vision", timeout_seconds=1)

    with caplog.at_level(logging.WARNING), pytest.raises(mapped):
        await provider.analyze_image(b"image-content", "image/png", "request-safe-123")

    logs = caplog.text
    assert type(upstream).__name__ in logs
    assert "provider=openai" in logs
    assert "model=gpt-test-vision" in logs
    assert "request_id=request-safe-123" in logs
    assert api_key not in logs
    assert "image-content" not in logs
    assert "sensitive upstream message" not in logs


def test_provider_diagnostics_never_returns_key() -> None:
    provider = OpenAIVisionProvider(api_key="secret-value", model="gpt-test-vision", timeout_seconds=1)
    diagnostic = provider.diagnostics()
    assert diagnostic == {"provider": "openai", "configured": True, "model": "gpt-test-vision"}
    assert "secret-value" not in str(diagnostic)
