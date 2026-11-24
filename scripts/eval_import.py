"""Değerlendirme görsel paketinin (ZIP) güvenli denetimi ve içeri alınması (TA-007 §25).

    python -m scripts.eval_import inspect <paket.zip>     # çıkarmadan denetler, hiçbir şey yazmaz
    python -m scripts.eval_import import <paket.zip>      # denetim geçerse görselleri evals/local/images'a yazar

Denetimler: mutlak yol, ``..``, ters bölü, sembolik bağ, yinelenen ad, izinli yol listesi, giriş sayısı,
dosya ve toplam boyut, sıkıştırma oranı (zip bombası), PNG imzası ve IHDR boyutları, manifest ↔ içerik sha256
tutarlılığı, paketteki 24 soru kimliğiyle birebir eşleşme, varyantların özgün soruya bağlanması, soru
kayıtlarında cevap alanı bulunmaması (sızıntı). Görseller Git dışında kalır; depoya yalnız ad, sha256, soru
kimliği ve tür (``base``/``ocr_variant``) yazılır. Cevap anahtarı üretilmez ve türetilmez. Hiçbir sağlayıcı
çağrısı yapılmaz.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import struct
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from scripts import answer_key

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "evals/local/images"
VARIANTS = answer_key.VARIANTS
MAX_ENTRIES = 64
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 96 * 1024 * 1024
MAX_RATIO = 60
MAX_SIDE = 6000
PNG = b"\x89PNG\r\n\x1a\n"
ALLOWED = re.compile(r"^(?:images/[A-Za-z0-9_-]{1,80}\.png|sorular\.jsonl|manifest\.json|README\.md)$")
IMAGE_NAME = re.compile(r"^(?P<id>[MPCB][0-9]{2})(?:_(?P<variant>[a-z0-9_]{1,60}))?$")
# Soru kaydında bulunmaması gereken (cevap sızdıran) alanlar.
LEAK_KEYS = {"answer", "answers", "expected", "expected_choice", "expected_value", "correct", "correct_choice",
             "solution", "solutions", "key", "answer_key", "dogru_cevap", "cevap", "cozum", "çözüm"}


@dataclass
class Report:
    problems: list[str] = field(default_factory=list)
    base: dict[str, str] = field(default_factory=dict)        # soru kimliği → sha256
    variants: dict[str, list[dict]] = field(default_factory=dict)
    questions: int = 0
    total_bytes: int = 0

    @property
    def ok(self) -> bool:
        return not self.problems


def png_problem(data: bytes) -> str | None:
    if not data.startswith(PNG) or len(data) < 33 or data[12:16] != b"IHDR":
        return "PNG imzası/IHDR yok"
    width, height = struct.unpack(">II", data[16:24])
    if not (0 < width <= MAX_SIDE and 0 < height <= MAX_SIDE):
        return f"görsel boyutu sınır dışı ({width}x{height})"
    if b"IEND" not in data[-16:]:
        return "PNG sonu (IEND) yok"
    return None


def _unsafe(info: zipfile.ZipInfo) -> str | None:
    name = info.filename
    if "\\" in name or name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        return "mutlak veya Windows yolu"
    if any(part in {"..", ""} for part in PurePosixPath(name).parts) or "/./" in f"/{name}":
        return "yol aşımı"
    if stat.S_ISLNK(info.external_attr >> 16):
        return "sembolik bağ"
    if info.flag_bits & 0x1:
        return "şifreli giriş"
    return None


def inspect(path: Path, expected_ids: list[str] | None = None) -> tuple[Report, dict[str, bytes]]:
    report, images = Report(), {}
    expected_ids = expected_ids or answer_key.pack_ids()
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        report.problems.append(f"ZIP açılamadı: {exc}")
        return report, images
    with archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        if len(infos) > MAX_ENTRIES:
            report.problems.append(f"Çok fazla giriş: {len(infos)} > {MAX_ENTRIES}")
            return report, images
        names = [info.filename for info in infos]
        if len({name.lower() for name in names}) != len(names):
            report.problems.append("Yinelenen dosya adı (büyük/küçük harf duyarsız)")
        for info in infos:
            reason = _unsafe(info) or (None if ALLOWED.match(info.filename) else "izinli yol listesinde değil")
            if reason:
                report.problems.append(f"{info.filename}: {reason}")
                continue
            if info.file_size > MAX_FILE_BYTES:
                report.problems.append(f"{info.filename}: dosya çok büyük ({info.file_size})")
                continue
            if info.compress_size and info.file_size / info.compress_size > MAX_RATIO:
                report.problems.append(f"{info.filename}: şüpheli sıkıştırma oranı")
                continue
            report.total_bytes += info.file_size
            if report.total_bytes > MAX_TOTAL_BYTES:
                report.problems.append("Toplam boyut sınırı aşıldı")
                return report, images
        if report.problems:
            return report, images
        files = {name: archive.read(name) for name in names}  # sınırlar yukarıda denetlendi
    for name, data in files.items():
        if name.startswith("images/"):
            problem = png_problem(data)
            if problem:
                report.problems.append(f"{name}: {problem}")
            else:
                images[name] = data
    _check_manifest(files, images, report, expected_ids)
    _check_questions(files, report, expected_ids)
    return report, images


def _check_manifest(files, images, report, expected_ids):
    if "manifest.json" not in files:
        report.problems.append("manifest.json yok")
        return
    try:
        rows = json.loads(files["manifest.json"].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        report.problems.append(f"manifest.json okunamadı: {exc}")
        return
    listed = set()
    for row in rows if isinstance(rows, list) else []:
        name, digest, kind = row.get("file"), row.get("sha256"), row.get("kind")
        listed.add(name)
        if name not in images:
            report.problems.append(f"Manifestteki dosya pakette yok veya geçersiz: {name}")
            continue
        actual = hashlib.sha256(images[name]).hexdigest()
        if actual != digest:
            report.problems.append(f"sha256 uyuşmuyor: {name}")
        match = IMAGE_NAME.match(PurePosixPath(name).stem)
        if match is None:
            report.problems.append(f"Görsel adı soru kimliği taşımıyor: {name}")
            continue
        qid, variant = match.group("id"), match.group("variant")
        if (kind == "base") != (variant is None) or kind not in {"base", "ocr_variant"}:
            report.problems.append(f"Tür ile ad uyuşmuyor: {name} ({kind})")
            continue
        if kind == "base":
            if qid in report.base:
                report.problems.append(f"Aynı soru için iki özgün görsel: {qid}")
            report.base[qid] = actual
        else:
            report.variants.setdefault(qid, []).append({"file": PurePosixPath(name).name, "sha256": actual,
                                                        "variant": variant})
    for name in sorted(set(images) - listed):
        report.problems.append(f"Manifestte olmayan görsel: {name}")
    missing = sorted(set(expected_ids) - set(report.base))
    unknown = sorted(set(report.base) - set(expected_ids))
    if missing:
        report.problems.append(f"Özgün görseli olmayan soru: {', '.join(missing)}")
    if unknown:
        report.problems.append(f"Pakette olmayan soru kimliği: {', '.join(unknown)}")
    orphans = sorted(set(report.variants) - set(report.base))
    if orphans:
        report.problems.append(f"Özgün görseli olmayan varyant: {', '.join(orphans)}")


def _check_questions(files, report, expected_ids):
    raw = files.get("sorular.jsonl")
    if raw is None:
        return
    ids = []
    for number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            report.problems.append(f"sorular.jsonl satır {number}: geçersiz JSON")
            continue
        leaked = sorted(key for key in row if key.casefold() in LEAK_KEYS)
        if leaked:
            report.problems.append(f"sorular.jsonl {row.get('id')}: cevap alanı içeriyor ({', '.join(leaked)})")
        ids.append(row.get("id"))
    report.questions = len(ids)
    if sorted(ids) != sorted(expected_ids):
        report.problems.append("sorular.jsonl kimlikleri paketteki 24 soruyla birebir eşleşmiyor")


def write(report: Report, images: dict[str, bytes], target: Path = IMAGES) -> None:
    """Yalnız denetimi geçmiş paketi yazar. Ad yeniden kurulur; arşivdeki yol kullanılmaz."""
    if not report.ok:
        raise ValueError("Denetimi geçmeyen paket yazılmaz.")
    target.mkdir(parents=True, exist_ok=True)
    for name, data in images.items():
        stem = PurePosixPath(name).stem
        if not IMAGE_NAME.match(stem):
            raise ValueError(f"Geçersiz ad: {name}")
        destination = (target / f"{stem}.png").resolve()
        if destination.parent != target.resolve():
            raise ValueError(f"Hedef dışı yol: {name}")
        destination.write_bytes(data)


def manifests(report: Report) -> tuple[dict, dict]:
    images = [{"file": f"{qid}.png", "sha256": digest, "question_id": qid} for qid, digest in sorted(report.base.items())]
    images += [{"file": item["file"], "sha256": item["sha256"], "question_id": qid, "kind": "ocr_variant"}
               for qid, items in sorted(report.variants.items()) for item in sorted(items, key=lambda x: x["file"])]
    for row in images:
        answer_key.ImageEntry.model_validate(row)
    variants = {"schema_name": "teacherai.ocr_variants", "version": "1.0.0",
                "note": "Varyant ayrı örnek değildir; özgün soruya bağlıdır ve aynı öğretmen anahtarıyla puanlanır. "
                        "Görseller Git dışında (evals/local/images).",
                "variants": [{"question_id": qid, **item} for qid, items in sorted(report.variants.items())
                             for item in sorted(items, key=lambda x: x["file"])]}
    return {"images_dir": "evals/local/images", "images": images}, variants


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=["inspect", "import"])
    parser.add_argument("zip", type=Path)
    args = parser.parse_args(argv)
    report, images = inspect(args.zip)
    print(f"Özgün: {len(report.base)}  varyant: {sum(len(v) for v in report.variants.values())}  "
          f"soru kaydı: {report.questions}  toplam bayt: {report.total_bytes}")
    for problem in report.problems:
        print(f"SORUN: {problem}")
    if not report.ok:
        return 1
    if args.mode == "inspect":
        print("Denetim geçti; hiçbir şey yazılmadı.")
        return 0
    write(report, images)
    main_manifest, variants = manifests(report)
    answer_key.MANIFEST.write_text(json.dumps(main_manifest, indent=2) + "\n", encoding="utf-8")
    VARIANTS.write_text(json.dumps(variants, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(images)} görsel {IMAGES.relative_to(ROOT)} altına yazıldı (Git dışı); manifestler güncellendi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
