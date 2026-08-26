import json
from pathlib import Path


def test_firebase_hosting_static_export_with_short_share_rewrite_only() -> None:
    config = json.loads(Path("firebase.json").read_text(encoding="utf-8-sig"))
    hosting = config["hosting"]

    assert hosting["public"] == "apps/web/out"
    assert hosting["cleanUrls"] is True
    assert hosting["trailingSlash"] is False
    assert hosting["rewrites"] == [
        {
            "source": "/s/**",
            "run": {"serviceId": "teacherai-api", "region": "us-east4"},
        }
    ]


def test_next_config_keeps_static_export_contract() -> None:
    source = Path("apps/web/next.config.ts").read_text(encoding="utf-8")

    assert "output: 'export'" in source
    assert "trailingSlash: true" in source
    assert "typedRoutes: true" in source


def test_firebase_project_and_cloudbuild_contract() -> None:
    firebaserc = json.loads(Path(".firebaserc").read_text(encoding="utf-8-sig"))
    cloudbuild = Path("cloudbuild.api.yaml").read_text(encoding="utf-8")

    assert firebaserc["projects"]["default"] == "teacherai-07"
    assert "docker/api/Dockerfile" in cloudbuild
    assert "us-east4-docker.pkg.dev/math-ai-07/teacherai/teacherai-api:latest" in cloudbuild


def test_production_deploy_script_keeps_safety_gates_and_secret_source() -> None:
    script = Path("scripts/deploy-production.ps1").read_text(encoding="utf-8")

    for required in (
        '$FirebaseProjectId = "teacherai-07"',
        '$ProjectId = "math-ai-07"',
        '$Region = "us-east4"',
        '$ServiceName = "teacherai-api"',
        "git branch --show-current",
        "git fetch origin main",
        "pytest -q apps/api/tests",
        "gcloud config set project $ProjectId",
        "gcloud builds submit",
        "gcloud run deploy",
        '--set-secrets "OPENAI_API_KEY=openai-api-key:latest"',
        "gcloud run services describe $ServiceName",
        '$env:NEXT_PUBLIC_API_BASE_URL = "$ApiUrl/api/v1"',
        "npm run build:web",
        "apps\\web\\out\\index.html",
        "Invoke-RestMethod",
        "firebase deploy --only hosting",
        "--project $FirebaseProjectId",
    ):
        assert required in script

    assert script.index("gcloud run services describe $ServiceName") < script.index('$env:NEXT_PUBLIC_API_BASE_URL = "$ApiUrl/api/v1"')
    assert script.index('$env:NEXT_PUBLIC_API_BASE_URL = "$ApiUrl/api/v1"') < script.index("npm run build:web")

    for forbidden in ("git push", "git stash", "gcloud secrets versions add", "--set-env-vars OPENAI_API_KEY"):
        assert forbidden not in script
