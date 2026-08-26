import json
from pathlib import Path


def test_firebase_hosting_static_export_without_cross_project_run_rewrites() -> None:
    config = json.loads(Path("firebase.json").read_text(encoding="utf-8-sig"))
    hosting = config["hosting"]

    assert hosting["public"] == "apps/web/out"
    assert hosting["cleanUrls"] is True
    assert hosting["trailingSlash"] is False
    assert "rewrites" not in hosting


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
        '$ApiProjectId = "math-ai-07"',
        "git branch --show-current",
        "git fetch origin main",
        "pytest -q apps/api/tests",
        "gcloud config set project $ApiProjectId",
        "gcloud builds submit",
        "gcloud run deploy",
        "gcloud run services describe $ServiceName",
        "PUBLIC_APP_URL=$WebUrl,PUBLIC_SHARE_URL_BASE=$ApiUrl",
        '$env:NEXT_PUBLIC_API_BASE_URL = $ApiBaseUrl',
        "npm run build:web",
        "apps\\web\\out\\index.html",
        "Invoke-RestMethod",
        "firebase deploy --only hosting",
        "--project $FirebaseProjectId",
    ):
        assert required in script

    assert script.index("gcloud run services describe $ServiceName") < script.index('$env:NEXT_PUBLIC_API_BASE_URL = $ApiBaseUrl')
    assert script.index('$env:NEXT_PUBLIC_API_BASE_URL = $ApiBaseUrl') < script.index("npm run build:web")
    assert "Assert-LastExitCode" in script
    assert "Invoke-Checked" in script

    for forbidden in ("git push", "git stash", "gcloud secrets versions add", "--set-secrets", "OPENAI_API_KEY="):
        assert forbidden not in script
