"""G paketi: eski paylaşımlar için inceleme ve yayından kaldırma. Yalnız emülatör."""

import json
from dataclasses import replace
from hashlib import sha256
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.app.core.settings import Settings
from apps.api.app.features.shares.firestore_repository import FirestoreShareRepository
from apps.api.app.features.shares.service import ShareService
from apps.api.app.main import create_app
from apps.api.tests.test_feedback import generated_result
from apps.api.tests.test_firestore_integration import databases as databases_fixture
from scripts import legacy_shares

databases = databases_fixture
SECRET_QUESTION = "GİZLİ SORU METNİ 7x + 3 = 24"
SECRET_NARRATION = "GİZLİ SERBEST ANLATIM"


@pytest.fixture
def shares(databases, tmp_path):
    db = databases[0]
    settings = Settings(environment="test")
    service = ShareService(FirestoreShareRepository(db), settings)
    result = generated_result()
    result.lesson.lesson_plan_id = "lesson_" + uuid4().hex
    current = service.create_or_reuse(result, owner_id="owner").share_id
    data = db.collection("shared_solutions").document(current).get().to_dict()
    legacy = "legacy" + uuid4().hex[:10]
    legacy_data = json.loads(json.dumps({k: v for k, v in data.items() if k not in ("owner_id", "created_at", "updated_at")}, default=str))
    legacy_data.update(share_id=legacy, question_summary=SECRET_QUESTION)
    legacy_data["lesson_snapshot"]["content"]["question_understanding"] = SECRET_NARRATION
    db.collection("shared_solutions").document(legacy).set(legacy_data)
    app = create_app(settings)
    app.state.container = replace(app.state.container, share_service=service)
    ids = tmp_path / "ids.txt"
    ids.write_text(f"{legacy}\n{current}\n", encoding="utf-8")
    return db, TestClient(app), legacy, current, ids, tmp_path


def digest(db):
    docs = sorted((snap.id, json.dumps(snap.to_dict(), sort_keys=True, default=str), str(snap.update_time)) for snap in db.collection("shared_solutions").stream())
    return sha256(json.dumps(docs).encode()).hexdigest()


def run_unpublish(db, ids, tmp_path, *, execute=True, project="demo-teacherai", env=True):
    argv = ["unpublish", "--ids-file", str(ids), "--backup-dir", str(tmp_path / "backup")]
    if execute:
        argv.append("--execute")
    if project:
        argv += ["--confirm-project", project]
    return legacy_shares.main(argv, db=db, env={"TEACHERAI_ALLOW_DESTRUCTIVE": "1"} if env else {})


def unpublished(db, share_id):
    return bool(db.collection("shared_solutions").document(share_id).get().to_dict().get("unpublished_at"))


def test_audit_is_read_only(shares):
    db, _, _, _, _, tmp_path = shares
    before = digest(db)
    assert legacy_shares.main(["audit", "--output", str(tmp_path / "audit.csv")], db=db) == 0
    assert digest(db) == before


def test_audit_reports_presence_only_never_content(shares, capsys):
    db, _, legacy, current, _, tmp_path = shares
    output = tmp_path / "audit.csv"
    legacy_shares.main(["audit", "--output", str(output)], db=db)
    text = output.read_text(encoding="utf-8") + capsys.readouterr().out
    assert SECRET_QUESTION not in text and SECRET_NARRATION not in text and "7x" not in text
    row = next(line for line in text.splitlines() if line.startswith(legacy))
    assert row.split(",")[2:5] == ["True", "True", "False"]
    assert current not in text, "yeni biçimli paylaşım eski sayılmaz"


@pytest.mark.parametrize("missing", ["execute", "confirm-project", "wrong-project", "env"])
def test_unpublish_writes_nothing_without_every_flag(shares, missing):
    db, _, legacy, _, ids, tmp_path = shares
    before = digest(db)
    run_unpublish(db, ids, tmp_path, execute=missing != "execute",
                  project=None if missing == "confirm-project" else "other-project" if missing == "wrong-project" else "demo-teacherai",
                  env=missing != "env")
    assert digest(db) == before and not unpublished(db, legacy)
    assert not (tmp_path / "backup").exists()


def test_unpublish_requires_ids_file(shares):
    db, *_ = shares
    before = digest(db)
    with pytest.raises(SystemExit):
        legacy_shares.main(["unpublish", "--execute", "--confirm-project", "demo-teacherai"], db=db, env={"TEACHERAI_ALLOW_DESTRUCTIVE": "1"})
    assert digest(db) == before


def test_unpublish_backs_up_and_returns_410_without_touching_new_shares(shares):
    db, client, legacy, current, ids, tmp_path = shares
    assert run_unpublish(db, ids, tmp_path) == 0
    assert unpublished(db, legacy) and not unpublished(db, current)
    backups = list((tmp_path / "backup").glob("unpublish-backup-*.json"))
    assert len(backups) == 1 and list(json.loads(backups[0].read_text(encoding="utf-8"))) == [legacy]
    page = client.get(f"/s/{legacy}")
    assert page.status_code == 410 and page.headers["cache-control"] == "no-store"
    api = client.get(f"/api/v1/shares/{legacy}")
    assert (api.status_code, api.json()["error"]) == (410, "share_unpublished")
    assert client.get(f"/s/{current}").status_code == 200
    assert client.get(f"/api/v1/shares/{current}").status_code == 200
