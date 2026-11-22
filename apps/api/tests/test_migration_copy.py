"""TA-005/TA-005B Firestore kopya betiği. Yerel emülatörde iki sahte proje kimliği kullanılır; canlı proje yoktur."""

import datetime as dt
import json
import os
import re
from argparse import Namespace
from uuid import uuid4

import pytest
from google.api_core.datetime_helpers import DatetimeWithNanoseconds
from google.cloud.firestore import GeoPoint

from scripts.migration import copy_firestore as cf


@pytest.fixture
def projects():
    host = os.environ.get("FIRESTORE_EMULATOR_HOST")
    if not host:
        pytest.skip("local Firestore emulator required")
    assert re.fullmatch(r"(127\.0\.0\.1|localhost):\d+", host)
    suffix = uuid4().hex[:10]
    source_id, target_id = f"demo-src-{suffix}", f"demo-dst-{suffix}"
    source, target = cf.client(source_id), cf.client(target_id)
    yield source_id, target_id, source, target
    source.close()
    target.close()


def policy(authority="source", deleted=(), auth=("uid-1", "uid-2"), **kw):
    return cf.Policy(authority, set(deleted), None if auth is None else set(auth), **kw)


def run_copy(projects, collections, execute=True, pol=None, reverse=False):
    source_id, target_id, source, target = projects
    if reverse:
        source_id, target_id, source, target = target_id, source_id, target, source
    return cf.copy(source_id, target_id, collections, execute, pol or policy(), source=source, target=target)


def run_verify(projects, collections, pol=None, now=None):
    source_id, target_id, source, target = projects
    return cf.verify(source_id, target_id, collections, pol or policy(auth=None), source=source, target=target, now=now)


def seed(source):
    expires = dt.datetime(2026, 12, 1, 8, 30, tzinfo=dt.UTC)
    source.collection("lessons").document("lesson_a").set({
        "student_id": "uid-1", "created_at": dt.datetime(2026, 11, 1, tzinfo=dt.UTC), "where": GeoPoint(39.9, 32.8),
        "blob": b"\x00\x01", "profile": source.document("student_profiles/uid-1"), "nested": {"items": [1, {"k": "v"}]}})
    source.collection("lessons").document("lesson_a").collection("notes").document("n1").set({"text": "alt koleksiyon"})
    source.collection("lesson_analyses").document("an_1").set({"owner": "uid-2", "expires_at": expires})
    source.collection("student_profiles").document("uid-1").set({"student_id": "uid-1", "grade": 8})
    return expires


def args(**overrides):
    return Namespace(**({"source": "a", "target": "b", "execute": False, "confirm_target": None, "allow_reverse": False,
                         "verify": False, "prune": False, "confirm_prune": None, "prune_from": None,
                         "collections": ["lessons"]} | overrides))


# --- kanonik özet (emülatörsüz) ---

def test_canonical_distinguishes_every_firestore_type():
    base = {"n": 1}
    assert cf.digest(base) != cf.digest({"n": 1.0})  # Firestore'da integer ve double ayrı tiplerdir
    assert cf.digest({"n": True}) != cf.digest(base)
    assert cf.digest({"n": None}) != cf.digest({})
    assert cf.digest({"n": "1"}) != cf.digest(base) and cf.digest({"n": b"1"}) != cf.digest({"n": "1"})
    assert cf.digest({"n": 0.0}) != cf.digest({"n": -0.0})
    assert cf.digest({"n": [1, 2]}) != cf.digest({"n": [2, 1]})
    assert cf.digest({"a": 1, "b": {"c": [None]}}) == cf.digest({"b": {"c": [None]}, "a": 1})
    early = DatetimeWithNanoseconds(2026, 11, 1, 0, 0, 0, nanosecond=123456789, tzinfo=dt.UTC)
    late = DatetimeWithNanoseconds(2026, 11, 1, 0, 0, 0, nanosecond=123456790, tzinfo=dt.UTC)
    assert cf.digest({"t": early}) != cf.digest({"t": late})  # aynı mikrosaniye, farklı nanosaniye
    naive = dt.datetime(2026, 11, 1, 3, 0)
    assert cf.digest({"t": naive}) == cf.digest({"t": dt.datetime(2026, 11, 1, 6, 0, tzinfo=dt.timezone(dt.timedelta(hours=3)))})
    assert cf.digest({"g": GeoPoint(1.0, 2.0)}) != cf.digest({"g": GeoPoint(2.0, 1.0)})
    with pytest.raises(TypeError, match="Desteklenmeyen"):
        cf.digest({"x": object()})


def test_decide_is_authority_aware_and_never_writes_blocked_owners():
    src, tgt = policy("source"), policy("target")
    assert cf.decide(src, "ok", "a", "a") == "same"
    assert cf.decide(src, "ok", "a", None) == "write_new" and cf.decide(tgt, "ok", "a", None) == "held_source_only"
    assert cf.decide(src, "ok", "a", "b") == "conflict_overwrite" and cf.decide(tgt, "ok", "a", "b") == "conflict_kept_target"
    assert cf.decide(src, "ok", None, "b") == "only_target"
    for status in cf.BLOCKED:
        assert cf.decide(src, status, "a", None) == f"blocked_{status}"
        assert cf.decide(src, status, "a", "b") == f"blocked_{status}"


def test_policy_owner_status_covers_hashed_and_ownerless_collections():
    pol = policy(deleted={"gone"})
    assert pol.status("lessons/l1", {"student_id": "uid-1"}) == "ok"
    assert pol.status("lessons/l1", {"student_id": "gone"}) == "deleted_owner"
    assert pol.status("lessons/l1", {"student_id": "stranger"}) == "owner_not_in_auth"
    assert pol.status("lessons/l1", {}) == "no_owner"
    assert pol.status("shared_solutions/s1", {}) == "ownerless_share"
    assert policy(copy_ownerless_shares=True).status("shared_solutions/s1", {}) == "ok"
    assert pol.status("users/gone", {}) == "deleted_owner"
    assert pol.status(f"ai_daily_usage/2026-11-01_{cf.owner_hash('gone')}", {}) == "deleted_owner"  # eski belge: kimlikten
    assert pol.status("ai_output_usage/x", {"owner_hash": cf.owner_hash("uid-2")}) == "ok"
    assert pol.status("ai_global_usage/2026-11-01", {}) == "unowned" and pol.status("account_deletions/gone", {}) == "unowned"


# --- emülatör ---

def test_copy_preserves_ids_types_subcollections_and_ttl(projects):
    source_id, target_id, source, target = projects
    expires = seed(source)
    stamp = DatetimeWithNanoseconds(2026, 11, 2, 1, 2, 3, nanosecond=456789000, tzinfo=dt.UTC)
    source.document("lessons/lesson_b").set({"student_id": "uid-1", "n_int": 1, "n_float": 1.0, "none": None,
                                             "at": stamp, "flag": False, "list": [b"\x02", None, 2.5]})
    report = run_copy(projects, ["lessons", "lesson_analyses", "student_profiles"])["collections"]
    assert report["lessons"]["written"] == 2 and report["lessons"]["references_rebound"] == 1
    assert report["lessons/*/notes"]["written"] == 1
    copied = target.document("lessons/lesson_a").get().to_dict()
    assert copied["where"].latitude == 39.9 and copied["blob"] == b"\x00\x01" and copied["nested"] == {"items": [1, {"k": "v"}]}
    assert copied["profile"].path == "student_profiles/uid-1" and copied["profile"]._client is target
    assert target.document("lessons/lesson_a/notes/n1").get().exists
    other = target.document("lessons/lesson_b").get().to_dict()
    assert type(other["n_int"]) is int and type(other["n_float"]) is float and other["none"] is None
    assert other["at"] == stamp and other["list"] == [b"\x02", None, 2.5]
    ttl = target.document("lesson_analyses/an_1").get().to_dict()["expires_at"]
    assert isinstance(ttl, dt.datetime) and ttl == expires  # TTL alanı Timestamp olarak kalır
    counts = run_verify(projects, ["lessons", "lesson_analyses", "student_profiles"])["collections"]
    assert counts["lessons"] == {"same": 2} and counts["lessons/*/notes"] == {"same": 1}


def test_same_updated_at_with_different_content_is_rewritten(projects):
    _, _, source, target = projects
    stamp = dt.datetime(2026, 11, 3, tzinfo=dt.UTC)
    source.document("lessons/l1").set({"student_id": "uid-1", "updated_at": stamp, "topic": "yeni"})
    target.document("lessons/l1").set({"student_id": "uid-1", "updated_at": stamp, "topic": "eski"})
    assert run_verify(projects, ["lessons"])["collections"]["lessons"] == {"different": 1}
    result = run_copy(projects, ["lessons"])
    assert result["collections"]["lessons"] == {"conflict_overwrite": 1, "written": 1}
    old = cf.digest({"student_id": "uid-1", "updated_at": stamp, "topic": "eski"})
    assert result["conflicts"] == [{"collection": "lessons", "path_sha256": cf.path_hash("lessons/l1"),
                                    "replaced_target_digest": old}]
    assert target.document("lessons/l1").get().to_dict()["topic"] == "yeni"


def test_dry_run_writes_nothing_and_rerun_is_incremental(projects):
    _, _, source, target = projects
    seed(source)
    dry = run_copy(projects, ["lessons"], execute=False)["collections"]
    assert dry["lessons"]["would_write"] == 1 and dry["lessons/*/notes"]["would_write"] == 1
    assert not target.document("lessons/lesson_a").get().exists
    run_copy(projects, ["lessons"])
    again = run_copy(projects, ["lessons"])["collections"]
    assert again["lessons"] == {"same": 1} and again["lessons/*/notes"] == {"same": 1}


def test_target_extra_documents_are_reported_not_deleted(projects):
    _, _, source, target = projects
    seed(source)
    run_copy(projects, ["lessons"])
    target.document("lessons/extra").set({"student_id": "uid-1"})
    report = run_copy(projects, ["lessons"])["collections"]["lessons"]
    assert report == {"same": 1, "only_target": 1}
    assert target.document("lessons/extra").get().exists
    assert run_verify(projects, ["lessons"])["collections"]["lessons"] == {"same": 1, "only_target": 1}


def test_subcollection_differences_are_reported_per_path(projects):
    _, _, source, target = projects
    seed(source)
    run_copy(projects, ["lessons"])
    source.document("lessons/lesson_a/notes/n2").set({"text": "yalnız kaynakta"})
    target.document("lessons/lesson_a/notes/n1").set({"text": "hedefte değişti"})
    target.document("lessons/lesson_a/notes/n3").set({"text": "yalnız hedefte"})
    counts = run_verify(projects, ["lessons"])["collections"]
    assert counts["lessons"] == {"same": 1}
    assert counts["lessons/*/notes"] == {"different": 1, "only_source": 1, "only_target": 1}


def test_deleted_accounts_are_not_copied_with_record_or_after_ttl(projects):
    _, _, source, target = projects
    source.document("lessons/kept").set({"student_id": "uid-1"})
    source.document("lessons/by_record").set({"student_id": "uid-gone"})
    source.document("lessons/by_record/notes/n").set({"text": "alt belge de taşınmaz"})
    source.document("student_profiles/uid-gone").set({"grade": 8})
    source.document(f"ai_daily_usage/2026-11-01_{cf.owner_hash('uid-gone')}").set({"count": 1})
    source.document("account_deletions/uid-gone").set({"status": "in_progress"})
    source.document("lessons/after_ttl").set({"student_id": "uid-expired"})  # silme kaydı TTL ile gitti; Auth'ta yok
    source.document("shared_solutions/legacy").set({"title": "sahipsiz eski paylaşım"})
    deleted = cf.deletion_uids(source, target)
    pol = policy(deleted=deleted, auth={"uid-1"})
    report = run_copy(projects, ["lessons", "student_profiles", "ai_daily_usage", "account_deletions",
                                 "shared_solutions"], pol=pol)["collections"]
    assert report["lessons"] == {"write_new": 1, "written": 1, "blocked_deleted_owner": 1, "blocked_owner_not_in_auth": 1}
    assert report["lessons/*/notes"] == {"blocked_deleted_owner": 1}
    assert report["student_profiles"] == {"blocked_deleted_owner": 1}
    assert report["ai_daily_usage"] == {"blocked_deleted_owner": 1}
    assert report["shared_solutions"] == {"blocked_ownerless_share": 1}
    assert report["account_deletions"]["written"] == 1  # silmenin kendisi taşınır
    written = {snap.id for snap in target.collection("lessons").stream()}
    assert written == {"kept"} and not target.document("student_profiles/uid-gone").get().exists
    assert "uid-gone" not in json.dumps(report) and "uid-expired" not in json.dumps(report)


def test_reverse_copy_does_not_resurrect_user_deleted_on_its_target(projects):
    _, _, old, new = projects  # old = math-ai-07 rolü, new = teacherai-07 rolü
    new.document("lessons/new_lesson").set({"student_id": "uid-1"})  # geçişten sonra yeni projede yazılan
    new.document("lessons/stale").set({"student_id": "uid-2"})  # geçişte taşınmış ama eski projede silinmiş
    old.document("account_deletions/uid-2").set({"status": "completed"})
    deleted = cf.deletion_uids(new, old)
    back = run_copy(projects, ["lessons"], pol=policy(deleted=deleted), reverse=True)["collections"]["lessons"]
    assert back == {"write_new": 1, "written": 1, "blocked_deleted_owner": 1}
    assert old.document("lessons/new_lesson").get().exists and not old.document("lessons/stale").get().exists
    # yetkili taraf hedef iken kaynağa özgü belge hedefe yazılmaz (hedefte silinmiş olabilir)
    old.document("lessons/only_old").set({"student_id": "uid-1"})
    held = run_copy(projects, ["lessons"], pol=policy("target", deleted=deleted))["collections"]["lessons"]
    assert held["held_source_only"] == 1 and not new.document("lessons/only_old").get().exists


def test_verify_reports_ownership_and_deleted_leftovers_without_ids(projects):
    _, _, source, target = projects
    source.document("lessons/a").set({"student_id": "uid-1"})
    target.document("lessons/a").set({"student_id": "uid-1"})
    target.document("lessons/left").set({"student_id": "uid-gone"})
    source.document("lessons/orphan").set({"topic": "sahipsiz"})
    pol = policy(deleted={"uid-gone"}, auth={"uid-1"})
    counts = run_verify(projects, ["lessons"], pol=pol)["collections"]["lessons"]
    assert counts == {"same": 1, "only_source": 1, "no_owner": 1, "only_target": 1, "deleted_owner_in_target": 1}
    assert "uid" not in json.dumps(counts)


def _report(projects, tmp_path, **manifest_overrides):
    result = run_verify(projects, ["lessons"])
    result["prune_manifest"] |= manifest_overrides
    path = tmp_path / "fark.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    return path


def test_prune_deletes_only_documents_seen_unchanged_in_report(projects, tmp_path):
    source_id, target_id, source, target = projects
    source.document("lessons/a").set({"student_id": "uid-1"})
    target.document("lessons/a").set({"student_id": "uid-1"})
    target.document("lessons/seen").set({"student_id": "uid-1"})
    target.document("lessons/changed").set({"student_id": "uid-1", "v": 1})
    manifest = cf.load_prune_report(_report(projects, tmp_path), source_id, target_id)
    target.document("lessons/changed").set({"student_id": "uid-1", "v": 2})
    target.document("lessons/unseen").set({"student_id": "uid-1"})
    dry = cf.prune(source_id, target_id, manifest, False, policy(auth=None), source=source, target=target)
    assert dry == {"would_prune": 1, "skipped_changed_since_report": 1, "skipped_not_in_report": 1}
    assert target.document("lessons/seen").get().exists
    done = cf.prune(source_id, target_id, manifest, True, policy(auth=None), source=source, target=target)
    assert done["pruned"] == 1
    assert {snap.id for snap in target.collection("lessons").stream()} == {"a", "changed", "unseen"}


def test_prune_rejects_stale_foreign_or_mismatched_reports(projects, tmp_path):
    source_id, target_id, _, _ = projects
    old = (dt.datetime.now(dt.UTC) - dt.timedelta(hours=2)).isoformat()
    with pytest.raises(SystemExit, match="süresi dolmuş"):
        cf.load_prune_report(_report(projects, tmp_path, created_at=old), source_id, target_id)
    with pytest.raises(SystemExit, match="başka bir kaynak/hedef"):
        cf.load_prune_report(_report(projects, tmp_path, target="demo-other"), source_id, target_id)
    with pytest.raises(SystemExit, match="--verify çıktısı değil"):
        cf.load_prune_report(_report(projects, tmp_path, tool="elle-yazılmış"), source_id, target_id)
    bad = tmp_path / "bozuk.json"
    bad.write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit, match="okunamadı"):
        cf.load_prune_report(bad, source_id, target_id)
    manifest = cf.load_prune_report(_report(projects, tmp_path), source_id, target_id)
    with pytest.raises(SystemExit, match="authority"):
        cf.prune(source_id, target_id, manifest, True, policy("target", auth=None))


def test_large_collection_is_paginated(projects):
    _, _, source, _ = projects
    batch = source.batch()
    for i in range(650):
        batch.set(source.collection("feedback").document(f"f{i:04d}"), {"user_id": f"u{i % 7}", "i": i})
        if i % 400 == 399:
            batch.commit()
            batch = source.batch()
    batch.commit()
    pol = policy(auth={f"u{i}" for i in range(7)})
    _, _, source, target = projects
    source_id, target_id = projects[0], projects[1]
    report = cf.copy(source_id, target_id, ["feedback"], True, pol, size=100, source=source, target=target)
    assert report["collections"]["feedback"]["written"] == 650
    counts = cf.verify(source_id, target_id, ["feedback"], pol, size=100, source=source, target=target)["collections"]
    assert counts["feedback"] == {"same": 650}


def test_copy_requires_authority_auth():
    with pytest.raises(ValueError, match="Auth"):
        cf.copy("a", "b", ["lessons"], False, policy(auth=None), source=object(), target=object())
    with pytest.raises(ValueError):
        cf.Policy("both", set())


def test_authority_flag_is_mandatory(capsys):
    with pytest.raises(SystemExit):
        cf.main(["--source", "a", "--target", "b"])
    assert "--authority" in capsys.readouterr().err


@pytest.mark.parametrize(("overrides", "message"), [
    ({"execute": True, "confirm_target": "x"}, "confirm-target"),
    ({"execute": True, "target": "math-ai-07", "confirm_target": "math-ai-07"}, "allow-reverse"),
    ({"collections": ["idempotency_tmp"]}, "İzin listesinde"),
    ({"target": "a"}, "aynı olamaz"),
    ({"prune": True, "confirm_prune": "b"}, "prune-from"),
    ({"prune": True, "confirm_prune": "x", "prune_from": "f"}, "confirm-prune"),
    ({"prune": True, "verify": True, "confirm_prune": "b", "prune_from": "f"}, "birlikte"),
    ({"prune": True, "target": "math-ai-07", "confirm_prune": "math-ai-07", "prune_from": "f"}, "allow-reverse"),
])
def test_guard_refuses_unsafe_invocations(overrides, message):
    with pytest.raises(SystemExit, match=message):
        cf.guard(args(**overrides))
    cf.guard(args(execute=True, target="math-ai-07", confirm_target="math-ai-07", allow_reverse=True))
    cf.guard(args(prune=True, execute=True, confirm_prune="b", prune_from="f"))


def test_allowlist_covers_every_collection_the_code_writes():
    from pathlib import Path

    written = set()
    for path in Path("apps/api/app").rglob("*.py"):
        written |= set(re.findall(r'collection\("([a-z_]+)"\)', path.read_text(encoding="utf-8")))
    from apps.api.app.core import retention

    written |= {retention.ANALYSES, retention.PRACTICE, retention.DAILY, retention.OUTPUT, retention.GLOBAL, retention.DELETIONS}
    assert written <= set(cf.ALLOWLIST)
    assert set(cf.OWNER_FIELDS) | {"ai_global_usage", "account_deletions"} == set(cf.ALLOWLIST)
