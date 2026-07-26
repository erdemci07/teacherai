from fastapi.testclient import TestClient

from apps.api.app.main import create_app


def test_health_endpoint_returns_structured_response() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["status"] == "ok"
    assert payload["data"]["service"] == "TeacherAI API"


def test_version_endpoint_returns_configured_version() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/version")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["version"] == "0.1.0"
