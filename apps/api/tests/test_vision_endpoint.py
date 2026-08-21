import io
import base64
import re
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from PIL import ImageOps
from pillow_heif import register_heif_opener

from apps.api.app.features.vision.exceptions import (
    InvalidProviderResponseError,
    ProviderConfigurationError,
    ProviderUnavailableError,
)
from apps.api.app.features.vision.openai_provider import OpenAIVisionProvider
from apps.api.app.features.vision.provider import ProviderResult
from apps.api.app.features.vision.schemas import VisionProviderAnalysis, VisualElements
from apps.api.app.features.vision.service import VisionService
from apps.api.app.features.vision.storage import LocalTemporaryImageStorage
from apps.api.app.main import create_app

register_heif_opener()


def image_bytes(image_format: str = "PNG") -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (32, 24), "white").save(output, format=image_format)
    return output.getvalue()


def oriented_jpeg_bytes() -> bytes:
    output = io.BytesIO()
    image = Image.new("RGB", (20, 40), "white")
    exif = image.getexif()
    exif[274] = 6
    image.save(output, format="JPEG", exif=exif.tobytes())
    return output.getvalue()


class SuccessfulProvider:
    name = "test-provider"
    model = "test-model"

    def __init__(self, image_status: str = "valid_math_question", topic: str = "Mutlak Değer", subtopic: str | None = "Denklemler") -> None:
        self.image_status = image_status
        self.topic = topic
        self.subtopic = subtopic
        self.calls: list[tuple[bytes, str]] = []

    async def analyze_image(self, image: bytes, media_type: str, request_id: str | None = None) -> ProviderResult:
        assert image
        assert media_type == "image/png"
        self.calls.append((image, media_type))
        return ProviderResult(
            analysis=VisionProviderAnalysis(
                image_status=self.image_status,
                is_valid_question=self.image_status == "valid_math_question",
                rejection_reason=None if self.image_status == "valid_math_question" else "Görsel güvenilir biçimde okunamadı.",
                subject="mathematics" if self.image_status == "valid_math_question" else "",
                exam_context="TYT" if self.image_status == "valid_math_question" else None,
                topic=self.topic if self.image_status == "valid_math_question" else "",
                subtopic=self.subtopic if self.image_status == "valid_math_question" else None,
                question_type="multiple_choice" if self.image_status == "valid_math_question" else "",
                language="tr",
                difficulty="medium" if self.image_status == "valid_math_question" else "unknown",
                question_text="|x - 2| = 4 denkleminin çözümleri nelerdir?" if self.image_status == "valid_math_question" else "",
                mathematical_expressions=["|x - 2| = 4"] if self.image_status == "valid_math_question" else [],
                answer_choices=["-2 ve 6", "2 ve 4"] if self.image_status == "valid_math_question" else [],
                visual_elements=VisualElements(
                    has_diagram=False,
                    has_graph=False,
                    has_table=False,
                    has_geometry_figure=False,
                    description=None,
                ),
                ocr_uncertainties=[],
                confidence=0.97,
            ),
            provider="test-provider",
            model="test-model",
            response_id="response-test",
        )

    async def health(self) -> bool:
        return True


class FailingProvider:
    name = "test-provider"
    model = "test-model"

    def __init__(self, error: Exception) -> None:
        self.error = error

    async def analyze_image(self, image: bytes, media_type: str, request_id: str | None = None) -> ProviderResult:
        raise self.error

    async def health(self) -> bool:
        return False


def client_with_provider(tmp_path, provider, max_bytes: int = 10 * 1024 * 1024) -> TestClient:
    app = create_app()
    service = VisionService(
        provider=provider,
        storage=LocalTemporaryImageStorage(tmp_path),
        max_upload_size_bytes=max_bytes,
        debug=False,
    )
    app.state.container = replace(app.state.container, vision_service=service)
    return TestClient(app, raise_server_exceptions=False)


def test_successful_upload_uses_injected_provider_and_cleans_file(tmp_path) -> None:
    with client_with_provider(tmp_path, SuccessfulProvider()) as client:
        response = client.post("/api/v1/vision/analyze", files={"image": ("question.png", image_bytes(), "image/png")})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["topic"] == "Mutlak Değer"
    assert payload["data"]["image_status"] == "valid_math_question"
    assert payload["data"]["is_valid_question"] is True
    assert payload["data"]["provider"] == "test-provider"
    assert payload["data"]["request_id"] == response.headers["x-request-id"]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("image_status", ["not_math_question", "unreadable", "incomplete_question"])
def test_returns_normal_structured_rejection_for_invalid_question_images(tmp_path, image_status) -> None:
    with client_with_provider(tmp_path, SuccessfulProvider(image_status)) as client:
        response = client.post("/api/v1/vision/analyze", files={"image": ("image.png", image_bytes(), "image/png")})

    assert response.status_code == 200
    analysis = response.json()["data"]
    assert analysis["image_status"] == image_status
    assert analysis["is_valid_question"] is False
    assert analysis["rejection_reason"]
    assert analysis["question_text"] == ""
    assert analysis["mathematical_expressions"] == []


def test_normalizes_english_topic_and_subtopic_before_response(tmp_path) -> None:
    with client_with_provider(tmp_path, SuccessfulProvider(topic="Algebra", subtopic="Linear equations")) as client:
        response = client.post("/api/v1/vision/analyze", files={"image": ("question.png", image_bytes(), "image/png")})

    assert response.status_code == 200
    analysis = response.json()["data"]
    assert analysis["topic"] == "Cebir"
    assert analysis["subtopic"] == "Denklemler"


def test_rejects_unsupported_content_type(tmp_path) -> None:
    with client_with_provider(tmp_path, SuccessfulProvider()) as client:
        response = client.post("/api/v1/vision/analyze", files={"image": ("question.gif", b"GIF89a", "image/gif")})
    assert response.status_code == 415
    assert response.json()["error"] == "unsupported_image_type"


@pytest.mark.parametrize(
    ("filename", "content_type", "image_format"),
    [
        ("test.jpg", "image/jpeg", "JPEG"),
        ("test.JPG", "image/jpeg", "JPEG"),
        ("test.jpeg", "image/jpeg", "JPEG"),
        ("test.JPEG", "image/jpeg", "JPEG"),
        ("IMG_4537.jpeg", "image/jpeg", "JPEG"),
        ("test.jpg", "image/jpg", "JPEG"),
        ("test.png", "image/png", "PNG"),
        ("test.PNG", "image/png", "PNG"),
        ("test.webp", "image/webp", "WEBP"),
        ("test.WEBP", "image/webp", "WEBP"),
    ],
)
def test_accepts_supported_image_names_and_media_types(tmp_path, filename, content_type, image_format) -> None:
    with client_with_provider(tmp_path, SuccessfulProvider()) as client:
        response = client.post(
            "/api/v1/vision/analyze",
            files={"image": (filename, image_bytes(image_format), content_type)},
        )
    assert response.status_code == 200


@pytest.mark.parametrize(("filename", "content_type"), [("iphone.heic", "image/heic"), ("iphone.heif", "image/heif")])
def test_accepts_heic_and_heif_then_sends_normalized_png_to_provider(tmp_path, filename, content_type) -> None:
    provider = SuccessfulProvider()
    with client_with_provider(tmp_path, provider) as client:
        response = client.post(
            "/api/v1/vision/analyze",
            files={"image": (filename, image_bytes("HEIF"), content_type)},
        )

    assert response.status_code == 200
    preview_url = response.json()["data"]["normalized_preview_url"]
    assert preview_url.startswith("data:image/png;base64,")
    with Image.open(io.BytesIO(base64.b64decode(preview_url.split(",", 1)[1]))) as image:
        assert image.format == "PNG"
    normalized, media_type = provider.calls[0]
    assert media_type == "image/png"
    with Image.open(io.BytesIO(normalized)) as image:
        assert image.format == "PNG"


def test_heif_normalized_preview_uses_same_png_sent_to_provider(tmp_path) -> None:
    provider = SuccessfulProvider()
    with client_with_provider(tmp_path, provider) as client:
        response = client.post(
            "/api/v1/vision/analyze",
            files={"image": ("iphone.heif", image_bytes("HEIF"), "image/heif")},
        )

    assert response.status_code == 200
    normalized, media_type = provider.calls[0]
    assert media_type == "image/png"
    preview_url = response.json()["data"]["normalized_preview_url"]
    assert base64.b64decode(preview_url.split(",", 1)[1]) == normalized


@pytest.mark.parametrize(("filename", "content_type"), [("iphone.heic", "image/heic"), ("iphone.heif", "image/heif")])
def test_preview_endpoint_returns_normalized_png_without_vision_provider(tmp_path, filename, content_type) -> None:
    provider = SuccessfulProvider()
    with client_with_provider(tmp_path, provider) as client:
        response = client.post(
            "/api/v1/vision/preview",
            files={"image": (filename, image_bytes("HEIF"), content_type)},
        )

    assert response.status_code == 200
    assert provider.calls == []
    assert list(tmp_path.iterdir()) == []
    preview = response.json()["data"]
    assert re.fullmatch(r"prepared_[a-f0-9]{32}", preview["image_id"])
    assert preview["format"] == "png"
    assert preview["content_type"] == "image/png"
    assert preview["preview"].startswith("data:image/png;base64,")
    assert "path" not in preview
    assert "/" not in preview["image_id"]
    assert "\\" not in preview["image_id"]
    with Image.open(io.BytesIO(base64.b64decode(preview["preview"].split(",", 1)[1]))) as image:
        assert image.format == "PNG"


@pytest.mark.parametrize(
    ("filename", "content_type", "image_format"),
    [
        ("question.jpg", "image/jpeg", "JPEG"),
        ("question.jpeg", "image/jpeg", "JPEG"),
        ("question.png", "image/png", "PNG"),
        ("question.webp", "image/webp", "WEBP"),
        ("question.heic", "image/heic", "HEIF"),
        ("question.heif", "image/heif", "HEIF"),
    ],
)
def test_prepare_endpoint_normalizes_every_supported_format_to_png(tmp_path, filename, content_type, image_format) -> None:
    provider = SuccessfulProvider()
    with client_with_provider(tmp_path, provider) as client:
        response = client.post(
            "/api/v1/vision/preview",
            files={"image": (filename, image_bytes(image_format), content_type)},
        )

    assert response.status_code == 200
    assert provider.calls == []
    preview = response.json()["data"]
    assert preview["format"] == "png"
    assert preview["content_type"] == "image/png"
    assert preview["preview"].startswith("data:image/png;base64,")
    with Image.open(io.BytesIO(base64.b64decode(preview["preview"].split(",", 1)[1]))) as image:
        assert image.format == "PNG"
        assert image.size == (32, 24)


@pytest.mark.parametrize(("filename", "content_type"), [("iphone.heic", "image/heic"), ("iphone.heif", "image/heif")])
def test_analyze_can_reuse_prepared_png_without_reuploading_original(tmp_path, filename, content_type) -> None:
    provider = SuccessfulProvider()
    with client_with_provider(tmp_path, provider) as client:
        prepared_response = client.post(
            "/api/v1/vision/preview",
            files={"image": (filename, image_bytes("HEIF"), content_type)},
        )
        prepared = prepared_response.json()["data"]
        analysis_response = client.post(
            "/api/v1/vision/analyze",
            data={
                "prepared_image_id": prepared["image_id"],
                "prepared_image_data_url": prepared["preview"],
                "prepared_image_expires_at": prepared["expires_at"],
            },
        )

    assert prepared_response.status_code == 200
    assert analysis_response.status_code == 200
    normalized, media_type = provider.calls[0]
    assert media_type == "image/png"
    assert normalized == base64.b64decode(prepared["preview"].split(",", 1)[1])
    assert analysis_response.json()["data"]["normalized_preview_url"] == prepared["preview"]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("filename", "content_type", "image_format"),
    [
        ("iphone.heic", "image/heic", "HEIF"),
        ("question.jpg", "image/jpeg", "JPEG"),
    ],
)
def test_preview_to_prepared_png_then_analyze_succeeds(tmp_path, filename, content_type, image_format) -> None:
    provider = SuccessfulProvider()
    with client_with_provider(tmp_path, provider) as client:
        prepared_response = client.post(
            "/api/v1/vision/preview",
            files={"image": (filename, image_bytes(image_format), content_type)},
        )
        prepared = prepared_response.json()["data"]
        analysis_response = client.post(
            "/api/v1/vision/analyze",
            data={
                "prepared_image_id": prepared["image_id"],
                "prepared_image_data_url": prepared["preview"],
                "prepared_image_expires_at": prepared["expires_at"],
            },
        )

    assert prepared_response.status_code == 200
    assert analysis_response.status_code == 200
    assert provider.calls[0][1] == "image/png"


def test_incomplete_prepared_payload_is_rejected_before_provider_call(tmp_path) -> None:
    provider = SuccessfulProvider()
    with client_with_provider(tmp_path, provider) as client:
        response = client.post(
            "/api/v1/vision/analyze",
            data={"prepared_image_id": "prepared_00000000000000000000000000000000"},
        )

    assert response.status_code == 404
    assert response.json()["error"] == "prepared_image_not_found"
    assert provider.calls == []


def test_invalid_prepared_data_url_is_rejected_before_provider_call(tmp_path) -> None:
    provider = SuccessfulProvider()
    with client_with_provider(tmp_path, provider) as client:
        response = client.post(
            "/api/v1/vision/analyze",
            data={
                "prepared_image_id": "prepared_00000000000000000000000000000000",
                "prepared_image_data_url": "data:image/jpeg;base64,not-a-png",
            },
        )

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_prepared_image"
    assert provider.calls == []


def test_missing_prepared_payload_uses_original_file_fallback_when_available(tmp_path) -> None:
    provider = SuccessfulProvider()
    with client_with_provider(tmp_path, provider) as client:
        response = client.post(
            "/api/v1/vision/analyze",
            data={"prepared_image_id": "prepared_00000000000000000000000000000000"},
            files={"image": ("iphone.heic", image_bytes("HEIF"), "image/heic")},
        )

    assert response.status_code == 200
    normalized, media_type = provider.calls[0]
    assert media_type == "image/png"
    with Image.open(io.BytesIO(normalized)) as image:
        assert image.format == "PNG"


def test_expired_prepared_payload_uses_original_heic_fallback_when_available(tmp_path) -> None:
    provider = SuccessfulProvider()
    expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    with client_with_provider(tmp_path, provider) as client:
        prepared_response = client.post(
            "/api/v1/vision/preview",
            files={"image": ("iphone.heic", image_bytes("HEIF"), "image/heic")},
        )
        prepared = prepared_response.json()["data"]
        response = client.post(
            "/api/v1/vision/analyze",
            data={
                "prepared_image_id": prepared["image_id"],
                "prepared_image_data_url": prepared["preview"],
                "prepared_image_expires_at": expired,
            },
            files={"image": ("iphone.heic", image_bytes("HEIF"), "image/heic")},
        )

    assert prepared_response.status_code == 200
    assert response.status_code == 200
    assert provider.calls[0][1] == "image/png"


def test_expired_prepared_payload_without_fallback_returns_specific_error(tmp_path) -> None:
    provider = SuccessfulProvider()
    expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    with client_with_provider(tmp_path, provider) as client:
        prepared_response = client.post(
            "/api/v1/vision/preview",
            files={"image": ("question.png", image_bytes(), "image/png")},
        )
        prepared = prepared_response.json()["data"]
        response = client.post(
            "/api/v1/vision/analyze",
            data={
                "prepared_image_id": prepared["image_id"],
                "prepared_image_data_url": prepared["preview"],
                "prepared_image_expires_at": expired,
            },
        )

    assert prepared_response.status_code == 200
    assert response.status_code == 410
    assert response.json()["error"] == "prepared_image_expired"
    assert provider.calls == []


def test_prepared_and_direct_payload_ambiguity_is_resolved_by_prepared_first(tmp_path) -> None:
    provider = SuccessfulProvider()
    with client_with_provider(tmp_path, provider) as client:
        prepared_response = client.post(
            "/api/v1/vision/preview",
            files={"image": ("question.png", image_bytes(), "image/png")},
        )
        prepared = prepared_response.json()["data"]
        response = client.post(
            "/api/v1/vision/analyze",
            data={
                "prepared_image_id": prepared["image_id"],
                "prepared_image_data_url": prepared["preview"],
                "prepared_image_expires_at": prepared["expires_at"],
            },
            files={"image": ("renamed.png", image_bytes("JPEG"), "image/png")},
        )

    assert response.status_code == 200
    assert provider.calls[0][0] == base64.b64decode(prepared["preview"].split(",", 1)[1])


def test_preview_endpoint_applies_orientation_without_provider(tmp_path) -> None:
    provider = SuccessfulProvider()
    with client_with_provider(tmp_path, provider) as client:
        response = client.post(
            "/api/v1/vision/preview",
            files={"image": ("rotated.jpg", oriented_jpeg_bytes(), "image/jpeg")},
        )

    assert response.status_code == 200
    assert provider.calls == []
    preview = response.json()["data"]["preview"]
    with Image.open(io.BytesIO(base64.b64decode(preview.split(",", 1)[1]))) as image:
        assert image.size == (40, 20)


def test_preview_endpoint_rejects_invalid_image_without_blocking_later_analysis_path(tmp_path) -> None:
    provider = SuccessfulProvider()
    with client_with_provider(tmp_path, provider) as client:
        preview = client.post(
            "/api/v1/vision/preview",
            files={"image": ("broken.heic", b"not a heif image", "image/heic")},
        )
        analysis = client.post(
            "/api/v1/vision/analyze",
            files={"image": ("question.png", image_bytes(), "image/png")},
        )

    assert preview.status_code == 422
    assert preview.json()["error"] == "invalid_image"
    assert analysis.status_code == 200
    assert provider.calls


@pytest.mark.parametrize(("filename", "content_type"), [("broken.heic", "image/heic"), ("broken.heif", "image/heif")])
def test_rejects_corrupt_heic_and_heif_safely(tmp_path, filename, content_type) -> None:
    with client_with_provider(tmp_path, SuccessfulProvider()) as client:
        response = client.post(
            "/api/v1/vision/analyze",
            files={"image": (filename, b"not a heif image", content_type)},
        )

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_image"


def test_rejects_spoofed_supported_mime_and_content_mismatch(tmp_path) -> None:
    with client_with_provider(tmp_path, SuccessfulProvider()) as client:
        response = client.post(
            "/api/v1/vision/analyze",
            files={"image": ("renamed.png", image_bytes("JPEG"), "image/png")},
        )

    assert response.status_code == 415
    assert response.json()["error"] == "unsupported_image_type"


def test_applies_exif_orientation_before_provider_analysis(tmp_path) -> None:
    provider = SuccessfulProvider()
    with client_with_provider(tmp_path, provider) as client:
        response = client.post(
            "/api/v1/vision/analyze",
            files={"image": ("rotated.jpg", oriented_jpeg_bytes(), "image/jpeg")},
        )

    assert response.status_code == 200
    normalized, _ = provider.calls[0]
    with Image.open(io.BytesIO(normalized)) as image:
        assert ImageOps.exif_transpose(image).size == (40, 20)
    preview_url = response.json()["data"]["normalized_preview_url"]
    with Image.open(io.BytesIO(base64.b64decode(preview_url.split(",", 1)[1]))) as image:
        assert image.size == (40, 20)


def test_preview_generation_failure_does_not_block_analysis(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(VisionService, "_preview_data_url", staticmethod(lambda content, media_type: None))
    with client_with_provider(tmp_path, SuccessfulProvider()) as client:
        response = client.post("/api/v1/vision/analyze", files={"image": ("question.png", image_bytes(), "image/png")})

    assert response.status_code == 200
    assert response.json()["data"]["normalized_preview_url"] is None


def test_no_jpeg_normalized_internal_path_remains() -> None:
    source = (Path(__file__).parents[1] / "app" / "features" / "vision" / "service.py").read_text(encoding="utf-8")

    assert 'save(output, format="JPEG"' not in source
    assert 'data:image/jpeg;base64,' not in source
    assert 'media_type="image/jpeg"' not in source
    assert 'content_type="image/jpeg"' not in source


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [
        ("test.pdf", "application/pdf"),
        ("test.txt", "text/plain"),
        ("test.svg", "image/svg+xml"),
        ("renamed.jpg", "application/pdf"),
    ],
)
def test_rejects_unsupported_names_and_media_types(tmp_path, filename, content_type) -> None:
    with client_with_provider(tmp_path, SuccessfulProvider()) as client:
        response = client.post(
            "/api/v1/vision/analyze",
            files={"image": (filename, b"unsupported", content_type)},
        )
    assert response.status_code == 415
    assert response.json()["error"] == "unsupported_image_type"


@pytest.mark.parametrize("filename", ["test.jpg", "test.JPG", "test.jpeg", "test.JPEG", "test.png", "test.PNG", "test.webp", "test.WEBP", "test.heic", "test.HEIC", "test.heif", "test.HEIF"])
def test_supported_extension_is_used_when_browser_omits_media_type(tmp_path, filename) -> None:
    image_format = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP", "heic": "HEIF", "heif": "HEIF"}[filename.rsplit(".", 1)[1].lower()]
    with client_with_provider(tmp_path, SuccessfulProvider()) as client:
        response = client.post(
            "/api/v1/vision/analyze",
            files={"image": (filename, image_bytes(image_format), "application/octet-stream")},
        )
    assert response.status_code == 200


def test_requires_an_image(tmp_path) -> None:
    with client_with_provider(tmp_path, SuccessfulProvider()) as client:
        response = client.post("/api/v1/vision/analyze")
    assert response.status_code == 400
    assert response.json()["error"] == "image_required"


def test_rejects_oversized_file(tmp_path) -> None:
    with client_with_provider(tmp_path, SuccessfulProvider(), max_bytes=20) as client:
        response = client.post("/api/v1/vision/analyze", files={"image": ("question.png", image_bytes(), "image/png")})
    assert response.status_code == 413
    assert response.json()["error"] == "image_too_large"


def test_rejects_corrupt_image_content(tmp_path) -> None:
    with client_with_provider(tmp_path, SuccessfulProvider()) as client:
        response = client.post("/api/v1/vision/analyze", files={"image": ("question.png", b"not an image", "image/png")})
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_image"


@pytest.mark.parametrize(
    ("provider_error", "expected_status", "expected_code"),
    [
        (ProviderUnavailableError(), 503, "provider_unavailable"),
        (InvalidProviderResponseError(), 502, "invalid_provider_response"),
    ],
)
def test_returns_controlled_provider_errors(tmp_path, provider_error, expected_status, expected_code) -> None:
    with client_with_provider(tmp_path, FailingProvider(provider_error)) as client:
        response = client.post("/api/v1/vision/analyze", files={"image": ("question.png", image_bytes(), "image/png")})
    assert response.status_code == expected_status
    assert response.json()["error"] == expected_code
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_openai_provider_reports_missing_api_key() -> None:
    provider = OpenAIVisionProvider(api_key=None, model="test-model", timeout_seconds=1)
    with pytest.raises(ProviderConfigurationError):
        await provider.analyze_image(image_bytes(), "image/png")
