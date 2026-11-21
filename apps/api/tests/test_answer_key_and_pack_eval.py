"""TA-005 öğretmen anahtarı, görsel manifesti ve paket değerlendiricisi. Sağlayıcı çağrısı yoktur; sahte servis
kullanılır ve sonuçlar model kalitesi değildir."""

import asyncio
import hashlib
import json
from argparse import Namespace
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from apps.api.app.core.settings import Settings
from scripts import answer_key, eval_pack, question_pack


def test_template_lists_all_pack_questions_without_answers():
    template = answer_key.template()
    assert [entry["id"] for entry in template["entries"]] == answer_key.pack_ids() and len(template["entries"]) == 24
    assert all(entry["expected_choice"] is None and entry["expected_value"] is None for entry in template["entries"])
    with pytest.raises(ValidationError):  # boş şablon geçerli bir anahtar değildir
        answer_key.AnswerKey.model_validate(template)


def write_key(tmp_path, entries):
    path = tmp_path / "key.json"
    path.write_text(json.dumps({"pack": "teacherai_24", "answer_origin": "teacher", "reviewed_by": "test", "entries": [
        {"id": qid, "expected_choice": choice, "answer_origin": "teacher", "trap_tags": tags} for qid, choice, tags in entries]}),
        encoding="utf-8")
    return path


def test_teacher_key_becomes_success_reference_and_disagreements_are_listed(tmp_path):
    pack = {q["id"]: q for q in json.loads(question_pack.PACK.read_text(encoding="utf-8"))["questions"]}
    derived = pack["M01"]["evaluation"]["answer"]
    other = next(label for label in "ABCDE" if label != derived)
    summary = question_pack.run(write_key(tmp_path, [("M01", other, ["choice_bait"])]))
    assert summary["success_reference"] == "teacher" and summary["teacher_key"] == "1 satır"
    assert any(item.startswith("M01:") for item in summary["derived_teacher_disagreements"])
    row = next(r for r in summary["rows"] if r["id"] == "M01")
    assert (row["derived_answer"], row["teacher_answer"], row["correct"]) == (derived, other, False)


def test_key_rejects_unknown_ids_and_derived_origin(tmp_path):
    with pytest.raises(ValueError):
        answer_key.load_key(write_key(tmp_path, [("M99", "A", [])]))
    with pytest.raises(ValidationError):
        answer_key.KeyEntry.model_validate({"id": "M01", "expected_choice": "A", "answer_origin": "derived"})


def test_manifest_records_name_hash_and_question_only(tmp_path):
    (tmp_path / "M03_kok.png").write_bytes(b"png-bytes")
    (tmp_path / "notlar.txt").write_text("yok sayılır", encoding="utf-8")
    rows = answer_key.manifest(tmp_path)
    assert rows == [{"file": "M03_kok.png", "sha256": hashlib.sha256(b"png-bytes").hexdigest(), "question_id": "M03"}]


def test_plan_refuses_image_whose_hash_changed(tmp_path):
    image = tmp_path / "M01.png"
    image.write_bytes(b"a")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"images": [{"file": "M01.png", "sha256": "0" * 64, "question_id": "M01"}]}), encoding="utf-8")
    with pytest.raises(ValueError):
        eval_pack.plan(manifest, tmp_path)


def test_reading_scores_by_field_type():
    expected = {"mathematical_expressions": ["\\sqrt{16+9}", "2^{3}", "\\frac{1}{2}"], "answer_choices": ["A) 5", "B) 7"]}
    analysis = SimpleNamespace(mathematical_expressions=["\\sqrt{16}+9", "2^{3}", "1/2"], answer_choices=["A) 5", "B)  7"])
    assert eval_pack.reading_scores(expected, analysis) == {
        "root_scope": [False], "exponent": [True], "fraction_bar": [True], "choices": [True, True]}


class FakeServices:
    def __init__(self, *args):
        self.calls = 0

    async def analyze(self, image, request_id):
        self.calls += 1
        return SimpleNamespace(integrity=SimpleNamespace(decision="ready", solvable=True),
                               mathematical_expressions=[], answer_choices=[])

    async def generate(self, analysis, request_id):
        return SimpleNamespace(lesson=SimpleNamespace(content=SimpleNamespace(final_answer="B) 4")))


def args(**overrides):
    return Namespace(**({"model": "gpt-6-luna", "lesson_model": "gpt-4.1-mini", "reasoning_effort": "low", "dry_run": False,
                         "allow_paid": True, "max_usd": 100.0, "max_calls": 1000} | overrides))


def fake_plan(n):
    questions = json.loads(question_pack.PACK.read_text(encoding="utf-8"))["questions"][:n]
    return lambda: ([{"question": q, "image": None} for q in questions], [])


def test_dry_run_makes_no_provider_call(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(eval_pack, "plan", fake_plan(3))
    made = []
    code = asyncio.run(eval_pack.run(args(dry_run=True), Settings(environment="test"), lambda *a: made.append(a), tmp_path))
    assert code == 0 and made == [] and "Kuru koşu" in capsys.readouterr().out


def test_cost_cap_stops_run_before_exceeding_budget(monkeypatch, tmp_path):
    monkeypatch.setattr(eval_pack, "plan", fake_plan(6))
    _, prices = eval_pack.load_pricing()
    per_question = eval_pack.upper_usd([None], "gpt-6-luna", "gpt-4.1-mini", prices)
    services = []
    factory = lambda *a: services.append(FakeServices()) or services[-1]  # noqa: E731
    code = asyncio.run(eval_pack.run(args(max_usd=per_question * 2.5), Settings(environment="test"), factory, tmp_path))
    assert code == 4 and services[0].calls == 2  # üçüncü soru tavanı aşacağı için koşulmadı
    summary = json.loads(next(tmp_path.glob("*/summary.json")).read_text(encoding="utf-8"))
    assert summary["questions"] == 2 and summary["stopped"] == "USD sınırı"
    assert summary["answer_accuracy_teacher"] in {"anahtar_yok"} or isinstance(summary["answer_accuracy_teacher"], float)


def test_unsupported_reasoning_effort_is_rejected_before_any_call(monkeypatch, tmp_path):
    monkeypatch.setattr(eval_pack, "plan", fake_plan(1))
    with pytest.raises(ValueError):
        asyncio.run(eval_pack.run(args(model="gpt-4.1-mini"), Settings(environment="test"), FakeServices, tmp_path))
