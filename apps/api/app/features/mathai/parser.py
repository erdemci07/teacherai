"""Small arithmetic grammar. Build SymPy nodes only from recognized tokens."""

import ast
import re
import sympy as sp


class MathParseError(ValueError):
    pass


def normalize(value: str) -> str:
    if len(value) > 400:
        raise MathParseError("expression too long")
    text = value.strip().strip("$").replace(r"\left", "").replace(r"\right", "")
    for old, new in (
        (r"\cdot", "*"),
        (r"\times", "*"),
        (r"\pm", "±"),
        (r"\,", ""),
        ("−", "-"),
        ("÷", "/"),
    ):
        text = text.replace(old, new)
    for _ in range(5):
        text = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"((\1)/(\2))", text)
        text = re.sub(r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)", text)
    return re.sub(r"\|([^|]+)\|", r"Abs(\1)", text).replace("{", "(").replace("}", ")")


def expression(value):
    text = normalize(value)
    if re.search(r"[A-Za-z]{2,}", text.replace("sqrt", "").replace("Abs", "")):
        raise MathParseError("unknown identifier")
    tokens = re.findall(r"\d+(?:\.\d+)?|sqrt|Abs|[a-zA-Z]|[+*/^()-]", text)
    if not tokens or "".join(tokens) != re.sub(r"\s+", "", text) or len(tokens) > 80:
        raise MathParseError("unsupported expression")
    if (
        any(len(t) > 12 for t in tokens)
        or len({t for t in tokens if len(t) == 1 and t.isalpha()}) > 4
    ):
        raise MathParseError("expression budget")
    parts = []
    prev = ""
    for t in tokens:
        if prev and prev[0].isdigit() and t[0].isdigit():
            raise MathParseError("ambiguous numbers")
        if (
            prev
            and (prev[-1].isalnum() or prev == ")")
            and (t[0].isalnum() or t == "(")
            and prev not in {"sqrt", "Abs"}
        ):
            parts.append("*")
        parts.append("**" if t == "^" else t)
        prev = t
    try:
        tree = ast.parse("".join(parts), mode="eval")
        if sum(1 for _ in ast.walk(tree)) > 100:
            raise MathParseError("tree budget")
        return _build(tree.body)
    except (SyntaxError, RecursionError, ArithmeticError, TypeError) as exc:
        raise MathParseError("invalid arithmetic") from exc


def _build(node):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return sp.Rational(str(node.value))
    if isinstance(node, ast.Name) and len(node.id) == 1:
        return sp.Symbol(node.id, real=True)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        arg = _build(node.operand)
        return -arg if isinstance(node.op, ast.USub) else arg
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and len(node.args) == 1
        and not node.keywords
    ):
        if node.func.id in {"sqrt", "Abs"}:
            return {"sqrt": sp.sqrt, "Abs": sp.Abs}[node.func.id](_build(node.args[0]))
    if isinstance(node, ast.BinOp):
        left, right = _build(node.left), _build(node.right)
        if isinstance(node.op, ast.Pow):
            if not isinstance(right, sp.Integer) or abs(right) > 10 or left.has(sp.Pow):
                raise MathParseError("power budget")
            return sp.Pow(left, right, evaluate=False)
        if isinstance(node.op, ast.Add):
            return sp.Add(left, right, evaluate=False)
        if isinstance(node.op, ast.Sub):
            return sp.Add(left, -right, evaluate=False)
        if isinstance(node.op, ast.Mult):
            return sp.Mul(left, right, evaluate=False)
        if isinstance(node.op, ast.Div) and right.is_zero is not True:
            return sp.Mul(left, sp.Pow(right, -1, evaluate=False), evaluate=False)
    raise MathParseError("unsupported syntax")


def branches(value):
    text = normalize(value)
    if "±" not in text:
        return [text]
    if text.count("±") != 1:
        raise MathParseError("multiple signs")
    return [text.replace("±", sign) for sign in ("+", "-")]


def equation(value):
    text = normalize(value)
    if text.count("=") != 1:
        raise MathParseError("expected equation")
    left, right = text.split("=")
    return sp.Eq(expression(left), expression(right), evaluate=False)


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
