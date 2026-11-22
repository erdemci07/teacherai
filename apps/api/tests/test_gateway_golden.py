"""TA-005B §7 altın testleri: üç işlemin OpenAI'ye giden HTTP istek gövdesi bayt bayt sabittir.

Gerçek ``openai`` SDK'sı ağsız bir ``httpx.MockTransport`` ile kullanılır; istek yakalanır ve 400 ile
kesilir, hiçbir ağ çağrısı yapılmaz. Altın dosyalar adaptör refactor'undan **önce**, o günkü kodla
üretildi (``python -m apps.api.tests.test_gateway_golden --write``). Gövde; model, input,
``text.format`` şeması, ``max_output_tokens``, reasoning, ``store`` ve ``metadata`` (yok) alanlarını taşır.
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import Mock

import httpx
import openai
import pytest

from apps.api.app.core.gateway import begin_accounting, end_accounting
from apps.api.app.core.settings import Settings

GOLDEN = Path(__file__).parent / "fixtures" / "golden"
IMAGE = b"\x89PNG\r\n\x1a\nTA005B-golden"


def _client_factory(captured):
    def handler(request: httpx.Request):
        captured.append({"method": request.method, "path": request.url.path, "body": request.content.decode()})
        return httpx.Response(400, json={"error": {"message": "golden capture", "type": "invalid_request_error"}})

    def factory(**kwargs):
        return openai.AsyncOpenAI(**kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    return factory


async def _capture(name, monkeypatch):
    captured = []
    factory = _client_factory(captured)
    if name == "vision":
        from apps.api.app.features.vision.openai_provider import OpenAIVisionProvider

        provider = OpenAIVisionProvider("golden-key", "gpt-4.1-mini", 30, client_factory=factory)
        from apps.api.app.features.vision.exceptions import InvalidProviderResponseError as expected

        call = provider.analyze_image(IMAGE, "image/png", "req_golden")
        settings = Settings()
    elif name == "lessons":
        from apps.api.app.features.lessons import openai_provider
        from apps.api.app.features.lessons.exceptions import InvalidLessonPlanError as expected
        from apps.api.tests.test_curriculum import linear_analysis

        monkeypatch.setattr(openai_provider, "AsyncOpenAI", factory)
        provider = openai_provider.OpenAILessonProvider("golden-key", "gpt-6-luna", 30)
        call = provider.generate_lesson_plan(linear_analysis(), request_id="req_golden")
        settings = Settings(reasoning_effort_by_operation={"lessons": "medium"})
    else:
        from apps.api.app.features.interactions.openai_provider import OpenAIInteractionProvider
        from apps.api.app.features.interactions.exceptions import InvalidInteractionResponseError as expected
        from apps.api.tests.test_mathai import plan

        provider = OpenAIInteractionProvider("golden-key", "gpt-4.1-mini", 30, client_factory=factory)
        call = provider.adapt("hint", plan(), 1)
        settings = Settings()
    token = begin_accounting("req_golden", settings, Mock(), "uid-golden")
    try:
        with pytest.raises(expected):  # yakalama 400 ile kesilir
            await call
    finally:
        end_accounting(token)
    assert len(captured) == 1, captured
    return captured[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["vision", "lessons", "interaction"])
async def test_outgoing_request_body_is_byte_identical(name, monkeypatch):
    captured = await _capture(name, monkeypatch)
    golden = json.loads((GOLDEN / f"{name}.json").read_text(encoding="utf-8"))
    assert captured["method"] == golden["method"] == "POST" and captured["path"] == golden["path"] == "/v1/responses"
    assert captured["body"] == golden["body"]  # bayt bayt
    body = json.loads(captured["body"])
    assert body["store"] is False and "metadata" not in body and body["text"]["format"]["type"] == "json_schema"
    assert ("reasoning" in body) == (name == "lessons")


def _write():
    """Altın dosya üretimi; yalnız elle çalıştırılır."""
    GOLDEN.mkdir(parents=True, exist_ok=True)
    patcher = pytest.MonkeyPatch()
    try:
        for name in ("vision", "lessons", "interaction"):
            captured = asyncio.run(_capture(name, patcher))
            (GOLDEN / f"{name}.json").write_text(json.dumps(captured, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    finally:
        patcher.undo()


if __name__ == "__main__" and "--write" in sys.argv:
    _write()
