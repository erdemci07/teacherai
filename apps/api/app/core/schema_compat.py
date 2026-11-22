"""Sıkı JSON şemalarının Anthropic yapılandırılmış çıktı kısıtlarıyla çevrimdışı uyumu (TA-005B §8).

Kaynak (22 Kasım 2026'da okundu): https://platform.claude.com/docs/en/build-with-claude/structured-outputs
Belgedeki "desteklenmeyen" listesi: özyinelemeli şema; ``oneOf``; ``not``; ``type``/``properties`` ile aynı
nesnede ``anyOf``; enum içinde karmaşık tip; dış ``$ref``; sayısal sınırlar (minimum, maximum,
multipleOf); dize uzunluğu (minLength, maxLength); 0 veya 1 dışında dizi sınırı; ``false`` dışında
``additionalProperties``; geri başvuru ve bakınma içeren regex. Desteklenmeyen özellik 400 döndürür.

Denetlenen şema, OpenAI adaptörünün gönderdiği sıkı şemanın aynısıdır. Uyumsuz alanı olan bir işlem
Anthropic adaptöründe desteklenmiyor sayılır; kısıtlar sessizce atılmaz.
"""

from __future__ import annotations

import re

NUMERIC = ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf")
STRING = ("minLength", "maxLength")
REGEX = re.compile(r"\\[1-9]|\(\?[=!<]|\\[bB]|\{\d*,\d{3,}\}")


def strict_schema(model) -> dict:
    """OpenAI adaptörünün ``text.format.schema`` olarak gönderdiği sıkı şema."""
    from openai.lib._pydantic import to_strict_json_schema

    return to_strict_json_schema(model)


def _refs(node, found):
    if isinstance(node, dict):
        if isinstance(node.get("$ref"), str):
            found.add(node["$ref"])
        for value in node.values():
            _refs(value, found)
    elif isinstance(node, list):
        for value in node:
            _refs(value, found)
    return found


def _recursive(schema) -> set[str]:
    defs = schema.get("$defs") or schema.get("definitions") or {}
    edges = {f"#/$defs/{name}": _refs(body, set()) for name, body in defs.items()}
    cyclic = set()
    for start in edges:
        stack, seen = list(edges[start]), set()
        while stack:
            ref = stack.pop()
            if ref == start:
                cyclic.add(start.rsplit("/", 1)[-1])
                break
            if ref in seen or ref not in edges:
                continue
            seen.add(ref)
            stack.extend(edges[ref])
    return cyclic


def incompatibilities(schema: dict) -> list[str]:
    """``yol: neden`` biçiminde uyumsuzluk listesi; boşsa şema belgedeki kısıtlara uyar."""
    issues = [f"$defs/{name}: recursive_schema" for name in sorted(_recursive(schema))]

    def walk(node, path):
        if isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{path}/{index}")
            return
        if not isinstance(node, dict):
            return
        for key in NUMERIC + STRING:
            if key in node:
                issues.append(f"{path}: {key}")
        for key in ("minItems", "maxItems"):
            if key in node and not (key == "minItems" and node[key] in (0, 1)):
                issues.append(f"{path}: {key}={node[key]}")
        for key in ("oneOf", "not"):
            if key in node:
                issues.append(f"{path}: {key}")
        if "anyOf" in node and ("type" in node or "properties" in node):
            issues.append(f"{path}: anyOf_with_type_or_properties")
        if node.get("type") == "object" and node.get("additionalProperties", False) is not False:
            issues.append(f"{path}: additionalProperties")
        if isinstance(node.get("$ref"), str) and not node["$ref"].startswith("#"):
            issues.append(f"{path}: external_ref")
        if isinstance(node.get("pattern"), str) and REGEX.search(node["pattern"]):
            issues.append(f"{path}: pattern")
        if isinstance(node.get("enum"), list) and any(isinstance(item, dict | list) for item in node["enum"]):
            issues.append(f"{path}: complex_enum")
        for key, value in node.items():
            walk(value, f"{path}/{key}")

    walk(schema, "#")
    return issues
