"""10 öğelik sentetik smoke setini deterministik olarak üretir (TA-001B, D paketi).

    python -m scripts.generate_smoke_set            # evals/datasets/smoke/ ve smoke.jsonl yazar

Görseller Pillow ile, rastgelelik olmadan çizilir. Set açıkça "synthetic" etiketlidir ve
gerçek model kalitesini ölçmez; yalnız değerlendirme hattının çalıştığını sınar.
Pillow'un varsayılan yazı tipinde bulunmayabilecek kök işareti ve kesir çizgisi elle çizilir.
Varsayılan yazı tipi Türkçe karakter içermediğinden görsel içi metin yalnız ASCII'dir;
işletim sistemine bağlı yazı tipi kullanılmaz, böylece üretim her ortamda aynı kalır.
"""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evals" / "datasets" / "smoke.jsonl"
SIZE = (720, 200)
META = {
    "source": "synthetic",
    "license": "CC0-1.0 (proje içinde üretilen sentetik görsel)",
    "author": "TeacherAI geliştirme ekibi (sentetik üretim betiği)",
    "created_at": "2026-11-20",
}


def font(size):
    return ImageFont.load_default(size=size)


def canvas():
    image = Image.new("RGB", SIZE, "white")
    return image, ImageDraw.Draw(image)


def text_image(parts, *, footer="x = ?"):
    """parts: (metin, üst_simge_mi) dizisi."""
    image, draw = canvas()
    x = 40
    for value, superscript in parts:
        size, y = (26, 52) if superscript else (44, 70)
        draw.text((x, y), value, fill="black", font=font(size))
        x += draw.textlength(value, font=font(size)) + (2 if superscript else 4)
    draw.text((40, 140), footer, fill="black", font=font(28))
    return image


def radical_image():
    image, draw = canvas()
    body = "x + 5"
    width = draw.textlength(body, font=font(44))
    draw.line([(40, 100), (52, 92), (66, 130), (84, 60), (100 + width, 60)], fill="black", width=3)
    draw.text((96, 68), body, fill="black", font=font(44))
    draw.text((110 + width, 68), "= 3", fill="black", font=font(44))
    draw.text((40, 150), "x = ?", fill="black", font=font(28))
    return image


def fraction_image():
    image, draw = canvas()
    draw.text((52, 30), "x", fill="black", font=font(40))
    draw.line([(40, 82), (90, 82)], fill="black", width=3)
    draw.text((52, 88), "4", fill="black", font=font(40))
    draw.text((104, 58), "+ 1 = 3", fill="black", font=font(44))
    draw.text((40, 150), "x = ?", fill="black", font=font(28))
    return image


def non_math_image():
    image, draw = canvas()
    draw.text((40, 70), "HAVA DURUMU: 24 C", fill="black", font=font(40))
    draw.ellipse([(600, 40), (680, 120)], outline="orange", width=6)
    draw.polygon([(470, 170), (530, 110), (590, 170)], outline="brown", width=4)
    return image


def item(item_id, topic, question, expressions, solutions, image, *, valid=True, variant=None):
    forbidden = [value for value in solutions] + [f"x = {value}" for value in solutions]
    return {
        "id": item_id, **META, "image": f"smoke/{item_id}.png", "is_valid_math_question": valid,
        "question_text": question, "topic": topic, "variable": "x",
        "expected_expressions": expressions, "expected_solutions": solutions,
        "forbidden_in_hint": forbidden if valid else [], "variant": variant,
    }, image


def build():
    blurred = text_image([("2x - 4 = 10", False)]).filter(ImageFilter.GaussianBlur(1.2))
    rotated = text_image([("5x + 2 = 17", False)]).rotate(7, resample=Image.Resampling.BICUBIC, expand=False, fillcolor="white")
    return [
        item("linear-single", "Birinci dereceden denklem", "3x + 7 = 19 ise x kaçtır?", ["3x + 7 = 19"], ["4"], text_image([("3x + 7 = 19", False)])),
        item("absolute-two-roots", "Mutlak değer", "|x - 1| = 2 denkleminin çözüm kümesi nedir?", ["|x - 1| = 2"], ["-1", "3"], text_image([("|x - 1| = 2", False)], footer="x = ?")),
        item("quadratic-two-roots", "İkinci dereceden denklem", "x^2 - 5x + 6 = 0 denkleminin kökleri nelerdir?", ["x^2 - 5x + 6 = 0"], ["2", "3"], text_image([("x", False), ("2", True), ("- 5x + 6 = 0", False)], footer="x = ?")),
        item("plus-minus", "İkinci dereceden denklem", "x^2 = 9 ise x kaçtır?", ["x^2 = 9"], ["-3", "3"], text_image([("x", False), ("2", True), ("= 9", False)], footer="x = ?")),
        item("fraction", "Kesirli denklem", "x/4 + 1 = 3 ise x kaçtır?", ["x/4 + 1 = 3"], ["8"], fraction_image()),
        item("radical", "Köklü ifade", "√(x + 5) = 3 ise x kaçtır?", ["sqrt(x + 5) = 3"], ["4"], radical_image()),
        item("double-root", "İkinci dereceden denklem", "x^2 - 6x + 9 = 0 denkleminin kökü nedir?", ["x^2 - 6x + 9 = 0"], ["3"], text_image([("x", False), ("2", True), ("- 6x + 9 = 0", False)])),
        item("not-math", "Matematik dışı", "Matematik sorusu içermeyen görsel", [], [], non_math_image(), valid=False),
        item("blurred-linear", "Birinci dereceden denklem", "2x - 4 = 10 ise x kaçtır?", ["2x - 4 = 10"], ["7"], blurred, variant="blur"),
        item("rotated-linear", "Birinci dereceden denklem", "5x + 2 = 17 ise x kaçtır?", ["5x + 2 = 17"], ["3"], rotated, variant="rotate"),
    ]


def write(dataset=DATASET):
    dataset.parent.mkdir(parents=True, exist_ok=True)
    (dataset.parent / "smoke").mkdir(exist_ok=True)
    rows = []
    for record, image in build():
        # optimize=False ve sabit parametreler aynı Pillow sürümünde aynı baytları üretir.
        image.save(dataset.parent / record["image"], format="PNG", optimize=False)
        rows.append(json.dumps(record, ensure_ascii=False))
    dataset.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return len(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DATASET)
    args = parser.parse_args(argv)
    print(f"{write(args.output)} sentetik smoke öğesi yazıldı: {args.output}")


if __name__ == "__main__":
    main()
