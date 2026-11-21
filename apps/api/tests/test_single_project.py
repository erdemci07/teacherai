"""TA-005 tek proje ayarları, bakım modu ve eski bağlantı yönlendirmesi."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.api.app.core.settings import Settings
from apps.api.app.main import create_app


def test_no_default_project_and_production_requires_equal_ids():
    assert Settings(_env_file=None).firebase_project_id is None
    for ids in ({}, {"firebase_project_id": "teacherai-07"}, {"firebase_project_id": "teacherai-07", "firebase_auth_project_id": "other"}):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, environment="production", **ids)
    ok = Settings(_env_file=None, environment="production", firebase_project_id="teacherai-07", firebase_auth_project_id="teacherai-07")
    assert ok.firebase_project_id == ok.firebase_auth_project_id == "teacherai-07"


def test_cloud_run_refuses_development_default(monkeypatch):
    from apps.api.app.core.container import build_container

    monkeypatch.setenv("K_SERVICE", "teacherai-api")
    with pytest.raises(RuntimeError, match="TEACHERAI_ENVIRONMENT"):
        build_container(Settings(_env_file=None, environment="development"))


def client(**settings):
    return TestClient(create_app(Settings(_env_file=None, environment="test", firebase_enabled=False, **settings)),
                      follow_redirects=False)


def test_read_only_blocks_writes_with_retry_after_but_keeps_reads():
    with client(maintenance_mode="read_only") as api:
        blocked = api.post("/api/v1/lessons/generate", json={"analysis_id": "a1"}, headers={"Authorization": "Bearer student-a"})
        assert blocked.status_code == 503 and blocked.headers["Retry-After"] == "900"
        assert blocked.json()["error"] == "maintenance_read_only"
        assert api.get("/api/v1/health").status_code == 200
        assert api.get("/s/unknown_share").status_code == 404  # paylaşım görüntüleme çalışır (bulunamadı)


def test_read_only_error_reaches_browser_with_cors_headers():
    with client(maintenance_mode="read_only") as api:
        response = api.post("/api/v1/feedback", json={}, headers={"Origin": "https://teacherai-07.web.app"})
    assert response.status_code == 503 and response.headers["access-control-allow-origin"] == "https://teacherai-07.web.app"


def test_legacy_share_links_redirect_permanently_in_every_mode():
    for mode in ("off", "read_only", "redirect"):
        with client(maintenance_mode=mode, legacy_redirect_base="https://teacherai-07.web.app") as api:
            response = api.get("/s/abc123?x=1")
        assert response.status_code == 301 and response.headers["location"] == "https://teacherai-07.web.app/s/abc123?x=1"


def test_redirect_mode_moves_pages_and_explains_api_move():
    with client(maintenance_mode="redirect", legacy_redirect_base="https://teacherai-07.web.app") as api:
        assert api.get("/").headers["location"] == "https://teacherai-07.web.app/"
        moved = api.get("/api/v1/history", headers={"Authorization": "Bearer student-a"})
        assert moved.status_code == 503 and moved.json()["error"] == "service_moved"
        assert api.get("/api/v1/health").status_code == 200
        assert api.post("/api/v1/feedback", json={}).json()["error"] == "maintenance_read_only"


def test_off_mode_without_base_changes_nothing():
    with client() as api:
        assert api.get("/s/unknown_share").status_code == 404
    with pytest.raises(ValidationError):
        Settings(_env_file=None, legacy_redirect_base="http://insecure.example")


def test_token_verification_and_admin_identity_use_the_single_project(monkeypatch):
    """K1: tek projede doğrulama ve hesap silme/token iptali aynı (hedef) projenin varsayılan uygulamasını kullanır."""
    import firebase_admin

    from apps.api.app.core.container import build_container

    for app in list(firebase_admin._apps.values()):
        firebase_admin.delete_app(app)
    settings = Settings(_env_file=None, environment="test", firebase_enabled=True,
                        firebase_project_id="teacherai-07", firebase_auth_project_id="teacherai-07")
    try:
        container = build_container(settings)
        assert firebase_admin.get_app().project_id == "teacherai-07"
        assert "identity" not in firebase_admin._apps  # ikinci bir Auth projesine uygulama açılmaz
        assert container.token_verifier.app is None and container.account_deletion.identity.app is None
    finally:
        for app in list(firebase_admin._apps.values()):
            firebase_admin.delete_app(app)
