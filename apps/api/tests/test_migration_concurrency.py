"""TA-005C §11: kopya/budama eşzamanlılığı, beklenmeyen çakışma, yetim alt koleksiyon, sahip farkı ve geri dönüş.

Yalnız yerel Firestore emülatörü ve sentetik belgeler; canlı proje ve gerçek öğrenci verisi yoktur.
"""

import datetime as dt
import json
import os
import re
from uuid import uuid4

import pytest

from apps.api.tests.test_migration_copy import _report, policy, run_copy, run_verify
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


def wrap(monkeypatch, name, before):
    original = getattr(cf, name)

    def wrapped(*args, **kwargs):
        before()
        return original(*args, **kwargs)

    monkeypatch.setattr(cf, name, wrapped)


def test_target_created_between_decision_and_write_is_not_overwritten(projects, monkeypatch):
    _, _, source, target = projects
    source.document("lessons/race").set({"student_id": "uid-1", "v": "kaynak"})
    wrap(monkeypatch, "_apply_writes", lambda: target.document("lessons/race").set({"student_id": "uid-1", "v": "hedefte yeni"}))
    report = run_copy(projects, ["lessons"])["collections"]["lessons"]
    assert report == {"write_new": 1, "skipped_target_changed": 1}
    assert target.document("lessons/race").get().to_dict()["v"] == "hedefte yeni"


def test_approved_overwrite_is_skipped_if_target_changes_before_commit(projects, monkeypatch):
    source_id, target_id, source, target = projects
    source.document("lessons/c").set({"student_id": "uid-1", "v": "kaynak"})
    target.document("lessons/c").set({"student_id": "uid-1", "v": "hedef"})
    manifest = run_verify(projects, ["lessons"])["prune_manifest"]
    approved = {(c["path_sha256"], c["target_digest"], c["source_digest"]) for c in manifest["overwrite_candidates"]}
    wrap(monkeypatch, "_apply_writes", lambda: target.document("lessons/c").set({"student_id": "uid-1", "v": "eşzamanlı"}))
    result = cf.copy(source_id, target_id, ["lessons"], True, policy(), source=source, target=target,
                     approved_overwrites=approved)
    assert result["collections"]["lessons"] == {"conflict_overwrite": 1, "skipped_target_changed": 1}
    assert target.document("lessons/c").get().to_dict()["v"] == "eşzamanlı"


def test_target_changed_after_verify_makes_the_conflict_unapproved_and_visible(projects):
    source_id, target_id, source, target = projects
    source.document("lessons/c").set({"student_id": "uid-1", "v": "kaynak"})
    target.document("lessons/c").set({"student_id": "uid-1", "v": "hedef"})
    manifest = run_verify(projects, ["lessons"])["prune_manifest"]
    approved = {(c["path_sha256"], c["target_digest"], c["source_digest"]) for c in manifest["overwrite_candidates"]}
    target.document("lessons/c").set({"student_id": "uid-1", "v": "rapordan sonra"})
    result = cf.copy(source_id, target_id, ["lessons"], True, policy(), source=source, target=target,
                     approved_overwrites=approved)
    assert result["collections"]["lessons"] == {"conflict_held_unapproved": 1}
    assert result["conflicts"][0]["held_target_digest"] == cf.digest({"student_id": "uid-1", "v": "rapordan sonra"})


def test_source_changed_after_read_is_not_written_with_stale_content(projects, monkeypatch):
    _, _, source, target = projects
    source.document("lessons/s").set({"student_id": "uid-1", "v": 1})
    wrap(monkeypatch, "_apply_writes", lambda: source.document("lessons/s").set({"student_id": "uid-1", "v": 2}))
    report = run_copy(projects, ["lessons"])["collections"]["lessons"]
    assert report == {"write_new": 1, "skipped_source_changed": 1}
    assert not target.document("lessons/s").get().exists


def test_prune_skips_documents_changed_between_verification_and_deletion(projects, tmp_path, monkeypatch):
    source_id, target_id, source, target = projects
    target.document("lessons/old").set({"student_id": "uid-1", "v": 1})
    manifest = cf.load_prune_report(_report(projects, tmp_path), source_id, target_id)
    wrap(monkeypatch, "_apply_deletes", lambda: target.document("lessons/old").set({"student_id": "uid-1", "v": 2}))
    done = cf.prune(source_id, target_id, manifest, True, policy(auth=None), source=source, target=target)
    assert done == {"skipped_changed_before_delete": 1}
    assert target.document("lessons/old").get().to_dict()["v"] == 2


def test_orphaned_subcollections_are_found_reported_and_not_copied_without_owner(projects):
    _, _, source, target = projects
    source.document("lessons/ghost/notes/n1").set({"text": "üst belgesi yok"})       # sahip alanı üst belgedeydi
    source.document("users/uid-1/devices/d1").set({"kind": "tablet"})                 # sahip belge kimliğinden
    counts = run_verify(projects, ["lessons", "users"])["collections"]
    assert counts["lessons"] == {"orphan_parent": 1}
    assert counts["lessons/*/notes"] == {"only_source": 1, "no_owner": 1}
    assert counts["users"] == {"orphan_parent": 1} and counts["users/*/devices"] == {"only_source": 1}
    report = run_copy(projects, ["lessons", "users"])["collections"]
    assert report["lessons/*/notes"] == {"blocked_no_owner": 1}
    assert report["users/*/devices"] == {"write_new": 1, "written": 1}
    assert not target.document("lessons/ghost/notes/n1").get().exists


def test_owner_differences_between_source_and_target_are_blocked_and_reported(projects):
    _, _, source, target = projects
    source.document("lessons/x").set({"student_id": "uid-1", "topic": "a"})
    target.document("lessons/x").set({"student_id": "uid-2", "topic": "a"})
    verify = run_verify(projects, ["lessons"])
    assert verify["collections"]["lessons"] == {"different": 1, "owner_mismatch": 1}
    assert verify["prune_manifest"]["overwrite_candidates"] == []  # onaylanamaz
    report = run_copy(projects, ["lessons"])["collections"]["lessons"]
    assert report == {"blocked_owner_mismatch": 1}
    assert target.document("lessons/x").get().to_dict()["student_id"] == "uid-2"


def test_deleted_owner_on_either_side_wins_over_owner_mismatch(projects):
    _, _, source, target = projects
    source.document("lessons/y").set({"student_id": "uid-1"})
    target.document("lessons/y").set({"student_id": "uid-gone"})
    report = run_copy(projects, ["lessons"], pol=policy(deleted={"uid-gone"}))["collections"]["lessons"]
    assert report == {"blocked_deleted_owner": 1}


def test_rollback_after_ttl_does_not_resurrect_deleted_account(projects):
    _, _, old, new = projects  # geri dönüş: yeni proje kaynak ve yetkili, eski proje hedef
    new.document("lessons/kept").set({"student_id": "uid-1"})
    new.document("lessons/expired").set({"student_id": "uid-expired"})  # silme kaydı 30 gün sonra TTL ile gitti
    assert cf.deletion_uids(new, old) == set()
    back = run_copy(projects, ["lessons"], pol=policy(auth={"uid-1"}), reverse=True)["collections"]["lessons"]
    assert back == {"write_new": 1, "written": 1, "blocked_owner_not_in_auth": 1}
    assert not old.document("lessons/expired").get().exists


def test_overwrite_approvals_require_fresh_matching_source_authority_report(projects, tmp_path):
    source_id, target_id, _, _ = projects
    path = _report(projects, tmp_path)
    assert cf.load_overwrite_approvals(path, source_id, target_id, "source") == set()
    with pytest.raises(SystemExit, match="authority source"):
        cf.load_overwrite_approvals(path, source_id, target_id, "target")
    stale = _report(projects, tmp_path, created_at=(dt.datetime.now(dt.UTC) - dt.timedelta(hours=2)).isoformat())
    with pytest.raises(SystemExit, match="Yazma yapılmadı"):
        cf.load_overwrite_approvals(stale, source_id, target_id, "source")
    with pytest.raises(SystemExit, match="Ezme onayı raporu"):
        cf.load_overwrite_approvals(_report(projects, tmp_path, target="demo-other"), source_id, target_id, "source")


def test_reports_carry_no_identifiers(projects):
    _, _, source, target = projects
    source.document("lessons/secret-lesson-id").set({"student_id": "uid-1", "v": 1})
    target.document("lessons/secret-lesson-id").set({"student_id": "uid-1", "v": 2})
    text = json.dumps([run_verify(projects, ["lessons"]), run_copy(projects, ["lessons"], execute=False)])
    assert "secret-lesson-id" not in text and "uid-1" not in text


def test_guard_rejects_overwrite_approval_outside_copy_mode():
    from apps.api.tests.test_migration_copy import args

    with pytest.raises(SystemExit, match="overwrite-from"):
        cf.guard(args(verify=True, overwrite_from="fark.json"))
