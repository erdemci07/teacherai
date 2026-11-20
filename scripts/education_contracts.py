"""Pydantic eğitim sözleşmesini JSON Schema ve TypeScript'e aktarır."""

import argparse
import json
from pathlib import Path

from pydantic.json_schema import models_json_schema

from apps.api.app.features.education.domain import Capabilities, QuestionUnderstanding
from apps.api.app.features.education.presentation import LessonView
from apps.api.app.features.education.source import ClarificationRequest, IntegrityReport
from apps.api.app.features.mathai.schemas import ChoiceMatch

ROOT = Path(__file__).resolve().parents[1]


def ts_type(node):
    if "$ref" in node:
        return node["$ref"].split("/")[-1]
    if "const" in node:
        return json.dumps(node["const"])
    if "enum" in node:
        return " | ".join(map(json.dumps, node["enum"]))
    for key in ("oneOf", "anyOf"):
        if key in node:
            return " | ".join(ts_type(member) for member in node[key])
    kind = node["type"]
    if kind == "array":
        return f'Array<{ts_type(node["items"])}>'
    if kind == "object":
        if node.get("additionalProperties") is not False:
            raise ValueError("Sınırsız nesne aktarılamaz")
        fields = []
        for name, prop in node["properties"].items():
            optional = "" if name in node.get("required", []) else "?"
            fields.append(f"  {name}{optional}: {ts_type(prop)};")
        return "{\n" + "\n".join(fields) + "\n}"
    return {"integer": "number", "number": "number", "string": "string",
            "boolean": "boolean", "null": "null"}[kind]


def outputs():
    roots = [LessonView, QuestionUnderstanding, Capabilities, IntegrityReport, ClarificationRequest, ChoiceMatch]
    _, schema = models_json_schema([(model, "serialization") for model in roots])
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$ref"] = "#/$defs/LessonView"
    defs = schema["$defs"]
    types = ["// Üretilen dosya · python -m scripts.education_contracts"]
    types.extend(f"export type {name} = {ts_type(defs[name])};" for name in sorted(defs))
    return {
        ROOT / "docs/contracts/education-v2.schema.json": json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        ROOT / "apps/web/app/lib/education.generated.ts": "\n\n".join(types) + "\n",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for path, contents in outputs().items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != contents:
                raise SystemExit(f"Güncel olmayan sözleşme: {path.relative_to(ROOT)}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
