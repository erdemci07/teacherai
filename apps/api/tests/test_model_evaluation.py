"""D paketi: değerlendirme altyapısı. Hiçbir test ağ veya ücretli çağrı yapmaz."""

import json
import shutil
import subprocess

import pytest

from apps.api.app.core.settings import Settings
from scripts import evaluate_models
from scripts.eval_dataset import SCHEMA_PATH, json_schema, load
from scripts.generate_smoke_set import build

SMOKE = evaluate_models.DATASETS / "smoke.jsonl"


def never_called(**kwargs):
    raise AssertionError("sağlayıcı istemcisi oluşturuldu: ağ çağrısı yapılmamalıydı")


def test_validate_and_legacy_argless_call_pass_smoke_set(capsys):
    assert evaluate_models.main(["validate"], client_factory=never_called) == 0
    assert evaluate_models.main([], client_factory=never_called) == 0
    out = capsys.readouterr().out
    assert "smoke.jsonl: 10 öğe" in out and "original-100.jsonl: boş" in out
    items, errors = load(SMOKE)
    assert not errors and len(items) == 10 and {item.source for item in items} == {"synthetic"}


@pytest.mark.parametrize(
    ("change", "reason"),
    [({"source": "ÖSYM"}, "telif"), ({"source": "yayınevi"}, "telif"), ({"license": "  "}, "boş olamaz"), ({"image": "smoke/yok.png"}, "görsel dosyası eksik")],
)
def test_validator_rejects_copyright_unlicensed_and_missing_image(tmp_path, change, reason):
    shutil.copytree(evaluate_models.DATASETS / "smoke", tmp_path / "smoke")
    record = json.loads(SMOKE.read_text(encoding="utf-8").splitlines()[0])
    (tmp_path / "bad.jsonl").write_text(json.dumps({**record, **change}, ensure_ascii=False) + "\n", encoding="utf-8")
    items, errors = load(tmp_path / "bad.jsonl")
    assert len(errors) == 1 and reason in errors[0]
    assert evaluate_models.main(["validate", str(tmp_path / "bad.jsonl")]) == 1


def test_validator_rejects_mislabeled_solution(tmp_path):
    shutil.copytree(evaluate_models.DATASETS / "smoke", tmp_path / "smoke")
    record = json.loads(SMOKE.read_text(encoding="utf-8").splitlines()[0])
    (tmp_path / "bad.jsonl").write_text(json.dumps({**record, "expected_solutions": ["5"]}) + "\n", encoding="utf-8")
    assert "denklemi sağlamıyor" in load(tmp_path / "bad.jsonl")[1][0]


def test_schema_file_matches_model():
    assert json.loads(SCHEMA_PATH.read_text(encoding="utf-8")) == json_schema()


def test_smoke_generator_is_deterministic():
    first = [(record, image.tobytes()) for record, image in build()]
    second = [(record, image.tobytes()) for record, image in build()]
    assert first == second and len(first) == 10


@pytest.mark.parametrize(
    "argv",
    [
        ["run"],
        ["run", "--max-usd", "1", "--max-calls", "5"],
        ["run", "--allow-paid", "--max-calls", "5"],
        ["run", "--allow-paid", "--max-usd", "1"],
        ["run", "--allow-paid", "--max-usd", "1", "--max-calls", "5"],  # fiyat yapılandırması yok
    ],
)
def test_no_network_without_full_paid_authorisation(argv):
    settings = Settings(openai_api_key="fixture-key")
    with pytest.raises(SystemExit) as stopped:
        evaluate_models.main(argv, settings=settings, client_factory=never_called)
    assert stopped.value.code == 2


def test_unsupported_reasoning_effort_is_rejected_before_any_call(tmp_path):
    with pytest.raises(ValueError):
        evaluate_models.main(["run", "--provider", "fake", "--candidate", "gpt-4.1-mini", "--reasoning-effort", "low",
                              "--output-dir", str(tmp_path)], settings=Settings())
    assert not any(tmp_path.iterdir())


PRICES = Settings(pricing_version="fixture", model_prices={"gpt-4.1-mini": (1, 0.5, 4), "gpt-6-luna": (2, 1, 8)})


def test_budget_estimate_over_limit_never_starts(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(evaluate_models, "execute", lambda *a, **k: calls.append(a))
    code = evaluate_models.main(["run", "--provider", "fake", "--max-usd", "0.01", "--output-dir", str(tmp_path)], settings=PRICES)
    assert code == 3 and calls == [] and not any(tmp_path.iterdir())
    code = evaluate_models.main(["run", "--provider", "fake", "--max-calls", "3", "--output-dir", str(tmp_path)], settings=PRICES)
    assert code == 3 and calls == []


def test_budget_stops_mid_run_when_actual_spend_exceeds_estimate(tmp_path):
    # Sahte sağlayıcı tahminden çok daha fazla giriş tokenı bildirir; kalan çağrılar yapılmaz.
    code = evaluate_models.main(["run", "--provider", "fake", "--operations", "vision", "--max-usd", "1.0",
                                 "--fake-input-tokens", "200000", "--output-dir", str(tmp_path)], settings=PRICES)
    rows = [json.loads(line) for line in (tmp_path / "raw.jsonl").read_text(encoding="utf-8").splitlines()]
    assert code == 4 and 0 < len(rows) < 20
    assert sum(row["estimated_usd"] for row in rows) <= 1.0 + max(row["estimated_usd"] for row in rows)
    assert "Erken durma: USD sınırı" in (tmp_path / "summary.md").read_text(encoding="utf-8")


def test_fake_end_to_end_fills_every_metric(tmp_path):
    code = evaluate_models.main(["run", "--provider", "fake", "--reasoning-effort", "none", "low", "medium",
                                 "--output-dir", str(tmp_path)], settings=PRICES)
    assert code == 0
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert summary.splitlines()[2].startswith("> **Sahte sağlayıcı — model kalitesi değildir.**")
    assert "100 soruluk özgün öğretmen veri seti henüz bulunmuyor" in summary
    rows = evaluate_models.summarize([json.loads(line) for line in (tmp_path / "raw.jsonl").read_text(encoding="utf-8").splitlines()])
    vision = [row for row in rows if row["operation"] == "vision"]
    interaction = [row for row in rows if row["operation"] == "interaction"]
    assert len(vision) == 4 and len(interaction) == 4, "mevcut model + üç reasoning düzeyi"
    for row in vision:
        for key in ("valid_question_accuracy", "expression_equivalence", "root_set_match", "schema_valid_rate",
                    "latency_p50_ms", "latency_p95_ms", "estimated_usd"):
            assert row[key] is not None, key
        assert row["outcomes"] == {"completed": 10}
    for row in interaction:
        assert row["answer_leak_rate"] == 0.0 and row["input_tokens"] > 0
    assert any(row["reasoning_tokens"] > 0 for row in interaction)
    rubric = (tmp_path / "rubric.csv").read_text(encoding="utf-8").splitlines()
    assert rubric[0].startswith("item_id,operation,model,reasoning_effort,output,pedagoji_1_5") and len(rubric) > 1


def test_answer_leak_detection_is_deterministic():
    assert evaluate_models.leaks("Sonuç x = 4 olur.", ["4", "x = 4"])
    assert evaluate_models.leaks("Cevap 4.", ["4"])
    assert not evaluate_models.leaks("Önce 7'yi karşıya at, sonra 3'e böl.", ["4", "x = 4"])
    assert not evaluate_models.leaks("14 ile çarp.", ["4"])


def test_production_model_defaults_are_unchanged():
    settings = Settings()
    assert (settings.openai_vision_model, settings.openai_lesson_model, settings.openai_interaction_model) == (
        "gpt-4.1-mini", "gpt-5.6-terra", "gpt-4.1-mini")
    if shutil.which("git"):
        diff = subprocess.run(["git", "diff", "a3b9d05f1526777172751f672f1c0c07475401b1", "--", ".env.example", "docker-compose.yml"],
                              capture_output=True, text=True, encoding="utf-8", check=False).stdout
        assert not [line for line in diff.splitlines() if line.startswith(("+", "-")) and "OPENAI_" in line and "MODEL" in line]
