"""TA-005C §13: değerlendirme hazırlığı ve açık offline muhasebe. Sağlayıcı çağrısı yoktur; sonuçlar model
kalitesi değildir."""

import pytest

from apps.api.app.core import gateway
from apps.api.app.core.settings import Settings
from scripts import eval_pack, evaluate_models


def test_readiness_reports_balance_missing_artifacts_and_no_accuracy():
    report = eval_pack.readiness()
    assert report["subjects"] == {"biology": 6, "chemistry": 6, "mathematics": 6, "physics": 6} and report["balanced"]
    assert report["real_accuracy_measured"] is False
    assert report["answer_key_separate_from_model_inputs"] is True
    assert len(report["images_missing"]) + report["images_ready"] == 24
    if report["answer_key"] == "bekleniyor":
        assert len(report["answer_key_missing"]) == 24  # anahtar modelden türetilmez; eksik açıkça listelenir
    dims = report["dimensions"]
    assert dims["requested_answer_correctness"]["status"] == "anahtar_gerekli"
    assert dims["method_suitability"]["status"] == "insan_degerlendirmesi"
    assert set(report["providers"]["anthropic"]) == {"vision", "lessons", "interaction"}
    assert any(item["model"] == "gpt-4.1-mini" and item["shutdown"] == "2027-01-14" for item in report["lifecycle"])


def test_readiness_command_makes_no_call(capsys):
    assert evaluate_models.main(["readiness"]) == 0
    assert "sağlayıcı çağrısı yapılmadı" in capsys.readouterr().out


def test_anthropic_vision_pack_requires_model_and_explicit_image_permission(capsys):
    base = ["pack", "--vision-provider", "anthropic", "--dry-run"]
    with pytest.raises(SystemExit):
        evaluate_models.main(base, settings=Settings(_env_file=None))
    with pytest.raises(SystemExit):
        evaluate_models.main([*base, "--model", "claude-sonnet-5-5"], settings=Settings(_env_file=None))
    assert "--pack-images-to-anthropic" in capsys.readouterr().err
    assert evaluate_models.main([*base, "--model", "claude-sonnet-5-5", "--pack-images-to-anthropic"],
                                settings=Settings(_env_file=None)) == 0
    assert "Vision Anthropic" in capsys.readouterr().out


def test_pack_services_wire_anthropic_vision_with_pack_permission_only():
    services = eval_pack.Services(Settings(_env_file=None, anthropic_api_key="k"), "claude-sonnet-5-5", "gpt-5.6-terra",
                                  None, vision_provider="anthropic", pack_images_to_anthropic=True)
    provider = services.vision._provider
    assert provider.name == "anthropic" and provider._allow_images is True
    assert services.lessons.provider.name == "openai"
    # Production izni bununla açılmaz.
    assert Settings(_env_file=None).allow_student_images_to_anthropic is False


@pytest.mark.asyncio
async def test_pack_question_runs_inside_explicit_offline_scope(tmp_path):
    seen = []

    class Fake:
        async def analyze(self, image, request_id):
            seen.append(gateway.current_scope())
            raise eval_pack_error()

    def eval_pack_error():
        from apps.api.app.features.vision.exceptions import ProviderUnavailableError

        return ProviderUnavailableError()

    item = {"question": {"id": "M01", "subject": "mathematics", "reading": {}}, "image": tmp_path / "x.png"}
    row = await eval_pack.run_question(item, Fake(), Settings(_env_file=None), {})
    scope = seen[0]
    assert scope.kind == "offline" and scope.max_calls == eval_pack.MAX_CALLS["vision"] and scope.tracker is None
    assert row["error"] == "provider_unavailable" and row["estimated_usd"] is None


def test_unknown_token_counts_are_not_summed_as_zero():
    assert evaluate_models.known_sum([1, 2]) == 3
    assert evaluate_models.known_sum([1, None]) is None
    assert evaluate_models.known_sum([]) == 0
