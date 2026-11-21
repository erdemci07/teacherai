"""TA-005 canlı proje denetimi. Yalnız okur; kaynak oluşturmaz, değiştirmez, API etkinleştirmez.

Kullanım (depo kökünden):
    python -m scripts.migration.audit_projects --source math-ai-07 --target teacherai-07 \\
        --output docs/migration/TA-005-audit-live.md

Kimlik: önce Application Default Credentials (`gcloud auth application-default login`),
yoksa etkin gcloud kullanıcı oturumunun kısa ömürlü erişim belirteci. Hizmet hesabı anahtarı
kullanılmaz. Belirteç ekrana veya dosyaya yazılmaz.

Gizlilik: Çıktı yalnız toplu sayı, ad ve yapı bilgisi içerir. UID karşılaştırması bellekte
yapılır; çıktıya UID, e-posta, telefon veya parola özeti yazılmaz. Auth kullanıcıları sunucu
tarafı alan maskesiyle (`localId`, `createdAt`, sağlayıcı kimliği) istenir; sunucu başka alan
döndürürse o bölüm atılır. Kişisel veri taşıyabilecek koleksiyonlarda (users, student_profiles,
feedback) yalnız belge kimliği veya sahip alanı okunur. Kişisel hesaplar IAM özetinde maskelenir.
"""

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
READ_VERBS = {"list", "describe", "get-iam-policy"}
WRITE_WORDS = {"create", "update", "delete", "deploy", "enable", "disable", "import", "export",
               "add-iam-policy-binding", "set-iam-policy", "access", "add", "set", "patch", "remove"}
FS = "https://firestore.googleapis.com/v1/projects/{p}/databases/(default)/documents"
IDT = "https://identitytoolkit.googleapis.com"
# Kişisel veri taşıyabilen koleksiyonlarda içerik okunmaz; yalnız kimlik/sahip alanı.
PII_COLLECTIONS = {"users", "student_profiles", "feedback", "account_deletions"}
# Koleksiyon → sahip UID'si nerede (None: belge kimliği). owner_hash sha256(uid) özetidir.
OWNER_FIELDS = {
    "users": None, "student_profiles": None, "student_memories": None, "account_deletions": None,
    "lessons": "student_id", "practice_questions": "student_id", "practice_attempts": "student_id",
    "interaction_events": "student_id", "shared_solutions": "owner_id", "feedback": "user_id",
    "lesson_analyses": "owner", "ai_daily_usage": "owner_hash", "ai_output_usage": "owner_hash",
}
USER_FIELDS = {"localId", "createdAt", "providerUserInfo"}


class AuditError(RuntimeError):
    pass


def error_class(text):
    """Hata metninden kişisel veri içermeyen sınıf (gcloud hataları hesap e-postası taşır)."""
    for code in ("SERVICE_DISABLED", "PERMISSION_DENIED", "NOT_FOUND", "UNAUTHENTICATED",
                 "FAILED_PRECONDITION", "INVALID_ARGUMENT", "RESOURCE_EXHAUSTED"):
        if code in text:
            return code
    if "has not been used" in text or "is disabled" in text:
        return "SERVICE_DISABLED"
    if "does not have permission" in text or "403" in text:
        return "PERMISSION_DENIED"
    if "404" in text or "not found" in text.lower():
        return "NOT_FOUND"
    return "ERROR"


def guard(args):
    """Yalnız okuyan gcloud komutlarına izin verir; diğer her fiil kod düzeyinde reddedilir."""
    words = [a for a in args if not a.startswith("-")]
    if not READ_VERBS.intersection(words) or WRITE_WORDS.intersection(words):
        raise AuditError(f"salt okunur olmayan komut reddedildi: gcloud {' '.join(words)}")


def gcloud(project, *args):
    guard(args)
    exe = shutil.which("gcloud")
    if not exe:
        raise AuditError("gcloud bulunamadı")
    env = {**os.environ, "CLOUDSDK_CORE_DISABLE_PROMPTS": "1"}
    cmd = [exe, *args, f"--project={project}", "--format=json"]
    done = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env, timeout=180, check=False)
    if done.returncode:
        return {"error": error_class(done.stderr)}
    return json.loads(done.stdout or "null")


def access_token():
    import google.auth
    import google.auth.exceptions
    import google.auth.transport.requests

    try:
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(google.auth.transport.requests.Request())
        return creds.token, "application-default"
    except google.auth.exceptions.GoogleAuthError:  # ADC yoksa gcloud kullanıcı oturumu
        exe = shutil.which("gcloud")
        done = subprocess.run([exe, "auth", "print-access-token"], capture_output=True, text=True,
                              env={**os.environ, "CLOUDSDK_CORE_DISABLE_PROMPTS": "1"}, timeout=60, check=False)
        if done.returncode:
            raise AuditError("kimlik yok: gcloud auth application-default login gerekli") from None
        return done.stdout.strip(), "gcloud-user"


class Rest:
    """Salt okunur REST istemcisi. POST yalnız sorgu uç noktalarına izinlidir."""

    QUERY_SUFFIXES = (":runQuery", ":runAggregationQuery", ":listCollectionIds", "accounts:query")

    def __init__(self, token):
        self.token = token

    def __call__(self, url, project, body=None):
        if body is not None and not url.split("?")[0].endswith(self.QUERY_SUFFIXES):
            raise AuditError("yalnız sorgu POST'larına izin var")
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, method="GET" if body is None else "POST")
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("x-goog-user-project", project)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read() or b"null")
        except urllib.error.HTTPError as exc:
            return {"error": error_class(f"{exc.code} {exc.read().decode(errors='ignore')}")}
        except urllib.error.URLError:
            return {"error": "NETWORK"}


# ---------- saf özet fonksiyonları (birim testli) ----------

def mask_member(member, people):
    kind = member.partition(":")[0]
    if kind in {"user", "group", "domain"}:  # kişi veya kurum: maskele; hizmet hesapları adıyla kalır
        label = people.setdefault(member, f"{kind}-{len([m for m in people if m.startswith(kind)]) + 1}")
        return f"{kind}:<{label}>"
    return member


def summarize_iam(policy):
    people = {}
    rows = []
    for binding in (policy or {}).get("bindings", []):
        members = [mask_member(m, people) for m in binding.get("members", [])]
        kinds = Counter(m.partition(":")[0] for m in binding.get("members", []))
        rows.append({"role": binding["role"], "members": sorted(members), "kinds": dict(kinds)})
    return sorted(rows, key=lambda r: r["role"])


def provider_of(user):
    providers = sorted({p.get("providerId", "?") for p in user.get("providerUserInfo") or []})
    return "+".join(providers) if providers else "anonymous"


def auth_summary(users):
    dates = sorted(datetime.fromtimestamp(int(u["createdAt"]) / 1000, UTC).date().isoformat()
                   for u in users if u.get("createdAt"))
    return {"count": len(users), "providers": dict(Counter(provider_of(u) for u in users)),
            "created": [dates[0], dates[-1]] if dates else None}


def overlap(left, right):
    return {"both": len(left & right), "only_left": len(left - right), "only_right": len(right - left)}


def owner_mapping(owners_by_collection, uids_by_project):
    """Koleksiyon başına sahip UID'lerinin hangi Auth projesinde karşılığı olduğu (yalnız sayı)."""
    hashed = {p: {hashlib.sha256(u.encode()).hexdigest() for u in uids} for p, uids in uids_by_project.items()}
    result = {}
    for collection, owners in owners_by_collection.items():
        hashed_field = OWNER_FIELDS.get(collection) == "owner_hash"
        pool = hashed if hashed_field else uids_by_project
        distinct = set(owners)
        row = {"distinct_owners": len(distinct)}
        for project, ids in pool.items():
            row[project] = len(distinct & ids)
        row["none"] = len([o for o in distinct if not any(o in ids for ids in pool.values())])
        result[collection] = row
    return result


def index_key(index):
    fields = tuple((f.get("fieldPath"), f.get("order") or f.get("arrayConfig"))
                   for f in index.get("fields", []) if f.get("fieldPath") != "__name__")
    group = index.get("collectionGroup") or index.get("name", "").split("/collectionGroups/")[-1].split("/")[0]
    return (group, index.get("queryScope", "COLLECTION"), fields)


def index_diff(live, repo):
    live_keys = {index_key(i) for i in live}
    repo_keys = {index_key(i) for i in repo}
    return {"only_live": sorted(map(str, live_keys - repo_keys)), "only_repo": sorted(map(str, repo_keys - live_keys)),
            "same": len(live_keys & repo_keys)}


def value_types(value, counts, source):
    for kind, inner in value.items():
        counts[kind] += 1
        if kind == "referenceValue" and f"projects/{source}/" in inner:
            counts["reference_to_source_project"] += 1
        elif kind == "mapValue":
            for v in (inner.get("fields") or {}).values():
                value_types(v, counts, source)
        elif kind == "arrayValue":
            for v in inner.get("values") or []:
                value_types(v, counts, source)
        elif kind == "stringValue" and ".run.app" in inner:
            counts["string_with_run_app"] += 1


def cloud_run_summary(service):
    meta, spec = service.get("metadata", {}), service.get("spec", {}).get("template", {})
    ann = {**meta.get("annotations", {}), **spec.get("metadata", {}).get("annotations", {})}
    tspec = spec.get("spec", {})
    container = (tspec.get("containers") or [{}])[0]
    env_names, secret_refs, public_hosts = [], [], {}
    for item in container.get("env", []):
        ref = (item.get("valueFrom") or {}).get("secretKeyRef")
        if ref:
            secret_refs.append(f"{item['name']} ← {ref.get('name')}:{ref.get('key')}")
        else:
            env_names.append(item["name"])
            if item["name"].endswith(("PUBLIC_APP_URL", "PUBLIC_SHARE_URL_BASE")):  # herkese açık adres; yalnız host
                public_hosts[item["name"]] = urllib.parse.urlsplit(item.get("value", "")).netloc
    return {
        "revision": service.get("status", {}).get("latestReadyRevisionName"),
        "url": service.get("status", {}).get("url"),
        "min_instances": ann.get("autoscaling.knative.dev/minScale", "0 (varsayılan)"),
        "max_instances": ann.get("autoscaling.knative.dev/maxScale", "belirtilmemiş"),
        "concurrency": tspec.get("containerConcurrency"),
        "timeout_seconds": tspec.get("timeoutSeconds"),
        "cpu": container.get("resources", {}).get("limits", {}).get("cpu"),
        "memory": container.get("resources", {}).get("limits", {}).get("memory"),
        "ingress": ann.get("run.googleapis.com/ingress", "all"),
        "service_account": tspec.get("serviceAccountName"),
        "env_names": sorted(env_names), "secret_refs": sorted(secret_refs), "public_url_hosts": public_hosts,
    }


def decide(facts, source, target):
    """K1–K4 kararları; kanıt yoksa 'doğrulanamadı'."""
    auth = facts.get("auth", {})
    counts = {p: (auth.get(p) or {}).get("count") for p in (source, target)}
    k = {}
    if None in counts.values():
        k["K1"] = ("doğrulanamadı", f"Auth sayıları okunamadı: {counts}")
    elif counts[source] and counts[target]:
        k["K1"] = ("c", f"iki projede de kullanıcı var: {counts}; kesişim {auth.get('overlap')}")
    elif counts[source]:
        k["K1"] = ("b", f"kullanıcılar {source}'da ({counts[source]}), {target}'de 0")
    elif counts[target]:
        k["K1"] = ("a", f"kullanıcılar {target}'de ({counts[target]}), {source}'da 0")
    else:
        k["K1"] = ("a", "iki projede de kullanıcı yok; taşınacak Auth verisi yok")
    dbs = (facts.get("firestore", {}).get(target) or {}).get("databases")
    if isinstance(dbs, dict) and dbs.get("error") == "SERVICE_DISABLED":
        k["K2"] = ("yok", f"{target}'de Firestore API etkin değil; veritabanı yok")
    elif isinstance(dbs, list):
        k["K2"] = ("var" if dbs else "yok", ", ".join(f"{d['name'].split('/')[-1]} @ {d.get('locationId')}" for d in dbs) or "veritabanı yok")
    else:
        k["K2"] = ("doğrulanamadı", str(dbs))
    billing = (facts.get("project", {}).get(target) or {}).get("billing")
    k["K3"] = ("Blaze" if billing is True else "Spark" if billing is False else "doğrulanamadı",
               f"billingEnabled={billing}")
    bundle = facts.get("web_bundle", {})
    shares = (facts.get("firestore", {}).get(source) or {}).get("share_scan", {})
    hist = facts.get("share_url_history", [])
    evidence = (f"paylaşım URL'si belgede saklanmıyor (run.app içeren dize: {shares.get('string_with_run_app', 'okunamadı')}); "
                f"git geçmişinde run.app tabanlı paylaşım commit'leri: {len(hist)}; Hosting /s/ yönlendirmesi run.app'e: {bundle.get('share_redirect_to_run_app')}")
    k["K4"] = ("evet" if hist else "doğrulanamadı", evidence)
    return k


# ---------- toplayıcılar ----------

def collect_project(project, rest):
    info = gcloud(project, "projects", "describe", project)
    billing = gcloud(project, "billing", "projects", "describe", project)
    services = gcloud(project, "services", "list", "--enabled")
    return {
        "number": info.get("projectNumber") if isinstance(info, dict) else None,
        "billing": billing.get("billingEnabled") if isinstance(billing, dict) and "error" not in billing else None,
        "services": sorted(s["config"]["name"] for s in services) if isinstance(services, list) else services,
    }


def list_users(project, rest):
    counted = rest(f"{IDT}/v1/projects/{project}/accounts:query", project, {"returnUserInfo": False})
    if "error" in (counted or {}):
        return {"error": counted["error"]}, set()
    users, token = [], None
    mask = "users(localId,createdAt,providerUserInfo(providerId)),nextPageToken"
    while True:
        query = {"maxResults": 1000, "fields": mask, **({"nextPageToken": token} if token else {})}
        page = rest(f"{IDT}/v1/projects/{project}/accounts:batchGet?{urllib.parse.urlencode(query)}", project)
        if "error" in (page or {}):
            return {"error": page["error"], "count": int(counted.get("recordsCount", 0))}, set()
        batch = page.get("users", [])
        if any(set(u) - USER_FIELDS for u in batch):
            return {"error": "FIELD_MASK_IGNORED", "count": int(counted.get("recordsCount", 0))}, set()
        users += batch
        token = page.get("nextPageToken")
        if not token or not batch:
            break
    summary = auth_summary(users)
    summary["records_count"] = int(counted.get("recordsCount", 0))
    return summary, {u["localId"] for u in users}


def collect_auth_config(project, rest):
    base = f"{IDT}/admin/v2/projects/{project}"
    cfg = rest(f"{base}/config?fields=signIn(email(enabled,passwordRequired),anonymous(enabled),"
               "phoneNumber(enabled)),authorizedDomains", project)
    idps = rest(f"{base}/defaultSupportedIdpConfigs?fields=defaultSupportedIdpConfigs(name,enabled)", project)
    if "error" in (cfg or {}):
        return {"error": cfg["error"]}
    methods = {k: v.get("enabled", False) for k, v in (cfg.get("signIn") or {}).items() if isinstance(v, dict)}
    for idp in (idps or {}).get("defaultSupportedIdpConfigs", []):
        methods[idp["name"].split("/")[-1]] = idp.get("enabled", False)
    return {"methods": methods, "authorized_domains": cfg.get("authorizedDomains", [])}


def fs_query(rest, project, collection, select=None, limit=1000, max_docs=None):
    docs, last = [], None
    while True:
        q = {"from": [{"collectionId": collection}], "orderBy": [{"field": {"fieldPath": "__name__"}}], "limit": limit}
        if select is not None:
            q["select"] = {"fields": [{"fieldPath": f} for f in select]}
        if last:
            q["startAt"] = {"values": [{"referenceValue": last}], "before": False}
        page = rest(f"{FS.format(p=project)}:runQuery", project, {"structuredQuery": q})
        if isinstance(page, dict) and "error" in page:
            raise AuditError(page["error"])
        batch = [row["document"] for row in page if "document" in row]
        docs += batch
        if len(batch) < limit or (max_docs and len(docs) >= max_docs):
            return docs
        last = batch[-1]["name"]


def collect_firestore(project, rest, source):
    out = {"databases": gcloud(project, "firestore", "databases", "list")}
    if not isinstance(out["databases"], list) or not out["databases"]:
        return out
    out["ttl"] = gcloud(project, "firestore", "fields", "ttls", "list", "--database=(default)")
    out["indexes"] = gcloud(project, "firestore", "indexes", "composite", "list", "--database=(default)")
    out["backup_schedules"] = gcloud(project, "firestore", "backups", "schedules", "list", "--database=(default)")
    names = rest(f"{FS.format(p=project)}:listCollectionIds", project, {"pageSize": 300})
    collections = sorted((names or {}).get("collectionIds", []))
    counts, owners, types, ranges, subcollections = {}, {}, {}, {}, {}
    for name in collections:
        agg = rest(f"{FS.format(p=project)}:runAggregationQuery", project, {"structuredAggregationQuery": {
            "structuredQuery": {"from": [{"collectionId": name}]}, "aggregations": [{"alias": "n", "count": {}}]}})
        counts[name] = int(agg[0]["result"]["aggregateFields"]["n"]["integerValue"]) if isinstance(agg, list) else agg
        field = OWNER_FIELDS.get(name, "?")
        if field != "?":
            docs = fs_query(rest, project, name, select=[field] if field else [])
            owners[name] = [d["name"].rsplit("/", 1)[-1] if field is None else
                            (d.get("fields", {}).get(field) or {}).get("stringValue") for d in docs]
            owners[name] = [o for o in owners[name] if o]
        stamps = fs_query(rest, project, name, select=["created_at"], max_docs=100000)
        values = sorted(v for d in stamps for v in [(d.get("fields", {}).get("created_at") or {})]
                        for v in [v.get("timestampValue") or v.get("stringValue")] if v)
        ranges[name] = [values[0][:10], values[-1][:10]] if values else None
        sample = fs_query(rest, project, name, select=[], limit=5, max_docs=5)
        subcollections[name] = sorted({c for d in sample for c in (rest(
            f"https://firestore.googleapis.com/v1/{d['name']}:listCollectionIds", project, {"pageSize": 50}) or {}).get("collectionIds", [])})
        if name not in PII_COLLECTIONS:
            counter = Counter()
            fields = Counter()
            for doc in fs_query(rest, project, name, max_docs=5000):
                for key, value in (doc.get("fields") or {}).items():
                    fields[f"{key}:{next(iter(value))}"] += 1
                    value_types(value, counter, source)
            types[name] = {"types": dict(counter), "fields": dict(fields)}
    out.update(collections=collections, counts=counts, owners=owners, types=types, created_ranges=ranges,
               subcollections=subcollections)
    if "shared_solutions" in types:
        out["share_scan"] = types["shared_solutions"]["types"]
    return out


def collect_rules(project, rest, repo_rules):
    releases = rest(f"https://firebaserules.googleapis.com/v1/projects/{project}/releases", project)
    if "error" in (releases or {}):
        return {"error": releases["error"]}
    firestore = [r for r in releases.get("releases", []) if "cloud.firestore" in r["name"]]
    if not firestore:
        return {"release": None}
    ruleset = rest(f"https://firebaserules.googleapis.com/v1/{firestore[0]['rulesetName']}", project)
    live = "\n".join(f.get("content", "") for f in ruleset.get("source", {}).get("files", []))
    diff = list(difflib.unified_diff(repo_rules.splitlines(), live.splitlines(), "repo/firestore.rules", "canlı", lineterm=""))
    return {"release": firestore[0]["name"].split("/releases/")[-1], "updated": firestore[0].get("updateTime"),
            "identical": not diff, "diff": diff}


def collect_run(project, rest):
    services = gcloud(project, "run", "services", "list")
    if not isinstance(services, list):
        return {"error": services.get("error") if isinstance(services, dict) else "?"}
    out = []
    for svc in services:
        name = svc["metadata"]["name"]
        region = svc["metadata"].get("labels", {}).get("cloud.googleapis.com/location")
        detail = gcloud(project, "run", "services", "describe", name, f"--region={region}")
        policy = gcloud(project, "run", "services", "get-iam-policy", name, f"--region={region}")
        public = any("allUsers" in b.get("members", []) and b["role"] == "roles/run.invoker"
                     for b in (policy or {}).get("bindings", []))
        out.append({"name": name, "region": region, **cloud_run_summary(detail), "allUsers_invoker": public})
    return out


def collect_other(project, rest):
    out = {"artifact_registry": gcloud(project, "artifacts", "repositories", "list")}
    if isinstance(out["artifact_registry"], list):
        out["artifact_registry"] = [f"{r['name'].split('/')[-1]} ({r.get('format')}, {r['name'].split('/')[3]})"
                                    for r in out["artifact_registry"]]
    secrets = gcloud(project, "secrets", "list")
    if isinstance(secrets, list):
        rows = []
        for s in secrets:
            name = s["name"].split("/")[-1]
            versions = gcloud(project, "secrets", "versions", "list", name)
            states = Counter(v.get("state") for v in versions) if isinstance(versions, list) else versions
            rows.append({"name": name, "versions": dict(states) if isinstance(states, Counter) else states})
        secrets = rows
    out["secrets"] = secrets
    buckets = gcloud(project, "storage", "buckets", "list")
    out["buckets"] = [f"{b.get('name')} ({b.get('location')})" for b in buckets] if isinstance(buckets, list) else buckets
    sites = rest(f"https://firebasehosting.googleapis.com/v1beta1/projects/{project}/sites", project)
    hosting = []
    for site in (sites or {}).get("sites", []):
        sid = site["name"].split("/")[-1]
        rel = rest(f"https://firebasehosting.googleapis.com/v1beta1/sites/{sid}/releases?pageSize=1", project)
        last = ((rel or {}).get("releases") or [{}])[0]
        domains = rest(f"https://firebasehosting.googleapis.com/v1beta1/projects/{project}/sites/{sid}/customDomains", project)
        hosting.append({"site": sid, "app": site.get("appId"), "last_release": last.get("releaseTime"),
                        "release_type": last.get("type"), "version_status": (last.get("version") or {}).get("status"),
                        "custom_domains": [d["name"].split("/")[-1] for d in (domains or {}).get("customDomains", [])]})
    out["hosting"] = hosting
    apps = rest(f"https://firebase.googleapis.com/v1beta1/projects/{project}/webApps", project)
    web = []
    for app in (apps or {}).get("apps", []):
        cfg = rest(f"https://firebase.googleapis.com/v1beta1/{app['name']}/config", project)
        appcheck = rest(f"https://firebaseappcheck.googleapis.com/v1/projects/{project}/apps/{app['appId']}/recaptchaV3Config", project)
        web.append({"app_id": app["appId"], "name": app.get("displayName"), "state": app.get("state"),
                    "project_id": (cfg or {}).get("projectId"), "auth_domain": (cfg or {}).get("authDomain"),
                    "app_check_recaptcha_v3": "yok/okunamadı: " + appcheck["error"] if "error" in (appcheck or {}) else "kayıtlı"})
    out["web_apps"] = web
    out["iam"] = summarize_iam(gcloud(project, "projects", "get-iam-policy", project))
    return out


def probe_bundle(site):
    """Canlı Hosting paketine gömülü Firebase yapılandırması ve API adresi (herkese açık GET)."""
    base = f"https://{site}.web.app"
    try:
        pages = [urllib.request.urlopen(f"{base}{p}", timeout=30).read().decode() for p in ("/", "/solve", "/login")]
    except urllib.error.URLError:
        return {"error": "NETWORK"}
    chunks = sorted({c for page in pages for c in re.findall(r'/_next/static/chunks/[^"\\]+\.js', page)})
    code = "".join(urllib.request.urlopen(f"{base}{c}", timeout=30).read().decode(errors="ignore") for c in chunks)
    return {
        "chunks": len(chunks),
        "firebase_env_inlined": "env.NEXT_PUBLIC_FIREBASE_PROJECT_ID" not in code,
        "project_ids": sorted(set(re.findall(r'projectId:"([a-z0-9-]+)"', code))),
        "auth_domains": sorted(set(re.findall(r'"([a-z0-9-]+\.firebaseapp\.com)"', code))),
        "api_hosts": sorted(set(re.findall(r'https://([a-z0-9-]+\.[a-z0-9-]+\.run\.app)', code))),
    }


def share_url_history():
    """`public_share_url_base` için run.app değerinin geçtiği commit'ler (yalnız kısa kimlik)."""
    done = subprocess.run(["git", "log", "--format=%h", "-S", ".run.app/s/", "--", "apps", "firebase.json"],
                          capture_output=True, text=True, cwd=ROOT, check=False)
    return done.stdout.split()


# ---------- rapor ----------

def render(facts, k, source, target):
    lines = [f"# TA-005 canlı proje denetimi ({source} → {target})", "",
             f"Üretim: `python -m scripts.migration.audit_projects`, {facts['generated']}, kimlik kaynağı `{facts['credential']}`. Salt okunur. Kişisel veri, UID ve gizli değer içermez.", ""]

    def section(title, body):
        lines.extend([f"## {title}", "", *body, ""])

    proj = facts["project"]
    section("1. Proje", [f"| | {source} | {target} |", "| --- | --- | --- |",
                         f"| Proje numarası | {proj[source]['number']} | {proj[target]['number']} |",
                         f"| Billing (Blaze) | {proj[source]['billing']} | {proj[target]['billing']} |",
                         f"| Etkin API sayısı | {len(proj[source]['services'])} | {len(proj[target]['services'])} |", "",
                         f"Yalnız {source}'da etkin: {', '.join(sorted(set(proj[source]['services']) - set(proj[target]['services'])))}", "",
                         f"Yalnız {target}'de etkin: {', '.join(sorted(set(proj[target]['services']) - set(proj[source]['services']))) or '—'}"])
    auth = facts["auth"]
    body = [f"| | {source} | {target} |", "| --- | --- | --- |"]
    for key in ("count", "providers", "created", "error"):
        body.append(f"| {key} | {auth[source].get(key, '—')} | {auth[target].get(key, '—')} |")
    for p in (source, target):
        cfg = facts["auth_config"][p]
        body.append(f"| oturum yöntemleri ({p}) | {cfg.get('methods', cfg.get('error'))} | |")
        body.append(f"| yetkili alanlar ({p}) | {cfg.get('authorized_domains', '—')} | |")
    body += ["", f"UID kesişimi: {auth.get('overlap', 'doğrulanamadı')} (left={source}, right={target})", "",
             "Firestore sahip UID'lerinin Auth karşılığı (farklı sahip sayısı):", "",
             f"| Koleksiyon | farklı sahip | {source} | {target} | hiçbiri |", "| --- | --- | --- | --- | --- |"]
    for coll, row in sorted(facts.get("owner_mapping", {}).items()):
        body.append(f"| {coll} | {row['distinct_owners']} | {row.get(source, '—')} | {row.get(target, '—')} | {row['none']} |")
    section("2. Auth", body)
    bundle = facts["web_bundle"]
    body = ["| Uygulama | Proje | Ad | authDomain | App Check |", "| --- | --- | --- | --- | --- |"]
    for p in (source, target):
        for app in facts["other"][p].get("web_apps", []):
            body.append(f"| {app['app_id']} | {p} | {app['name']} | {app['auth_domain']} | {app['app_check_recaptcha_v3']} |")
    body += ["", f"Canlı `{target}.web.app` paketi: {bundle}"]
    section("3. Web yapılandırması", body)
    body = []
    for p in (source, target):
        fs = facts["firestore"][p]
        body += [f"### {p}", "", f"- Veritabanları: {fs['databases']}"]
        if "collections" not in fs:
            body.append("")
            continue
        body += [f"- Yedek planları: {fs.get('backup_schedules')}",
                 f"- TTL: {[t.get('name', '').split('/fields/')[-1] + ' (' + t.get('ttlConfig', {}).get('state', '?') + ')' for t in fs['ttl']] if isinstance(fs['ttl'], list) else fs['ttl']}",
                 f"- Bileşik indeks farkı (canlı/repo): {facts['index_diff'].get(p)}",
                 f"- Kurallar: {({k: v for k, v in facts['rules'][p].items() if k != 'diff'})}", "",
                 "| Koleksiyon | Belge | created_at aralığı | Alt koleksiyon (5 örnek) | Değer türleri |", "| --- | --- | --- | --- | --- |"]
        for c in fs["collections"]:
            t = fs["types"].get(c, {}).get("types", "kişisel veri riski: içerik okunmadı")
            body.append(f"| {c} | {fs['counts'][c]} | {fs['created_ranges'].get(c)} | {fs['subcollections'].get(c) or '—'} | {t} |")
        diff = facts["rules"][p].get("diff")
        if diff:
            body += ["", "Canlı kural farkı:", "", "```diff", *diff, "```"]
        body.append("")
    section("4. Firestore", body)
    body = []
    for p in (source, target):
        body.append(f"- **{p}:** {json.dumps(facts['run'][p], ensure_ascii=False)}")
    section("5. Cloud Run", body)
    body = []
    for p in (source, target):
        o = facts["other"][p]
        body += [f"### {p}", "", f"- Artifact Registry: {o['artifact_registry']}", f"- Secret Manager: {o['secrets']}",
                 f"- Bucket'lar: {o['buckets']}", f"- Hosting: {o['hosting']}", ""]
    section("6. Diğer", body)
    body = []
    for p in (source, target):
        body += [f"### {p}", "", "| Rol | Üyeler |", "| --- | --- |"]
        body += [f"| {r['role']} | {', '.join(r['members'])} |" for r in facts["other"][p]["iam"]]
        body.append("")
    section("7. IAM (kişisel hesaplar maskeli)", body)
    section("8. Paylaşım bağlantıları", [
        f"- `shared_solutions` belge sayısı ({source}): {facts['firestore'][source].get('counts', {}).get('shared_solutions')}",
        f"- Paylaşım belgelerindeki değer türleri: {facts['firestore'][source].get('share_scan')}",
        f"- run.app paylaşım tabanının geçtiği commit'ler: {', '.join(facts['share_url_history']) or 'yok'}"])
    section("Bulunan durum", [f"- **{key}:** {val[0]} — {val[1]}" for key, val in k.items()])
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", default="math-ai-07")
    parser.add_argument("--target", default="teacherai-07")
    parser.add_argument("--output", default="docs/migration/TA-005-audit-live.md")
    args = parser.parse_args(argv)
    token, credential = access_token()
    rest = Rest(token)
    repo_rules = (ROOT / "firestore.rules").read_text(encoding="utf-8")
    repo_indexes = json.loads((ROOT / "firestore.indexes.json").read_text(encoding="utf-8"))["indexes"]
    projects = (args.source, args.target)
    facts = {"generated": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"), "credential": credential,
             "project": {}, "auth": {}, "auth_config": {}, "firestore": {}, "rules": {}, "run": {}, "other": {}, "index_diff": {}}
    uids = {}
    for p in projects:
        facts["project"][p] = collect_project(p, rest)
        facts["auth"][p], uids[p] = list_users(p, rest)
        facts["auth_config"][p] = collect_auth_config(p, rest)
        facts["firestore"][p] = collect_firestore(p, rest, args.source)
        facts["rules"][p] = collect_rules(p, rest, repo_rules)
        facts["run"][p] = collect_run(p, rest)
        facts["other"][p] = collect_other(p, rest)
        live = facts["firestore"][p].get("indexes")
        if isinstance(live, list):
            facts["index_diff"][p] = index_diff(live, repo_indexes)
    if all("error" not in facts["auth"][p] for p in projects):
        facts["auth"]["overlap"] = overlap(uids[args.source], uids[args.target])
    owners = {c: v for p in projects for c, v in facts["firestore"][p].get("owners", {}).items()}
    facts["owner_mapping"] = owner_mapping(owners, uids)
    facts["web_bundle"] = probe_bundle(args.target)
    facts["web_bundle"]["share_redirect_to_run_app"] = ".run.app/s/" in (ROOT / "firebase.json").read_text(encoding="utf-8")
    facts["share_url_history"] = share_url_history()
    for p in projects:  # sahip listeleri yalnız bellekte; rapora girmez
        facts["firestore"][p].pop("owners", None)
    k = decide(facts, args.source, args.target)
    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(facts, k, args.source, args.target), encoding="utf-8")
    print(f"yazıldı: {args.output}")
    for key, val in k.items():
        print(f"{key}: {val[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
