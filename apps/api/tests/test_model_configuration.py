from apps.api.app.core.settings import Settings


def test_default_model_configuration_is_cost_aware() -> None:
    settings = Settings(_env_file=None)

    assert settings.openai_vision_model == "gpt-4.1-mini"
    assert settings.openai_lesson_model == "gpt-5.6-terra"
    assert settings.openai_interaction_model == "gpt-4.1-mini"
    assert settings.openai_lesson_model != "gpt-5.6-sol"


def test_openai_model_environment_overrides_still_work(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_VISION_MODEL", "vision-override")
    monkeypatch.setenv("OPENAI_LESSON_MODEL", "lesson-override")
    monkeypatch.setenv("OPENAI_INTERACTION_MODEL", "interaction-override")

    settings = Settings(_env_file=None)

    assert settings.openai_vision_model == "vision-override"
    assert settings.openai_lesson_model == "lesson-override"
    assert settings.openai_interaction_model == "interaction-override"
