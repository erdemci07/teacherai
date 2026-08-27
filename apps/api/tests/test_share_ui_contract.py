from pathlib import Path


def test_share_button_is_only_rendered_inside_success_result_block() -> None:
    source = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")

    assert "import { ShareSolution }" in source
    assert "{result && (" in source
    assert '<div className="solutionMobileScreen">' in source
    assert "<InteractionPanel lesson={result.lesson} />" in source
    assert "<ShareSolution result={result} />" in source
    assert "<SolutionFeedback result={result} />" in source
    assert source.index("<ShareSolution result={result} />") < source.index("<SolutionFeedback result={result} />")
    assert "setResult(null)" in source


def test_native_share_and_clipboard_fallback_are_implemented() -> None:
    source = Path("apps/web/app/solve/ShareSolution.tsx").read_text(encoding="utf-8")
    api = Path("apps/web/app/lib/share-api.ts").read_text(encoding="utf-8")

    assert "navigator.share" in source
    assert "navigator.clipboard.writeText" in source
    assert "AbortError" in source
    assert "existing_share_id" in api
    assert "TeacherAI bu matematik sorusunu adım adım çözdü" in api
    assert "Paylaşım bağlantısı şu anda oluşturulamadı" in api


def test_public_page_reuses_existing_solution_renderers_and_cta() -> None:
    source = Path("apps/web/app/shared/page.tsx").read_text(encoding="utf-8")

    assert "TeacherBoardView" in source
    assert "LessonText" in source
    assert "RichMathText" in source
    assert 'href="/solve"' in source
    assert "Sen de soru çöz" in source


def test_firebase_hosting_routes_short_share_urls_without_api_rewrite() -> None:
    firebase = Path("firebase.json").read_text(encoding="utf-8")

    assert '"public": "apps/web/out"' in firebase
    assert '"rewrites"' in firebase
    assert '"/s/**"' in firebase
    assert '"serviceId": "teacherai-api"' in firebase
    assert '"region": "us-east4"' in firebase
    assert '"/api/**"' not in firebase


def test_share_rewrite_is_ordered_before_static_fallback_shape() -> None:
    import json

    hosting = json.loads(Path("firebase.json").read_text(encoding="utf-8-sig"))["hosting"]

    assert hosting["rewrites"][0] == {
        "source": "/s/**",
        "run": {"serviceId": "teacherai-api", "region": "us-east4"},
    }


def test_brand_mark_component_drives_visible_teacherai_identity() -> None:
    brand = Path("apps/web/app/components/BrandMark.tsx").read_text(encoding="utf-8")
    logo = Path("apps/web/app/components/Logo.tsx").read_text(encoding="utf-8")
    home = Path("apps/web/app/page.tsx").read_text(encoding="utf-8")

    assert 'src="/teacherai-mascot.png"' in brand
    assert "BrandMark" in logo
    assert "BrandMark" in home
    assert "Senin yapay zekâ öğretmenin" in logo
    assert "Senin yapay zekâ öğretmenin" in home


def test_camera_gallery_actions_keep_existing_handlers_with_clear_icons() -> None:
    source = Path("apps/web/app/solve/UploadCard.tsx").read_text(encoding="utf-8")

    assert "onCamera();" in source
    assert "onGallery();" in source
    assert "onFilePicker();" in source
    assert "📷" in source
    assert "🖼️" in source
    assert "⌁" not in source
    assert ">□<" not in source


def test_teacher_flow_uses_single_number_treatment() -> None:
    home = Path("apps/web/app/page.tsx").read_text(encoding="utf-8")
    css = Path("apps/web/app/globals.css").read_text(encoding="utf-8")

    assert "step: '01'" in home
    assert "teacherFlowCard li:before{display:none!important}" in css


def test_static_og_asset_and_public_url_copy_are_present() -> None:
    asset = Path("apps/web/public/teacherai-share-og.svg").read_text(encoding="utf-8")
    service = Path("apps/api/app/features/shares/service.py").read_text(encoding="utf-8")

    assert "TeacherAI" in asset
    assert "og:image" in service
    assert "SHARE_TITLE" in service
    assert "noindex, follow" in service


def test_api_helpers_use_configured_absolute_api_base() -> None:
    for path in (
        "apps/web/app/lib/vision-api.ts",
        "apps/web/app/lib/lesson-api.ts",
        "apps/web/app/lib/feedback-api.ts",
        "apps/web/app/lib/share-api.ts",
        "apps/web/app/lib/interaction-api.ts",
        "apps/web/app/lib/student-api.ts",
    ):
        source = Path(path).read_text(encoding="utf-8")
        assert "NEXT_PUBLIC_API_BASE_URL" in source
        assert "localhost:8000/api/v1" in source
        assert "teacherai-07.web.app/api" not in source


def test_share_public_html_links_to_teacherai07_solve() -> None:
    settings = Path("apps/api/app/core/settings.py").read_text(encoding="utf-8")
    service = Path("apps/api/app/features/shares/service.py").read_text(encoding="utf-8")

    assert 'https://teacherai-07.web.app' in settings
    assert "public_share_url_base" in settings
    assert "PUBLIC_SHARE_URL_BASE" in settings
    assert "self.public_app_url}/shared/?id=" in service
