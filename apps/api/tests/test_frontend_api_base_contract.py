import re
from pathlib import Path


API_HELPERS = (
    "apps/web/app/lib/vision-api.ts",
    "apps/web/app/lib/lesson-api.ts",
    "apps/web/app/lib/feedback-api.ts",
    "apps/web/app/lib/share-api.ts",
    "apps/web/app/lib/interaction-api.ts",
    "apps/web/app/lib/student-api.ts",
)


def test_frontend_api_helpers_use_configured_api_base() -> None:
    for helper in API_HELPERS:
        source = Path(helper).read_text(encoding="utf-8")
        assert "NEXT_PUBLIC_API_BASE_URL" in source
        assert "NEXT_PUBLIC_TEACHERAI_API_BASE_URL" in source
        assert "teacherai-07.web.app/api" not in source
        assert not re.search(r"[a-z0-9-]+\.web\.app/api", source)  # hiçbir Hosting alanı API tabanı değildir


def test_deploy_script_resolves_absolute_cloud_run_api_before_static_build() -> None:
    # TA-005B: sıra scripts/deploy_plan.py adım tablosundadır: API dağıtımı ve URL, web build'inden önce gelir.
    from scripts import deploy_plan

    steps = [action.__name__ for _, action in deploy_plan.STEPS]
    assert steps.index("step_deploy") < steps.index("step_revision") < steps.index("step_url") < steps.index("step_web_build")
    plan = Path("scripts/deploy_plan.py").read_text(encoding="utf-8")
    assert '"NEXT_PUBLIC_API_BASE_URL": ctx.state["api_base"]' in plan
    assert """ctx.state["api_base"] = f"{ctx.state['url']}/api/v1\"""" in plan
