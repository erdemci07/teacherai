from dataclasses import replace

from fastapi.testclient import TestClient

from apps.api.app.core.settings import Settings
from apps.api.app.features.shares.repository import InMemoryShareRepository
from apps.api.app.features.shares.service import ShareService
from apps.api.app.main import create_app
from apps.api.tests.test_feedback import generated_result


def client_with_shares():
    app = create_app(Settings(environment="test", firebase_enabled=False, public_app_url="https://math-ai-07.web.app"))
    repo = InMemoryShareRepository()
    service = ShareService(repo, Settings(environment="test", firebase_enabled=False, public_app_url="https://math-ai-07.web.app"))
    app.state.container = replace(app.state.container, share_service=service)
    return TestClient(app, raise_server_exceptions=False), repo


def share_payload(result=None, **extra):
    value = {"result": (result or generated_result()).model_dump(mode="json")}
    value.update(extra)
    return value


def test_successful_solution_creates_public_share_snapshot():
    client, repo = client_with_shares()

    response = client.post("/api/v1/shares", json=share_payload())

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["share_url"].startswith("https://math-ai-07.web.app/s/")
    assert len(data["share_id"]) >= 10
    assert data["share_id"].isalnum()
    assert len(repo.items) == 1
    snapshot = next(iter(repo.items.values()))
    assert snapshot.status == "published"
    assert snapshot.question_summary
    assert snapshot.lesson_snapshot.content.steps
    assert snapshot.board_snapshot.elements


def test_repeated_share_for_same_solution_reuses_snapshot():
    client, repo = client_with_shares()
    body = share_payload()

    first = client.post("/api/v1/shares", json=body).json()["data"]
    second = client.post("/api/v1/shares", json=body).json()["data"]
    third = client.post("/api/v1/shares", json=share_payload(existing_share_id=first["share_id"])).json()["data"]

    assert first == second == third
    assert len(repo.items) == 1


def test_public_snapshot_excludes_private_feedback_auth_and_image_data():
    client, repo = client_with_shares()
    body = share_payload(user_id="spoof", feedback={"rating": "negative"}, image_bytes="abc")

    assert client.post("/api/v1/shares", json=body).status_code == 422
    response = client.post("/api/v1/shares", json=share_payload())

    assert response.status_code == 200
    dumped = next(iter(repo.items.values())).model_dump(mode="json")
    text = str(dumped).lower()
    assert "user_id" not in text
    assert "email" not in text
    assert "feedback" not in text
    assert "image_bytes" not in text
    assert "authorization" not in text
    assert "api_key" not in text


def test_placeholder_contaminated_content_cannot_be_published():
    result = generated_result()
    result.lesson.content.steps[0].explanation = "Önce {metin buraya} sonra işlemi yap."
    client, repo = client_with_shares()

    response = client.post("/api/v1/shares", json=share_payload(result))

    assert response.status_code == 502
    assert response.json()["error"] == "invalid_lesson_plan"
    assert repo.items == {}


def test_public_share_loads_without_authentication_and_contains_lesson_data():
    client, _ = client_with_shares()
    created = client.post("/api/v1/shares", json=share_payload()).json()["data"]

    response = client.get(f"/api/v1/shares/{created['share_id']}")

    assert response.status_code == 200
    snapshot = response.json()["data"]["snapshot"]
    assert snapshot["lesson_snapshot"]["content"]["steps"]
    assert snapshot["lesson_snapshot"]["content"]["final_answer_expressions"]
    assert snapshot["board_snapshot"]["elements"][-1]["type"] == "final_answer"


def test_crawler_route_returns_real_open_graph_metadata_without_private_data():
    client, _ = client_with_shares()
    created = client.post("/api/v1/shares", json=share_payload()).json()["data"]

    response = client.get(f"/s/{created['share_id']}")

    assert response.status_code == 200
    html = response.text
    assert 'property="og:title"' in html
    assert "TeacherAI bu matematik sorusunu çözdü" in html
    assert 'property="og:description"' in html
    assert 'property="og:image"' in html
    assert 'meta name="robots" content="noindex, follow"' in html
    assert "/shared/?id=" in html
    assert "user_id" not in html
    assert "feedback" not in html
    assert "api_key" not in html


def test_missing_public_share_returns_not_found_without_authentication():
    client, _ = client_with_shares()

    response = client.get("/api/v1/shares/notfound123")
    crawler = client.get("/s/notfound123")

    assert response.status_code == 404
    assert crawler.status_code == 404
