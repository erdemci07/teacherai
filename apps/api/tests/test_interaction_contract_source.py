from pathlib import Path


def test_ben_deneyeyim_is_not_rendered_and_other_actions_remain() -> None:
    panel = Path("apps/web/app/solve/InteractionPanel.tsx").read_text(encoding="utf-8")

    assert "Ben deneyeyim" not in panel
    for label in ("Anladım", "Daha basit anlat", "Başka yöntem göster", "İpucu ver", "Benzer örnek"):
        assert label in panel


def test_practice_removed_from_interaction_action_types_and_prompt() -> None:
    frontend = Path("apps/web/app/lib/interaction-api.ts").read_text(encoding="utf-8")
    backend = Path("apps/api/app/features/interactions/schemas.py").read_text(encoding="utf-8")
    prompt = Path("apps/api/app/features/interactions/prompts/interaction.txt").read_text(encoding="utf-8")

    assert "'practice'" not in frontend.split("export type InteractionAction=", 1)[1].split(";", 1)[0]
    assert '"practice"' not in backend.split("Action=Literal", 1)[1].split("]", 1)[0]
    assert "practice:" not in prompt
