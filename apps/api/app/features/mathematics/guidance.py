"""Üretim öncesi belirlenimci matematik ipuçları (TA-008 §24). Saf Python; SymPy ve alt süreç yoktur.

Kaynak ifadelerin AST'sinden: tanım kümesi uyarıları (payda, çift kök, logaritma), yapısal özellikler (doğrusal,
ikinci derece, mutlak değer, sistem, fonksiyon...) ve istenen hedef türü. Bu bilgiler doğrulama değildir;
sağlayıcıya yalnız *dikkat edilecek koşullar* olarak verilir ve sonuç her zaman ayrıca sunucuda denetlenir.
"""

from __future__ import annotations

from ..integrity import expression as tree

MAX_NOTES = 4


def _walk(node):
    yield node
    for child in tree._children(node):
        yield from _walk(child)


def _has_symbol(node) -> bool:
    return bool(tree.symbols(node))


def _degree(node) -> int:
    """Kaba polinom derecesi (yalnız özellik etiketi için)."""
    best = 1 if _has_symbol(node) else 0
    for item in _walk(node):
        if isinstance(item, tree.Pow) and _has_symbol(item.base) and isinstance(item.exp, tree.Num):
            best = max(best, int(item.exp.value) if item.exp.value.denominator == 1 else best)
        if isinstance(item, tree.Bin) and item.op == "*" and _has_symbol(item.left) and _has_symbol(item.right):
            best = max(best, 2)
    return best


def analyze_sources(analysis) -> tuple[set[str], list[str]]:
    """(yapısal özellikler, tanım kümesi notları)."""
    integrity = getattr(analysis, "integrity", None)
    features: set[str] = set()
    notes: list[str] = []
    if integrity is None and hasattr(analysis, "mathematical_expressions") and hasattr(analysis, "visual_elements"):
        from ..integrity.engine import EvaluationState, evaluate

        integrity = evaluate(analysis, EvaluationState(revision=getattr(analysis, "revision", 1), origin="legacy"))
    if integrity is None:
        return features, notes
    parsed = []
    for item in integrity.expressions:
        if item.status != "parsed" or item.role not in {"given", "requested"}:
            continue
        result = tree.parse(item.source)
        if result.parsed:
            parsed.append((item.role, result.tree))
    relations = [node for role, node in parsed if role == "given" and isinstance(node, tree.Rel)]
    for _, node in parsed:
        for sub in _walk(node):
            if isinstance(sub, tree.Frac) and _has_symbol(sub.den):
                notes.append(f"payda sıfır olamaz: {tree.to_latex(sub.den)} ≠ 0")
            elif isinstance(sub, tree.Root) and sub.index is None and _has_symbol(sub.radicand):
                notes.append(f"karekök içi negatif olamaz: {tree.to_latex(sub.radicand)} ≥ 0")
            elif isinstance(sub, tree.Func) and sub.name in {"log", "ln"} and _has_symbol(sub.arg):
                notes.append(f"logaritma argümanı pozitif olmalı: {tree.to_latex(sub.arg)} > 0")
            elif isinstance(sub, tree.Abs) and _has_symbol(sub.arg):
                features.add("absolute_value")
            elif isinstance(sub, tree.Func) and sub.name in {"sin", "cos", "tan", "cot"}:
                features.add("trigonometry")
    equations = [node for node in relations if node.ops == ("=",)]
    inequalities = [node for node in relations if all(op in {"<", ">", "<=", ">="} for op in node.ops)]
    variables = set().union(*(tree.symbols(node) for node in relations)) if relations else set()
    if len(equations) >= 2 and len(variables) >= 2:
        features.add("linear_system")
    for node in equations:
        if isinstance(node.operands[0], tree.Sym) and node.operands[0].name in {"y", "f"}:
            features.add("function")
            continue
        degree = max(_degree(side) for side in node.operands)
        features.add("linear_equation" if degree <= 1 else "quadratic" if degree == 2 else "polynomial_equation")
        if any(isinstance(side, tree.Frac) for side in node.operands) and degree <= 1 and \
                all(not _has_symbol(side) or isinstance(side, tree.Frac) for side in node.operands):
            features.add("proportion")
    for node in inequalities:
        features.add("inequality")
        degree = max(_degree(side) for side in node.operands)
        has_fraction = any(isinstance(sub, tree.Frac) and _has_symbol(sub.den) for side in node.operands for sub in _walk(side))
        features.add("rational_or_polynomial_inequality" if degree > 1 or has_fraction else "linear_inequality")
    return features, list(dict.fromkeys(notes))[:MAX_NOTES]


def prompt_hints(analysis) -> dict | None:
    """İsteme giden küçük, doğrulama iddiası taşımayan ipucu. Not yoksa None (istem değişmez)."""
    _, notes = analyze_sources(analysis)
    if not notes:
        return None
    return {"domain_conditions_tr": notes,
            "authority_tr": "Sunucunun kaynak ifadelerden çıkardığı tanım kümesi koşulları; çözümü kanıtlamaz."}
