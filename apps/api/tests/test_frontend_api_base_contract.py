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
        assert "math-ai-07.web.app/api" not in source


def test_deploy_script_resolves_absolute_cloud_run_api_before_static_build() -> None:
    script = Path("scripts/deploy-production.ps1").read_text(encoding="utf-8")

    assert '$env:NEXT_PUBLIC_API_BASE_URL = "$ApiUrl/api/v1"' in script
    assert script.index("gcloud run services describe $ServiceName") < script.index('$env:NEXT_PUBLIC_API_BASE_URL = "$ApiUrl/api/v1"')
    assert script.index('$env:NEXT_PUBLIC_API_BASE_URL = "$ApiUrl/api/v1"') < script.index("npm run build:web")
