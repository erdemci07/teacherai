"""SymPy düğümlerini yalnızca güvenli ifade ağacından kuran sınırlı dönüştürücü.

TA-003: Ayrıştırma ``integrity.expression`` içindeki dengeli, özyinelemeli inişli ayrıştırıcıya
taşındı. Bu modül ``eval``, ``exec``, ``ast.parse``, ``sympify`` veya ``parse_expr`` kullanmaz.
Hesap bütçeleri (sembol, sayı uzunluğu, düğüm, üs) önceki sınırlarla korunur; pahalı SymPy
işlemleri yalıtılmış işçi sürecinde çalışır.
"""

import sympy as sp

from ..integrity import expression as tree

MAX_COMPUTE_SYMBOLS = 4
MAX_COMPUTE_DIGITS = 12
MAX_COMPUTE_NODES = 100
MAX_COMPUTE_EXPONENT = 10


class MathParseError(ValueError):
    pass


def normalize(value: str) -> str:
    """Geriye uyumluluk: karakter düzeyinde normalleştirilmiş metin (± tespiti için)."""
    if len(value) > tree.MAX_SOURCE_CHARS:
        raise MathParseError("expression too long")
    text, _ = tree.normalize(value)
    return text.replace("\\pm", "±")


def _parse(value: str):
    if not isinstance(value, str):
        raise MathParseError("expected text")
    result = tree.parse(value)
    if not result.parsed:
        raise MathParseError(result.reason or "unsupported expression")
    return result.tree


class _Budget:
    def __init__(self):
        self.nodes = 0
        self.symbols: set[str] = set()

    def tick(self):
        self.nodes += 1
        if self.nodes > MAX_COMPUTE_NODES:
            raise MathParseError("tree budget")


def to_sympy(node, budget: _Budget | None = None):
    """Ağaç düğümünü SymPy nesnesine çevirir; desteklenmeyen düğümde MathParseError."""
    budget = budget or _Budget()
    budget.tick()
    if isinstance(node, tree.Num):
        if sum(ch.isdigit() for ch in node.text) > MAX_COMPUTE_DIGITS:
            raise MathParseError("expression budget")
        return sp.Rational(node.value.numerator, node.value.denominator)
    if isinstance(node, tree.Sym):
        name = node.name + (f"_{node.sub}" if node.sub else "")
        budget.symbols.add(name)
        if len(budget.symbols) > MAX_COMPUTE_SYMBOLS:
            raise MathParseError("expression budget")
        return sp.Symbol(name, real=True)
    if isinstance(node, tree.Const):
        return sp.pi
    if isinstance(node, tree.Group):
        return to_sympy(node.arg, budget)
    if isinstance(node, tree.Neg):
        return -to_sympy(node.arg, budget)
    if isinstance(node, tree.Mixed):
        return sp.Rational(node.whole * node.den + node.num, node.den)
    if isinstance(node, tree.Frac):
        return _divide(to_sympy(node.num, budget), to_sympy(node.den, budget))
    if isinstance(node, tree.Bin):
        if node.op == "±":
            raise MathParseError("multiple signs")
        left, right = to_sympy(node.left, budget), to_sympy(node.right, budget)
        if node.op == "+":
            return sp.Add(left, right, evaluate=False)
        if node.op == "-":
            return sp.Add(left, -right, evaluate=False)
        if node.op == "*":
            return sp.Mul(left, right, evaluate=False)
        return _divide(left, right)
    if isinstance(node, tree.Pow):
        left, right = to_sympy(node.base, budget), to_sympy(node.exp, budget)
        if right.is_number and not right.free_symbols and isinstance(right.doit(), sp.Integer):
            right = right.doit()  # TA-005: 2^{3^2} gibi sabit tam sayı üssü; bütçe aynı kalır
        if not isinstance(right, sp.Integer) or abs(right) > MAX_COMPUTE_EXPONENT or left.has(sp.Pow):
            raise MathParseError("power budget")
        return sp.Pow(left, right, evaluate=False)
    if isinstance(node, tree.Root):
        radicand = to_sympy(node.radicand, budget)
        if node.index is None:
            return sp.sqrt(radicand)
        index = to_sympy(node.index, budget)
        if not isinstance(index, sp.Integer) or not 2 <= index <= MAX_COMPUTE_EXPONENT:
            raise MathParseError("root budget")
        if index % 2 == 1 and radicand.is_number and radicand.is_negative:
            return -sp.root(-radicand, index)
        return sp.root(radicand, index)
    if isinstance(node, tree.Abs):
        return sp.Abs(to_sympy(node.arg, budget))
    raise MathParseError("unsupported syntax")


def _divide(left, right):
    if right.is_zero is True:
        raise MathParseError("division by zero")
    return sp.Mul(left, sp.Pow(right, -1, evaluate=False), evaluate=False)


def expression(value):
    node = _parse(value)
    if isinstance(node, tree.Rel):
        raise MathParseError("unexpected relation")
    return to_sympy(node)


def branches(value):
    text = normalize(value)
    if "±" not in text:
        return [text]
    if text.count("±") != 1:
        raise MathParseError("multiple signs")
    return [text.replace("±", sign) for sign in ("+", "-")]


def equation(value):
    node = _parse(value)
    if not isinstance(node, tree.Rel) or node.ops != ("=",):
        raise MathParseError("expected equation")
    budget = _Budget()
    return sp.Eq(to_sympy(node.operands[0], budget), to_sympy(node.operands[1], budget), evaluate=False)


_RELATIONS = {"<": sp.StrictLessThan, "<=": sp.LessThan, ">": sp.StrictGreaterThan, ">=": sp.GreaterThan}


def is_inequality(value) -> bool:
    try:
        node = _parse(value)
    except MathParseError:
        return False
    return isinstance(node, tree.Rel) and all(op in _RELATIONS for op in node.ops)


_FLIPPED = {"<": ">", "<=": ">=", ">": "<", ">=": "<="}


def relation_set(value, variable, flip: bool = False):
    """Tek değişkenli eşitsizliğin (zincir dahil) gerçel çözüm kümesi. TA-004.

    Yalnızca <, ≤, >, ≥ desteklenir; ≠ ve eşitlik karışımı desteklenmez. Küme sembolik olarak
    SymPy ``solveset`` ile, yalıtılmış işçide hesaplanır. ``flip`` yönü ters çevrilmiş ilişkiyi çözer
    (eşitsizlik yönü hatasını adlandırmak için).
    """
    node = _parse(value)
    if not isinstance(node, tree.Rel) or not all(op in _RELATIONS for op in node.ops):
        raise MathParseError("expected inequality")
    budget = _Budget()
    operands = [to_sympy(item, budget) for item in node.operands]
    result = sp.S.Reals
    for op, left, right in zip(node.ops, operands, operands[1:]):
        relation = _RELATIONS[_FLIPPED[op] if flip else op](left, right, evaluate=False)
        if relation.free_symbols - {variable}:
            raise MathParseError("unexpected variables")
        result = sp.Intersection(result, sp.solveset(relation, variable, domain=sp.S.Reals))
    return result


def denominators(expr):
    """Sıfır olmaması gereken paydalar (negatif üslü kuvvetlerin tabanları)."""
    return [item.base for item in expr.atoms(sp.Pow) if item.exp.is_number and item.exp.is_negative]


def solutions(value, variable):
    result = set()
    for branch in branches(value):
        eq = equation(branch)
        if eq.free_symbols != {variable}:
            raise MathParseError("unexpected variables")
        roots = sp.solveset(eq, variable, domain=sp.S.Reals)
        if roots != sp.EmptySet and not isinstance(roots, sp.FiniteSet):
            raise MathParseError("non-finite solution set")
        result.update(roots)
    return result
