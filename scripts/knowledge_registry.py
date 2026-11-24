"""Bilimsel kaynak/bilgi kaydı doğrulaması, kapsam raporu ve çevrimdışı taslak önizleme (TA-006).

    python -m scripts.knowledge_registry                 # doğrular, docs/knowledge/TA-007-knowledge-coverage.md yazar
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
REPORT = ROOT / "docs/knowledge/TA-007-knowledge-coverage.md"
AUDIT = ROOT / "apps/api/app/features/knowledge/audit/TA-007-draft-audit.json"
SUBJECT_TR = {"mathematics": "Matematik (geometri dahil)", "physics": "Fizik", "chemistry": "Kimya", "biology": "Biyoloji",
              "science": "Ortaokul fen (bütünleşik)"}
PERM_TR = {"allowed": "evet", "not_allowed": "hayır", "conditional": "koşullu", "unknown": "bilinmiyor"}


def render(registry: knowledge.KnowledgeRegistry) -> str:
    rows = knowledge.coverage(registry)
    lines = ["# TA-007 bilimsel bilgi kapsam raporu", "",
             "Bu dosya `python -m scripts.knowledge_registry` ile üretilir; elle düzenlenmez.", "",
             f"- Kayıt sürümü: `{registry.version}`",
             f"- Kaynak: {len(registry.sources)} · bilgi girdisi: {len(registry.entries)} · tanımlı denetleyici: {len(CAPABILITIES)}", "",
             "Bütün girdiler `claude-draft` taslağıdır. Hiçbiri öğretmen veya alan uzmanınca incelenmedi; inceleyen yetki kaydı",
             f"boştur ({len(registry.reviewers)} yetkili). Bu yüzden çalışma zamanına uygun girdi sayısı 0'dır. Denetleyici",
             "bağlantısı iddianın yalnız belirtilen parçasını kapsar.", "",
             "| Alan | Girdi | Kaynaklı | Kaynaksız | Kazanıma bağlı | Denetleyicili | İncelenen | Çalışma zamanına uygun | Tür dağılımı |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for row in rows:
        kinds = ", ".join(f"{key} {value}" for key, value in row["kinds"].items())
        lines.append(f"| {SUBJECT_TR[row['subject']]} | {row['total']} | {row['sourced']} | {len(row['unsourced'])} | {row['with_outcome']} | "
                     f"{row['with_verifier']} | {row['reviewed']} | {row['runtime_eligible']} | {kinds} |")
    lines += ["", "| Alan | Düzeltilen (sürüm 2+) | Müfredat başlığına bağlı | Kaynak kullanım sınıfı |", "| --- | --- | --- | --- |"]
    for row in rows:
        uses = ", ".join(f"{key} {value}" for key, value in row["source_use"].items())
        lines.append(f"| {SUBJECT_TR[row['subject']]} | {row['revised']} | {row['topic_linked']} | {uses} |")
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    actions = Counter(item["action"] for item in audit["rows"])
    severities = Counter(finding["severity"] for item in audit["rows"] for finding in item["findings"])
    expert = ", ".join(f"`{item['entry_id']}`" for item in audit["rows"] if item["action"] == "needs_expert") or "yok"
    action_text = ", ".join(f"{key} {value}" for key, value in sorted(actions.items()))
    severity_text = ", ".join(f"{key} {value}" for key, value in sorted(severities.items()))
    lines += ["", "## TA-007 bağımsız taslak denetimi", "",
              (f"`{AUDIT.relative_to(ROOT).as_posix()}`: {len(audit['rows'])} TA-006 taslağı. Eylem: {action_text}. "
               f"Bulgu düzeyi: {severity_text}."),
              "AI destekli denetimdir; uzman onayı değildir. Düzeltilen girdiler önceki sürümü `revisions` içinde korur.",
              f"Uzman kararı gereken girdiler: {expert}.", "",
              "## TA-006 → TA-007", "", "| Ölçü | TA-006 | TA-007 |", "| --- | --- | --- |",
              f"| Kaynak | 30 | {len(registry.sources)} |", f"| Bilgi girdisi | 74 | {len(registry.entries)} |"]
    before = {"mathematics": 19, "physics": 18, "chemistry": 16, "biology": 15, "science": 6}
    for row in rows:
        lines.append(f"| {SUBJECT_TR[row['subject']]} | {before[row['subject']]} | {row['total']} |")
    lines.append(f"| Çalışma zamanına uygun | 0 | {sum(row['runtime_eligible'] for row in rows)} |")
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
