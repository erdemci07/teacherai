from dataclasses import replace

from fastapi.testclient import TestClient

from apps.api.app.core.settings import Settings
from apps.api.app.features.shares.repository import InMemoryShareRepository
from apps.api.app.features.shares.schemas import PublicSolutionSnapshot
from apps.api.app.features.shares.service import ShareService
from apps.api.app.main import create_app
from apps.api.tests.test_feedback import generated_result


class SharedDictRepository(InMemoryShareRepository):
    def __init__(self, items):
        self.items = items


class FailingShareRepository:
    def get(self, share_id: str):
        raise RuntimeError("firestore unavailable")

    def find_by_lesson_plan_id(self, lesson_plan_id: str):
        raise RuntimeError("firestore unavailable")

    def save(self, snapshot: PublicSolutionSnapshot) -> bool:
        raise RuntimeError("firestore unavailable")


class MissingAfterSaveRepository(InMemoryShareRepository):
    def get(self, share_id: str):
        return None


class SaveFailingRepository(InMemoryShareRepository):
    def save(self, snapshot: PublicSolutionSnapshot) -> bool:
        raise RuntimeError("permission denied")


def client_with_shares():
    app = create_app(Settings(environment="test", firebase_enabled=False, public_app_url="https://teacherai-07.web.app", public_share_url_base="https://teacherai-api.example.run.app"))
    repo = InMemoryShareRepository()
    service = ShareService(repo, Settings(environment="test", firebase_enabled=False, public_app_url="https://teacherai-07.web.app", public_share_url_base="https://teacherai-api.example.run.app"))
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
    assert data["share_url"].startswith("https://teacherai-api.example.run.app/s/")
    assert len(data["share_id"]) >= 10
    assert data["share_id"].isalnum()
    assert len(repo.items) == 1
    snapshot = next(iter(repo.items.values()))
    assert snapshot.status == "published"
    assert snapshot.question_summary
    assert snapshot.lesson_snapshot.content.steps
    assert snapshot.board_snapshot.elements


def test_api_does_not_return_url_if_persistence_fails():
    app = create_app(Settings(environment="test", firebase_enabled=False))
    service = ShareService(SaveFailingRepository(), Settings(environment="test", firebase_enabled=False))
    app.state.container = replace(app.state.container, share_service=service)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post("/api/v1/shares", json=share_payload())

    assert response.status_code == 503
    assert response.json()["error"] == "share_storage_error"
    assert "share_url" not in response.text


def test_api_confirms_persisted_record_before_returning_url():
    app = create_app(Settings(environment="test", firebase_enabled=False))
    repo = MissingAfterSaveRepository()
    service = ShareService(repo, Settings(environment="test", firebase_enabled=False))
    app.state.container = replace(app.state.container, share_service=service)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post("/api/v1/shares", json=share_payload())

    assert response.status_code == 503
    assert response.json()["error"] == "share_storage_error"


def test_repeated_share_for_same_solution_reuses_snapshot():
    client, repo = client_with_shares()
    body = share_payload()

    first = client.post("/api/v1/shares", json=body).json()["data"]
    second = client.post("/api/v1/shares", json=body).json()["data"]
    third = client.post("/api/v1/shares", json=share_payload(existing_share_id=first["share_id"])).json()["data"]

    assert first == second == third
    assert len(repo.items) == 1


def test_new_repository_service_instance_can_fetch_persisted_share():
    shared_items = {}
    creator_app = create_app(Settings(environment="test", firebase_enabled=False, public_app_url="https://teacherai-07.web.app", public_share_url_base="https://teacherai-api.example.run.app"))
    creator_service = ShareService(SharedDictRepository(shared_items), Settings(environment="test", firebase_enabled=False, public_app_url="https://teacherai-07.web.app", public_share_url_base="https://teacherai-api.example.run.app"))
    creator_app.state.container = replace(creator_app.state.container, share_service=creator_service)
    creator = TestClient(creator_app, raise_server_exceptions=False)
    created = creator.post("/api/v1/shares", json=share_payload()).json()["data"]

    reader_app = create_app(Settings(environment="test", firebase_enabled=False, public_app_url="https://teacherai-07.web.app", public_share_url_base="https://teacherai-api.example.run.app"))
    reader_service = ShareService(SharedDictRepository(shared_items), Settings(environment="test", firebase_enabled=False, public_app_url="https://teacherai-07.web.app", public_share_url_base="https://teacherai-api.example.run.app"))
    reader_app.state.container = replace(reader_app.state.container, share_service=reader_service)
    reader = TestClient(reader_app, raise_server_exceptions=False)

    response = reader.get(f"/api/v1/shares/{created['share_id']}")

    assert response.status_code == 200
    assert response.json()["data"]["share_id"] == created["share_id"]


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
    assert 'property="og:url" content="https://teacherai-api.example.run.app/s/' in html
    assert 'meta name="robots" content="noindex, follow"' in html
    assert "https://teacherai-07.web.app/shared/?id=" in html
    assert "https://teacherai-07.web.app/solve" in html
    assert "user_id" not in html
    assert "feedback" not in html
    assert "api_key" not in html


def test_missing_public_share_returns_not_found_without_authentication():
    client, _ = client_with_shares()

    response = client.get("/api/v1/shares/notfound123")
    crawler = client.get("/s/notfound123")

    assert response.status_code == 404
    assert crawler.status_code == 404


def test_repository_infrastructure_error_is_5xx_not_fake_not_found():
    app = create_app(Settings(environment="test", firebase_enabled=False))
    service = ShareService(FailingShareRepository(), Settings(environment="test", firebase_enabled=False))
    app.state.container = replace(app.state.container, share_service=service)
    client = TestClient(app, raise_server_exceptions=False)

    api_response = client.get("/api/v1/shares/abc123def45")
    crawler_response = client.get("/s/abc123def45")

    assert api_response.status_code == 503
    assert api_response.json()["error"] == "share_storage_error"
    assert crawler_response.status_code == 503
    assert "not found" not in crawler_response.text.lower()


def test_revoked_record_behaves_as_unavailable_without_deleting_data():
    client, repo = client_with_shares()
    created = client.post("/api/v1/shares", json=share_payload()).json()["data"]
    snapshot = repo.items[created["share_id"]]
    repo.items[created["share_id"]] = snapshot.model_copy(update={"status": "revoked"})

    response = client.get(f"/api/v1/shares/{created['share_id']}")

    assert response.status_code == 404
    assert created["share_id"] in repo.items
    assert repo.items[created["share_id"]].expires_at is None


def test_latex_survives_snapshot_round_trip():
    client, _ = client_with_shares()
    created = client.post("/api/v1/shares", json=share_payload()).json()["data"]

    response = client.get(f"/api/v1/shares/{created['share_id']}")

    text = str(response.json()["data"]["snapshot"])
    assert "x = 4" in text
    assert "final_answer_expressions" in text


def test_production_share_storage_uses_firestore_not_in_memory() -> None:
    container_source = __import__("pathlib").Path("apps/api/app/core/container.py").read_text(encoding="utf-8")
    requirements = __import__("pathlib").Path("apps/api/requirements.txt").read_text(encoding="utf-8")

    assert 'resolved_settings.environment != "test"' in container_source
    assert "FirestoreShareRepository" in container_source
    assert "firebase-admin" in requirements


def test_share_url_defaults_to_request_origin_when_public_share_base_missing():
    app = create_app(Settings(environment="test", firebase_enabled=False, public_app_url="https://teacherai-07.web.app", public_share_url_base=None))
    repo = InMemoryShareRepository()
    service = ShareService(repo, Settings(environment="test", firebase_enabled=False, public_app_url="https://teacherai-07.web.app", public_share_url_base=None))
    app.state.container = replace(app.state.container, share_service=service)
    client = TestClient(app, raise_server_exceptions=False, base_url="https://api.example.run.app")

    response = client.post("/api/v1/shares", json=share_payload())

    assert response.status_code == 200
    assert response.json()["data"]["share_url"].startswith("https://api.example.run.app/s/")
