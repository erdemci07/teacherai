"""Okul düzeyi matematik gösterimi için sınırlı, belirlenimci ifade ağacı (TA-003).

Amaç bir bilgisayar cebiri sistemi değil, kaynak yapısını korumaktır: kök kapsamı, kesir payı ve
paydası, üs tabanı ve kapsamı, tekli eksi, gruplama ve fonksiyon argümanı. Ayrıştırıcı
özyinelemeli inişlidir; ``eval``, ``exec``, ``ast.parse`` veya ``sympify`` kullanmaz. Her girdi
uzunluk, token, derinlik, düğüm, sembol ve sayı basamağı sınırlarıyla korunur.

Sonuç üç durumdan biridir:
- ``parsed``: yapı kuruldu.
- ``unsupported``: geçerli olabilecek ama bu dilbilgisinin dışında kalan gösterim (integral, birim, derece…).
  Bu, ifadenin yanlış olduğu anlamına gelmez.
- ``invalid``: yapısal tutarsızlık (dengesiz ayraç, eksik pay/payda, eksik işlenen). Çıkarım hatasına kanıttır.

Ağaç kaynak gösterimini korur (``Group``, ``Frac``, ``Root`` ayrı düğümlerdir). Anlam karşılaştırması
``shape`` ile yapılır; görüntü LaTeX'i ağacın kendisinden üretilir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Literal

MAX_SOURCE_CHARS = 400
MAX_TOKENS = 160
MAX_DEPTH = 32
MAX_NODES = 240
MAX_SYMBOLS = 8
MAX_DIGITS = 15
MAX_EXACT_EXPONENT = 10
MAX_EXACT_BITS = 256

FUNCTIONS = {"sin", "cos", "tan", "cot", "log", "ln"}
LATEX_RELATIONS = {"le": "<=", "leq": "<=", "ge": ">=", "geq": ">=", "ne": "!=", "neq": "!=", "lt": "<", "gt": ">"}
LATEX_OPERATORS = {"cdot": "*", "times": "*", "div": "/", "pm": "±"}
LATEX_BARS = {"lvert", "rvert", "vert", "mid"}


# --------------------------------------------------------------------------- düğümler


@dataclass(frozen=True)
class Num:
    value: Fraction
    text: str = field(compare=False)
    integer: bool = field(default=True, compare=False)


@dataclass(frozen=True)
class Sym:
    name: str
    sub: str | None = None


@dataclass(frozen=True)
class Const:
    name: Literal["pi"]


@dataclass(frozen=True)
class Neg:
    arg: "Node"


@dataclass(frozen=True)
class Bin:
    op: Literal["+", "-", "±", "*", "/"]
    left: "Node"
    right: "Node"
    implicit: bool = field(default=False, compare=False)


@dataclass(frozen=True)
class Frac:
    num: "Node"
    den: "Node"


@dataclass(frozen=True)
class Mixed:
    whole: int
    num: int
    den: int


@dataclass(frozen=True)
class Pow:
    base: "Node"
    exp: "Node"


@dataclass(frozen=True)
class Root:
    radicand: "Node"
    index: "Node | None" = None


@dataclass(frozen=True)
class Abs:
    arg: "Node"


@dataclass(frozen=True)
class Group:
    arg: "Node"
    delim: str = field(default="(", compare=False)


@dataclass(frozen=True)
class Func:
    name: str
    arg: "Node"
    base: "Node | None" = None
    parens: bool = field(default=True, compare=False)


@dataclass(frozen=True)
class Rel:
    ops: tuple[str, ...]
    operands: tuple["Node", ...]


Node = Num | Sym | Const | Neg | Bin | Frac | Mixed | Pow | Root | Abs | Group | Func | Rel


@dataclass(frozen=True)
class Note:
    rule: str
    original: str
    normalized: str


@dataclass(frozen=True)
class Ambiguity:
    category: Literal["decimal", "exponent_scope"]
    readings: tuple[str, str]


@dataclass(frozen=True)
class ParseResult:
    source: str
    status: Literal["parsed", "unsupported", "invalid"]
    tree: Node | None = None
    reason: str | None = None
    notes: tuple[Note, ...] = ()
    ambiguity: Ambiguity | None = None

    @property
    def parsed(self) -> bool:
        return self.status == "parsed"

    def canonical(self) -> str | None:
        return canonical(self.tree) if self.tree is not None else None

    def latex(self) -> str | None:
        return to_latex(self.tree) if self.tree is not None else None


class _Unsupported(Exception):
    pass


class _Invalid(Exception):
    pass


# --------------------------------------------------------------------------- normalleştirme

_CHAR_RULES = (
    ("−", "-", "unicode_minus"),
    ("–", "-", "dash_as_minus"),
    ("‒", "-", "dash_as_minus"),
    ("‐", "-", "dash_as_minus"),
    ("×", "*", "multiplication_sign"),
    ("·", "*", "multiplication_sign"),
    ("∙", "*", "multiplication_sign"),
    ("⋅", "*", "multiplication_sign"),
    ("✕", "*", "multiplication_sign"),
    ("÷", "/", "division_sign"),
    ("≤", "<=", "unicode_relation"),
    ("⩽", "<=", "unicode_relation"),
    ("≥", ">=", "unicode_relation"),
    ("⩾", ">=", "unicode_relation"),
    ("≠", "!=", "unicode_relation"),
    ("√", "\\sqrt ", "unicode_root"),
    ("∛", "\\sqrt[3] ", "unicode_root"),
    ("π", "\\pi ", "unicode_constant"),
)
_SUPERSCRIPTS = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9", "⁻": "-", "⁺": "+"}
_LATEX_SPACING = ("\\,", "\\;", "\\:", "\\!", "\\ ", "~")


def normalize(value: str) -> tuple[str, list[Note]]:
    """Anlamı koruyan karakter dönüşümleri. Her dönüşüm not olarak kaydedilir."""
    notes: list[Note] = []
    text = value.strip()
    for delimiter in (("\\(", "\\)"), ("\\[", "\\]"), ("$$", "$$"), ("$", "$")):
        if text.startswith(delimiter[0]) and text.endswith(delimiter[1]) and len(text) > len(delimiter[0]) + len(delimiter[1]):
            text = text[len(delimiter[0]):-len(delimiter[1])].strip()
            break
    for old, new, rule in _CHAR_RULES:
        if old in text:
            notes.append(Note(rule, old, new.strip()))
            text = text.replace(old, new)
    if any(ch in _SUPERSCRIPTS for ch in text):
        out, run = [], []
        for ch in text + "\0":
            if ch in _SUPERSCRIPTS:
                run.append(ch)
                continue
            if run:
                converted = "^{" + "".join(_SUPERSCRIPTS[c] for c in run) + "}"
                notes.append(Note("superscript_digit", "".join(run), converted))
                out.append(converted)
                run = []
            if ch != "\0":
                out.append(ch)
        text = "".join(out)
    for spacing in _LATEX_SPACING:
        if spacing in text:
            notes.append(Note("latex_spacing", spacing, " "))
            text = text.replace(spacing, " ")
    for variant in ("\\dfrac", "\\tfrac"):
        if variant in text:
            notes.append(Note("latex_fraction_variant", variant, "\\frac"))
            text = text.replace(variant, "\\frac")
    return text, notes


# --------------------------------------------------------------------------- tokenleştirme


@dataclass(frozen=True)
class _Tok:
    kind: str  # num sym const op rel lparen rparen lbrace rbrace lbracket rbracket bar frac sqrt func comma bang under caret
    text: str
    value: object = None


def _comma_decimals(text: str) -> tuple[bool, str | None]:
    """Virgülün ondalık ayırıcı olup olmadığına bağlamdan karar verir.

    Döner: (virgül ondalık mı, belirsiz okuma). Virgül yalnızca rakamlar arasında geçiyorsa ondalıktır.
    "1,250" gibi üç basamaklı kesirli kısım binlik ayırıcıyla karışabileceğinden belirsizdir.
    """
    import re

    if "," not in text:
        return False, None
    plain = text.replace("{,}", ",")
    # "(2,3)" veya "[1,4]" nokta ya da aralık olabilir; ondalık sayılmaz.
    if re.search(r"[(\[]\s*-?\d+,\d+\s*[)\]]", text):
        return False, None
    separators = [m.start() for m in re.finditer(",", plain)]
    decimal = [m for m in re.finditer(r"(\d+),(\d+)", plain)]
    if len(decimal) != len(separators):
        return False, None
    for match in decimal:
        whole, fraction = match.group(1), match.group(2)
        if len(fraction) == 3 and whole != "0":
            return True, match.group(0)
    return True, None


def _tokenize(text: str, notes: list[Note]) -> tuple[list[_Tok], bool, str | None]:
    comma_decimal, ambiguous_decimal = _comma_decimals(text)
    tokens: list[_Tok] = []
    latex_context = "\\" in text
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch.isdigit() or (ch == "." and i + 1 < n and text[i + 1].isdigit()):
            j = i
            while j < n and text[j].isdigit():
                j += 1
            integer = True
            if j < n and text[j] == "." and j + 1 < n and text[j + 1].isdigit():
                integer = False
                j += 1
                while j < n and text[j].isdigit():
                    j += 1
            elif comma_decimal and j + 1 < n and text[j] == "," and text[j + 1].isdigit():
                notes.append(Note("decimal_comma", text[i:j + 1 + _digit_run(text, j + 1)], text[i:j] + "." + text[j + 1:j + 1 + _digit_run(text, j + 1)]))
                integer = False
                j += 1
                while j < n and text[j].isdigit():
                    j += 1
            elif comma_decimal and text.startswith("{,}", j) and j + 3 < n and text[j + 3].isdigit():
                integer = False
                j += 3
                while j < n and text[j].isdigit():
                    j += 1
            raw = text[i:j]
            digits = sum(c.isdigit() for c in raw)
            if digits > MAX_DIGITS:
                raise _Unsupported("numeric_literal_budget")
            normalized = raw.replace("{,}", ".").replace(",", ".")
            tokens.append(_Tok("num", raw, (Fraction(normalized), integer)))
            i = j
            continue
        if ch.isalpha():
            j = i
            while j < n and text[j].isalpha():
                j += 1
            word = text[i:j]
            if word in FUNCTIONS:
                tokens.append(_Tok("func", word))
            elif word == "sqrt":
                tokens.append(_Tok("sqrt", word, "plain"))
            elif word in {"abs", "Abs"}:
                tokens.append(_Tok("func", "abs"))
            elif word == "pi":
                tokens.append(_Tok("const", "pi"))
            elif len(word) == 1:
                tokens.append(_Tok("sym", word))
            else:
                raise _Unsupported("multi_letter_identifier")
            i = j
            continue
        if ch == "\\":
            j = i + 1
            while j < n and text[j].isalpha():
                j += 1
            command = text[i + 1:j]
            if not command:
                if j < n and text[j] in "{}":
                    raise _Unsupported("latex_set_braces")
                raise _Unsupported("latex_command")
            i = j
            if command in {"left", "right", "big", "Big", "bigl", "bigr"}:
                continue
            if command == "frac":
                tokens.append(_Tok("frac", command))
            elif command == "sqrt":
                tokens.append(_Tok("sqrt", command, "latex"))
            elif command in FUNCTIONS:
                tokens.append(_Tok("func", command))
            elif command == "pi":
                tokens.append(_Tok("const", "pi"))
            elif command in LATEX_RELATIONS:
                tokens.append(_Tok("rel", LATEX_RELATIONS[command]))
            elif command in LATEX_OPERATORS:
                tokens.append(_Tok("op", LATEX_OPERATORS[command], command))
            elif command in LATEX_BARS:
                tokens.append(_Tok("bar", "|"))
            else:
                raise _Unsupported("latex_command")
            continue
        two = text[i:i + 2]
        if two in {"<=", ">=", "!="}:
            tokens.append(_Tok("rel", two))
            i += 2
            continue
        simple = {
            "+": ("op", "+"), "-": ("op", "-"), "*": ("op", "*"), "/": ("op", "/"), "±": ("op", "±"),
            "=": ("rel", "="), "<": ("rel", "<"), ">": ("rel", ">"), "(": ("lparen", "("), ")": ("rparen", ")"),
            "[": ("lbracket", "["), "]": ("rbracket", "]"), "{": ("lbrace", "{"), "}": ("rbrace", "}"),
            "|": ("bar", "|"), ",": ("comma", ","), "!": ("bang", "!"), "_": ("under", "_"), "^": ("caret", "^"),
        }
        if ch in simple:
            kind, value = simple[ch]
            tokens.append(_Tok(kind, value))
            i += 1
            continue
        raise _Unsupported("unsupported_symbol")
        # (ulaşılmaz)
    if len(tokens) > MAX_TOKENS:
        raise _Unsupported("token_budget")
    return tokens, latex_context, ambiguous_decimal


def _digit_run(text: str, start: int) -> int:
    j = start
    while j < len(text) and text[j].isdigit():
        j += 1
    return j - start


# --------------------------------------------------------------------------- ayrıştırıcı


class _Parser:
    def __init__(self, tokens: list[_Tok], latex_context: bool):
        self.tokens = tokens
        self.pos = 0
        self.depth = 0
        self.nodes = 0
        self.symbols: set[tuple[str, str | None]] = set()
        self.latex_context = latex_context
        self.abs_depth = 0
        self.exponent_ambiguity: tuple[str, str] | None = None

    # yardımcılar
    def peek(self, offset: int = 0) -> _Tok | None:
        index = self.pos + offset
        return self.tokens[index] if index < len(self.tokens) else None

    def take(self) -> _Tok:
        token = self.peek()
        if token is None:
            raise _Invalid("operand_missing")
        self.pos += 1
        return token

    def expect(self, kind: str, reason: str) -> _Tok:
        token = self.peek()
        if token is None or token.kind != kind:
            raise _Invalid(reason)
        self.pos += 1
        return token

    def node(self, value: Node) -> Node:
        self.nodes += 1
        if self.nodes > MAX_NODES:
            raise _Unsupported("node_budget")
        return value

    def enter(self):
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise _Unsupported("depth_budget")

    def leave(self):
        self.depth -= 1

    # dilbilgisi
    def parse(self) -> Node:
        tree = self.relation()
        if self.peek() is not None:
            token = self.peek()
            if token.kind in {"rparen", "rbracket", "rbrace", "bar"}:
                raise _Invalid("unbalanced_delimiter")
            if token.kind == "comma":
                raise _Unsupported("list_or_tuple")
            raise _Invalid("unexpected_token")
        return tree

    def relation(self) -> Node:
        operands = [self.sum()]
        ops: list[str] = []
        while (token := self.peek()) is not None and token.kind == "rel":
            ops.append(self.take().text)
            operands.append(self.sum())
            if len(ops) > 2:
                raise _Unsupported("relation_chain")
        if not ops:
            return operands[0]
        if len(ops) == 2 and not ({ops[0], ops[1]} <= {"<", "<="} or {ops[0], ops[1]} <= {">", ">="}):
            raise _Invalid("relation_chain_direction")
        return self.node(Rel(tuple(ops), tuple(operands)))

    def sum(self) -> Node:
        left = self.term()
        while (token := self.peek()) is not None and token.kind == "op" and token.text in {"+", "-", "±"}:
            op = self.take().text
            right = self.term()
            left = self.node(Bin(op, left, right))  # type: ignore[arg-type]
        return left

    def _starts_operand(self, token: _Tok | None) -> bool:
        if token is None:
            return False
        if token.kind == "bar":
            return self.abs_depth == 0
        return token.kind in {"num", "sym", "const", "lparen", "lbracket", "frac", "sqrt", "func"} or (
            token.kind == "lbrace" and self.latex_context
        )

    def term(self) -> Node:
        left = self.unary()
        while True:
            token = self.peek()
            if token is not None and token.kind == "op" and token.text in {"*", "/"}:
                op = self.take().text
                right = self.unary()
                left = self.node(Bin(op, left, right))  # type: ignore[arg-type]
                continue
            if self._starts_operand(token):
                if isinstance(left, Num) and token.kind == "frac":
                    mixed = self._mixed(left)
                    if mixed is not None:
                        left = mixed
                        continue
                right = self.power()
                if isinstance(_rightmost(left), Num) and isinstance(_leftmost(right), Num):
                    raise _Invalid("adjacent_numbers")
                left = self.node(Bin("*", left, right, implicit=True))
                continue
            return left

    def _mixed(self, whole: Num) -> Node | None:
        """Tam sayılı kesir: 2\\frac{1}{3} okul gösteriminde 2 + 1/3 anlamına gelir."""
        saved = self.pos
        if not whole.integer:
            return None
        self.take()
        if not (self.peek() and self.peek().kind == "lbrace"):
            self.pos = saved
            return None
        try:
            self.take()
            num = self.expect("num", "fraction_operand_missing")
            self.expect("rbrace", "fraction_operand_missing")
            self.expect("lbrace", "fraction_operand_missing")
            den = self.expect("num", "fraction_operand_missing")
            self.expect("rbrace", "fraction_operand_missing")
        except _Invalid:
            self.pos = saved
            return None
        n_value, n_int = num.value  # type: ignore[misc]
        d_value, d_int = den.value  # type: ignore[misc]
        if not (n_int and d_int) or not (0 < n_value < d_value):
            self.pos = saved
            return None
        return self.node(Mixed(int(whole.value), int(n_value), int(d_value)))

    def unary(self) -> Node:
        token = self.peek()
        if token is not None and token.kind == "op" and token.text in {"-", "+"}:
            self.take()
            self.enter()
            try:
                operand = self.unary()
            finally:
                self.leave()
            return self.node(Neg(operand)) if token.text == "-" else operand
        return self.power()

    def power(self) -> Node:
        base = self.postfix()
        if (token := self.peek()) is not None and token.kind == "caret":
            self.take()
            exponent = self.exponent()
            return self.node(Pow(base, exponent))
        return base

    def exponent(self) -> Node:
        token = self.peek()
        if token is None:
            raise _Invalid("exponent_missing")
        if token.kind == "lbrace":
            return self.braced("exponent_missing")
        if token.kind == "op" and token.text == "-":
            self.take()
            return self.node(Neg(self.exponent()))
        if token.kind == "num" and self.latex_context and len(token.text) > 1 and token.text.isdigit():
            self.exponent_ambiguity = (token.text[0], token.text)
        self.enter()
        try:
            return self.power()
        finally:
            self.leave()

    def postfix(self) -> Node:
        atom = self.atom()
        if (token := self.peek()) is not None and token.kind == "bang":
            raise _Unsupported("factorial")
        return atom

    def braced(self, reason: str) -> Node:
        self.expect("lbrace", reason)
        if self.peek() is not None and self.peek().kind == "rbrace":
            raise _Invalid(reason)
        self.enter()
        try:
            inner = self.relation()
        finally:
            self.leave()
        self.expect("rbrace", "unbalanced_delimiter")
        return inner

    def atom(self) -> Node:
        token = self.peek()
        if token is None:
            raise _Invalid("operand_missing")
        kind = token.kind
        if kind == "num":
            self.take()
            value, integer = token.value  # type: ignore[misc]
            return self.node(Num(value, token.text, integer))
        if kind == "sym":
            self.take()
            sub = None
            if self.peek() is not None and self.peek().kind == "under":
                self.take()
                sub = self._subscript()
            self.symbols.add((token.text, sub))
            if len(self.symbols) > MAX_SYMBOLS:
                raise _Unsupported("symbol_budget")
            return self.node(Sym(token.text, sub))
        if kind == "const":
            self.take()
            return self.node(Const("pi"))
        if kind in {"lparen", "lbracket"}:
            self.take()
            closing = "rparen" if kind == "lparen" else "rbracket"
            if self.peek() is not None and self.peek().kind == closing:
                raise _Invalid("empty_group")
            self.enter()
            saved_abs, self.abs_depth = self.abs_depth, 0
            try:
                inner = self.relation()
            finally:
                self.abs_depth = saved_abs
                self.leave()
            if self.peek() is not None and self.peek().kind == "comma":
                raise _Unsupported("list_or_tuple")
            self.expect(closing, "unbalanced_delimiter")
            return self.node(Group(inner, token.text))
        if kind == "lbrace":
            inner = self.braced("empty_group")
            return self.node(Group(inner, "{"))
        if kind == "bar":
            self.take()
            self.enter()
            self.abs_depth += 1
            try:
                inner = self.sum()
            finally:
                self.abs_depth -= 1
                self.leave()
            self.expect("bar", "unbalanced_delimiter")
            return self.node(Abs(inner))
        if kind == "frac":
            self.take()
            if not (self.peek() and self.peek().kind == "lbrace"):
                raise _Invalid("fraction_operand_missing")
            num = self.braced("fraction_operand_missing")
            if not (self.peek() and self.peek().kind == "lbrace"):
                raise _Invalid("fraction_operand_missing")
            den = self.braced("fraction_operand_missing")
            return self.node(Frac(num, den))
        if kind == "sqrt":
            self.take()
            index = None
            if self.peek() is not None and self.peek().kind == "lbracket":
                self.take()
                self.enter()
                try:
                    index = self.sum()
                finally:
                    self.leave()
                self.expect("rbracket", "unbalanced_delimiter")
            follow = self.peek()
            if follow is None:
                raise _Invalid("radicand_missing")
            if follow.kind == "lbrace":
                radicand = self.braced("radicand_missing")
            elif token.value == "plain" and follow.kind != "lparen":
                raise _Invalid("radicand_missing")
            elif follow.kind == "lparen":
                group = self.atom()
                radicand = group.arg if isinstance(group, Group) else group
            elif follow.kind in {"num", "sym", "const", "sqrt", "func", "frac", "bar"}:
                radicand = self.atom()
            else:
                raise _Invalid("radicand_missing")
            return self.node(Root(radicand, index))
        if kind == "func":
            self.take()
            name = token.text
            base = None
            power = None
            if name == "log" and self.peek() is not None and self.peek().kind == "under":
                self.take()
                base = self.braced("operand_missing") if self.peek() and self.peek().kind == "lbrace" else self.atom()
            if name != "abs" and self.peek() is not None and self.peek().kind == "caret":
                self.take()
                power = self.exponent()
            follow = self.peek()
            if follow is None:
                raise _Invalid("function_argument_missing")
            if follow.kind in {"lparen", "lbracket"}:
                group = self.atom()
                arg = group.arg if isinstance(group, Group) else group
                parens = True
            else:
                if name == "abs":
                    raise _Invalid("function_argument_missing")
                self.enter()
                try:
                    arg = self.power()
                finally:
                    self.leave()
                parens = False
            result: Node = self.node(Abs(arg)) if name == "abs" else self.node(Func(name, arg, base, parens))
            return self.node(Pow(result, power)) if power is not None else result
        if kind in {"rparen", "rbracket", "rbrace"}:
            raise _Invalid("unbalanced_delimiter")
        if kind == "comma":
            raise _Unsupported("list_or_tuple")
        raise _Invalid("operand_missing")

    def _subscript(self) -> str:
        token = self.peek()
        if token is None:
            raise _Invalid("subscript_missing")
        if token.kind == "lbrace":
            self.take()
            parts = []
            while self.peek() is not None and self.peek().kind in {"num", "sym"}:
                parts.append(self.take().text)
            self.expect("rbrace", "unbalanced_delimiter")
            text = "".join(parts)
        elif token.kind in {"num", "sym"}:
            text = self.take().text
        else:
            raise _Invalid("subscript_missing")
        if not text or len(text) > 4:
            raise _Unsupported("subscript_budget")
        return text


def _leftmost(node: Node) -> Node:
    while isinstance(node, Bin):
        node = node.left
    return node


def _rightmost(node: Node) -> Node:
    while isinstance(node, Bin):
        node = node.right
    return node


def parse(value: str) -> ParseResult:
    """Kaynak gösterimi ayrıştırır. Asla istisna yaymaz; durum ve neden döndürür."""
    source = value if isinstance(value, str) else ""
    if not source.strip():
        return ParseResult(source, "invalid", reason="empty")
    if len(source) > MAX_SOURCE_CHARS:
        return ParseResult(source, "unsupported", reason="length_budget")
    text, notes = normalize(source)
    try:
        tokens, latex_context, ambiguous_decimal = _tokenize(text, notes)
        if not tokens:
            return ParseResult(source, "invalid", reason="empty", notes=tuple(notes))
        parser = _Parser(tokens, latex_context)
        tree = parser.parse()
    except _Unsupported as exc:
        return ParseResult(source, "unsupported", reason=str(exc), notes=tuple(notes))
    except _Invalid as exc:
        return ParseResult(source, "invalid", reason=str(exc), notes=tuple(notes))
    except RecursionError:
        return ParseResult(source, "unsupported", reason="depth_budget", notes=tuple(notes))
    ambiguity = None
    if ambiguous_decimal:
        whole, fraction = ambiguous_decimal.split(",")
        ambiguity = Ambiguity("decimal", (f"{whole}.{fraction}", f"{whole}{fraction}"))
    elif parser.exponent_ambiguity:
        first, full = parser.exponent_ambiguity
        ambiguity = Ambiguity("exponent_scope", (f"^{{{first}}}{full[1:]}", f"^{{{full}}}"))
    return ParseResult(source, "parsed", tree, notes=tuple(notes), ambiguity=ambiguity)


# --------------------------------------------------------------------------- anlam şekli


def shape(node: Node) -> Node:
    """Gruplamayı ağaç yapısına gömülü olduğu için atar; Frac ve tam sayılı kesir bölmeye eşlenir.

    İki ifadenin ``shape`` değeri eşitse aynı matematiksel yapıyı taşırlar. Değer eşitliği ayrıca
    ``exact_value`` veya SymPy ile denetlenir.
    """
    if isinstance(node, Group):
        return shape(node.arg)
    if isinstance(node, Frac):
        return Bin("/", shape(node.num), shape(node.den))
    if isinstance(node, Mixed):
        return Bin("+", Num(Fraction(node.whole), str(node.whole)), Bin("/", Num(Fraction(node.num), str(node.num)), Num(Fraction(node.den), str(node.den))))
    if isinstance(node, Neg):
        return Neg(shape(node.arg))
    if isinstance(node, Bin):
        return Bin(node.op, shape(node.left), shape(node.right))
    if isinstance(node, Pow):
        return Pow(shape(node.base), shape(node.exp))
    if isinstance(node, Root):
        index = shape(node.index) if node.index is not None else None
        if isinstance(index, Num) and index.value == 2:
            index = None
        return Root(shape(node.radicand), index)
    if isinstance(node, Abs):
        return Abs(shape(node.arg))
    if isinstance(node, Func):
        return Func(node.name, shape(node.arg), shape(node.base) if node.base is not None else None)
    if isinstance(node, Rel):
        return Rel(node.ops, tuple(shape(item) for item in node.operands))
    return node


def same_structure(left: Node, right: Node) -> bool:
    return shape(left) == shape(right)


# --------------------------------------------------------------------------- yazdırma

_PREC = {"rel": 0, "sum": 1, "product": 2, "neg": 3, "pow": 4, "atom": 5}


def _prec(node: Node) -> int:
    if isinstance(node, Rel):
        return _PREC["rel"]
    if isinstance(node, Bin):
        return _PREC["sum"] if node.op in {"+", "-", "±"} else _PREC["product"]
    if isinstance(node, Neg):
        return _PREC["neg"]
    if isinstance(node, Pow):
        return _PREC["pow"]
    return _PREC["atom"]


def _num_text(node: Num) -> str:
    if node.value.denominator == 1 and node.integer:
        return str(node.value.numerator)
    return node.text.replace("{,}", ".").replace(",", ".")


def canonical(node: Node) -> str:
    """Belirlenimci ASCII biçim. Gruplama, kaynak ayraçlarından değil ağaç yapısından gelir."""
    return _canon(shape(node))


def _wrap(node: Node, needed: bool) -> str:
    text = _canon(node)
    return f"({text})" if needed else text


def _canon(node: Node) -> str:
    if isinstance(node, Num):
        return _num_text(node)
    if isinstance(node, Sym):
        return node.name + (f"_{node.sub}" if node.sub else "")
    if isinstance(node, Const):
        return "pi"
    if isinstance(node, Neg):
        return "-" + _wrap(node.arg, _prec(node.arg) < _PREC["atom"])
    if isinstance(node, Bin):
        if node.op in {"+", "-", "±"}:
            left = _wrap(node.left, _prec(node.left) < _PREC["sum"])
            # Sol birleşmeli işlemlerde sağdaki aynı öncelikli alt ağaç parantezlenir; aksi halde gruplama değişir.
            right = _wrap(node.right, _prec(node.right) <= _PREC["sum"])
            return f"{left} {node.op} {right}"
        left = _wrap(node.left, _prec(node.left) < _PREC["product"])
        right_needs = _prec(node.right) <= _PREC["product"] or isinstance(node.right, Neg)
        right = _wrap(node.right, right_needs)
        return f"{left}/{right}" if node.op == "/" else f"{left} * {right}"
    if isinstance(node, Pow):
        base = _wrap(node.base, _prec(node.base) <= _PREC["pow"])
        exponent = _wrap(node.exp, _prec(node.exp) < _PREC["pow"])
        return f"{base}^{exponent}"
    if isinstance(node, Root):
        if node.index is None:
            return f"sqrt({_canon(node.radicand)})"
        return f"sqrt[{_canon(node.index)}]({_canon(node.radicand)})"
    if isinstance(node, Abs):
        return f"|{_canon(node.arg)}|"
    if isinstance(node, Func):
        base = f"_({_canon(node.base)})" if node.base is not None else ""
        return f"{node.name}{base}({_canon(node.arg)})"
    if isinstance(node, Rel):
        parts = [_canon(node.operands[0])]
        for op, operand in zip(node.ops, node.operands[1:]):
            parts.append(f" {op} {_canon(operand)}")
        return "".join(parts)
    raise TypeError(type(node).__name__)


_LATEX_REL = {"=": "=", "<": "<", ">": ">", "<=": "\\le", ">=": "\\ge", "!=": "\\ne"}


def to_latex(node: Node) -> str:
    """Görüntü LaTeX'i ağaçtan üretilir; kesir, kök ve ayraçlar kaynak gösterimindeki gibi kalır."""
    if isinstance(node, Num):
        if not node.integer and ("," in node.text):
            return node.text.replace("{,}", ",").replace(",", "{,}")
        return _num_text(node)
    if isinstance(node, Sym):
        return node.name + (f"_{{{node.sub}}}" if node.sub else "")
    if isinstance(node, Const):
        return "\\pi"
    if isinstance(node, Neg):
        inner = to_latex(node.arg)
        if _prec(node.arg) < _PREC["neg"]:
            inner = f"\\left({inner}\\right)"
        return "-" + inner
    if isinstance(node, Bin):
        left, right = to_latex(node.left), to_latex(node.right)
        if node.op in {"+", "-"}:
            return f"{left} {node.op} {right}"
        if node.op == "±":
            return f"{left} \\pm {right}"
        if node.op == "/":
            return f"{left} / {right}"
        if node.implicit:
            return f"{left} {right}"
        return f"{left} \\cdot {right}"
    if isinstance(node, Frac):
        return f"\\frac{{{to_latex(node.num)}}}{{{to_latex(node.den)}}}"
    if isinstance(node, Mixed):
        return f"{node.whole}\\frac{{{node.num}}}{{{node.den}}}"
    if isinstance(node, Pow):
        if isinstance(node.base, Func) and not node.base.parens and _prec(node.base.arg) >= _PREC["pow"]:
            # \sin^{2} x: üs fonksiyona aittir; "\sin x^{2}" anlamı değiştirirdi.
            fn = node.base
            sub = f"_{{{to_latex(fn.base)}}}" if fn.base is not None else ""
            return f"\\{fn.name}{sub}^{{{to_latex(node.exp)}}} {to_latex(fn.arg)}"
        base = to_latex(node.base)
        if isinstance(node.base, Func) and not node.base.parens:
            base = f"\\left({base}\\right)"
        elif _prec(node.base) <= _PREC["pow"] and not isinstance(node.base, Group):
            base = f"\\left({base}\\right)"
        return f"{base}^{{{to_latex(node.exp)}}}"
    if isinstance(node, Root):
        index = f"[{to_latex(node.index)}]" if node.index is not None else ""
        return f"\\sqrt{index}{{{to_latex(node.radicand)}}}"
    if isinstance(node, Abs):
        return f"\\left|{to_latex(node.arg)}\\right|"
    if isinstance(node, Group):
        inner = to_latex(node.arg)
        if node.delim == "{":
            return f"{{{inner}}}"
        if node.delim == "[":
            return f"\\left[{inner}\\right]"
        return f"\\left({inner}\\right)"
    if isinstance(node, Func):
        base = f"_{{{to_latex(node.base)}}}" if node.base is not None else ""
        arg = to_latex(node.arg)
        if node.parens or _prec(node.arg) < _PREC["pow"]:
            return f"\\{node.name}{base}\\left({arg}\\right)"
        return f"\\{node.name}{base} {arg}"
    if isinstance(node, Rel):
        parts = [to_latex(node.operands[0])]
        for op, operand in zip(node.ops, node.operands[1:]):
            parts.append(f" {_LATEX_REL[op]} {to_latex(operand)}")
        return "".join(parts)
    raise TypeError(type(node).__name__)


# --------------------------------------------------------------------------- kesin değer


def _bounded(value: Fraction) -> Fraction:
    if value.numerator.bit_length() > MAX_EXACT_BITS or value.denominator.bit_length() > MAX_EXACT_BITS:
        raise ArithmeticError("exact_budget")
    return value


def _exact_root(value: Fraction, index: int) -> Fraction | None:
    if value < 0:
        if index % 2 == 0:
            return None
        root = _exact_root(-value, index)
        return -root if root is not None else None

    def integer_root(n: int) -> int | None:
        if n < 2:
            return n
        guess = int(round(n ** (1.0 / index)))
        for candidate in (guess - 1, guess, guess + 1):
            if candidate >= 0 and candidate ** index == n:
                return candidate
        return None

    num, den = integer_root(value.numerator), integer_root(value.denominator)
    return Fraction(num, den) if num is not None and den is not None else None


def exact_value(node: Node) -> Fraction | None:
    """Sembolsüz ve rasyonel değerli ağaçlar için kesin değer; aksi halde None.

    Yalnızca saf Python ``Fraction`` kullanılır ve üs ile bit uzunluğu sınırlıdır. SymPy gerektirmez.
    """
    try:
        return _exact(node)
    except (ArithmeticError, ZeroDivisionError, OverflowError, ValueError):
        return None


def _exact(node: Node) -> Fraction | None:
    if isinstance(node, Num):
        return node.value
    if isinstance(node, Group):
        return _exact(node.arg)
    if isinstance(node, Neg):
        value = _exact(node.arg)
        return -value if value is not None else None
    if isinstance(node, Mixed):
        return Fraction(node.whole) + Fraction(node.num, node.den)
    if isinstance(node, (Bin, Frac)):
        op = "/" if isinstance(node, Frac) else node.op
        left = _exact(node.num if isinstance(node, Frac) else node.left)
        right = _exact(node.den if isinstance(node, Frac) else node.right)
        if left is None or right is None or op == "±":
            return None
        if op == "+":
            return _bounded(left + right)
        if op == "-":
            return _bounded(left - right)
        if op == "*":
            return _bounded(left * right)
        if right == 0:
            return None
        return _bounded(left / right)
    if isinstance(node, Pow):
        base, exponent = _exact(node.base), _exact(node.exp)
        if base is None or exponent is None or exponent.denominator != 1 or abs(exponent) > MAX_EXACT_EXPONENT:
            return None
        if base == 0 and exponent < 0:
            return None
        return _bounded(base ** int(exponent))
    if isinstance(node, Root):
        radicand = _exact(node.radicand)
        index = _exact(node.index) if node.index is not None else Fraction(2)
        if radicand is None or index is None or index.denominator != 1 or not 2 <= index <= MAX_EXACT_EXPONENT:
            return None
        return _exact_root(radicand, int(index))
    if isinstance(node, Abs):
        value = _exact(node.arg)
        return abs(value) if value is not None else None
    return None


def symbols(node: Node) -> set[str]:
    found: set[str] = set()

    def walk(item: Node | None):
        if item is None:
            return
        if isinstance(item, Sym):
            found.add(item.name + (f"_{item.sub}" if item.sub else ""))
        for child in _children(item):
            walk(child)

    walk(node)
    return found


def _children(node: Node) -> tuple[Node, ...]:
    if isinstance(node, (Neg, Abs, Group)):
        return (node.arg,)
    if isinstance(node, Bin):
        return (node.left, node.right)
    if isinstance(node, Frac):
        return (node.num, node.den)
    if isinstance(node, Pow):
        return (node.base, node.exp)
    if isinstance(node, Root):
        return (node.radicand,) + ((node.index,) if node.index is not None else ())
    if isinstance(node, Func):
        return (node.arg,) + ((node.base,) if node.base is not None else ())
    if isinstance(node, Rel):
        return node.operands
    return ()


def equivalent_readings(left: ParseResult, right: ParseResult) -> bool:
    """İki okuma aynı yapıda mı, ya da sembolsüz ve kesin olarak aynı değerde mi?

    Farklı gruplamadaki ifadeler (``sqrt(5 + sqrt(9))`` ile ``sqrt(5) + sqrt(9)``) eşit sayılmaz,
    meğer ki ikisi de sembolsüz olup kesin değerleri aynı olsun. Bu durumda okuma farkı cevabı
    etkilemez.
    """
    if not (left.parsed and right.parsed):
        return False
    if same_structure(left.tree, right.tree):
        return True
    if isinstance(left.tree, Rel) or isinstance(right.tree, Rel):
        return False
    a, b = exact_value(left.tree), exact_value(right.tree)
    return a is not None and b is not None and a == b
