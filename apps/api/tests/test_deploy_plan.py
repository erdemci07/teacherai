"""TA-005B §3: dağıtım planı. Dış komutlar sahte çalıştırıcıyla; gerçek gcloud/npm/firebase çağrısı yoktur."""

import json
import shutil
from pathlib import Path

import pytest

from scripts import deploy_plan as dp

SHA = "0123456789abcdef0123456789abcdef01234567"
DIGEST = "sha256:" + "a" * 64
REGION = "europe-west1"
MUTATING = (("builds", "submit"), ("run", "deploy"), ("npm", "run"), ("firebase", "deploy"))


def make_root(tmp_path, region=REGION, service="teacherai-api", web_env=True, project="teacherai-07"):
    (tmp_path / "scripts").mkdir()
    shutil.copy(Path(dp.CONFIG), tmp_path / dp.CONFIG)
    config = json.loads(Path("firebase.json").read_text(encoding="utf-8"))
    config["hosting"]["rewrites"] = [{"source": "/s/**", "run": {"serviceId": service, "region": region}}]
    (tmp_path / "firebase.json").write_text(json.dumps(config), encoding="utf-8")
    (tmp_path / "apps/web").mkdir(parents=True)
    if web_env:
        lines = ["NEXT_PUBLIC_FIREBASE_API_KEY=k", f"NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN={project}.firebaseapp.com",
                 f"NEXT_PUBLIC_FIREBASE_PROJECT_ID={project}", "NEXT_PUBLIC_FIREBASE_APP_ID=1:2:web:3"]
        (tmp_path / "apps/web/.env.production").write_text("\n".join(lines), encoding="utf-8")
    return tmp_path


class FakeRunner:
    def __init__(self, root, exists=False, overrides=None):
        self.root, self.exists, self.calls, self.overrides = root, exists, [], overrides or {}
        self.envs = {}

    def __call__(self, argv, env=None):
        self.calls.append(argv)
        self.envs[tuple(argv)] = env
        text = " ".join(argv)
        for key, value in self.overrides.items():
            if key in text:
                return value
        return dp.Result(0, self.answer(argv, text))

    def answer(self, argv, text):
        image = f"{REGION}-docker.pkg.dev/teacherai-07/teacherai/teacherai-api@{DIGEST}"
        table = {
            "branch --show-current": "main", "status --porcelain": "", "rev-parse": SHA,
            "billing projects describe": "True", "projects describe": "teacherai-07",
            "services list --enabled": " ".join(json.loads(Path(dp.CONFIG).read_text(encoding="utf-8"))["required_apis"]),
            "secrets versions list": "projects/p/secrets/openai-api-key/versions/1",
            "get-iam-policy": "roles/datastore.user roles/firebaseauth.admin",
            "run services list": "teacherai-api" if self.exists else "",
            "docker images describe": DIGEST,
            "run services describe": json.dumps({"status": {"latestReadyRevisionName": "teacherai-api-00002-abc",
                                                            "latestCreatedRevisionName": "teacherai-api-00002-abc",
                                                            "url": "https://teacherai-api-x.a.run.app"}}),
            "revisions describe": image,
        }
        if argv[:3] == ["npm", "run", "build:web"]:
            (self.root / "apps/web/out").mkdir(parents=True, exist_ok=True)
            (self.root / "apps/web/out/index.html").write_text("ok", encoding="utf-8")
        for key, value in table.items():
            if key in text:
                return value
        return ""

    def kinds(self):
        return [" ".join(c[1:3]) if c[0] == "gcloud" else "pytest" if "pytest" in c else " ".join(c[:2]) for c in self.calls]

    def mutated(self):
        return [c for c in self.calls if any(c[0:2] == list(m) or c[1:3] == list(m) for m in MUTATING)]


def context(root, mode="bootstrap", exists=False, publish=False, region=REGION, **kw):
    runner = FakeRunner(root, exists=exists, overrides=kw.pop("overrides", None))
    health = kw.pop("health", lambda url: (200, {"success": True}))
    ctx = dp.Context(dp.load_config(root, region), mode, root, runner, http=health, sleep=lambda s: None,
                     publish_hosting=publish)
    return ctx, runner


def test_bootstrap_sequence_deploys_digest_before_web_build(tmp_path):
    ctx, runner = context(make_root(tmp_path))
    state = dp.execute(ctx, log=lambda m: None)
    assert runner.kinds() == [
        "git branch", "git status", "git fetch", "git rev-parse", "git rev-parse", "pytest",  # yerel kapılar
        "projects describe", "billing projects", "services list", "artifacts repositories", "secrets versions",
        "iam service-accounts", "projects get-iam-policy", "run services",  # ön koşullar ve mod
        "builds submit", "artifacts docker",  # image ve digest
        "run deploy", "run services", "run revisions",  # dağıtım ve hazır revizyon
        "npm run",  # web build, API'den sonra
    ]
    deploy = next(c for c in runner.calls if c[1:3] == ["run", "deploy"])
    image = deploy[deploy.index("--image") + 1]
    assert image.endswith(f"teacherai-api@{DIGEST}") and ":latest" not in image
    assert "--allow-unauthenticated" in deploy
    assert deploy[deploy.index("--region") + 1] == REGION and deploy[deploy.index("--max-instances") + 1] == "20"
    assert deploy[deploy.index("--service-account") + 1] == "teacherai-api-runtime@teacherai-07.iam.gserviceaccount.com"
    env = deploy[deploy.index("--set-env-vars") + 1]
    assert "TEACHERAI_ENVIRONMENT=production" in env and "TEACHERAI_FIREBASE_ENABLED=true" in env
    assert "TEACHERAI_FIREBASE_PROJECT_ID=teacherai-07" in env and "TEACHERAI_FIREBASE_AUTH_PROJECT_ID=teacherai-07" in env
    assert deploy[deploy.index("--set-secrets") + 1] == "OPENAI_API_KEY=openai-api-key:latest"
    build = next(c for c in runner.calls if c[1:3] == ["builds", "submit"])
    assert f"--substitutions=_REGION={REGION},_TAG={SHA[:12]}" in build
    web = next(c for c in runner.calls if c[:2] == ["npm", "run"])
    assert runner.envs[tuple(web)]["NEXT_PUBLIC_API_BASE_URL"] == "https://teacherai-api-x.a.run.app/api/v1"
    assert not any(c[0] == "firebase" for c in runner.calls)  # -PublishHosting yok
    assert state["revision"] == "teacherai-api-00002-abc"
    for call in runner.calls:
        if call[0] == "gcloud":
            assert call[-2:] == ["--project", "teacherai-07"]


def test_update_sequence_keeps_iam_and_publishes_hosting_only_on_flag(tmp_path):
    ctx, runner = context(make_root(tmp_path), mode="update", exists=True, publish=True)
    dp.execute(ctx, log=lambda m: None)
    deploy = next(c for c in runner.calls if c[1:3] == ["run", "deploy"])
    assert "--allow-unauthenticated" not in deploy
    assert runner.calls[-1] == ["firebase", "deploy", "--only", "hosting", "--project", "teacherai-07"]


@pytest.mark.parametrize(("mode", "exists"), [("bootstrap", True), ("update", False)])
def test_wrong_mode_stops_before_any_change(tmp_path, mode, exists):
    ctx, runner = context(make_root(tmp_path), mode=mode, exists=exists)
    with pytest.raises(dp.DeployError, match="Hiçbir değişiklik"):
        dp.execute(ctx, log=lambda m: None)
    assert runner.mutated() == []


def test_missing_secret_stops_before_any_change(tmp_path):
    ctx, runner = context(make_root(tmp_path), overrides={"secrets versions list": dp.Result(0, "")})
    with pytest.raises(dp.DeployError, match="Secret openai-api-key"):
        dp.execute(ctx, log=lambda m: None)
    assert runner.mutated() == []


def test_missing_firebase_web_config_stops_before_build(tmp_path):
    ctx, runner = context(make_root(tmp_path, web_env=False))
    with pytest.raises(dp.DeployError, match="Firebase web yapılandırması eksik"):
        dp.execute(ctx, log=lambda m: None)
    assert runner.mutated() == []


def test_web_config_of_another_project_is_rejected(tmp_path):
    ctx, runner = context(make_root(tmp_path, project="other-project"))
    with pytest.raises(dp.DeployError, match="tek proje"):
        dp.execute(ctx, log=lambda m: None)
    assert runner.mutated() == []


@pytest.mark.parametrize("root_kw", [{"region": "us-east4"}, {"service": "other-api"}])
def test_rewrite_region_or_service_mismatch_stops_before_build(tmp_path, root_kw):
    ctx, runner = context(make_root(tmp_path, **root_kw))
    with pytest.raises(dp.DeployError, match="rewrite"):
        dp.execute(ctx, log=lambda m: None)
    assert runner.mutated() == []


def test_editor_role_or_billing_off_stops_before_change(tmp_path):
    root = make_root(tmp_path)
    for overrides, message in (({"get-iam-policy": dp.Result(0, "roles/editor")}, "Editor"),
                               ({"billing projects describe": dp.Result(0, "False")}, "Billing")):
        ctx, runner = context(root, overrides=overrides)
        with pytest.raises(dp.DeployError, match=message):
            dp.execute(ctx, log=lambda m: None)
        assert runner.mutated() == []


def test_revision_running_other_image_is_rejected(tmp_path):
    other = dp.Result(0, f"{REGION}-docker.pkg.dev/teacherai-07/teacherai/teacherai-api@sha256:{'b' * 64}")
    ctx, runner = context(make_root(tmp_path), overrides={"revisions describe": other})
    with pytest.raises(dp.DeployError, match="digest"):
        dp.execute(ctx, log=lambda m: None)
    assert not any(c[:2] == ["npm", "run"] for c in runner.calls)


def test_health_retries_then_fails_without_web_build(tmp_path):
    seen = []
    ctx, runner = context(make_root(tmp_path), health=lambda url: (seen.append(url), (503, None))[1])
    with pytest.raises(dp.DeployError, match="health"):
        dp.execute(ctx, log=lambda m: None)
    assert len(seen) == 30 and seen[0] == "https://teacherai-api-x.a.run.app/api/v1/health"
    assert not any(c[:2] == ["npm", "run"] for c in runner.calls)


def test_missing_region_without_k2_decision_stops_before_any_command(tmp_path):
    ctx, runner = context(make_root(tmp_path), region=None)
    assert ctx.cfg.region is None  # K2 kararı yazılmadı; kodda bölge sabiti yok
    with pytest.raises(dp.DeployError, match="K2"):
        dp.execute(ctx, log=lambda m: None)
    assert runner.calls == []


def test_plan_only_is_default_and_calls_nothing(capsys):
    def forbidden(argv, env=None):
        raise AssertionError(f"plan kipinde dış komut çağrıldı: {argv}")

    assert dp.main(["--mode", "bootstrap"], runner=forbidden) == 0
    assert dp.main(["--mode", "update", "--region", REGION, "--plan-only"], runner=forbidden) == 0
    out = capsys.readouterr().out
    assert "<K2 kararı yok>" in out and "UYARI" in out
    assert "12. Hosting yayını" in out and "--allow-unauthenticated" in out
    assert out.index("Cloud Run dağıtımı") < out.index("Web build")


def test_powershell_wrapper_delegates_and_defaults_to_plan():
    script = Path("scripts/deploy-production.ps1").read_text(encoding="utf-8")
    assert "scripts.deploy_plan" in script and '[ValidateSet("Bootstrap", "Update")]' in script
    assert '$arguments += "--plan-only"' in script and "[switch]$PublishHosting" in script
    for forbidden in ("gcloud ", "firebase deploy", "npm run", "us-east4", ":latest", "gcloud config set project"):
        assert forbidden not in script
    assert "us-east4" not in Path("scripts/deploy_plan.py").read_text(encoding="utf-8")
    assert json.loads(Path(dp.CONFIG).read_text(encoding="utf-8"))["region"] is None  # K2 bekliyor
