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

TA-005C:
- **Ortam uzlaştırması (Update).** ``--set-env-vars``/``--set-secrets`` servisin ortamını tümüyle değiştirir.
  Bu yüzden önce çalışan servisin ortamı okunur: yönetilen değişkenler bu betikten gelir, onaylı çalışma
  zamanı ayarları (``runtime_env_policy.preserve_env``) ve secret referansları (``preserve_secrets``)
  korunur. Yasaklı (düz metin anahtar, hizmet hesabı JSON'u, debug) veya listede olmayan ad değişiklikten
  önce dağıtımı durdurur; kaldırma yalnız ``--drop-env AD`` ile açıkça yapılır. Değerler yazdırılmaz.
- **Firebase web yapılandırması.** Çevrimdışı biçim denetimi (proje, AUTH_DOMAIN, APP_ID, API_KEY,
  isteğe bağlı alanlar) ve ``--execute``'ta değişiklikten önce ``firebase apps:list``/``apps:sdkconfig``
  ile hedef uygulamanın gerçek SDK yapılandırmasıyla alan alan karşılaştırma. Plan kipinde yalnız
  çevrimdışı denetim yapılır ve bu açıkça yazılır. Hiçbir değer yazdırılmaz.
- **Tutarlılık.** Cloud Run bölgesi, Hosting rewrite'ları, ``.firebaserc`` ve ``cloudbuild.api.yaml``
  image yolu aynı proje/bölge/depoyu göstermelidir.
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
# Web paketinde varsa doğrulanan isteğe bağlı SDK alanları; env adı → sdkConfig alanı.
WEB_SDK_FIELDS = {"API_KEY": "apiKey", "AUTH_DOMAIN": "authDomain", "PROJECT_ID": "projectId", "APP_ID": "appId",
                  "STORAGE_BUCKET": "storageBucket", "MESSAGING_SENDER_ID": "messagingSenderId",
                  "MEASUREMENT_ID": "measurementId"}
API_KEY_FORMAT = re.compile(r"^AIza[0-9A-Za-z_-]{35}$")
APP_ID_FORMAT = re.compile(r"^1:(\d+):web:[0-9a-f]+$")
# Cloud Run'ın ortamı tümüyle değiştirdiği için betiğin her dağıtımda kendisinin yazdığı değişkenler.
MANAGED_ENV = ("TEACHERAI_ENVIRONMENT", "TEACHERAI_FIREBASE_ENABLED", "TEACHERAI_FIREBASE_PROJECT_ID",
               "TEACHERAI_FIREBASE_AUTH_PROJECT_ID")
DELIMITERS = ",|;~#@"
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
    runtime_env_policy: dict = field(default_factory=dict)
    firebase_web: dict = field(default_factory=dict)

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
    drop_env: frozenset = frozenset()

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


def web_firebase_config(root, project_id, environ=None, approved_auth_domains=()):
    """Web paketine girecek Firebase SDK yapılandırması; çevrimdışı biçim denetimi. Değer yazdırılmaz.

    Dönen sözlük ``WEB_SDK_FIELDS`` anahtarlarıyla (``API_KEY`` …) yalnız tanımlı alanları taşır.
    """
    values = {}
    for name in reversed(WEB_ENV_FILES):
        path = Path(root) / "apps/web" / name
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                key, sep, value = line.strip().partition("=")
                if sep and not key.startswith("#"):
                    values[key.strip()] = value.strip().strip("'\"")
    values |= {k: v for k, v in (os.environ if environ is None else environ).items() if k.startswith("NEXT_PUBLIC_")}
    web = {key: values[f"NEXT_PUBLIC_FIREBASE_{key}"] for key in WEB_SDK_FIELDS if values.get(f"NEXT_PUBLIC_FIREBASE_{key}")}
    missing = [key for key in WEB_KEYS if key not in web]
    if missing:
        raise DeployError(f"Firebase web yapılandırması eksik: {', '.join(missing)}")
    if web["PROJECT_ID"] != project_id:
        raise DeployError("Firebase web PROJECT_ID dağıtım projesiyle aynı değil (tek proje).")
    problems = []
    if web["AUTH_DOMAIN"] not in {f"{project_id}.firebaseapp.com", f"{project_id}.web.app", *approved_auth_domains}:
        problems.append("AUTH_DOMAIN (hedef projenin alanı veya onaylı özel alan değil)")
    app = APP_ID_FORMAT.match(web["APP_ID"])
    if not app:
        problems.append("APP_ID (web uygulaması kimliği biçimi değil)")
    elif "MESSAGING_SENDER_ID" in web and web["MESSAGING_SENDER_ID"] != app.group(1):
        problems.append("MESSAGING_SENDER_ID (APP_ID'deki proje numarasıyla aynı değil)")
    if not API_KEY_FORMAT.match(web["API_KEY"]):
        problems.append("API_KEY (Firebase web anahtarı biçimi değil)")
    if "STORAGE_BUCKET" in web and web["STORAGE_BUCKET"] not in {f"{project_id}.appspot.com", f"{project_id}.firebasestorage.app"}:
        problems.append("STORAGE_BUCKET (hedef projenin kovası değil)")
    if problems:
        raise DeployError("Firebase web yapılandırması karışık veya geçersiz: " + "; ".join(problems))
    return web


def verify_web_app(ctx, web):
    """Gerçek doğrulama: hedef projedeki web uygulamasının SDK yapılandırmasıyla alan alan karşılaştırma.

    ``firebase apps:sdkconfig`` uygulamayı proje jokeriyle (``projects/-``) okur; bu yüzden dönen
    ``projectId`` ayrıca hedefle karşılaştırılır ve uygulamanın hedef projede listelendiği denetlenir.
    Yalnız okuma komutlarıdır; hiçbir değer yazdırılmaz.
    """
    project = ctx.cfg.project_id
    listed = _json_result(ctx.call(["firebase", "apps:list", "WEB", "--project", project, "--json"], "Firebase web uygulama listesi"))
    if web["APP_ID"] not in {item.get("appId") for item in listed or [] if isinstance(item, dict)}:
        raise DeployError("Firebase web APP_ID hedef projede kayıtlı bir web uygulaması değil.")
    result = _json_result(ctx.call(["firebase", "apps:sdkconfig", "WEB", web["APP_ID"], "--project", project, "--json"],
                                   "Firebase web SDK yapılandırması"))
    sdk = (result or {}).get("sdkConfig") if isinstance(result, dict) else None
    if not isinstance(sdk, dict):
        raise DeployError("Firebase web SDK yapılandırması okunamadı.")
    custom = set(ctx.cfg.firebase_web.get("approved_auth_domains") or ())
    mismatched = sorted(key for key, value in web.items()
                        if not (key == "AUTH_DOMAIN" and value in custom) and sdk.get(WEB_SDK_FIELDS[key]) != value)
    if sdk.get("projectId") != project:
        mismatched.append("projectId (uygulama başka projeye ait)")
    if mismatched:
        raise DeployError("Firebase web yapılandırması hedef uygulamayla uyuşmuyor: " + ", ".join(mismatched))
    ctx.state["web_config_verification"] = "authoritative"


def _json_result(out):
    try:
        data = json.loads(out)
    except (TypeError, ValueError):
        raise DeployError("Firebase CLI JSON çıktısı okunamadı.") from None
    if not isinstance(data, dict) or data.get("status") != "success":
        raise DeployError("Firebase CLI komutu başarılı sonuç döndürmedi.")
    return data.get("result")


def check_rewrite(root, cfg):
    hosting = json.loads((Path(root) / "firebase.json").read_text(encoding="utf-8-sig"))["hosting"]
    rules = [rule for rule in hosting.get("rewrites", []) if rule.get("source") == "/s/**"]
    run = rules[0].get("run", {}) if rules else {}
    if run.get("serviceId") != cfg.service or run.get("region") != cfg.region:
        raise DeployError(f"firebase.json /s/** rewrite'ı {cfg.service} ({cfg.region}) servisine bağlı değil.")
    for rule in hosting.get("rewrites", []):  # TA-005C: Cloud Run'a giden her rewrite aynı servis ve bölge
        target = rule.get("run")
        if target and (target.get("serviceId") != cfg.service or target.get("region") != cfg.region):
            raise DeployError(f"firebase.json {rule.get('source')} rewrite'ı {cfg.service} ({cfg.region}) servisine bağlı değil.")


def check_consistency(root, cfg):
    """TA-005C: proje, bölge ve Artifact Registry yolu dağıtım dosyalarında aynı olmalı (değişiklikten önce)."""
    firebaserc = json.loads((Path(root) / ".firebaserc").read_text(encoding="utf-8-sig"))
    if (firebaserc.get("projects") or {}).get("default") != cfg.project_id:
        raise DeployError(f".firebaserc varsayılan projesi {cfg.project_id} değil.")
    build = (Path(root) / "cloudbuild.api.yaml").read_text(encoding="utf-8")
    image = f"${{_REGION}}-docker.pkg.dev/$PROJECT_ID/{cfg.repository}/{cfg.service}:${{_TAG}}"
    if build.count(image) < 2:  # build adımı ve images listesi
        raise DeployError("cloudbuild.api.yaml image yolu bölge değişkeni, depo ve servisle uyuşmuyor.")
    if not cfg.image.startswith(f"{cfg.region}-docker.pkg.dev/{cfg.project_id}/{cfg.repository}/"):
        raise DeployError("Artifact Registry image yolu seçilen bölge ve projeyle uyuşmuyor.")


def current_runtime(service: dict) -> tuple[dict, dict]:
    """Çalışan servisin (env, secret referansları). Secret değeri okunmaz; yalnız ad ve sürüm."""
    containers = (((service.get("spec") or {}).get("template") or {}).get("spec") or {}).get("containers") or [{}]
    env, secrets = {}, {}
    for item in containers[0].get("env") or []:
        ref = (item.get("valueFrom") or {}).get("secretKeyRef")
        if ref:
            secrets[item["name"]] = f"{ref.get('name')}:{ref.get('key', 'latest')}"
        else:
            env[item["name"]] = item.get("value", "")
    return env, secrets


def reconcile_runtime(cfg, current_env, current_secrets, drop=frozenset()):
    """Yönetilen + korunan ortam. Bilinmeyen veya yasaklı ad ``DeployError``; değerler mesaja girmez."""
    policy = cfg.runtime_env_policy or {}
    preserve, preserve_secrets = set(policy.get("preserve_env") or ()), set(policy.get("preserve_secrets") or ())
    prohibited = set(policy.get("prohibited_env") or ())
    managed = {"TEACHERAI_ENVIRONMENT": "production", "TEACHERAI_FIREBASE_ENABLED": "true",
               "TEACHERAI_FIREBASE_PROJECT_ID": cfg.project_id, "TEACHERAI_FIREBASE_AUTH_PROJECT_ID": cfg.project_id}
    report = {"managed": sorted(managed), "preserved": [], "dropped": [], "managed_changed": []}
    blocked = sorted(name for name in current_env if name in prohibited and name not in drop)
    unknown = sorted(name for name in current_env
                     if name not in preserve | prohibited | set(MANAGED_ENV) and name not in drop)
    unknown_secrets = sorted(name for name in current_secrets
                             if name not in preserve_secrets | {cfg.secret["env"]} and name not in drop)
    if blocked:
        raise DeployError(f"Çalışan serviste yasaklı ortam değişkeni var: {', '.join(blocked)}. "
                          "Düz metin anahtar/hizmet hesabı/debug kabul edilmez; secret'a taşıyın veya --drop-env ile kaldırın.")
    if unknown or unknown_secrets:
        raise DeployError("Çalışan serviste politikada olmayan ayar var: " + ", ".join(unknown + unknown_secrets)
                          + ". Bilinmeyen ayar ne korunur ne silinir: runtime_env_policy'ye ekleyin veya --drop-env ile kaldırın.")
    env = dict(managed)
    for name, value in sorted(current_env.items()):
        if name in drop:
            report["dropped"].append(name)
        elif name in managed:
            if value != managed[name]:
                report["managed_changed"].append(name)
        elif name in preserve:
            env[name] = value
            report["preserved"].append(name)
    secrets = {cfg.secret["env"]: f"{cfg.secret['name']}:{cfg.secret['version']}"}
    for name, ref in sorted(current_secrets.items()):
        if name in drop:
            report["dropped"].append(name)
        elif name in preserve_secrets:
            secrets[name] = ref
            report["preserved"].append(name)
    return env, secrets, report


def env_flag(env: dict) -> str:
    """``--set-env-vars`` değeri. Değerde virgül varsa gcloud'un ``^ayraç^`` sözdizimi kullanılır."""
    for delimiter in DELIMITERS:
        if not any(delimiter in value for value in env.values()):
            joined = delimiter.join(f"{key}={value}" for key, value in env.items())
            return joined if delimiter == "," else f"^{delimiter}^{joined}"
    raise DeployError("Ortam değerleri için güvenli ayraç bulunamadı.")


def step_validate(ctx):
    cfg = ctx.cfg
    if not cfg.region or not REGION.match(cfg.region):
        raise DeployError(f"Bölge yok veya geçersiz. {cfg.region_decision}")
    if cfg.max_instances < 1 or cfg.min_instances < 0 or cfg.min_instances > cfg.max_instances:
        raise DeployError("Instance sınırları geçersiz.")
    if cfg.runtime_sa.endswith("-compute@developer.gserviceaccount.com"):
        raise DeployError("Compute varsayılan hesabı kullanılamaz.")
    check_rewrite(ctx.root, cfg)  # değişiklikten önce; 11. adımda yeniden denetlenir
    check_consistency(ctx.root, cfg)
    approved = tuple(cfg.firebase_web.get("approved_auth_domains") or ())
    web = web_firebase_config(ctx.root, cfg.project_id, approved_auth_domains=approved)  # 9. adımda yeniden denetlenir
    verify_web_app(ctx, web)  # gerçek SDK yapılandırması; yalnız okuma
    ctx.state["web_config"] = web
    if ctx.mode == "update":
        current_env, current_secrets = current_runtime(describe(ctx))
    else:
        current_env, current_secrets = {}, {}
    ctx.state["env"], ctx.state["secrets"], ctx.state["runtime_report"] = reconcile_runtime(
        cfg, current_env, current_secrets, ctx.drop_env)


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
    if "env" in ctx.state:  # TA-005C: uzlaştırılmış tam ortam (yönetilen + onaylı korunan)
        env = env_flag(ctx.state["env"])
        secrets = ",".join(f"{name}={ref}" for name, ref in ctx.state["secrets"].items())
    else:  # plan kipi: yalnız yönetilen değişkenler gösterilir; Update'te korunan ayarlar ayrıca okunur
        env = ",".join([
            "TEACHERAI_ENVIRONMENT=production",
            "TEACHERAI_FIREBASE_ENABLED=true",
            f"TEACHERAI_FIREBASE_PROJECT_ID={cfg.project_id}",
            f"TEACHERAI_FIREBASE_AUTH_PROJECT_ID={cfg.project_id}",
        ])
        secrets = f"{cfg.secret['env']}={cfg.secret['name']}:{cfg.secret['version']}"
    args = ["run", "deploy", cfg.service, "--image", ctx.state.get("image", f"{cfg.image}@<digest>"),
            "--region", cfg.region, "--platform", "managed", "--port", "8000",
            "--service-account", cfg.runtime_sa, "--max-instances", str(cfg.max_instances),
            "--min-instances", str(cfg.min_instances), "--concurrency", str(cfg.concurrency),
            "--timeout", str(cfg.timeout_seconds), "--cpu", cfg.cpu, "--memory", cfg.memory,
            "--set-env-vars", env,
            "--set-secrets", secrets]
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
    approved = tuple(ctx.cfg.firebase_web.get("approved_auth_domains") or ())
    if web_firebase_config(ctx.root, ctx.cfg.project_id, approved_auth_domains=approved) != ctx.state.get("web_config"):
        raise DeployError("Firebase web yapılandırması doğrulamadan sonra değişti; web build yapılmadı.")


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
    (("Yapılandırma doğrulaması (değişiklikten önce): bölge, instance sınırları, rewrite, .firebaserc ve image yolu, "
      "web yapılandırması (biçim + firebase apps:sdkconfig ile gerçek uygulama), çalışan ortamın uzlaştırılması"),
     step_validate),
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
    policy = cfg.runtime_env_policy or {}
    if ctx.mode == "update":
        lines.append(f"    Update: çalışan ortam okunur; {len(policy.get('preserve_env') or ())} onaylı ayar ve "
                     f"{len(policy.get('preserve_secrets') or ())} secret referansı korunur, bilinmeyen/yasaklı ad durdurur"
                     + (f"; --drop-env: {', '.join(sorted(ctx.drop_env))}" if ctx.drop_env else "") + ".")
    try:
        web_firebase_config(ctx.root, cfg.project_id, approved_auth_domains=tuple(cfg.firebase_web.get("approved_auth_domains") or ()))
        lines.append("    Firebase web yapılandırması: yalnız çevrimdışı biçim denetimi geçti. Gerçek uygulamayla "
                     "karşılaştırma --execute'ta değişiklikten önce yapılır.")
    except DeployError as error:
        lines.append(f"    Firebase web yapılandırması (çevrimdışı): {error}")
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
    parser.add_argument("--drop-env", action="append", default=[], metavar="AD",
                        help="Update: çalışan servisten bu ortam değişkenini veya secret referansını açıkça kaldır")
    args = parser.parse_args(argv)
    ctx = Context(load_config(ROOT, args.region), args.mode, ROOT, runner or system_runner,
                  publish_hosting=args.publish_hosting, drop_env=frozenset(args.drop_env))
    if not args.execute:
        print("\n".join(plan_lines(ctx)))
        return 0
    try:
        state = execute(ctx)
    except DeployError as error:
        print(f"DURDU: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"revision": state["revision"], "image": state["image"], "api": state["api_base"],
                      "runtime": state["runtime_report"], "web_config": state.get("web_config_verification")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
