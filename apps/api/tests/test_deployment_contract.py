import json
from pathlib import Path


def test_firebase_hosting_rewrites_share_to_same_project_cloud_run() -> None:
    # TA-005: tek proje. /s/** aynı projedeki Cloud Run servisine rewrite ile gider; paylaşım adresi Hosting'de kalır.
    # API rewrite'tan geçmez (Hosting 60 sn sınırı), bu yüzden yalnızca /s/** kuralı vardır.
    config = json.loads(Path("firebase.json").read_text(encoding="utf-8-sig"))
    hosting = config["hosting"]

    assert hosting["public"] == "apps/web/out"
    assert hosting["cleanUrls"] is True
    assert hosting["trailingSlash"] is False
    assert hosting.get("redirects") is None
    assert hosting["rewrites"] == [{"source": "/s/**", "run": {"serviceId": "teacherai-api", "region": "us-east4"}}]
    assert config["firestore"] == {"rules": "firestore.rules", "indexes": "firestore.indexes.json"}


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
    # Proje kimliği Cloud Build'in --project ile verilen $PROJECT_ID değişkeninden gelir; dosyaya yazılmaz.
    assert "${_REGION}-docker.pkg.dev/$PROJECT_ID/teacherai/teacherai-api:latest" in cloudbuild


def test_production_deploy_script_keeps_safety_gates_and_secret_source() -> None:
    script = Path("scripts/deploy-production.ps1").read_text(encoding="utf-8")

    for required in (
        '$ProjectId = "teacherai-07"',
        '$FirebaseProjectId = $ProjectId',
        '$Region = "us-east4"',
        '$ServiceName = "teacherai-api"',
        "git branch --show-current",
        "git fetch origin main",
        "pytest -q apps/api/tests",
        "--service-account $RuntimeServiceAccount",
        "--max-instances $MaxInstances",
        "TEACHERAI_ENVIRONMENT=production",
        "TEACHERAI_FIREBASE_AUTH_PROJECT_ID=$ProjectId",
        "gcloud builds submit",
        "gcloud run deploy",
        '--set-secrets "OPENAI_API_KEY=openai-api-key:latest"',
        'Where-Object { $_.source -eq "/s/**" }',
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

    assert "--async" not in script

    for forbidden in ("git push", "git stash", "gcloud secrets versions add", "--set-env-vars OPENAI_API_KEY",
                      "gcloud config set project", "firebase use"):
        assert forbidden not in script


LEGACY = "math-ai" + "-07"
# Eski proje kimliği yalnızca geçiş belgelerinde, geçmiş faz raporlarında ve açıkça işaretlenmiş geçiş
# araçlarında (denetim, kopya, eski yönlendirme) geçebilir.
LEGACY_ALLOWED = ("docs/migration/", "docs/phase-reports/", "docs/architecture/adr-ta-005-single-project.md",
                  "scripts/migration/", "apps/api/tests/test_migration_")


def test_legacy_project_id_only_in_migration_material() -> None:
    import subprocess

    found = subprocess.run(["git", "grep", "-l", LEGACY], capture_output=True, text=True, check=False)
    assert found.returncode in (0, 1), found.stderr
    offenders = [path for path in found.stdout.split() if not path.startswith(LEGACY_ALLOWED)]
    assert offenders == []
