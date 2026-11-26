"""Uygulama şemalarının Anthropic yapılandırılmış çıktı kısıtlarıyla çevrimdışı uyumu (TA-005B §8, TA-005C §2).

    python -m scripts.anthropic_schema_compat          # rapor
    python -m scripts.anthropic_schema_compat --check  # destek tablosu rapora uymuyorsa çıkış 1

Sağlayıcı çağrısı yoktur. Her şema için iki satır yazılır: özgün sıkı şemanın uyumsuzlukları ve onaylı
izdüşümün (``core/schema_compat.APPROVED_PROJECTIONS``) çıkardığı sınırlar ile bunları sunucuda uygulayan
Pydantic alanı. Bir işlem yalnız bütün şemaları izdüşümden sonra uyumluysa Anthropic'te desteklenir
(``core/providers.SUPPORTED_OPERATIONS``). Onaysız çıkarma, eskimiş onay satırı veya kalan uyumsuzluk
``--check``'i başarısız kılar.
"""

from __future__ import annotations

import argparse
import json
import sys


def schemas():
    from apps.api.app.core.operations import Operation
    from apps.api.app.features.interactions.schemas import AdaptiveDraft
    from apps.api.app.features.lessons.schemas import (
        LessonDraftResponse,
        PhysicsLessonDraftResponse,
    )
    from apps.api.app.features.vision.schemas import (
        RecheckResponse,
        VisionProviderAnalysis,
    )

    return {Operation.VISION: {"VisionProviderAnalysis": VisionProviderAnalysis, "RecheckResponse": RecheckResponse},
            Operation.LESSONS: {"LessonDraftResponse": LessonDraftResponse,
                                "PhysicsLessonDraftResponse": PhysicsLessonDraftResponse},
            Operation.INTERACTION: {"AdaptiveDraft": AdaptiveDraft}}


def report():
    from apps.api.app.core.schema_compat import (
        APPROVED_PROJECTIONS,
        SchemaProjectionError,
        anthropic_projection,
        incompatibilities,
        strict_schema,
    )

    result = {}
    for operation, models in schemas().items():
        rows = {}
        for name, model in models.items():
            row = {"original_issues": incompatibilities(strict_schema(model))}
            try:
                projection = anthropic_projection(model)
                row["projected"] = [{"path": path, "keyword": key, "value": value,
                                     "server_validation": APPROVED_PROJECTIONS[name][(path, key)]}
                                    for path, key, value in projection.removed]
                row["error"] = None
            except SchemaProjectionError as error:
                row["projected"], row["error"] = [], str(error)
            rows[name] = row
        result[str(operation)] = {"compatible": all(row["error"] is None for row in rows.values()), "schemas": rows}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    from apps.api.app.core.providers import SUPPORTED_OPERATIONS

    result = report()
    for operation, row in result.items():
        print(f"{operation}: {'uyumlu (izdüşümle)' if row['compatible'] else 'UYUMSUZ'}")
        for name, schema in row["schemas"].items():
            print(f"  {name}: özgün şemada {len(schema['original_issues'])} uyumsuz alan")
            for item in schema["projected"]:
                print(f"    gönderilmez: {item['path']} {item['keyword']}={json.dumps(item['value'])}"
                      f" → sunucuda: {item['server_validation']}")
            if schema["error"]:
                print(f"    HATA: {schema['error']}")
    claimed = {str(op) for op in SUPPORTED_OPERATIONS["anthropic"]}
    compatible = {op for op, row in result.items() if row["compatible"]}
    if args.check and not claimed <= compatible:
        print(f"HATA: şeması uyumsuz işlem destekli gösteriliyor: {sorted(claimed - compatible)}", file=sys.stderr)
        return 1
    print("Çevrimdışı denetim; sağlayıcı çağrısı yapılmadı.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
