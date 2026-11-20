"""TA-003 görüntü hazırlama ve hedefli yeniden okuma testleri.

Görüntüler Pillow ile belirlenimci üretilir. Bu testler ön işlemenin davranışını sınar; sahte Vision
yanıtları gerçek modelin bu görüntüleri tanıyabileceğini kanıtlamaz.
"""

import base64
import io
from dataclasses import replace
from types import SimpleNamespace

import pytest
from apps.api.app.features.education.source import SourceRegion
from apps.api.app.features.integrity.image_quality import (
    assess,
    contrast_view,
    region_crop,
)
from apps.api.app.features.vision.openai_provider import OpenAIVisionProvider
from apps.api.app.features.vision.schemas import RecheckResponse
from apps.api.app.features.vision.service import MAX_VISION_SIDE, VisionService
from apps.api.app.features.vision.storage import LocalTemporaryImageStorage
from apps.api.app.main import create_app
from apps.api.tests.client import authenticated_client
from apps.api.tests.test_question_integrity import SIGN, wire
from PIL import Image, ImageDraw, ImageFilter
from PIL.PngImagePlugin import PngInfo


def page(size=(1200, 800), background="white", ink="black", mode="RGB"):
    image = Image.new(mode, size, background)
    draw = ImageDraw.Draw(image)
    for row in range(60, size[1] - 60, 50):
        for column in range(60, max(61, size[0] - 400), 420):
            draw.text((column, row), "3x + 7 = 19  A) 2", fill=ink, font_size=14)
    return image


def encoded(image, image_format="PNG", **kwargs) -> bytes:
    output = io.BytesIO()
    image.save(output, format=image_format, **kwargs)
    return output.getvalue()


def prepare(data: bytes, content_type="image/png"):
    return VisionService._prepare_bytes(data, content_type, "q." + content_type.split("/")[1])


def test_clean_png_without_metadata_is_passed_through_unchanged():
    data = encoded(page())
    prepared = prepare(data)
    assert prepared.content == data and "metadata_removed" not in prepared.advisories


def test_transparency_is_flattened_onto_white_without_losing_ink():
    image = Image.new("RGBA", (600, 300), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((100, 140, 500, 142), fill=(0, 0, 0, 255))  # ince eksi / kesir çizgisi
    prepared = prepare(encoded(image))
    with Image.open(io.BytesIO(prepared.content)) as result:
        assert result.mode == "RGB"
        assert result.getpixel((10, 10)) == (255, 255, 255)
        assert result.getpixel((300, 141)) == (0, 0, 0)
    assert "transparency_flattened" in prepared.advisories


def test_oversized_image_is_downscaled_proportionally_and_thin_marks_survive():
    image = Image.new("RGB", (4000, 3000), "white")
    ImageDraw.Draw(image).line((1000, 2500, 3000, 2500), fill="black", width=2)  # 2 px eksi işareti
    prepared = prepare(encoded(image, "JPEG", quality=92), "image/jpeg")
    assert max(prepared.width, prepared.height) == MAX_VISION_SIDE
    assert abs(prepared.width / prepared.height - 4 / 3) < 0.01
    with Image.open(io.BytesIO(prepared.content)) as result:
        row = round(2500 * prepared.height / 3000)
        darkest = min(result.convert("L").getpixel((x, y)) for x in range(900, 1100) for y in range(row - 2, row + 3))
    assert darkest < 120 and "downscaled" in prepared.advisories


def test_metadata_is_removed_from_png_and_webp():
    info = PngInfo()
    info.add_text("Author", "öğrenci adı")
    prepared = prepare(encoded(page(), pnginfo=info))
    with Image.open(io.BytesIO(prepared.content)) as result:
        assert not getattr(result, "text", {})
    assert "metadata_removed" in prepared.advisories
    exif = Image.Exif()
    exif[315] = "kişisel"
    webp = prepare(encoded(page(), "WEBP", exif=exif.tobytes(), lossless=True), "image/webp")
    with Image.open(io.BytesIO(webp.content)) as result:
        assert not result.info.get("exif")
    assert webp.media_type == "image/webp"


def test_exif_orientation_is_corrected_and_reported():
    image = page(size=(400, 800))
    exif = image.getexif()
    exif[274] = 6
    prepared = prepare(encoded(image, "JPEG", exif=exif.tobytes()), "image/jpeg")
    assert (prepared.width, prepared.height) == (800, 400) and "orientation_corrected" in prepared.advisories


@pytest.mark.parametrize(("image", "present", "absent"), [
    (page(), set(), {"low_contrast", "overexposed", "underexposed", "possible_blur"}),
    (page().filter(ImageFilter.GaussianBlur(0.8)), set(), {"possible_blur"}),
    (page().filter(ImageFilter.GaussianBlur(3)), {"possible_blur"}, set()),
    (page(background=(130, 130, 130), ink=(110, 110, 110)), {"low_contrast"}, set()),
    (page(background=(40, 40, 40), ink=(10, 10, 10)), {"underexposed"}, set()),
    (page(background=(90, 90, 90), ink=(5, 5, 5)), {"underexposed"}, {"low_contrast"}),
    (page(size=(240, 180)), {"small_image"}, set()),
])
def test_quality_advisories(image, present, absent):
    found = set(assess(image))
    assert present <= found and not (absent & found)


def test_clipping_advisory_when_ink_touches_the_border():
    image = page()
    ImageDraw.Draw(image).rectangle((0, 300, 1199, 330), fill="black")
    assert "possible_clipping" in assess(image) and "possible_clipping" not in assess(page())


def test_region_crop_keeps_context_and_derived_views_do_not_replace_the_original():
    original = encoded(page())
    crop = region_crop(original, SourceRegion(kind="expression", x0=0.1, y0=0.1, x1=0.3, y1=0.2))
    with Image.open(io.BytesIO(crop)) as result:
        assert min(result.size) >= 512
        assert result.width / result.height == pytest.approx((0.2 + 0.12) * 1200 / ((0.1 + 0.12) * 800), rel=0.05)
    view = contrast_view(crop)
    with Image.open(io.BytesIO(view)) as result:
        assert result.mode == "L"
    assert original == encoded(page())


@pytest.mark.parametrize("coordinates", [(0.5, 0.1, 0.2, 0.3), (0.1, 0.1, 0.11, 0.11), (-0.1, 0, 0.5, 0.5), (0, 0, 1.5, 0.5), (float("nan"), 0, 1, 1)])
def test_invalid_regions_are_rejected(coordinates):
    x0, y0, x1, y1 = coordinates
    with pytest.raises(ValueError):
        SourceRegion(kind="question", x0=x0, y0=y0, x1=x1, y1=y1)


def _scripted_provider(responses, calls):
    def body(model):
        return {"id": "r", "model": "gpt-4.1-mini", "status": "completed",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": model.model_dump_json()}]}],
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}

    async def parse(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(http_response=SimpleNamespace(json=lambda: body(responses[len(calls) - 1])), request_id="req")

    async def close():
        return None

    return OpenAIVisionProvider("test-key", "gpt-4.1-mini", 5, client_factory=lambda **_: SimpleNamespace(
        responses=SimpleNamespace(with_raw_response=SimpleNamespace(parse=parse)), close=close))


def test_analyze_route_rechecks_once_through_gateway_quota_and_saves_the_revision(tmp_path):
    app = create_app()
    calls: list = []
    responses = [wire(**SIGN), RecheckResponse(readings=[{"item": 1, "legible": True, "reading": "+ 7"}])]
    service = VisionService(_scripted_provider(responses, calls), LocalTemporaryImageStorage(tmp_path), 10 * 1024 * 1024, False, recheck_limit=1)
    app.state.container = replace(app.state.container, vision_service=service)
    with authenticated_client(app) as client:
        response = client.post("/api/v1/vision/analyze", files={"image": ("q.png", encoded(page()), "image/png")})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["integrity"]["decision"] == "ready_with_noncritical_uncertainty"
    assert data["integrity"]["rechecks_used"] == 1 and data["revision"] == 1
    assert len(calls) == 2
    recheck_text = calls[1]["input"][0]["content"][0]["text"]
    assert "mathematical expression number 1" in recheck_text and "Do not solve" in recheck_text
    tracker = app.state.container.usage_tracker
    assert next(iter(tracker.globals.values()))["provider_calls"] == 2
    saved = app.state.container.student_service.repository.analyses[data["request_id"]][1]
    assert saved.integrity.rechecks_used == 1 and saved.normalized_preview_url is None
    assert not any(tmp_path.iterdir())  # geçici görsel istekten sonra silinir


def test_recheck_can_be_disabled_by_the_operator(tmp_path):
    app = create_app()
    calls: list = []
    service = VisionService(_scripted_provider([wire(**SIGN)], calls), LocalTemporaryImageStorage(tmp_path), 10 * 1024 * 1024, False, recheck_limit=0)
    app.state.container = replace(app.state.container, vision_service=service)
    with authenticated_client(app) as client:
        data = client.post("/api/v1/vision/analyze", files={"image": ("q.png", encoded(page()), "image/png")}).json()["data"]
    assert len(calls) == 1 and data["integrity"]["decision"] == "clarification_required"
    assert base64.b64decode(data["normalized_preview_url"].split(",", 1)[1])
