from pathlib import Path


def test_share_button_is_only_rendered_inside_success_result_block() -> None:
    source = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")

    assert "import { ShareSolution }" in source
    assert "{result && <>" in source
    assert "<InteractionPanel lesson={result.lesson} /><ShareSolution result={result} />" in source
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


def test_firebase_rewrites_public_share_route_to_cloud_run_before_api() -> None:
    firebase = Path("firebase.json").read_text(encoding="utf-8")

    assert '"source": "/s/**"' in firebase
    assert firebase.index('"source": "/s/**"') < firebase.index('"source": "/api/**"')
    assert '"serviceId": "teacherai-api"' in firebase
    assert '"region": "us-east4"' in firebase


def test_static_og_asset_and_public_url_copy_are_present() -> None:
    asset = Path("apps/web/public/teacherai-share-og.svg").read_text(encoding="utf-8")
    service = Path("apps/api/app/features/shares/service.py").read_text(encoding="utf-8")

    assert "TeacherAI" in asset
    assert "og:image" in service
    assert "SHARE_TITLE" in service
    assert "noindex, follow" in service
