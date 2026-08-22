from pathlib import Path


def test_feedback_ui_appears_only_after_successful_solution_and_is_independent_from_interactions() -> None:
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")
    component = Path("apps/web/app/solve/SolutionFeedback.tsx").read_text(encoding="utf-8")

    assert "import { SolutionFeedback }" in workspace
    assert "{result && <>" in workspace
    assert "<SolutionFeedback result={result} />" in workspace
    assert "<InteractionPanel lesson={result.lesson} />" in workspace
    assert "Nasıl, burası oturdu mu?" not in component


def test_feedback_buttons_open_positive_and_negative_options() -> None:
    component = Path("apps/web/app/solve/SolutionFeedback.tsx").read_text(encoding="utf-8")

    assert "Bu anlatım nasıldı?" in component
    assert "Olumlu geri bildirim ver" in component
    assert "Olumsuz geri bildirim ver" in component
    for label in ("Anlaşılırdı", "Çözüm doğruydu", "Anlatım güzeldi", "İşime yaradı"):
        assert label in component
    for label in ("Çözüm yanlış", "Soruyu yanlış okudu", "Bir işlem/adım hatalı", "Formül/gösterim hatalı"):
        assert label in component


def test_feedback_submission_confirmation_and_failure_do_not_remove_solution() -> None:
    component = Path("apps/web/app/solve/SolutionFeedback.tsx").read_text(encoding="utf-8")
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")

    assert "Teşekkürler! Geri bildirimin alındı." in component
    assert "Geri bildirimin gönderilemedi. Tekrar deneyebilirsin." in component
    assert "setResult(null)" not in component
    assert "<TeacherBoard result={result} />" in workspace


def test_feedback_accessibility_contract() -> None:
    component = Path("apps/web/app/solve/SolutionFeedback.tsx").read_text(encoding="utf-8")

    assert 'role="dialog"' in component
    assert 'aria-modal="true"' in component
    assert "aria-pressed" in component
    assert "aria-label" in component
    assert "Escape" in component
    assert "closeRef.current?.focus()" in component


def test_feedback_api_does_not_use_public_email_secrets() -> None:
    api = Path("apps/web/app/lib/feedback-api.ts").read_text(encoding="utf-8")

    assert "RESEND_API_KEY" not in api
    assert "FEEDBACK_NOTIFICATION_EMAIL" not in api
    assert "/feedback" in api
