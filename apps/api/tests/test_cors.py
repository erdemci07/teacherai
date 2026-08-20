import pytest
from fastapi.testclient import TestClient

from apps.api.app.core.settings import Settings
from apps.api.app.main import create_app


PRODUCTION_ORIGIN = "https://math-ai-07.web.app"
LOCAL_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")


def preflight(client: TestClient, origin: str):
    return client.options(
        "/api/v1/vision/analyze",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )


def test_malformed_cors_environment_falls_back_without_startup_failure(monkeypatch) -> None:
    monkeypatch.setenv("TEACHERAI_CORS_ALLOWED_ORIGINS", "this-is-not-json-or-an-origin")
    settings = Settings(_env_file=None)
    assert PRODUCTION_ORIGIN in settings.cors_allowed_origins
    assert all(origin in settings.cors_allowed_origins for origin in LOCAL_ORIGINS)
    create_app(settings)


def test_production_origin_preflight_succeeds() -> None:
    with TestClient(create_app(Settings(_env_file=None))) as client:
        response = preflight(client, PRODUCTION_ORIGIN)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == PRODUCTION_ORIGIN


@pytest.mark.parametrize("origin", LOCAL_ORIGINS)
def test_localhost_preflight_succeeds(origin: str) -> None:
    with TestClient(create_app(Settings(_env_file=None))) as client:
        response = preflight(client, origin)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
