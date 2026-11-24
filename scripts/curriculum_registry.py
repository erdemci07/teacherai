"""Müfredat Kaydı v2 doğrulaması ve kapsam raporu (TA-006). Ağ ve sağlayıcı çağrısı yoktur.

    python -m scripts.curriculum_registry          # kaydı doğrular, docs/curriculum/TA-006-coverage.md yazar
    python -m scripts.curriculum_registry --check  # doğrular; rapor güncel değilse başarısız olur
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from apps.api.app.features.curriculum import registry as legacy
from apps.api.app.features.curriculum import registry_v2

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/curriculum/TA-006-coverage.md"
SUBJECT_TR = {"mathematics": "Matematik", "science": "Fen Bilimleri", "physics": "Fizik", "chemistry": "Kimya",
              "biology": "Biyoloji"}
FRAMEWORK_TR = {"meb_2018": "MEB 2018", "tymm": "Maarif Modeli (2026)"}


def _cell(value) -> str:
    return "bilinmiyor" if value is None else str(value)


def render(registry: registry_v2.CurriculumRegistryV2) -> str:
    rows = registry_v2.coverage(registry)
    total = sum(row["actual"] for row in rows)
    disciplines = Counter(item.discipline.value for item in registry.outcomes.values())
    lines = [
        "# TA-006 müfredat kapsam raporu",
        "",
        "Bu dosya `python -m scripts.curriculum_registry` ile üretilir; elle düzenlenmez. CI `--check` ile eskimiş raporu reddeder.",
        "",
        f"- Kayıt sürümü: `{registry.version}`",
        f"- Program sürümü: {len(registry.programs)} · başlık (ünite/tema/konu): {len(registry.units)} · kazanım/öğrenme çıktısı: {total}",
        "- Disiplin dağılımı: " + ", ".join(f"{key} {value}" for key, value in sorted(disciplines.items())),
        f"- Yöntem politikası: {len(registry.policies)} (hepsi `{', '.join(sorted({p.status for p in registry.policies}))}`; v1'den göç)",
        "",
        "Sütunlar: **beklenen** resmî sayı tablosundan okunabildiyse yazılır, okunamadıysa `bilinmiyor` kalır. **eksik** yalnız beklenen",
        "sayı biliniyorsa hesaplanır. **resmî metin** TA-005'ten korunan birebir kazanım metnidir (hak incelemesi bekliyor).",
        "**betimleme** özgün, incelenmemiş kısa açıklamadır. **incelenen** bağımsız insan incelemesinden geçmiş kayıt sayısıdır.",
        "**uygulama** doğrulanmış resmî kaynağa göre o sınıfta programın okutulduğu öğretim yıllarıdır.",
        "",
        "| Alan | Çerçeve | Program | Sınıf | Beklenen | Kayıtlı | Eksik | Resmî metin | Betimleme | İncelenen | Kaynak | Uygulama |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(" | ".join([
            f"| {SUBJECT_TR[row['subject']]}", FRAMEWORK_TR[row["framework"]], f"`{row['program_id']}`", str(row["grade"]),
            _cell(row["expected"]), str(row["actual"]), _cell(row["missing"]), str(row["with_official_text"]),
            str(row["with_description"]), str(row["reviewed"]), "erişildi (sha256)" if row["source"] == "accessed" else "eksik",
            ", ".join(row["applies"]) or "doğrulanmadı",
        ]) + " |")
    lines += ["", "## Uygulama takvimi (doğrulanmış kaynaklar)", "",
              "| Öğretim yılı | Kademe | Sınıflar | Çerçeve | Program belgesi | Kanıt |", "| --- | --- | --- | --- | --- | --- |"]
    for rule in registry.catalog.application:
        lines.append(f"| {rule.academic_year} | {rule.stage} | {', '.join(map(str, rule.grades))} | {FRAMEWORK_TR[rule.framework]} | "
                     f"{', '.join(f'`{ref}`' for ref in rule.program_ids) or 'kayıtta yok'} | "
                     f"{'açık' if rule.evidence == 'explicit' else 'dışlama yoluyla'} — [{rule.citation.title}]({rule.citation.url}) |")
    lines += ["", "## Sınav kapsamı", "", "Sınav kapsamı okul programından ayrı sürümlenir. Doğrulanmamış kapsam hiçbir kazanımı sınava bağlamaz.", "",
              "| Kimlik | Sınav | Yıl | Durum | Sınıf | Not |", "| --- | --- | --- | --- | --- | --- |"]
    for scope in registry.catalog.exam_scopes:
        lines.append(f"| `{scope.id}` | {scope.exam} | {scope.exam_year} | {'doğrulandı' if scope.status == 'verified' else 'doğrulanmadı'} | "
                     f"{', '.join(map(str, scope.grades)) or '—'} | {scope.note} |")
    lines += ["", "## Durum ayrımı", "",
              "| Düzey | Sayı |", "| --- | --- |",
              "| Şemada temsil edilebilir | 5–12. sınıf, 5 alan, iki çerçeve, sınırsız sürüm |",
              f"| Kayıtlı (kod, başlık, sayfa) | {total} |",
              f"| Kaynağa dayalı (resmî belge + sayfa) | {sum(1 for item in registry.outcomes.values() if item.source_status == 'sourced')} |",
              f"| Bağımsız incelenmiş | {sum(1 for item in registry.outcomes.values() if item.review_status == 'source_verified')} |",
              f"| Özgün betimlemeli (incelenmemiş) | {sum(1 for item in registry.outcomes.values() if item.description_tr)} |",
              "| Ders bağlamına girebilir (resmî kod/başlık, çözümlenmiş program, eşleşen konu) | matematik: 2026-2027'de 5-12. sınıflar |",
              "| Gerçek öğrenci veya sağlayıcıyla doğrulanmış | 0 |", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    registry = registry_v2.load()
    v1 = legacy.default_registry()
    migrated = [registry.outcomes[registry_v2.legacy_global_id(item.outcome_id)] for item in v1.outcomes]
    if any(item.official_text_tr != source.outcome_text_tr for item, source in zip(migrated, v1.outcomes)):
        raise SystemExit("v1 kazanım metni göçte değişti")
    contents = render(registry)
    if args.check:
        if not REPORT.exists() or REPORT.read_text(encoding="utf-8") != contents:
            raise SystemExit(f"Güncel olmayan rapor: {REPORT.relative_to(ROOT)} (python -m scripts.curriculum_registry)")
        print(f"Müfredat kaydı geçerli: {registry.version}, {len(registry.outcomes)} kayıt, v1 göçü {len(migrated)}/29")
        return
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(contents, encoding="utf-8", newline="\n")
    print(f"Yazıldı: {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
