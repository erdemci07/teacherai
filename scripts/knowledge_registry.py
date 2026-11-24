"""Bilimsel kaynak/bilgi kaydı doğrulaması, kapsam raporu ve çevrimdışı taslak önizleme (TA-006).

    python -m scripts.knowledge_registry                 # doğrular, docs/knowledge/TA-006-knowledge-coverage.md yazar
    python -m scripts.knowledge_registry --check         # doğrular; rapor güncel değilse başarısız olur
    python -m scripts.knowledge_registry preview <kimlik> # taslak girdiyi engelleri ve denetleyici kapsamıyla gösterir

Ağ, sağlayıcı ve Firestore çağrısı yoktur. Önizleme çıktısı öğrenciye veya modele gitmez.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from apps.api.app.features.knowledge import registry as knowledge
from apps.api.app.features.knowledge.capabilities import CAPABILITIES, capability_check

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/knowledge/TA-006-knowledge-coverage.md"
SUBJECT_TR = {"mathematics": "Matematik (geometri dahil)", "physics": "Fizik", "chemistry": "Kimya", "biology": "Biyoloji",
              "science": "Ortaokul fen (bütünleşik)"}
PERM_TR = {"allowed": "evet", "not_allowed": "hayır", "conditional": "koşullu", "unknown": "bilinmiyor"}


def render(registry: knowledge.KnowledgeRegistry) -> str:
    rows = knowledge.coverage(registry)
    lines = ["# TA-006 bilimsel bilgi kapsam raporu", "",
             "Bu dosya `python -m scripts.knowledge_registry` ile üretilir; elle düzenlenmez.", "",
             f"- Kayıt sürümü: `{registry.version}`",
             f"- Kaynak: {len(registry.sources)} · bilgi girdisi: {len(registry.entries)} · tanımlı denetleyici: {len(CAPABILITIES)}", "",
             "Bütün girdiler `claude-draft` taslağıdır. Hiçbiri öğretmen veya alan uzmanınca incelenmedi; bu yüzden çalışma",
             "zamanına uygun girdi sayısı 0'dır. Denetleyici bağlantısı iddianın yalnız belirtilen parçasını kapsar.", "",
             "| Alan | Girdi | Kaynaklı | Kaynaksız | Kazanıma bağlı | Denetleyicili | İncelenen | Çalışma zamanına uygun | Tür dağılımı |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for row in rows:
        kinds = ", ".join(f"{key} {value}" for key, value in row["kinds"].items())
        lines.append(f"| {SUBJECT_TR[row['subject']]} | {row['total']} | {row['sourced']} | {len(row['unsourced'])} | {row['with_outcome']} | "
                     f"{row['with_verifier']} | {row['reviewed']} | {row['runtime_eligible']} | {kinds} |")
    unsourced = [entry for row in rows for entry in row["unsourced"]]
    lines += ["", f"Kaynaksız girdiler (çalışma zamanına kapalı): {', '.join(f'`{item}`' for item in unsourced) or 'yok'}", "",
              "## Kaynaklar ve izinler", "",
              "Dört izin ayrıdır: akademik başvuru, içeri alma/dönüştürme, öğrenciye yeniden dağıtım, model eğitimi.", "",
              "| Kaynak | Tür | Erişim | Lisans | Lisans doğrulandı | Başvuru | İçeri alma | Dağıtım | Eğitim | Kullanan girdi |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    used = Counter(locator.source_id for entry in registry.entries.values() for locator in entry.provenance)
    for source in sorted(registry.sources.values(), key=lambda item: item.id):
        perms = source.permissions
        lines.append(f"| `{source.id}` | {source.kind} | {source.access} | {source.license or '—'} | {'evet' if source.license_verified else 'hayır'} | "
                     f"{PERM_TR[perms.academic_reference]} | {PERM_TR[perms.ingestion]} | {PERM_TR[perms.redistribution]} | "
                     f"{PERM_TR[perms.model_training]} | {used.get(source.id, 0)} |")
    lines += ["", "## Denetleyici kapsamı", "", "| Denetleyici | Kanıtlar | Kanıtlamaz | Bağlı girdi |", "| --- | --- | --- | --- |"]
    links = Counter(link.verifier for entry in registry.entries.values() for link in entry.verifiers)
    for name, capability in sorted(CAPABILITIES.items()):
        lines.append(f"| `{name}` | {capability.proves_tr} | {capability.does_not_prove_tr} | {links.get(name, 0)} |")
    states = Counter(capability_check(entry).claim_state for entry in registry.entries.values())
    summary = (f"Girdi düzeyinde iddia durumu: `partially_checked` {states.get('partially_checked', 0)}, "
               f"`not_checked` {states.get('not_checked', 0)}, `passed` 0 (yapı gereği).")
    lines += ["", summary, ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", nargs="?", choices=["report", "preview"], default="report")
    parser.add_argument("entry", nargs="?")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    registry = knowledge.load()
    if args.mode == "preview":
        if args.entry not in registry.entries:
            raise SystemExit(f"Girdi yok: {args.entry}")
        sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(knowledge.preview(registry, args.entry), ensure_ascii=False, indent=2))
        return
    contents = render(registry)
    if args.check:
        if not REPORT.exists() or REPORT.read_text(encoding="utf-8") != contents:
            raise SystemExit(f"Güncel olmayan rapor: {REPORT.relative_to(ROOT)} (python -m scripts.knowledge_registry)")
        print(f"Bilgi kaydı geçerli: {registry.version}, {len(registry.sources)} kaynak, {len(registry.entries)} girdi")
        return
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(contents, encoding="utf-8", newline="\n")
    print(f"Yazıldı: {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
