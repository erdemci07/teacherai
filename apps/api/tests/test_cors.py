import pytest
from fastapi.testclient import TestClient

from apps.api.app.core.settings import Settings
from apps.api.app.main import create_app


# TA-005: eski proje sitesi canlıda 404 döndüğü ve istemcisi olmadığı için izin listesinden çıkarıldı.
PRODUCTION_ORIGINS = ("https://teacherai-07.web.app",)
RETIRED_ORIGINS = ("https://" + "math-ai" + "-07.web.app",)
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
    assert all(origin in settings.cors_allowed_origins for origin in PRODUCTION_ORIGINS)
    assert all(origin in settings.cors_allowed_origins for origin in LOCAL_ORIGINS)
    create_app(settings)


@pytest.mark.parametrize("origin", PRODUCTION_ORIGINS)
def test_production_origin_preflight_succeeds(origin: str) -> None:
    with TestClient(create_app(Settings(_env_file=None))) as client:
        response = preflight(client, origin)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


@pytest.mark.parametrize("origin", RETIRED_ORIGINS)
def test_retired_project_origin_is_not_allowed_by_default(origin: str) -> None:
    assert origin not in Settings(_env_file=None).cors_allowed_origins
    with TestClient(create_app(Settings(_env_file=None))) as client:
        assert "access-control-allow-origin" not in preflight(client, origin).headers


@pytest.mark.parametrize("origin", LOCAL_ORIGINS)
def test_localhost_preflight_succeeds(origin: str) -> None:
    with TestClient(create_app(Settings(_env_file=None))) as client:
        response = preflight(client, origin)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
