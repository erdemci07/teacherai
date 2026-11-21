"""TA-005 Firestore kopya betiği. Yerel emülatörde iki sahte proje kimliği kullanılır; canlı proje yoktur."""

import datetime as dt
import os
import re
from argparse import Namespace
from uuid import uuid4

import pytest

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


def seed(source):
    from google.cloud.firestore import GeoPoint

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
                         "collections": ["lessons"]} | overrides))


def test_copy_preserves_ids_types_subcollections_and_ttl(projects):
    source_id, target_id, source, target = projects
    expires = seed(source)
    report = cf.copy(source_id, target_id, ["lessons", "lesson_analyses", "student_profiles"], True, source=source, target=target)
    assert report["lessons"]["written"] == 2 and report["lessons"]["references_rebound"] == 1
    copied = target.document("lessons/lesson_a").get().to_dict()
    assert copied["where"].latitude == 39.9 and copied["blob"] == b"\x00\x01" and copied["nested"] == {"items": [1, {"k": "v"}]}
    assert copied["profile"].path == "student_profiles/uid-1" and copied["profile"]._client is target
    assert target.document("lessons/lesson_a/notes/n1").get().exists
    ttl = target.document("lesson_analyses/an_1").get().to_dict()["expires_at"]
    assert isinstance(ttl, dt.datetime) and ttl == expires  # TTL alanı Timestamp olarak kalır


def test_dry_run_writes_nothing_and_rerun_is_incremental(projects):
    source_id, target_id, source, target = projects
    seed(source)
    dry = cf.copy(source_id, target_id, ["lessons"], False, source=source, target=target)
    assert dry["lessons"]["would_write"] == 2 and not target.document("lessons/lesson_a").get().exists
    cf.copy(source_id, target_id, ["lessons"], True, source=source, target=target)
    again = cf.copy(source_id, target_id, ["lessons"], True, source=source, target=target)
    assert again["lessons"].get("written", 0) == 0 and again["lessons"]["unchanged"] == 2
    source.document("lessons/lesson_a").update({"student_id": "uid-1", "topic": "değişti"})
    delta = cf.copy(source_id, target_id, ["lessons"], True, source=source, target=target)
    assert delta["lessons"]["written"] == 1 and target.document("lessons/lesson_a").get().to_dict()["topic"] == "değişti"


def test_verify_reports_counts_hashes_and_ownership_only(projects):
    source_id, target_id, source, target = projects
    seed(source)
    cf.copy(source_id, target_id, ["lessons", "lesson_analyses"], True, source=source, target=target)
    target.document("lesson_analyses/an_1").update({"owner": "uid-2", "extra": 1})
    report = cf.verify(source_id, target_id, ["lessons", "lesson_analyses"], auth_uids={"uid-1"}, source=source, target=target)
    assert report["lessons"] == {"source": 1, "same": 1, "owner_in_target_auth": 1, "target": 1}
    assert report["lesson_analyses"] == {"source": 1, "different": 1, "owner_missing": 1, "target": 1}
    assert "uid-1" not in repr(report) and "uid-2" not in repr(report)


def test_reverse_copy_restores_changes_back(projects):
    source_id, target_id, source, target = projects
    seed(source)
    cf.copy(source_id, target_id, ["lessons"], True, source=source, target=target)
    target.collection("lessons").document("lesson_new").set({"student_id": "uid-1"})  # yeni projede yazılan
    back = cf.copy(target_id, source_id, ["lessons"], True, source=target, target=source)
    assert back["lessons"]["written"] == 1 and source.document("lessons/lesson_new").get().exists


def test_large_collection_is_paginated(projects):
    source_id, target_id, source, target = projects
    batch = source.batch()
    for i in range(650):
        batch.set(source.collection("feedback").document(f"f{i:04d}"), {"user_id": f"u{i % 7}", "i": i})
        if i % 400 == 399:
            batch.commit()
            batch = source.batch()
    batch.commit()
    report = cf.copy(source_id, target_id, ["feedback"], True, size=100, source=source, target=target)
    assert report["feedback"]["written"] == 650
    assert cf.verify(source_id, target_id, ["feedback"], size=100, source=source, target=target)["feedback"]["same"] == 650


@pytest.mark.parametrize(("overrides", "message"), [
    ({"execute": True, "confirm_target": "x"}, "confirm-target"),
    ({"execute": True, "target": "math-ai-07", "confirm_target": "math-ai-07"}, "allow-reverse"),
    ({"collections": ["idempotency_tmp"]}, "İzin listesinde"),
    ({"target": "a"}, "aynı olamaz"),
])
def test_guard_refuses_unsafe_invocations(overrides, message):
    with pytest.raises(SystemExit, match=message):
        cf.guard(args(**overrides))
    cf.guard(args(execute=True, target="math-ai-07", confirm_target="math-ai-07", allow_reverse=True))


def test_allowlist_covers_every_collection_the_code_writes():
    from pathlib import Path

    written = set()
    for path in Path("apps/api/app").rglob("*.py"):
        written |= set(re.findall(r'collection\("([a-z_]+)"\)', path.read_text(encoding="utf-8")))
    from apps.api.app.core import retention

    written |= {retention.ANALYSES, retention.PRACTICE, retention.DAILY, retention.OUTPUT, retention.GLOBAL, retention.DELETIONS}
    assert written <= set(cf.ALLOWLIST)
