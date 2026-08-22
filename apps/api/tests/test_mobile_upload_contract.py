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


def test_selection_preserves_original_file_and_direct_solve_upload() -> None:
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")
    api = Path("apps/web/app/lib/vision-api.ts").read_text(encoding="utf-8")

    assert "setFile(selected)" in workspace
    assert "analyzeQuestionImage(file, () => setState('analyzing'))" in workspace
    assert "form.append('image', image)" in api
    assert "prepared_image_id" not in api
    assert "prepared_image_data_url" not in api
    assert "normalized_preview_url: string | null" in api
    assert "heic2any" not in workspace
    assert "setFile(url" not in workspace


def test_no_mandatory_backend_preview_before_solve() -> None:
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")

    assert "setState('image_selected')" in workspace
    assert "prepareImagePreview(" not in workspace
    assert "requestBackendPreview" not in workspace
    assert "const [previewPreparing" not in workspace
    assert "preparedImage" not in workspace


def test_solve_sends_direct_original_file_without_prepared_payload() -> None:
    api = Path("apps/web/app/lib/vision-api.ts").read_text(encoding="utf-8")

    assert "form.append('image', image)" in api
    assert "preparedImage" not in api


def test_supported_files_get_immediate_native_preview_attempt() -> None:
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")

    assert "setPreview(URL.createObjectURL(selected)); setPreviewAvailable(true);" in workspace
    assert "needsGenericPreview" not in workspace


def test_solve_is_available_as_soon_as_supported_file_is_selected() -> None:
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")

    assert "if (!file) return;" in workspace
    assert "disabled={!file || busy}" in workspace
    assert "Görsel hazırlanıyor..." not in workspace


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


def test_native_preview_failure_falls_back_to_generic_state_without_disabling_solve() -> None:
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")
    preview = Path("apps/web/app/solve/ImagePreview.tsx").read_text(encoding="utf-8")

    assert "onError={onPreviewError}" in preview
    assert "const handlePreviewError" in workspace
    assert "setPreviewAvailable(false)" in workspace
    assert "requestBackendPreview" not in workspace


def test_preview_state_remains_after_downstream_solve_error() -> None:
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")
    catch_block = workspace.split("} catch (caught) {", 1)[1].split("  const pasted", 1)[0]

    assert "setPreview('')" not in catch_block
    assert "setFile(null)" not in catch_block


def test_successful_solve_marks_only_current_file_for_resolve_label() -> None:
    workspace = Path("apps/web/app/solve/SolveWorkspace.tsx").read_text(encoding="utf-8")

    assert "const fileKey = (value: File)" in workspace
    assert "selectedFileKeyRef.current = key" in workspace
    assert "setSolvedFileKey('')" in workspace
    assert "if (solveFileKey && selectedFileKeyRef.current === solveFileKey) setSolvedFileKey(solveFileKey)" in workspace
    assert "solvedCurrentImage ? 'Yeniden Çöz' : 'Soruyu Çöz'" in workspace
    assert "setSelectedFileKey('')" in workspace
