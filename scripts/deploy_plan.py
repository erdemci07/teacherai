"""Production dağıtımının karar ve sıra mantığı (TA-005B §3).

``scripts/deploy-production.ps1`` yalnız bir sarmalayıcıdır. Dış komutlar enjekte edilebilir bir
çalıştırıcıyla çağrılır; böylece sıra Linux CI'da birim testiyle sınanır.

    python -m scripts.deploy_plan --mode bootstrap|update [--region R]            # yalnız plan (varsayılan)
    python -m scripts.deploy_plan --mode update --region R --execute [--publish-hosting]

- Varsayılan ``--plan-only``: hiçbir dış komut çalışmaz, sıralı plan yazdırılır.
- Mod, servisin gerçek varlığıyla tutarlı değilse hiçbir değişiklik yapılmadan durulur.
- Ön koşullar yalnız kontrol edilir; kaynak oluşturulmaz.
- Image ``:latest`` ile değil, build'in ürettiği digest ile dağıtılır.
- Bölge ``scripts/deploy-production.json`` içindeki K2 kararından gelir; karar yoksa ``--region`` zorunludur.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = "scripts/deploy-production.json"
WEB_KEYS = ("API_KEY", "AUTH_DOMAIN", "PROJECT_ID", "APP_ID")
# Next'in production build'de okuduğu sıra: önce gelen kazanır.
WEB_ENV_FILES = (".env.production.local", ".env.local", ".env.production", ".env")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
REGION = re.compile(r"^[a-z]+-[a-z]+\d$")


class DeployError(RuntimeError):
    """Dağıtım durdu. Mesaj hangi adımda ve neden durduğunu söyler."""


@dataclass
class Result:
    code: int
    out: str = ""


Runner = Callable[[list[str], dict | None], Result]


def system_runner(argv, env=None):
    exe = shutil.which(argv[0]) or argv[0]  # Windows'ta gcloud/npm/firebase .cmd dosyalarıdır
    done = subprocess.run([exe, *argv[1:]], capture_output=True, text=True, env=env, cwd=ROOT, check=False)
    if done.returncode:
        sys.stderr.write(done.stderr[-2000:])
    return Result(done.returncode, done.stdout.strip())


def http_get(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode() or "null")
    except (OSError, ValueError) as error:  # URLError, HTTPError, zaman aşımı ve bozuk JSON yeniden denenir
        return 0, {"error": type(error).__name__}


@dataclass
class Config:
    project_id: str
    service: str
    repository: str
    runtime_service_account: str
    region: str | None
    max_instances: int
    min_instances: int
    concurrency: int
    timeout_seconds: int
    cpu: str
    memory: str
    secret: dict
    required_apis: list[str]
    region_decision: str = ""

    @property
    def runtime_sa(self):
        return f"{self.runtime_service_account}@{self.project_id}.iam.gserviceaccount.com"

    @property
    def image(self):
        return f"{self.region}-docker.pkg.dev/{self.project_id}/{self.repository}/{self.service}"


def load_config(root=ROOT, region=None):
    data = json.loads((Path(root) / CONFIG).read_text(encoding="utf-8"))
    data["region"] = region or data.get("region")
    return Config(**data)


@dataclass
class Context:
    cfg: Config
    mode: str
    root: Path
    run: Runner
    http: Callable = http_get
    sleep: Callable = time.sleep
    publish_hosting: bool = False
    git_sha: str = ""
    state: dict = field(default_factory=dict)

    def call(self, argv, what, env=None):
        result = self.run(argv, env)
        if result.code != 0:
            raise DeployError(f"{what} başarısız (çıkış {result.code}).")
        return result.out


def gc(ctx, *args):
    return ["gcloud", *args, "--project", ctx.cfg.project_id]


# --- adımlar -------------------------------------------------------------------------------------

def step_local_gates(ctx):
    if ctx.call(["git", "branch", "--show-current"], "git dalı") != "main":
        raise DeployError("Dağıtım yalnız main dalından yapılır.")
    if ctx.call(["git", "status", "--porcelain"], "git durumu"):
        raise DeployError("Çalışma ağacı temiz değil.")
    ctx.call(["git", "fetch", "origin", "main"], "git fetch")
    head = ctx.call(["git", "rev-parse", "HEAD"], "git rev-parse")
    if head != ctx.call(["git", "rev-parse", "origin/main"], "git rev-parse origin/main"):
        raise DeployError("Yerel main, origin/main ile aynı değil.")
    ctx.git_sha = head
    ctx.call([sys.executable, "-m", "pytest", "-q", "apps/api/tests"], "API testleri")


def service_exists(ctx):
    out = ctx.call(gc(ctx, "run", "services", "list", "--region", ctx.cfg.region,
                      f"--filter=metadata.name={ctx.cfg.service}", "--format=value(metadata.name)"), "servis listesi")
    return ctx.cfg.service in out.split()


def step_prerequisites(ctx):
    cfg = ctx.cfg
    if ctx.call(gc(ctx, "projects", "describe", cfg.project_id, "--format=value(projectId)"), "proje") != cfg.project_id:
        raise DeployError(f"Proje okunamadı: {cfg.project_id}")
    if ctx.call(gc(ctx, "billing", "projects", "describe", cfg.project_id, "--format=value(billingEnabled)"),
                "billing").lower() != "true":
        raise DeployError("Billing etkin değil (K3). Betik billing değiştirmez.")
    enabled = set(ctx.call(gc(ctx, "services", "list", "--enabled", "--format=value(config.name)"), "API listesi").split())
    missing = sorted(set(cfg.required_apis) - enabled)
    if missing:
        raise DeployError(f"Etkin olmayan API: {', '.join(missing)}. Betik API etkinleştirmez.")
    ctx.call(gc(ctx, "artifacts", "repositories", "describe", cfg.repository, "--location", cfg.region,
                "--format=value(name)"), "Artifact Registry deposu")
    versions = ctx.call(gc(ctx, "secrets", "versions", "list", cfg.secret["name"], "--filter=state:ENABLED",
                           "--format=value(name)"), f"secret {cfg.secret['name']}")
    if not versions:
        raise DeployError(f"Secret {cfg.secret['name']} için etkin sürüm yok.")
    ctx.call(gc(ctx, "iam", "service-accounts", "describe", cfg.runtime_sa, "--format=value(email)"), "çalışma zamanı hesabı")
    roles = set(ctx.call(gc(ctx, "projects", "get-iam-policy", cfg.project_id, "--flatten=bindings[].members",
                            f"--filter=bindings.members:serviceAccount:{cfg.runtime_sa}",
                            "--format=value(bindings.role)"), "IAM politikası").split())
    if roles & {"roles/editor", "roles/owner"}:
        raise DeployError("Çalışma zamanı hesabı Editor/Owner rolü taşıyor; en az yetki gerekir.")
    exists = service_exists(ctx)
    if exists != (ctx.mode == "update"):
        raise DeployError(f"Mod {ctx.mode} ama servis {'var' if exists else 'yok'}. Hiçbir değişiklik yapılmadı.")


def web_firebase_config(root, project_id, environ=None):
    values = {}
    for name in reversed(WEB_ENV_FILES):
        path = Path(root) / "apps/web" / name
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                key, sep, value = line.strip().partition("=")
                if sep and not key.startswith("#"):
                    values[key.strip()] = value.strip().strip("'\"")
    values |= {k: v for k, v in (os.environ if environ is None else environ).items() if k.startswith("NEXT_PUBLIC_")}
    missing = [key for key in WEB_KEYS if not values.get(f"NEXT_PUBLIC_FIREBASE_{key}")]
    if missing:
        raise DeployError(f"Firebase web yapılandırması eksik: {', '.join(missing)}")
    if values["NEXT_PUBLIC_FIREBASE_PROJECT_ID"] != project_id:
        raise DeployError("Firebase web PROJECT_ID dağıtım projesiyle aynı değil (tek proje).")


def check_rewrite(root, cfg):
    hosting = json.loads((Path(root) / "firebase.json").read_text(encoding="utf-8-sig"))["hosting"]
    rules = [rule for rule in hosting.get("rewrites", []) if rule.get("source") == "/s/**"]
    run = rules[0].get("run", {}) if rules else {}
    if run.get("serviceId") != cfg.service or run.get("region") != cfg.region:
        raise DeployError(f"firebase.json /s/** rewrite'ı {cfg.service} ({cfg.region}) servisine bağlı değil.")


def step_validate(ctx):
    cfg = ctx.cfg
    if not cfg.region or not REGION.match(cfg.region):
        raise DeployError(f"Bölge yok veya geçersiz. {cfg.region_decision}")
    if cfg.max_instances < 1 or cfg.min_instances < 0 or cfg.min_instances > cfg.max_instances:
        raise DeployError("Instance sınırları geçersiz.")
    if cfg.runtime_sa.endswith("-compute@developer.gserviceaccount.com"):
        raise DeployError("Compute varsayılan hesabı kullanılamaz.")
    check_rewrite(ctx.root, cfg)  # değişiklikten önce; 9. adımda yeniden denetlenir
    web_firebase_config(ctx.root, cfg.project_id)  # değişiklikten önce; 7. adımda yeniden denetlenir


def step_build(ctx):
    cfg, tag = ctx.cfg, ctx.git_sha[:12] or "plan"
    ctx.call(gc(ctx, "builds", "submit", "--config", "cloudbuild.api.yaml",
                f"--substitutions=_REGION={cfg.region},_TAG={tag}"), "image build")
    digest = ctx.call(gc(ctx, "artifacts", "docker", "images", "describe", f"{cfg.image}:{tag}",
                         "--format=value(image_summary.digest)"), "image digest")
    if not DIGEST.match(digest):
        raise DeployError("Build bir image digest'i üretmedi.")
    ctx.state["image"] = f"{cfg.image}@{digest}"


def deploy_args(ctx):
    cfg = ctx.cfg
    env = ",".join([
        "TEACHERAI_ENVIRONMENT=production",
        "TEACHERAI_FIREBASE_ENABLED=true",
        f"TEACHERAI_FIREBASE_PROJECT_ID={cfg.project_id}",
        f"TEACHERAI_FIREBASE_AUTH_PROJECT_ID={cfg.project_id}",
    ])
    args = ["run", "deploy", cfg.service, "--image", ctx.state.get("image", f"{cfg.image}@<digest>"),
            "--region", cfg.region, "--platform", "managed", "--port", "8000",
            "--service-account", cfg.runtime_sa, "--max-instances", str(cfg.max_instances),
            "--min-instances", str(cfg.min_instances), "--concurrency", str(cfg.concurrency),
            "--timeout", str(cfg.timeout_seconds), "--cpu", cfg.cpu, "--memory", cfg.memory,
            "--set-env-vars", env,
            "--set-secrets", f"{cfg.secret['env']}={cfg.secret['name']}:{cfg.secret['version']}"]
    if ctx.mode == "bootstrap":
        args.append("--allow-unauthenticated")  # herkese açık API; kimlik uygulama içinde doğrulanır
    return gc(ctx, *args)


def step_deploy(ctx):
    ctx.call(deploy_args(ctx), "Cloud Run dağıtımı")


def describe(ctx):
    out = ctx.call(gc(ctx, "run", "services", "describe", ctx.cfg.service, "--region", ctx.cfg.region,
                      "--format=json"), "servis açıklaması")
    return json.loads(out)


def step_revision(ctx):
    status = describe(ctx).get("status", {})
    ready, created = status.get("latestReadyRevisionName"), status.get("latestCreatedRevisionName")
    if not ready or ready != created:
        raise DeployError("Son oluşturulan revizyon hazır değil.")
    image = ctx.call(gc(ctx, "run", "revisions", "describe", ready, "--region", ctx.cfg.region,
                        "--format=value(spec.containers[0].image)"), "revizyon image'ı")
    if image != ctx.state["image"]:
        raise DeployError("Hazır revizyon dağıtılan digest'i çalıştırmıyor.")
    ctx.state["revision"], ctx.state["url"] = ready, status.get("url")
    if not ctx.state["url"]:
        raise DeployError("Cloud Run URL alınamadı.")


def step_health(ctx, attempts=30):
    for _ in range(attempts):
        code, body = ctx.http(f"{ctx.state['url']}/api/v1/health")
        if code == 200 and isinstance(body, dict) and body.get("success"):
            return
        ctx.sleep(5)
    raise DeployError("/health zamanında başarılı olmadı.")


def step_url(ctx):
    ctx.state["api_base"] = f"{ctx.state['url']}/api/v1"


def step_web_config(ctx):
    web_firebase_config(ctx.root, ctx.cfg.project_id)


def step_web_build(ctx):
    for name in ("out", ".next"):
        shutil.rmtree(ctx.root / "apps/web" / name, ignore_errors=True)
    ctx.call(["npm", "run", "build:web"], "web build", env={**os.environ, "NEXT_PUBLIC_API_BASE_URL": ctx.state["api_base"]})
    if not (ctx.root / "apps/web/out/index.html").exists():
        raise DeployError("Statik dışa aktarım oluşmadı: apps/web/out/index.html yok.")


def step_rewrite(ctx):
    check_rewrite(ctx.root, ctx.cfg)


def step_hosting(ctx):
    if ctx.publish_hosting:
        ctx.call(["firebase", "deploy", "--only", "hosting", "--project", ctx.cfg.project_id], "Hosting yayını")


STEPS = (
    ("Yerel kapılar: main dalı, temiz ağaç, origin/main, API testleri", step_local_gates),
    ("Ön koşullar (yalnız kontrol): proje, billing, API'ler, Artifact Registry, secret, hizmet hesabı, mod", step_prerequisites),
    ("Yapılandırma doğrulaması: bölge, instance sınırları, rewrite ve web yapılandırması (değişiklikten önce)", step_validate),
    ("Image build ve digest", step_build),
    ("Cloud Run dağıtımı (digest ile)", step_deploy),
    ("Hazır revizyon ve digest eşliği", step_revision),
    ("/api/v1/health doğrulaması", step_health),
    ("API URL'si", step_url),
    ("Web Firebase yapılandırması", step_web_config),
    ("Web build (NEXT_PUBLIC_API_BASE_URL = Cloud Run URL/api/v1)", step_web_build),
    ("firebase.json /s/** rewrite tutarlılığı (servis ve bölge)", step_rewrite),
    ("Hosting yayını (yalnız --publish-hosting)", step_hosting),
)


def plan_lines(ctx):
    cfg = ctx.cfg
    lines = [f"Mod: {ctx.mode}  Proje: {cfg.project_id}  Bölge: {cfg.region or '<K2 kararı yok>'}  Servis: {cfg.service}"]
    if not cfg.region:
        lines.append(f"UYARI: {cfg.region_decision}")
    for number, (title, _) in enumerate(STEPS, 1):
        lines.append(f"{number:>2}. {title}")
    shown = Context(Config(**{**vars(cfg), "region": cfg.region or "<K2>"}), ctx.mode, ctx.root, ctx.run)
    lines.append("    " + " ".join(deploy_args(shown)))
    if not ctx.publish_hosting:
        lines.append("    Hosting yayımlanmayacak; sonra: firebase deploy --only hosting --project " + cfg.project_id)
    return lines


def execute(ctx, log=print):
    if not ctx.cfg.region or not REGION.match(ctx.cfg.region):  # ön koşul komutları bölgeye ihtiyaç duyar
        raise DeployError(f"Bölge yok veya geçersiz. {ctx.cfg.region_decision}")
    for number, (title, action) in enumerate(STEPS, 1):
        log(f"{number}/{len(STEPS)} {title}")
        action(ctx)
    return ctx.state


def main(argv=None, runner: Runner | None = None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", required=True, choices=["bootstrap", "update"])
    parser.add_argument("--region")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--plan-only", action="store_true", help="varsayılan: yalnız planı yazdır")
    group.add_argument("--execute", action="store_true")
    parser.add_argument("--publish-hosting", action="store_true")
    args = parser.parse_args(argv)
    ctx = Context(load_config(ROOT, args.region), args.mode, ROOT, runner or system_runner,
                  publish_hosting=args.publish_hosting)
    if not args.execute:
        print("\n".join(plan_lines(ctx)))
        return 0
    try:
        state = execute(ctx)
    except DeployError as error:
        print(f"DURDU: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"revision": state["revision"], "image": state["image"], "api": state["api_base"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
