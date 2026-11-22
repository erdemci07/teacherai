"""Uygulama şemalarının Anthropic yapılandırılmış çıktı kısıtlarıyla çevrimdışı uyumu (TA-005B §8).

    python -m scripts.anthropic_schema_compat          # rapor
    python -m scripts.anthropic_schema_compat --check  # destek tablosu rapora uymuyorsa çıkış 1

Sağlayıcı çağrısı yoktur. Bir işlem yalnız bütün şemaları uyumluysa Anthropic'te desteklenir
(``core/providers.SUPPORTED_OPERATIONS``).
"""

from __future__ import annotations

import argparse
import json
import sys


def schemas():
    from apps.api.app.core.operations import Operation
    from apps.api.app.features.interactions.schemas import AdaptiveDraft
    from apps.api.app.features.lessons.schemas import LessonDraftResponse
    from apps.api.app.features.vision.schemas import (
        RecheckResponse,
        VisionProviderAnalysis,
    )

    return {Operation.VISION: {"VisionProviderAnalysis": VisionProviderAnalysis, "RecheckResponse": RecheckResponse},
            Operation.LESSONS: {"LessonDraftResponse": LessonDraftResponse},
            Operation.INTERACTION: {"AdaptiveDraft": AdaptiveDraft}}


def report():
    from apps.api.app.core.schema_compat import incompatibilities, strict_schema

    result = {}
    for operation, models in schemas().items():
        rows = {name: incompatibilities(strict_schema(model)) for name, model in models.items()}
        result[str(operation)] = {"compatible": not any(rows.values()), "schemas": rows}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    from apps.api.app.core.providers import SUPPORTED_OPERATIONS

    result = report()
    for operation, row in result.items():
        print(f"{operation}: {'uyumlu' if row['compatible'] else 'UYUMSUZ'}")
        for name, issues in row["schemas"].items():
            print(f"  {name}: {len(issues)} uyumsuz alan")
            reasons = {}
            for issue in issues:
                reasons[issue.rsplit(": ", 1)[-1].split("=")[0]] = reasons.get(issue.rsplit(": ", 1)[-1].split("=")[0], 0) + 1
            if reasons:
                print("    " + json.dumps(reasons, ensure_ascii=False, sort_keys=True))
    claimed = {str(op) for op in SUPPORTED_OPERATIONS["anthropic"]}
    compatible = {op for op, row in result.items() if row["compatible"]}
    if args.check and not claimed <= compatible:
        print(f"HATA: şeması uyumsuz işlem destekli gösteriliyor: {sorted(claimed - compatible)}", file=sys.stderr)
        return 1
    print("Çevrimdışı denetim; sağlayıcı çağrısı yapılmadı.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
