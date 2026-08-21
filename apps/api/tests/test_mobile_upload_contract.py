from pathlib import Path
import re


def test_camera_and_gallery_use_separate_mobile_inputs() -> None:
    source = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")
    camera = re.search(r'ref=\{cameraRef\}[^>]+', source)
    gallery = re.search(r'ref=\{galleryRef\}[^>]+', source)

    assert camera and 'accept="image/*"' in camera.group(0)
    assert 'capture="environment"' in camera.group(0)
    assert gallery and 'accept="image/*"' in gallery.group(0)
    assert "capture=" not in gallery.group(0)


def test_existing_desktop_and_retry_upload_paths_remain_available() -> None:
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")
    upload_card = Path("apps/web/app/solve/UploadCard.tsx").read_text(encoding="utf-8")

    assert "onDrop={dropped}" in upload_card
    assert "onPaste={pasted}" in workspace
    assert "Tekrar Çek" in workspace
    assert "Başka Görsel Seç" in workspace


def test_frontend_accepts_jpeg_extensions_and_supported_mime_types() -> None:
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")

    for media_type in ("image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif"):
        assert media_type in workspace
    for extension in (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"):
        assert extension in workspace
    assert "selected.type.toLowerCase()" in workspace
    assert "selected.name.split('.').pop()?.toLowerCase()" in workspace
    assert "JPG, JPEG, PNG, WEBP, HEIC veya HEIF" in workspace


def test_heic_preview_can_fall_back_to_generic_file_state() -> None:
    preview = Path("apps/web/app/solve/ImagePreview.tsx").read_text(encoding="utf-8")

    assert "previewAvailable && previewUrl" in preview
    assert "genericImagePreview" in preview
    assert "Önizleme bu tarayıcıda desteklenmeyebilir." in preview


def test_heic_preview_uses_backend_normalized_response_and_preserves_upload_file() -> None:
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")
    api = Path("apps/web/app/lib/vision-api.ts").read_text(encoding="utf-8")

    assert "setFile(selected)" in workspace
    assert "analyzeQuestionImage(file" in workspace
    assert "value.normalized_preview_url" in workspace
    assert "normalized_preview_url: string | null" in api
    assert "heic2any" not in workspace
    assert "setFile(url" not in workspace


def test_backend_preview_success_and_failure_paths_are_non_blocking() -> None:
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")

    assert "if (!previewAvailable && value.normalized_preview_url)" in workspace
    assert "setPreview(value.normalized_preview_url)" in workspace
    assert "setState('image_selected')" in workspace


def test_jpeg_png_webp_preview_behavior_remains_direct_object_url() -> None:
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")

    assert "!['image/heic', 'image/heif'].includes(mediaType)" in workspace
    assert "setPreview(URL.createObjectURL(selected)); setPreviewAvailable(true);" in workspace


def test_generated_preview_urls_are_cleaned_up_on_replace_remove() -> None:
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")

    assert "useEffect(() => () => { if (preview) revokeBlobPreview(preview); }, [preview])" in workspace
    assert "if (preview) revokeBlobPreview(preview);" in workspace
    assert "url.startsWith('blob:')" in workspace
    assert "onRemove={reset}" in workspace
    assert "onReplace={() => galleryRef.current?.click()}" in workspace


def test_browser_heic_decoder_dependency_is_not_required() -> None:
    package_json = Path("apps/web/package.json").read_text(encoding="utf-8")
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")

    assert "heic2any" not in package_json
    assert "createHeicPreviewUrl" not in workspace
    assert not Path("apps/web/app/solve/heicPreview.ts").exists()
