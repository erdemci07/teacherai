import json
from pathlib import Path


def test_firebase_hosting_static_export_and_api_rewrite_contract() -> None:
    config = json.loads(Path("firebase.json").read_text(encoding="utf-8-sig"))
    hosting = config["hosting"]

    assert hosting["public"] == "apps/web/out"
    assert {
        "source": "/api/**",
        "run": {"serviceId": "teacherai-api", "region": "us-east4"},
    } in hosting["rewrites"]


def test_next_config_keeps_static_export_contract() -> None:
    source = Path("apps/web/next.config.ts").read_text(encoding="utf-8")

    assert "output: 'export'" in source
    assert "trailingSlash: true" in source
    assert "typedRoutes: true" in source


def test_firebase_project_and_cloudbuild_contract() -> None:
    firebaserc = json.loads(Path(".firebaserc").read_text(encoding="utf-8-sig"))
    cloudbuild = Path("cloudbuild.api.yaml").read_text(encoding="utf-8")

    assert firebaserc["projects"]["default"] == "math-ai-07"
    assert "docker/api/Dockerfile" in cloudbuild
    assert "us-east4-docker.pkg.dev/math-ai-07/teacherai/teacherai-api:latest" in cloudbuild


def test_production_deploy_script_keeps_safety_gates_and_secret_source() -> None:
    script = Path("scripts/deploy-production.ps1").read_text(encoding="utf-8")

    for required in (
        "git branch --show-current",
        "git fetch origin main",
        "pytest -q apps/api/tests",
        "npm run build:web",
        "apps\\web\\out\\index.html",
        "gcloud builds submit",
        "gcloud run deploy",
        "Invoke-RestMethod",
        "firebase deploy --only hosting",
        "OPENAI_API_KEY=openai-api-key:latest",
    ):
        assert required in script

    for forbidden in ("git push", "git stash", "gcloud secrets versions add", "OPENAI_API_KEY="):
        if forbidden == "OPENAI_API_KEY=":
            assert "OPENAI_API_KEY=openai-api-key:latest" in script
        else:
            assert forbidden not in script
