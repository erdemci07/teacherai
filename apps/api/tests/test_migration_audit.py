"""TA-005 canlı denetim betiğinin ağsız birim testleri: salt okunur koruma ve kişisel veri maskeleme."""

import hashlib

import pytest

from scripts.migration import audit_projects as audit


@pytest.mark.parametrize("args", [
    ("firestore", "databases", "create"),
    ("services", "enable", "run.googleapis.com"),
    ("secrets", "versions", "access", "latest"),
    ("projects", "add-iam-policy-binding", "p"),
    ("run", "deploy", "svc"),
    ("firestore", "export", "gs://b"),
    ("config", "set", "project", "x"),
    ("auth", "print-identity-token"),
])
def test_guard_rejects_every_mutating_or_sensitive_command(args):
    with pytest.raises(audit.AuditError):
        audit.guard(args)


@pytest.mark.parametrize("args", [
    ("projects", "describe", "p"), ("services", "list", "--enabled"), ("projects", "get-iam-policy", "p"),
    ("firestore", "indexes", "composite", "list"), ("secrets", "versions", "list", "name"),
])
def test_guard_allows_read_only_commands(args):
    audit.guard(args)


def test_rest_client_refuses_non_query_post():
    with pytest.raises(audit.AuditError):
        audit.Rest("t")("https://firestore.googleapis.com/v1/projects/p/databases/(default)/documents/x", "p", {"a": 1})


def test_error_class_never_echoes_account_email():
    text = "ERROR: [someone@example.com] does not have permission ... SERVICE_DISABLED"
    assert audit.error_class(text) == "SERVICE_DISABLED"
    assert "@" not in audit.error_class("[a@b.c] does not have permission to access")


def test_iam_summary_masks_people_but_names_service_accounts():
    policy = {"bindings": [
        {"role": "roles/owner", "members": ["user:a@gmail.com", "group:g@x.org"]},
        {"role": "roles/editor", "members": ["serviceAccount:1-compute@developer.gserviceaccount.com", "user:a@gmail.com"]},
    ]}
    rows = audit.summarize_iam(policy)
    text = repr(rows)
    assert "gmail" not in text and "x.org" not in text
    assert "serviceAccount:1-compute@developer.gserviceaccount.com" in text
    owner = next(r for r in rows if r["role"] == "roles/owner")
    editor = next(r for r in rows if r["role"] == "roles/editor")
    assert set(owner["members"]) == {"user:<user-1>", "group:<group-1>"}
    assert "user:<user-1>" in editor["members"]  # aynı kişi aynı etiketi alır


def test_auth_summary_and_overlap_report_counts_only():
    users = [
        {"localId": "u1", "createdAt": "1756000000000", "providerUserInfo": [{"providerId": "password"}]},
        {"localId": "u2", "createdAt": "1757000000000", "providerUserInfo": [{"providerId": "google.com"}]},
        {"localId": "u3", "createdAt": "1758000000000"},
    ]
    summary = audit.auth_summary(users)
    assert summary == {"count": 3, "providers": {"password": 1, "google.com": 1, "anonymous": 1},
                       "created": ["2025-08-24", "2025-09-16"]}
    assert audit.overlap({"u1", "u2"}, {"u2", "u9"}) == {"both": 1, "only_left": 1, "only_right": 1}


def test_owner_mapping_matches_hashed_usage_owners_and_reports_numbers():
    uids = {"src": {"u1", "u2"}, "dst": {"u2"}}
    owners = {"lessons": ["u1", "u1", "u2", "ghost"],
              "ai_daily_usage": [hashlib.sha256(b"u2").hexdigest()]}
    result = audit.owner_mapping(owners, uids)
    assert result["lessons"] == {"distinct_owners": 3, "src": 2, "dst": 1, "none": 1}
    assert result["ai_daily_usage"] == {"distinct_owners": 1, "src": 1, "dst": 1, "none": 0}
    assert "u1" not in repr(result)


def test_index_diff_ignores_name_field_and_detects_missing_live_index():
    repo = [{"collectionGroup": "lessons", "queryScope": "COLLECTION", "fields": [
        {"fieldPath": "student_id", "order": "ASCENDING"}, {"fieldPath": "created_at", "order": "DESCENDING"}]}]
    live = [{"name": "projects/p/databases/(default)/collectionGroups/lessons/indexes/1", "queryScope": "COLLECTION",
             "fields": [{"fieldPath": "student_id", "order": "ASCENDING"}, {"fieldPath": "created_at", "order": "DESCENDING"},
                        {"fieldPath": "__name__", "order": "DESCENDING"}]}]
    assert audit.index_diff(live, repo)["same"] == 1
    assert audit.index_diff([], repo)["only_repo"]


def test_value_types_flag_source_project_references_and_run_app_strings():
    counts = audit.Counter()
    audit.value_types({"mapValue": {"fields": {
        "ref": {"referenceValue": "projects/math-ai-07/databases/(default)/documents/lessons/a"},
        "url": {"stringValue": "https://x-uk.a.run.app/s/abc"},
        "at": {"timestampValue": "2026-01-01T00:00:00Z"},
    }}}, counts, "math-ai-07")
    assert counts["reference_to_source_project"] == 1 and counts["string_with_run_app"] == 1
    assert counts["timestampValue"] == 1


def test_cloud_run_summary_lists_names_never_values():
    service = {"metadata": {"annotations": {"run.googleapis.com/ingress": "all"}},
               "status": {"latestReadyRevisionName": "r1", "url": "https://s.run.app"},
               "spec": {"template": {"metadata": {"annotations": {"autoscaling.knative.dev/maxScale": "20"}},
                                     "spec": {"containerConcurrency": 80, "timeoutSeconds": 300, "serviceAccountName": "sa",
                                              "containers": [{"env": [
                                                  {"name": "SECRET_PLAIN", "value": "sk-very-secret"},
                                                  {"name": "PUBLIC_APP_URL", "value": "https://teacherai-07.web.app"},
                                                  {"name": "OPENAI_API_KEY", "valueFrom": {"secretKeyRef": {"name": "openai-api-key", "key": "latest"}}},
                                              ], "resources": {"limits": {"cpu": "1", "memory": "512Mi"}}}]}}}}
    summary = audit.cloud_run_summary(service)
    assert "sk-very-secret" not in repr(summary)
    assert summary["env_names"] == ["PUBLIC_APP_URL", "SECRET_PLAIN"]
    assert summary["secret_refs"] == ["OPENAI_API_KEY ← openai-api-key:latest"]
    assert summary["public_url_hosts"] == {"PUBLIC_APP_URL": "teacherai-07.web.app"}
    assert summary["max_instances"] == "20" and summary["min_instances"].startswith("0")


def test_decisions_follow_evidence_and_fall_back_to_unverified():
    facts = {"auth": {"s": {"count": 5}, "t": {"count": 0}}, "project": {"t": {"billing": False}},
             "firestore": {"t": {"databases": {"error": "SERVICE_DISABLED"}}, "s": {}}, "web_bundle": {}, "share_url_history": []}
    k = audit.decide(facts, "s", "t")
    assert k["K1"][0] == "b" and k["K2"][0] == "yok" and k["K3"][0] == "Spark" and k["K4"][0] == "doğrulanamadı"
    facts["auth"]["t"] = {"count": 2}
    assert audit.decide(facts, "s", "t")["K1"][0] == "c"
    facts["auth"]["t"] = {"error": "PERMISSION_DENIED"}
    assert audit.decide(facts, "s", "t")["K1"][0] == "doğrulanamadı"
