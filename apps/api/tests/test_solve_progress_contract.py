from pathlib import Path


def test_solve_progress_uses_ordered_stage_model_without_fast_cycle() -> None:
    source = Path("apps/web/app/solve/AnalysisLoading.tsx").read_text(encoding="utf-8")

    for message in (
        "Görsel hazırlanıyor",
        "Soruyu okuyorum",
        "Şekil ve ifadeleri dikkatlice inceliyorum",
        "Çözüm yolunu planlıyorum",
        "Adımları kontrol ediyorum",
        "Anlatımı hazırlıyorum",
    ):
        assert message in source
    assert "setInterval" not in source
    assert "setTimeout" in source
    assert "7000" in source


def test_empty_state_uses_teacherai_native_icon_not_sparkle() -> None:
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")
    styles = Path("apps/web/app/globals.css").read_text(encoding="utf-8")

    assert "✦" not in workspace
    assert "emptyBoardIcon" in workspace
    assert "∑" in workspace
    assert ".emptyBoardIcon" in styles


def test_vision_and_lesson_errors_remain_distinguishable() -> None:
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")

    assert "caught instanceof VisionApiError" in workspace
    assert "caught instanceof LessonApiError" in workspace
    assert "provider_unavailable" in workspace
    assert "provider_timeout" in workspace
    assert "invalid_provider_response" in workspace
    assert "lesson_provider_unavailable" in workspace
    assert "invalid_lesson_plan" in workspace
    assert "math_verification_failed" in workspace
    assert "lesson_timeout" in workspace
    assert "network_error" in workspace
