"""Sınırlı ifade kurucu (TA-008). Yalnız ``integrity.expression`` ağacından SymPy nesnesi kurar.

``mathai.parser.to_sympy``'nin bütçelerini korur ve yalnız şunları ekler: ``sin``, ``cos``, ``tan``, ``cot``,
``ln``, ``log`` (taban verilmezse 10), sembolik ``π``. Mevcut MathAI yolları bu modülü kullanmaz; davranışları
değişmez. ``eval``/``exec``/``sympify``/``parse_expr`` yoktur.
"""

from __future__ import annotations

import sympy as sp

from ..integrity import expression as tree
from ..mathai import parser

MAX_NODES = 160
MAX_SYMBOLS = 4
FUNCTIONS = {"sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "cot": sp.cot, "ln": sp.log}


class ExprError(ValueError):
    pass


class _Budget(parser._Budget):
    def tick(self):
        self.nodes += 1
        if self.nodes > MAX_NODES:
            raise ExprError("tree budget")


def symbol(name: str) -> sp.Symbol:
    return sp.Symbol(name, real=True)


def build(node, budget: _Budget | None = None):
    budget = budget or _Budget()
    budget.tick()
    if isinstance(node, tree.Func):
        arg = build(node.arg, budget)
        if node.name == "log":
            base = build(node.base, budget) if node.base is not None else sp.Integer(10)
            if not base.is_number or base.is_positive is not True or base == 1:
                raise ExprError("log base")
            return sp.log(arg, base)
        if node.name not in FUNCTIONS:
            raise ExprError("unsupported function")
        return FUNCTIONS[node.name](arg)
    if isinstance(node, tree.Group):
        return build(node.arg, budget)
    if isinstance(node, tree.Neg):
        return -build(node.arg, budget)
    if isinstance(node, tree.Bin):
        if node.op == "±":
            raise ExprError("multiple signs")
        left, right = build(node.left, budget), build(node.right, budget)
        return {"+": lambda: left + right, "-": lambda: left - right, "*": lambda: left * right,
                "/": lambda: _divide(left, right)}[node.op]()
    if isinstance(node, tree.Frac):
        return _divide(build(node.num, budget), build(node.den, budget))
    if isinstance(node, tree.Pow):
        base, exp = build(node.base, budget), build(node.exp, budget)
        if not exp.is_number or not exp.is_rational or abs(exp) > parser.MAX_COMPUTE_EXPONENT:
            # Değişken veya büyük üs: üstel ifade yalnız sabit tabanla ve küçük ağaçla
            if exp.free_symbols and base.is_number and base.is_positive and len(exp.free_symbols) == 1:
                return sp.Pow(base, exp)
            raise ExprError("power budget")
        return sp.Pow(base, exp)
    if isinstance(node, tree.Root):
        radicand = build(node.radicand, budget)
        if node.index is None:
            return sp.sqrt(radicand)
        index = build(node.index, budget)
        if not isinstance(index, sp.Integer) or not 2 <= index <= parser.MAX_COMPUTE_EXPONENT:
            raise ExprError("root budget")
        if index % 2 == 1 and radicand.is_number and radicand.is_negative:
            return -sp.root(-radicand, index)
        return sp.root(radicand, index)
    if isinstance(node, tree.Abs):
        return sp.Abs(build(node.arg, budget))
    if isinstance(node, tree.Sym):
        name = node.name + (f"_{node.sub}" if node.sub else "")
        budget.symbols.add(name)
        if len(budget.symbols) > MAX_SYMBOLS:
            raise ExprError("symbol budget")
        return symbol(name)
    try:
        return parser.to_sympy(node, budget)
    except parser.MathParseError as exc:
        raise ExprError(str(exc)) from exc


def _divide(left, right):
    if right.is_zero is True:
        raise ExprError("division by zero")
    return left / right


def parse_tree(latex: str):
    result = tree.parse(latex)
    if not result.parsed:
        raise ExprError(result.reason or "unparsed")
    return result.tree


def expression(latex: str):
    node = parse_tree(latex)
    if isinstance(node, tree.Rel):
        raise ExprError("unexpected relation")
    return build(node)


def relation(latex: str):
    """(sol taraf, işleçler, ifadeler). Zincir ilişkiler (a < x < b) korunur."""
    node = parse_tree(latex)
    if not isinstance(node, tree.Rel):
        raise ExprError("expected relation")
    budget = _Budget()
    return node.ops, [build(item, budget) for item in node.operands]


def finite(value) -> bool:
    """NaN/sonsuz/karmaşık olmayan gerçel sayı mı?"""
    try:
        return bool(value.is_real) and bool(value.is_finite)
    except (AttributeError, TypeError):
        return False


def text(value) -> str:
    return sp.sstr(value) if not isinstance(value, str) else value
