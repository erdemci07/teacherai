"""TA-009B §3: aday matrisi, önceden yazılmış karar kuralı, kör puanlama ve gerileme (sahte koşucu; çağrı yok)."""

import asyncio
import csv
import json
from argparse import Namespace

import pytest

from apps.api.app.core.settings import Settings
from scripts import eval_matrix, eval_pack, evaluate_models


def _args(**extra):
    return Namespace(**({"dry_run": False, "allow_paid": True, "max_usd": 50.0, "max_calls": 2000,
                         "pack_images_to_anthropic": True} | extra))


def test_decision_rule_is_pinned_before_any_run():
    assert eval_matrix.rule_digest() == eval_matrix.RULE_SHA256


def test_candidate_matrix_matches_spec_and_privacy_gate():
    labels = [c.label for c in eval_matrix.CANDIDATES]
    assert len(labels) == 11 and len(set(labels)) == 11
    assert all(c.repeats == 2 for c in eval_matrix.CANDIDATES if c.operation == "vision")
    rows = eval_matrix.plan(Settings(_env_file=None), 24, images_to_anthropic=False)
    skipped = {r["candidate"].label for r in rows if r["skipped"]}
    assert skipped == {"vision:claude-haiku-5-5:varsayilan", "vision:claude-sonnet-5-5:varsayilan"}
    assert all(r["upper_usd"] is not None for r in rows)  # Haiku artık kademeli fiyatlı


def test_missing_prerequisites_stop_paid_run(monkeypatch):
    monkeypatch.setattr(eval_matrix, "prerequisites", lambda: (["öğretmen anahtarı yok"], 24))
    called = []
    monkeypatch.setattr(eval_pack, "run", lambda *a, **k: called.append(a))
    assert asyncio.run(eval_matrix.run_matrix(_args(dry_run=True), Settings(_env_file=None))) == 0
    assert asyncio.run(eval_matrix.run_matrix(_args(), Settings(_env_file=None))) == 3
    assert called == []


def test_cli_refuses_paid_matrix_without_flags():
    with pytest.raises(SystemExit):
        evaluate_models.main(["matrix", "--allow-paid"], settings=Settings(_env_file=None))


def _fake_pack(log):
    async def run(args, settings, out_root):
        log.append(args)
        folder = out_root / "20270101T000000Z"
        folder.mkdir(parents=True)
        rows = [{"id": f"Q{i}", "decision": "solvable", "selected": "A", "reading": {"choices": [True]},
                 "provider_calls": 2 if args.vision_only else 5, **({} if args.vision_only else {"lesson": {"steps": ["x"]}})}
                for i in range(2)]
        (folder / "raw.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        summary = {"vision_model": args.model, "lesson_model": args.lesson_model or settings.openai_lesson_model,
                   "confident_wrong_rate": 0.0, "spent_usd_estimate": 0.5}
        (folder / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return 0
    return run


async def _fake_execute(call, settings, factory, dataset_dir, key):
    return {"item_id": call.item.id, "output": "ipucu", "answer_leak": False, "outcome": "success",
            "provider_calls": 1, "estimated_usd": 0.001}


def test_paid_matrix_writes_blind_files_without_model_names(monkeypatch, tmp_path):
    log = []
    monkeypatch.setattr(eval_matrix, "prerequisites", lambda: ([], 2))
    monkeypatch.setattr(eval_pack, "run", _fake_pack(log))
    monkeypatch.setattr(evaluate_models, "execute", _fake_execute)
    assert asyncio.run(eval_matrix.run_matrix(_args(), Settings(_env_file=None), out_root=tmp_path)) == 0
    out = next(tmp_path.glob("matrix-*"))
    matrix = json.loads((out / "matrix.json").read_text(encoding="utf-8"))
    assert matrix["rule_sha256"] == eval_matrix.RULE_SHA256
    vision = [r for r in matrix["results"] if r["label"].startswith("vision:")]
    assert all(r["stability"] == 1.0 and len(r["runs"]) == 2 for r in vision)
    assert sum(a.vision_only for a in log) == 5  # her Vision adayının ikinci koşusu ders üretmez
    blind = (out / "blind.csv").read_text(encoding="utf-8")
    assert not any(c.model in blind for c in eval_matrix.CANDIDATES)
    key = json.loads((out / "blind_key.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader((out / "blind.csv").open(encoding="utf-8")))
    assert len(rows) == len(key) and {r["islem"] for r in rows} == {"lessons", "interaction"}
    with (out / "blind_scored.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({**r, "dogruluk_1_5": "4", "aciklik_1_5": "2"} for r in rows)
    scores = eval_matrix.score(out)
    assert set(scores) == set(key.values()) and set(scores.values()) == {3.0}


def test_regress_reports_difference_from_last_result(monkeypatch, tmp_path, capsys):
    settings = Settings(_env_file=None)
    old = tmp_path / "regress" / "20261201T000000Z"
    old.mkdir(parents=True)
    (old / "summary.json").write_text(json.dumps({"vision_model": settings.openai_vision_model,
                                                  "lesson_model": settings.openai_lesson_model,
                                                  "confident_wrong_rate": 0.125}), encoding="utf-8")
    monkeypatch.setattr(eval_matrix, "prerequisites", lambda: ([], 2))

    async def fake(args, settings, out_root):
        folder = out_root / "20270101T000000Z"
        folder.mkdir(parents=True)
        (folder / "summary.json").write_text(json.dumps({"vision_model": settings.openai_vision_model,
                                                         "lesson_model": settings.openai_lesson_model,
                                                         "confident_wrong_rate": 0.042}), encoding="utf-8")
    monkeypatch.setattr(eval_pack, "run", fake)
    assert asyncio.run(eval_matrix.regress(_args(), settings, out_root=tmp_path)) == 0
    assert "| confident_wrong_rate | 0.125 | 0.042 |" in capsys.readouterr().out


def test_confident_wrong_rate_counts_only_committed_wrong_answers():
    base = {"reading": {}, "latency_ms": 1, "estimated_usd": None, "outcomes": [], "provider_calls": 0, "trap_tags": []}
    rows = [{**base, "id": "a", "teacher_answer": "A", "selected": "B", "decision": "solvable"},
            {**base, "id": "b", "teacher_answer": "A", "selected": None, "decision": "clarification_required"},
            {**base, "id": "c", "teacher_answer": "A", "selected": "A", "decision": "solvable"},
            {**base, "id": "d", "teacher_answer": None, "selected": "C", "decision": "solvable"}]
    summary = eval_pack.summarize(rows)
    assert summary["confident_wrong_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert eval_pack.summarize([rows[3]])["confident_wrong_rate"] == "anahtar_yok"
