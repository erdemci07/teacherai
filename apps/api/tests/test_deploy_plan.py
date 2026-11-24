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
# TA-005C: sentetik ama biçimce gerçekçi web yapılandırması (gerçek anahtar değildir).
API_KEY = "AIza" + "S" * 35
APP_ID = "1:123456789012:web:0a1b2c3d4e5f"
SDK = {"projectId": "teacherai-07", "appId": APP_ID, "apiKey": API_KEY, "authDomain": "teacherai-07.firebaseapp.com",
       "storageBucket": "teacherai-07.firebasestorage.app", "messagingSenderId": "123456789012"}


def web_lines(project="teacherai-07", api_key=API_KEY, app_id=APP_ID, auth_domain=None, extra=()):
    return [f"NEXT_PUBLIC_FIREBASE_API_KEY={api_key}",
            f"NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN={auth_domain or project + '.firebaseapp.com'}",
            f"NEXT_PUBLIC_FIREBASE_PROJECT_ID={project}", f"NEXT_PUBLIC_FIREBASE_APP_ID={app_id}", *extra]


def make_root(tmp_path, region=REGION, service="teacherai-api", web_env=True, project="teacherai-07", lines=None):
    (tmp_path / "scripts").mkdir(parents=True)
    shutil.copy(Path(dp.CONFIG), tmp_path / dp.CONFIG)
    shutil.copy(Path(".firebaserc"), tmp_path / ".firebaserc")
    shutil.copy(Path("cloudbuild.api.yaml"), tmp_path / "cloudbuild.api.yaml")
    config = json.loads(Path("firebase.json").read_text(encoding="utf-8"))
    config["hosting"]["rewrites"] = [{"source": "/s/**", "run": {"serviceId": service, "region": region}}]
    (tmp_path / "firebase.json").write_text(json.dumps(config), encoding="utf-8")
    (tmp_path / "apps/web").mkdir(parents=True)
    if web_env:
        (tmp_path / "apps/web/.env.production").write_text("\n".join(lines or web_lines(project)), encoding="utf-8")
    return tmp_path


def cli(result):
    return json.dumps({"status": "success", "result": result})


class FakeRunner:
    def __init__(self, root, exists=False, overrides=None, service_env=None, sdk=None, apps=None):
        self.root, self.exists, self.calls, self.overrides = root, exists, [], overrides or {}
        self.envs = {}
        self.service_env = service_env or []
        self.sdk = SDK if sdk is None else sdk
        self.apps = [{"appId": APP_ID, "platform": "WEB"}] if apps is None else apps

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
                                                            "url": "https://teacherai-api-x.a.run.app"},
                                                 "spec": {"template": {"spec": {"containers": [{"env": self.service_env}]}}}}),
            "revisions describe": image,
            "apps:list": cli(self.apps),
            "apps:sdkconfig": cli({"fileName": "firebase-js-config.json", "sdkConfig": self.sdk}),
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
    runner = FakeRunner(root, exists=exists, overrides=kw.pop("overrides", None), service_env=kw.pop("service_env", None),
                        sdk=kw.pop("sdk", None), apps=kw.pop("apps", None))
    health = kw.pop("health", lambda url: (200, {"success": True}))
    ctx = dp.Context(dp.load_config(root, region), mode, root, runner, http=health, sleep=lambda s: None,
                     publish_hosting=publish, drop_env=frozenset(kw.pop("drop", ())))
    return ctx, runner


def test_bootstrap_sequence_deploys_digest_before_web_build(tmp_path):
    ctx, runner = context(make_root(tmp_path))
    state = dp.execute(ctx, log=lambda m: None)
    assert runner.kinds() == [
        "git branch", "git status", "git fetch", "git rev-parse", "git rev-parse", "pytest",  # yerel kapılar
        "projects describe", "billing projects", "services list", "artifacts repositories", "secrets versions",
        "iam service-accounts", "projects get-iam-policy", "run services",  # ön koşullar ve mod
        "firebase apps:list", "firebase apps:sdkconfig",  # TA-005C: gerçek web uygulaması, yalnız okuma
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
    assert not any(c[:2] == ["firebase", "deploy"] for c in runner.calls)  # -PublishHosting yok
    assert {tuple(c[:2]) for c in runner.calls if c[0] == "firebase"} == {("firebase", "apps:list"), ("firebase", "apps:sdkconfig")}
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
    assert '$arguments += @("--drop-env", $name)' in script  # TA-005C: açık kaldırma sarmalayıcıdan geçer


# --- TA-005C §9: Firebase web yapılandırması --------------------------------------------------------------

@pytest.mark.parametrize(("lines", "message"), [
    (web_lines(auth_domain="math-ai-legacy.firebaseapp.com"), "AUTH_DOMAIN"),       # karışık kaynak/hedef
    (web_lines(app_id="1:2:ios:3"), "APP_ID"),
    (web_lines(api_key="k"), "API_KEY"),
    (web_lines(extra=["NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=999"]), "MESSAGING_SENDER_ID"),
    (web_lines(extra=["NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=other.appspot.com"]), "STORAGE_BUCKET"),
])
def test_mixed_or_malformed_web_config_is_rejected_offline_before_any_change(tmp_path, lines, message):
    ctx, runner = context(make_root(tmp_path, lines=lines))
    with pytest.raises(dp.DeployError, match=message) as caught:
        dp.execute(ctx, log=lambda m: None)
    assert runner.mutated() == [] and not any(c[0] == "firebase" for c in runner.calls)
    assert API_KEY not in str(caught.value) and "math-ai-legacy" not in str(caught.value)  # değer yazılmaz


@pytest.mark.parametrize(("sdk", "apps", "message"), [
    ({**SDK, "apiKey": "AIza" + "T" * 35}, None, "API_KEY"),                 # başka uygulamanın anahtarı
    ({**SDK, "authDomain": "teacherai-07.web.app"}, None, "AUTH_DOMAIN"),
    ({**SDK, "projectId": "other-project"}, None, "başka projeye ait"),
    (SDK, [{"appId": "1:123456789012:web:ffff"}], "kayıtlı bir web uygulaması değil"),
])
def test_authoritative_sdk_config_mismatch_stops_before_any_change(tmp_path, sdk, apps, message):
    ctx, runner = context(make_root(tmp_path), sdk=sdk, apps=apps)
    with pytest.raises(dp.DeployError, match=message) as caught:
        dp.execute(ctx, log=lambda m: None)
    assert runner.mutated() == [] and API_KEY not in str(caught.value)


def test_failed_firebase_cli_output_stops_before_any_change(tmp_path):
    failed = dp.Result(0, json.dumps({"status": "error", "error": "yetki yok"}))
    ctx, runner = context(make_root(tmp_path), overrides={"apps:list": failed})
    with pytest.raises(dp.DeployError, match="başarılı sonuç"):
        dp.execute(ctx, log=lambda m: None)
    assert runner.mutated() == []


def test_custom_auth_domain_needs_explicit_approval_and_optional_fields_are_compared(tmp_path):
    lines = web_lines(auth_domain="giris.teacherai.example",
                      extra=["NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=teacherai-07.firebasestorage.app"])
    root = make_root(tmp_path, lines=lines)
    with pytest.raises(dp.DeployError, match="AUTH_DOMAIN"):
        dp.execute(context(root)[0], log=lambda m: None)
    config = json.loads((root / dp.CONFIG).read_text(encoding="utf-8"))
    config["firebase_web"]["approved_auth_domains"] = ["giris.teacherai.example"]
    (root / dp.CONFIG).write_text(json.dumps(config), encoding="utf-8")
    state = dp.execute(context(root)[0], log=lambda m: None)
    assert state["web_config_verification"] == "authoritative" and state["web_config"]["STORAGE_BUCKET"]
    with pytest.raises(dp.DeployError, match="STORAGE_BUCKET"):  # SDK'daki kova farklıysa
        dp.execute(context(root, sdk={**SDK, "storageBucket": "teacherai-07.appspot.com"})[0], log=lambda m: None)


def test_web_config_changed_after_verification_blocks_web_build(tmp_path):
    root = make_root(tmp_path)
    ctx, runner = context(root)
    original = dp.step_web_config

    def tamper(c):
        (root / "apps/web/.env.production.local").write_text("NEXT_PUBLIC_FIREBASE_API_KEY=AIza" + "Z" * 35, encoding="utf-8")
        return original(c)

    with pytest.raises(dp.DeployError, match="değişti"):
        for _, action in dp.STEPS:
            (tamper if action is dp.step_web_config else action)(ctx)
    assert not any(c[:2] == ["npm", "run"] for c in runner.calls)


def test_plan_states_offline_only_web_verification_and_update_policy(capsys):
    def forbidden(argv, env=None):
        raise AssertionError(f"plan kipinde dış komut çağrıldı: {argv}")

    assert dp.main(["--mode", "update", "--region", REGION], runner=forbidden) == 0
    out = capsys.readouterr().out
    assert "Firebase web yapılandırması" in out and "Update: çalışan ortam okunur" in out


# --- TA-005C §10: Update ortam uzlaştırması ----------------------------------------------------------------

RUNNING = [
    {"name": "TEACHERAI_ENVIRONMENT", "value": "production"},
    {"name": "TEACHERAI_FIREBASE_ENABLED", "value": "true"},
    {"name": "TEACHERAI_FIREBASE_PROJECT_ID", "value": "teacherai-07"},
    {"name": "TEACHERAI_FIREBASE_AUTH_PROJECT_ID", "value": "teacherai-07"},
    {"name": "TEACHERAI_OPENAI_LESSON_MODEL", "value": "gpt-5.6-terra"},
    {"name": "TEACHERAI_MAINTENANCE_MODE", "value": "read_only"},
    {"name": "TEACHERAI_GLOBAL_DAILY_PROVIDER_CALLS", "value": "1500"},
    {"name": "TEACHERAI_APP_CHECK_MODE", "value": "monitor"},
    {"name": "FEEDBACK_NOTIFICATION_EMAIL", "value": "geri-bildirim@example.invalid"},
    {"name": "TEACHERAI_MATHAI_MAX_PROCESSES", "value": "2"},
    {"name": "TEACHERAI_OPERATION_LIMITS", "value": json.dumps({"analyze": 20, "generate": 20}, separators=(",", ":"))},
    {"name": "OPENAI_API_KEY", "valueFrom": {"secretKeyRef": {"name": "openai-api-key", "key": "latest"}}},
    {"name": "RESEND_API_KEY", "valueFrom": {"secretKeyRef": {"name": "resend-api-key", "key": "3"}}},
]


def test_update_preserves_approved_runtime_configuration_and_secret_refs(tmp_path):
    ctx, runner = context(make_root(tmp_path), mode="update", exists=True, service_env=RUNNING)
    state = dp.execute(ctx, log=lambda m: None)
    deploy = next(c for c in runner.calls if c[1:3] == ["run", "deploy"])
    flag = deploy[deploy.index("--set-env-vars") + 1]
    assert flag.startswith("^|^")  # değerde virgül olduğu için ayraç değişti; değer bölünmez
    pairs = dict(item.split("=", 1) for item in flag[3:].split("|"))
    assert pairs["TEACHERAI_MAINTENANCE_MODE"] == "read_only" and pairs["TEACHERAI_APP_CHECK_MODE"] == "monitor"
    assert pairs["TEACHERAI_OPENAI_LESSON_MODEL"] == "gpt-5.6-terra" and pairs["TEACHERAI_MATHAI_MAX_PROCESSES"] == "2"
    assert json.loads(pairs["TEACHERAI_OPERATION_LIMITS"]) == {"analyze": 20, "generate": 20}
    assert pairs["TEACHERAI_ENVIRONMENT"] == "production" and pairs["TEACHERAI_GLOBAL_DAILY_PROVIDER_CALLS"] == "1500"
    secrets = deploy[deploy.index("--set-secrets") + 1].split(",")
    assert secrets == ["OPENAI_API_KEY=openai-api-key:latest", "RESEND_API_KEY=resend-api-key:3"]
    assert "geri-bildirim@example.invalid" not in json.dumps(state["runtime_report"])  # rapor yalnız ad taşır
    assert "TEACHERAI_MAINTENANCE_MODE" in state["runtime_report"]["preserved"]


@pytest.mark.parametrize(("extra", "message"), [
    ({"name": "TEACHERAI_SURPRISE", "value": "1"}, "politikada olmayan"),
    ({"name": "ANTHROPIC_API_KEY", "value": "sk-ant-duz-metin"}, "yasaklı"),
    ({"name": "TEACHERAI_DEBUG", "value": "true"}, "yasaklı"),
    ({"name": "TEACHERAI_FIREBASE_SERVICE_ACCOUNT_JSON", "value": "{}"}, "yasaklı"),
    ({"name": "UNKNOWN_SECRET", "valueFrom": {"secretKeyRef": {"name": "x", "key": "1"}}}, "politikada olmayan"),
])
def test_unknown_or_prohibited_runtime_configuration_stops_before_build(tmp_path, extra, message):
    ctx, runner = context(make_root(tmp_path), mode="update", exists=True, service_env=[*RUNNING, extra])
    with pytest.raises(dp.DeployError, match=message) as caught:
        dp.execute(ctx, log=lambda m: None)
    assert runner.mutated() == [] and "sk-ant-duz-metin" not in str(caught.value)


def test_explicit_drop_removes_only_the_named_setting(tmp_path):
    env = [*RUNNING, {"name": "TEACHERAI_SURPRISE", "value": "1"}]
    ctx, runner = context(make_root(tmp_path), mode="update", exists=True, service_env=env,
                          drop={"TEACHERAI_SURPRISE", "TEACHERAI_APP_CHECK_MODE"})
    state = dp.execute(ctx, log=lambda m: None)
    text = " ".join(next(c for c in runner.calls if c[1:3] == ["run", "deploy"]))
    assert "TEACHERAI_SURPRISE" not in text and "TEACHERAI_APP_CHECK_MODE" not in text
    assert "TEACHERAI_MAINTENANCE_MODE=read_only" in text
    assert sorted(state["runtime_report"]["dropped"]) == ["TEACHERAI_APP_CHECK_MODE", "TEACHERAI_SURPRISE"]


def test_bootstrap_sets_only_managed_configuration(tmp_path):
    ctx, runner = context(make_root(tmp_path))
    state = dp.execute(ctx, log=lambda m: None)
    assert set(state["env"]) == set(dp.MANAGED_ENV) and list(state["secrets"]) == ["OPENAI_API_KEY"]
    describes = [c for c in runner.calls if c[1:4] == ["run", "services", "describe"]]
    assert len(describes) == 1  # yalnız hazır revizyon adımı; bootstrap'ta okunacak eski ortam yok


def test_preserved_names_are_real_runtime_settings():
    from apps.api.app.core.settings import Settings

    policy = json.loads(Path(dp.CONFIG).read_text(encoding="utf-8"))["runtime_env_policy"]
    known = set()
    for name, info in Settings.model_fields.items():
        known.add(f"TEACHERAI_{name.upper()}")
        alias = info.validation_alias
        known.update(getattr(alias, "choices", None) or ([alias] if isinstance(alias, str) else []))
    known |= {"TEACHERAI_MATHAI_MAX_PROCESSES", "TEACHERAI_MATHAI_MAX_WAITING"}  # mathai/isolated.py os.environ
    assert sorted(set(policy["preserve_env"]) - known) == []  # korunan her ad uygulamanın okuduğu bir ayardır
    assert not set(policy["preserve_env"]) & set(policy["prohibited_env"])
    assert not set(policy["preserve_env"]) & set(dp.MANAGED_ENV)


# --- TA-005C §10: bölge / proje / Artifact Registry tutarlılığı -------------------------------------------

def test_other_cloud_run_rewrite_project_or_image_path_mismatch_stops(tmp_path):
    root = make_root(tmp_path / "a")
    config = json.loads((root / "firebase.json").read_text(encoding="utf-8"))
    config["hosting"]["rewrites"].append({"source": "/api/**", "run": {"serviceId": "teacherai-api", "region": "asia-east1"}})
    (root / "firebase.json").write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(dp.DeployError, match="/api/"):
        dp.execute(context(root)[0], log=lambda m: None)
    root2 = make_root(tmp_path / "b")
    (root2 / ".firebaserc").write_text(json.dumps({"projects": {"default": "legacy-project"}}), encoding="utf-8")
    with pytest.raises(dp.DeployError, match="firebaserc"):
        dp.execute(context(root2)[0], log=lambda m: None)
    root3 = make_root(tmp_path / "c")
    build = (root3 / "cloudbuild.api.yaml").read_text(encoding="utf-8").replace("/teacherai/teacherai-api", "/other/teacherai-api")
    (root3 / "cloudbuild.api.yaml").write_text(build, encoding="utf-8")
    ctx3, runner3 = context(root3)
    with pytest.raises(dp.DeployError, match="cloudbuild"):
        dp.execute(ctx3, log=lambda m: None)
    assert runner3.mutated() == []
