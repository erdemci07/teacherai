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


def test_selection_uses_backend_preparation_and_preserves_original_file() -> None:
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")
    api = Path("apps/web/app/lib/vision-api.ts").read_text(encoding="utf-8")

    assert "setFile(selected)" in workspace
    assert "setPreparedImage(null)" in workspace
    assert "prepareImagePreview(selected" in workspace
    assert "requestBackendPreview(selected, requestId)" in workspace
    assert "analyzeQuestionImage(file, () => setState('analyzing'), preparedImage)" in workspace
    assert "/vision/preview" in api
    assert "prepared_image_id" in api
    assert "prepared_image_data_url" in api
    assert "prepared_image_expires_at" in api
    assert "format: 'png'" in api
    assert "content_type: 'image/png'" in api
    assert "preview: string" in api
    assert "normalized_preview_url: string | null" in api
    assert "heic2any" not in workspace
    assert "setFile(url" not in workspace


def test_backend_preview_success_and_failure_paths_are_non_blocking() -> None:
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")

    assert "setPreparedImage(value)" in workspace
    assert "setPreview(value.preview)" in workspace
    assert ".catch(() => undefined)" in workspace
    assert "setState('image_selected')" in workspace
    assert "Görseli yeniden hazırla" in workspace
    assert "setError(" not in workspace.split("const requestBackendPreview", 1)[1].split("const select", 1)[0]


def test_solve_sends_prepared_png_with_original_file_fallback() -> None:
    api = Path("apps/web/app/lib/vision-api.ts").read_text(encoding="utf-8")

    prepared_block = api.split("if (preparedImage) {", 1)[1].split("} else {", 1)[0]
    assert "form.append('prepared_image_id', preparedImage.image_id)" in prepared_block
    assert "form.append('prepared_image_data_url', preparedImage.preview)" in prepared_block
    assert "form.append('prepared_image_expires_at', preparedImage.expires_at)" in prepared_block
    assert "form.append('image', image)" in prepared_block


def test_jpeg_png_webp_keep_native_preview_while_backend_preparation_runs() -> None:
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")

    assert "if (!needsGenericPreview(mediaType, extension))" in workspace
    assert "setPreview(URL.createObjectURL(selected)); setPreviewAvailable(true);" in workspace
    assert "requestBackendPreview(selected, requestId)" in workspace


def test_solve_requires_prepared_backend_image_before_analysis() -> None:
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")

    assert "if (!file || !preparedImage || previewPreparing) return;" in workspace
    assert "disabled={!file || busy || previewPreparing || !preparedImage}" in workspace
    assert "Görsel hazırlanıyor..." in workspace


def test_generated_preview_urls_are_cleaned_up_on_replace_remove() -> None:
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")

    assert "useEffect(() => () => { if (preview) revokeBlobPreview(preview); }, [preview])" in workspace
    assert "if (preview) revokeBlobPreview(preview);" in workspace
    assert "url.startsWith('blob:')" in workspace
    assert "previewAbortRef.current?.abort()" in workspace
    assert "previewRequestRef.current += 1" in workspace
    assert "setPreparedImage(null)" in workspace
    assert "if (previewRequestRef.current !== requestId) return;" in workspace
    assert "onRemove={reset}" in workspace
    assert "onReplace={() => galleryRef.current?.click()}" in workspace


def test_browser_heic_decoder_dependency_is_not_required() -> None:
    package_json = Path("apps/web/package.json").read_text(encoding="utf-8")
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")

    assert "heic2any" not in package_json
    assert "createHeicPreviewUrl" not in workspace
    assert not Path("apps/web/app/solve/heicPreview.ts").exists()


def test_native_preview_failure_can_request_backend_preparation_again() -> None:
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")
    preview = Path("apps/web/app/solve/ImagePreview.tsx").read_text(encoding="utf-8")

    assert "onError={onPreviewError}" in preview
    assert "const handlePreviewError" in workspace
    assert "setPreviewAvailable(false)" in workspace
    assert "requestBackendPreview(file, previewRequestRef.current)" in workspace


def test_png_preview_state_remains_after_downstream_solve_error() -> None:
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")
    catch_block = workspace.split("} catch (caught) {", 1)[1].split("  const pasted", 1)[0]

    assert "setPreview('')" not in catch_block
    assert "setPreparedImage(null)" not in catch_block
    assert "setFile(null)" not in catch_block
    assert "Görseli yeniden hazırla" in workspace
