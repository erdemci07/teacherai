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
