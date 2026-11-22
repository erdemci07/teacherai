"""Sınıf düzeyi yöntem ve müfredat denetimi (TA-005). Saf Python; sağlayıcı çağırmaz.

- Konu, sağlayıcının serbest ``topic`` etiketinden değil, kaynak ifadelerin yapısından belirlenimci çıkarılır.
  Belirlenemezse ``None`` döner ve iki boyut ``not_checked`` kalır.
- Adım işlemleri iki kanıt düzeyiyle toplanır (TA-005B):
  - **Güçlü:** sunucunun sınıflandırdığı adım işlemi ve adım ifadesinin AST'sinde gerçekten bulunan yapı
    (``f'(x)``, Leibniz, ``\\log``, ``\\sin``, ``\\lim``, ``\\int``, kökte ``b^2-4ac``). Yalnız güçlü kanıt
    ``failed`` üretir ve düzeltme turunu tetikler. Nokta adındaki üs (``A'``) ve tek başına ``\\Delta`` yetmez.
  - **Zayıf:** başlık/açıklama metninde konu sözcüğü. Tek başına ``partially_checked``
    (``prose_mention_unverified``) üretir. Olumsuzlanan söz ("türev kullanmadan", "değil", "gerekmez")
    zayıf kanıt da sayılmaz.
- Yalnızca ``approved`` politikalar kısıtlama uygular. Sınıf bilgisi yoksa sınıf sorudan tahmin edilmez.
"""

from __future__ import annotations

import re
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

from ..education.curriculum import CurriculumRegistry, MethodPolicy, PolicyCheck
from ..integrity import expression as tree

DATA = Path(__file__).with_name("data") / "lgs-matematik-8.json"

# Zayıf kanıt: düz metinde (başlık, açıklama) konu sözcüğü. Matematik ifadesi burada taranmaz.
PROSE = {
    "derivative": re.compile(r"türev", re.IGNORECASE),
    "integral": re.compile(r"integral", re.IGNORECASE),
    "limit": re.compile(r"\blimit\w*\s+(?:al|hesapla|bul)\w*", re.IGNORECASE),  # "hız limiti" değil
    "logarithm": re.compile(r"logaritma", re.IGNORECASE),
    "trigonometry": re.compile(r"\b(?:sinüs|kosinüs|tanjant|kotanjant)", re.IGNORECASE),
    "complex_number": re.compile(r"karmaşık sayı|sanal (?:birim|sayı)", re.IGNORECASE),
    "quadratic_formula": re.compile(r"diskriminant|kök formül", re.IGNORECASE),
}
# Olumsuzlama tümcenin tamamındaki sözü geçersiz kılar. "…madan önce" olumsuzlama değildir.
NEGATION = re.compile(r"\w*(?:madan|meden)\b(?!\s+önce)|\bdeğil\w*|\bgerek(?:mez|miyor|meden)\b|\bgerek yok"
                      r"|\bhiçbir\b|\bkullanıl(?:maz|mayacak|madan)\w*|\bkullanma(?:yacağ|yız|yın|dan)\w*"
                      r"|\byerine\b|\bolmadan\b", re.IGNORECASE)
CLAUSE = re.compile(r"[.;:!?\n]+")
TRIGONOMETRY = {"sin", "cos", "tan", "cot", "sec", "csc", "arcsin", "arccos", "arctan"}
# v1 adım türünden kesin işlem (math_adapter ile aynı eşleme).
STEP_TYPE_OPERATIONS = {"result": "state_result", "explanation": "explain"}


@lru_cache
def default_registry() -> CurriculumRegistry:
    return CurriculumRegistry.model_validate_json(DATA.read_text(encoding="utf-8"))


def approved_policies(registry: CurriculumRegistry, grade: int, topic: str | None) -> list[MethodPolicy]:
    wanted = {"genel", topic} if topic else {"genel"}
    return [p for p in registry.policies if p.status == "approved" and p.grade == grade and p.topic in wanted]


def _walk(node):
    yield node
    for child in tree._children(node):
        yield from _walk(child)


def _nonlinear(node) -> bool:
    """Değişken içeren üs, kök, paydada değişken veya değişken çarpımı."""
    for item in _walk(node):
        if isinstance(item, (tree.Pow, tree.Root)) and tree.symbols(item):
            return True
        if isinstance(item, tree.Frac) and tree.symbols(item.den):
            return True
        if isinstance(item, tree.Bin) and item.op == "*" and tree.symbols(item.left) and tree.symbols(item.right):
            return True
    return False


def topic_of(analysis) -> str | None:
    """Kaynak ifadelerin yapısından 8. sınıf konu anahtarı; belirsizse None."""
    integrity = getattr(analysis, "integrity", None)
    if integrity is None:
        return None
    items = [item for item in integrity.expressions if item.status == "parsed" and item.role in {"given", "requested"}]
    parsed = [(item.role, tree.parse(item.source)) for item in items]
    if not parsed or any(not result.parsed for _, result in parsed):
        return None
    given = [result.tree for role, result in parsed if role == "given"]
    if len(given) == 1 and isinstance(given[0], tree.Rel) and len(tree.symbols(given[0])) == 1 and not _nonlinear(given[0]):
        return "esitsizlikler" if any(op in {"<", ">", "<=", ">=", "≤", "≥"} for op in given[0].ops) else (
            "dogrusal_denklemler" if given[0].ops == ("=",) else None)
    if given:
        return None
    nodes = [node for _, result in parsed for node in _walk(result.tree)]
    if any(tree.symbols(result.tree) for _, result in parsed):
        return None
    if any(isinstance(node, tree.Root) for node in nodes):
        return "karekoklu_ifadeler"
    if any(isinstance(node, tree.Pow) for node in nodes):
        return "uslu_ifadeler"
    return None


def _bare(node):
    while isinstance(node, tree.Group):
        node = node.arg
    return node


def _factors(node) -> list:
    node = _bare(node)
    if isinstance(node, tree.Bin) and node.op == "*":
        return _factors(node.left) + _factors(node.right)
    return [node]


def _discriminant(node) -> bool:
    """``b^2 - 4ac`` yapısı: kare eksi, biri 4 olan üç çarpanlı çarpım."""
    node = _bare(node)
    if not (isinstance(node, tree.Bin) and node.op == "-"):
        return False
    square, product = _bare(node.left), _factors(node.right)
    return (isinstance(square, tree.Pow) and _bare(square.exp) == tree.Num(Fraction(2), "2")
            and len(product) == 3 and tree.Num(Fraction(4), "4") in product)


def ast_constructs(latex: str) -> set[str]:
    """Güçlü kanıt: ifadenin yapı kipindeki AST'sinde gerçekten bulunan yapılar. Ayrışmayan ifade kanıt değildir.

    Kök formülü yalnız diskriminant kök içinde ya da ``\\Delta = b^2-4ac`` eşitliğinde hesaplanıyorsa
    tanınır; açılımdaki ``x^2 - 4xy`` gibi terimler kök formülü değildir.
    """
    result = tree.parse(latex, constructs=True)
    if not result.parsed:
        return set()
    found = set()
    for node in _walk(result.tree):
        if isinstance(node, tree.Calculus):
            found.add(node.kind)
        elif isinstance(node, tree.Func) and node.name in {"log", "ln"}:
            found.add("logarithm")
        elif isinstance(node, tree.Func) and node.name in TRIGONOMETRY:
            found.add("trigonometry")
        elif isinstance(node, tree.Root):
            if _discriminant(node.radicand):
                found.add("quadratic_formula")
            if node.index is None and isinstance(_bare(node.radicand), tree.Neg) and not tree.symbols(node.radicand):
                found.add("complex_number")
        elif isinstance(node, tree.Rel):
            sides = [_bare(item) for item in node.operands]
            if tree.Sym("Δ") in sides and any(_discriminant(item) for item in sides):
                found.add("quadratic_formula")
            if (tree.Pow(tree.Sym("i"), tree.Num(Fraction(2), "2")) in sides
                    and tree.Neg(tree.Num(Fraction(1), "1")) in sides):
                found.add("complex_number")
    return found


def prose_constructs(text: str) -> set[str]:
    """Zayıf kanıt: olumsuzlanmamış tümcelerde geçen konu sözcükleri."""
    return {name for clause in CLAUSE.split(text or "") if not NEGATION.search(clause)
            for name, pattern in PROSE.items() if pattern.search(clause)}


def step_operations(plan, verification) -> list[tuple[str, list[str], list[str], bool]]:
    """(adım kimliği, güçlü işlemler, zayıf sözler, sınıflandırıldı mı). Sınıflandırma yalnız sunucudadır."""
    classified = {check.id: check.operation for check in verification.checks if getattr(check, "operation", None)}
    rows = []
    for step in plan.content.steps:
        strong = sorted(set().union(*(ast_constructs(item.latex) for item in step.expressions)))
        weak = sorted(prose_constructs(f"{step.title or ''}. {step.explanation or ''}") - set(strong))
        operation = classified.get(f"{step.id}_0") or classified.get(step.id) or STEP_TYPE_OPERATIONS.get(step.type)
        if operation is None and not step.expressions:
            operation = "explain"
        rows.append((step.id, ([operation] if operation else []) + strong, weak, operation is not None))
    return rows


def method_check(plan, verification, grade: int | None, registry: CurriculumRegistry | None = None) -> PolicyCheck:
    if grade is None:
        return PolicyCheck(dimension="method", state="not_checked", reason="grade_unknown")
    registry = registry or default_registry()
    topic = topic_of(plan.source_analysis)
    policies = approved_policies(registry, grade, topic)
    if not policies:
        return PolicyCheck(dimension="method", state="not_checked", reason="no_approved_policy", grade=grade, topic=topic)
    ids = [p.id for p in policies]
    forbidden = {item.operation: item.reason for p in policies for item in p.forbidden_operations}
    rows = step_operations(plan, verification)
    for step, operations, _, _ in rows:
        hit = next((op for op in operations if op in forbidden), None)
        if hit:  # yalnız güçlü kanıt
            return PolicyCheck(dimension="method", state="failed", reason="forbidden_operation", grade=grade, topic=topic,
                               step=step, operations=[hit], policy_ids=ids, detail=forbidden[hit][:400])
    used = sorted({op for _, operations, _, _ in rows for op in operations})
    for step, _, weak, _ in rows:
        mention = next((op for op in weak if op in forbidden), None)
        if mention:  # zayıf kanıt: yasak sayılmaz, doğrulanmış da sayılmaz
            return PolicyCheck(dimension="method", state="partially_checked", reason="prose_mention_unverified",
                               grade=grade, topic=topic, step=step, operations=[mention], policy_ids=ids)
    topical = [p for p in policies if p.topic == topic]
    allowed = {op for p in topical for op in p.allowed_operations}
    if topical and all(classified for *_, classified in rows) and set(used) <= allowed:
        return PolicyCheck(dimension="method", state="passed", reason="allowed_operations_only", grade=grade, topic=topic,
                           operations=used, policy_ids=ids)
    return PolicyCheck(dimension="method", state="partially_checked",
                       reason="no_forbidden_operation" if topical else "topic_policy_missing",
                       grade=grade, topic=topic, operations=used, policy_ids=ids)


def curriculum_check(analysis, grade: int | None, registry: CurriculumRegistry | None = None) -> PolicyCheck:
    """Konu, onaylı politika üzerinden kaynaklı bir kazanıma eşlenirse ``passed``; aksi halde ``not_checked``."""
    if grade is None:
        return PolicyCheck(dimension="curriculum", state="not_checked", reason="grade_unknown")
    registry = registry or default_registry()
    topic = topic_of(analysis)
    policies = [p for p in approved_policies(registry, grade, topic) if p.topic == topic]
    sourced = {o.outcome_id for o in registry.outcomes if o.source_status == "sourced" and o.grade == grade}
    outcomes = sorted({ref for p in policies for ref in p.outcome_ids if ref in sourced})
    if topic is None or not outcomes:
        return PolicyCheck(dimension="curriculum", state="not_checked",
                           reason="topic_unresolved" if topic is None else "no_sourced_outcome", grade=grade, topic=topic)
    return PolicyCheck(dimension="curriculum", state="passed", reason="sourced_outcome", grade=grade, topic=topic,
                       outcome_ids=outcomes, policy_ids=[p.id for p in policies])


def correction_feedback(check: PolicyCheck, registry: CurriculumRegistry | None = None) -> str:
    """Hedefli düzeltme istemi: yalnızca izinli işlemler ve yasaklanan adım verilir."""
    registry = registry or default_registry()
    allowed = sorted({op for p in approved_policies(registry, check.grade, check.topic) for op in p.allowed_operations})
    return (f"Yöntem denetimi: {check.grade}. sınıf düzeyine uygun olmayan işlem ({', '.join(check.operations)}) "
            f"{check.step} adımında kullanıldı. Bu adımı ve çözümü yalnızca şu işlemlerle yeniden yaz: "
            f"{', '.join(allowed) or 'temel cebirsel işlemler'}.")[:1200]
