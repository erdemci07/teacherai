"""Hafif Pillow görüntü göstergeleri ve tahribatsız yardımcı görünümler (TA-003).

Göstergeler tavsiye niteliğindedir ve kalibre edilmemiştir. Tek başına bir soruyu okunamaz saymaz:
karanlık bir fotoğraf okunabilir, keskin bir fotoğrafta soru eksik olabilir. Karar her zaman
okuma kanıtıyla birlikte verilir.

Yardımcı görünümler her zaman normalleştirilmiş özgünden türetilir ve özgünün yerini almaz.
Keskinleştirme, eşikleme veya morfolojik işlem uygulanmaz; bunlar ince kök çizgisini, eksi
işaretini, ondalık virgülünü veya kesir çizgisini silebilir.
"""

from __future__ import annotations

import io

from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat

from ..education.source import SourceRegion

ANALYSIS_SIDE = 1024
SMALL_SIDE = 300
CROP_PADDING = 0.06
MIN_CROP_SIDE = 512


def _percentile(histogram: list[int], q: float) -> int:
    total = sum(histogram)
    accumulated = 0
    for value, count in enumerate(histogram):
        accumulated += count
        if accumulated >= q * total:
            return value
    return 255


def assess(image: Image.Image) -> list[str]:
    """Görüntüden tavsiye kategorileri çıkarır. Eşikler sezgiseldir; gerçek doğruluk ölçülmedi.

    Kontrast, belge fotoğraflarında küresel sapma yerine mürekkep (koyu uç %0,1) ile kâğıt (açık uç %99)
    arasındaki farkla ölçülür; böylece az yazılı beyaz sayfa düşük kontrastlı sayılmaz. Bulanıklık,
    ince ölçekteki (σ=1) ayrıntı enerjisinin kaba ölçeğe (σ=3) oranıyla tahmin edilir; hafif ama
    okunabilir bulanıklık işaretlenmez.
    """
    advisories: list[str] = []
    if min(image.size) < SMALL_SIDE:
        advisories.append("small_image")
    gray = image.convert("L")
    factor = -(-max(gray.size) // ANALYSIS_SIDE)
    if factor > 1:
        gray = gray.reduce(factor)  # tam sayılı kutu azaltma; yalnızca ölçüm içindir, gönderilen görüntüye dokunmaz
    histogram = gray.histogram()
    total = max(1, sum(histogram))
    ink, paper, median = _percentile(histogram, 0.001), _percentile(histogram, 0.99), _percentile(histogram, 0.5)
    if paper - ink < 50:
        advisories.append("low_contrast")
    if paper < 100:
        advisories.append("underexposed")
    elif ink > 200:
        advisories.append("overexposed")
    if sum(histogram[250:]) / total > 0.02 and median < 180:
        advisories.append("possible_glare")
    fine = ImageStat.Stat(ImageChops.difference(gray, gray.filter(ImageFilter.GaussianBlur(1)))).mean[0]
    coarse = ImageStat.Stat(ImageChops.difference(gray, gray.filter(ImageFilter.GaussianBlur(3)))).mean[0]
    if coarse > 0.2 and fine / coarse < 0.25:
        advisories.append("possible_blur")
    width, height = gray.size
    half_w, half_h = max(1, width // 2), max(1, height // 2)
    quadrants = [
        ImageStat.Stat(gray.crop(box)).mean[0]
        for box in ((0, 0, half_w, half_h), (half_w, 0, width, half_h), (0, half_h, half_w, height), (half_w, half_h, width, height))
        if box[2] > box[0] and box[3] > box[1]
    ]
    if quadrants and max(quadrants) - min(quadrants) > 60:
        advisories.append("uneven_lighting")
    if paper - ink >= 50 and _ink_touches_border(gray, (ink + paper) / 2):
        advisories.append("possible_clipping")
    return advisories


def _ink_touches_border(gray: Image.Image, threshold: float) -> bool:
    """Kenar şeritlerinde yazı benzeri koyu piksel varsa içerik kadraj dışına taşıyor olabilir."""
    width, height = gray.size
    strip = max(1, min(width, height) // 50)
    boxes = ((0, 0, width, strip), (0, height - strip, width, height), (0, 0, strip, height), (width - strip, 0, width, height))
    for box in boxes:
        histogram = gray.crop(box).histogram()
        count = sum(histogram)
        if count and sum(histogram[: int(threshold)]) / count > 0.02:
            return True
    return False


def region_crop(content: bytes, region: SourceRegion) -> bytes:
    """Bölgeyi çevresiyle birlikte kırpar; küçük kırpıntıyı okunabilirlik için orantılı büyütür.

    Matematiksel yapının anlamı bağlama dayandığından kenarlara pay bırakılır.
    """
    with Image.open(io.BytesIO(content)) as source:
        image = source.convert("RGB")
    width, height = image.size
    pad_x, pad_y = CROP_PADDING * width, CROP_PADDING * height
    box = (
        max(0, int(region.x0 * width - pad_x)),
        max(0, int(region.y0 * height - pad_y)),
        min(width, int(region.x1 * width + pad_x + 1)),
        min(height, int(region.y1 * height + pad_y + 1)),
    )
    crop = image.crop(box)
    short = min(crop.size)
    if 0 < short < MIN_CROP_SIDE:
        scale = min(4.0, MIN_CROP_SIDE / short)
        crop = crop.resize((max(1, round(crop.width * scale)), max(1, round(crop.height * scale))), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    crop.save(output, format="PNG")
    return output.getvalue()


def contrast_view(content: bytes) -> bytes:
    """Gri ton ve ölçülü otomatik kontrast (%1 kırpma). Yalnızca ek yorum yardımıdır."""
    with Image.open(io.BytesIO(content)) as source:
        view = ImageOps.autocontrast(source.convert("L"), cutoff=1)
    output = io.BytesIO()
    view.save(output, format="PNG")
    return output.getvalue()
