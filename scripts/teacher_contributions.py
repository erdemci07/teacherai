"""Öğretmen katkı dosyalarını doğrular (TA-006). Katkı onay değildir; yalnız biçim ve başvurular denetlenir.

    python -m scripts.teacher_contributions validate data/contributions/<dosya>.json
    python -m scripts.teacher_contributions validate-all     # data/contributions altındaki bütün .json dosyaları
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from apps.api.app.features.curriculum import registry_v2
from apps.api.app.features.education.contribution import TeacherContribution
from apps.api.app.features.knowledge import registry as knowledge

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "data/contributions"


def validate(path: Path) -> list[str]:
    contribution = TeacherContribution.model_validate_json(registry_v2._read(path))
    outcomes = set(registry_v2.default_registry().outcomes)
    entries = set(knowledge.default_knowledge().entries)
    problems = []
    for index, item in enumerate(contribution.items):
        problems += [f"öğe {index}: tanımsız kazanım {ref}" for ref in item.outcome_ids if ref not in outcomes]
        problems += [f"öğe {index}: tanımsız bilgi girdisi {ref}" for ref in item.knowledge_ids if ref not in entries]
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["validate", "validate-all"])
    parser.add_argument("path", nargs="?", type=Path)
    args = parser.parse_args(argv)
    paths = sorted(FOLDER.glob("*.json")) if args.mode == "validate-all" else [args.path]
    failed = False
    for path in paths:
        problems = validate(path)
        failed |= bool(problems)
        print(json.dumps({"file": str(path), "valid": not problems, "problems": problems}, ensure_ascii=False))
    if not paths:
        print("Katkı dosyası yok (data/contributions).")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
