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
    # TA-005B: bölge ve etiket dağıtım planından gelir; :latest yerine build'in digest'i dağıtılır.
    assert "${_REGION}-docker.pkg.dev/$PROJECT_ID/teacherai/teacherai-api:${_TAG}" in cloudbuild
    assert ":latest" not in cloudbuild and "us-east4" not in cloudbuild
    assert "substitutionOption: MUST_MATCH" in cloudbuild


def test_production_deploy_plan_keeps_safety_gates_and_secret_source() -> None:
    # TA-005B: mantık scripts/deploy_plan.py'ye taşındı; PowerShell yalnız sarmalayıcı. Sıra ve kapılar
    # test_deploy_plan.py'de davranışla sınanır; burada kaynak metindeki kapılar korunur.
    plan = Path("scripts/deploy_plan.py").read_text(encoding="utf-8")
    config = json.loads(Path("scripts/deploy-production.json").read_text(encoding="utf-8"))

    assert config["project_id"] == "teacherai-07" and config["service"] == "teacherai-api"
    assert config["secret"] == {"env": "OPENAI_API_KEY", "name": "openai-api-key", "version": "latest"}
    for required in ('"branch", "--show-current"', '"fetch", "origin", "main"', '"pytest", "-q", "apps/api/tests"',
                     '"--service-account"', '"--max-instances"', "TEACHERAI_ENVIRONMENT=production",
                     "TEACHERAI_FIREBASE_ENABLED=true", "TEACHERAI_FIREBASE_AUTH_PROJECT_ID=", '"builds", "submit"',
                     '"run", "deploy"', '"--set-secrets"', '"/s/**"', '"npm", "run", "build:web"',
                     "apps/web/out/index.html", "/api/v1/health", '"firebase", "deploy", "--only", "hosting"'):
        assert required in plan
    assert "--async" not in plan
    for forbidden in ("git push", "git stash", "secrets versions add", "secrets create", "services enable",
                      "repositories create", "service-accounts create", "add-iam-policy-binding",
                      "gcloud config set project", "firebase use", "billing projects link"):
        assert forbidden not in plan
        assert forbidden not in Path("scripts/deploy-production.ps1").read_text(encoding="utf-8")


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
