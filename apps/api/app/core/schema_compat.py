"""Sıkı JSON şemalarının Anthropic yapılandırılmış çıktı kısıtlarıyla çevrimdışı uyumu (TA-005B §8).

Kaynak (22 Kasım 2026'da okundu, 24 Kasım 2026'da yeniden doğrulandı):
https://platform.claude.com/docs/en/build-with-claude/structured-outputs
Belgedeki "desteklenmeyen" listesi: özyinelemeli şema; ``oneOf``; ``not``; ``type``/``properties`` ile aynı
nesnede ``anyOf``; çelişen ``allOf``; biri doğrudan ``$ref``/``anyOf``/``allOf`` taşıyan iki veya daha çok
şemalı ``allOf``; enum içinde karmaşık tip; dış ``$ref``; sayısal sınırlar (minimum, maximum,
multipleOf); dize uzunluğu (minLength, maxLength); 0 veya 1 dışında dizi sınırı; ``false`` dışında
``additionalProperties``; geri başvuru ve bakınma içeren regex. Desteklenmeyen özellik 400 döndürür.

Denetlenen şema, OpenAI adaptörünün gönderdiği sıkı şemanın aynısıdır. Uyumsuz alanı olan bir işlem
Anthropic adaptöründe desteklenmiyor sayılır; kısıtlar sessizce atılmaz.

TA-005C: Anthropic'e gönderilen şema için dar bir izdüşüm (``anthropic_projection``). Yalnız onaylı
listedeki (``APPROVED_PROJECTIONS``) sayı/dize sınırları gönderilen şemadan çıkarılır ve alanın
açıklamasına yazılır. Bu, resmî SDK yardımcılarının yaptığı dönüşümün aynısıdır (structured-outputs
belgesi: "Most SDK helpers transform schemas ... Remove unsupported constraints ... Update descriptions
... Validate responses against your original schema"). Yanıt her zaman geçitte özgün Pydantic modeliyle
doğrulanır; çıkarılan sınır sunucuda aynen uygulanır. Onaylı listede olmayan bir çıkarma, eskimiş onay
satırı veya izdüşümden sonra kalan uyumsuzluk ``SchemaProjectionError`` verir: yeni bir kısıt eklenirse
şema Anthropic'e gönderilmez ve CI (``scripts/anthropic_schema_compat.py --check``) kırılır.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass

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
        parts = node.get("allOf")
        if isinstance(parts, list) and len(parts) > 1 and any(
                isinstance(part, dict) and ({"$ref", "anyOf", "allOf"} & set(part)) for part in parts):
            issues.append(f"{path}: allOf_with_ref_or_combinator")
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


# --- TA-005C: Anthropic'e özgü izdüşüm -----------------------------------------------------------

# Çıkarılabilecek anahtarlar: belgede açıkça desteklenmeyen sayı ve dize sınırları. Bunların dışında
# kalan uyumsuzluk (oneOf, özyineleme, dizi sınırı, additionalProperties, regex ...) izdüşümle
# giderilmez; işlem Anthropic'te desteklenmez.
PROJECTABLE = NUMERIC + STRING

# Model → onaylı (JSON işaretçisi, anahtar) çiftleri ve sunucuda o sınırı uygulayan Pydantic alanı.
# Her satır ADR TA-005C §2 tablosunda belgelenir; yeni satır ADR ile birlikte eklenir.
APPROVED_PROJECTIONS: dict[str, dict[tuple[str, str], str]] = {
    "VisionProviderAnalysis": {
        ("#/properties/confidence", "minimum"): "VisionProviderAnalysis.confidence: Field(ge=0)",
        ("#/properties/confidence", "maximum"): "VisionProviderAnalysis.confidence: Field(le=1)",
        ("#/$defs/SourceProposal/properties/question_count", "minimum"): "SourceProposal.question_count: Field(ge=0)",
    },
    "AdaptiveDraft": {
        ("#/$defs/Expression/properties/latex", "minLength"): "Expression.latex: Field(min_length=1)",
    },
}


class SchemaProjectionError(ValueError):
    """Şema onaylı izdüşümle Anthropic kısıtlarına indirgenemiyor; şema gönderilmez."""


@dataclass(frozen=True)
class Projection:
    model: str
    schema: dict
    removed: tuple[tuple[str, str, object], ...]  # (işaretçi, anahtar, değer)
    original_issues: tuple[str, ...]


def _strip(node, path, removed):
    if isinstance(node, list):
        for index, item in enumerate(node):
            _strip(item, f"{path}/{index}", removed)
        return
    if not isinstance(node, dict):
        return
    dropped = {key: node.pop(key) for key in PROJECTABLE if key in node}
    if dropped:
        removed.extend((path, key, value) for key, value in dropped.items())
        note = ", ".join(f"{key}: {json_value}" for key, json_value in dropped.items())
        node["description"] = f"{node['description']} {{{note}}}" if node.get("description") else f"{{{note}}}"
    for key, value in list(node.items()):
        if key != "description":
            _strip(value, f"{path}/{key}", removed)


def anthropic_projection(model) -> Projection:
    """Anthropic'e gönderilecek şema. Özgün Pydantic modeli değişmez; doğrulama onunla yapılır."""
    name = model.__name__
    original = strict_schema(model)
    issues = tuple(incompatibilities(original))
    schema, removed = copy.deepcopy(original), []
    _strip(schema, "#", removed)
    approved = APPROVED_PROJECTIONS.get(name, {})
    unapproved = sorted({(path, key) for path, key, _ in removed} - set(approved))
    if unapproved:
        raise SchemaProjectionError(f"{name}: onaysız şema dönüşümü {unapproved}; ADR TA-005C §2'ye eklenmeden gönderilmez.")
    stale = sorted(set(approved) - {(path, key) for path, key, _ in removed})
    if stale:
        raise SchemaProjectionError(f"{name}: onaylı dönüşüm şemada yok {stale}; onay listesi eskimiş.")
    residual = incompatibilities(schema)
    if residual:
        raise SchemaProjectionError(f"{name}: izdüşümden sonra uyumsuz alan kaldı {residual}.")
    return Projection(name, schema, tuple(removed), issues)
