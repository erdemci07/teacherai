"""Belirteç (token) düzeyinde alıntı eşleme (TA-009 §3.1). Saf Python; SymPy veya sağlayıcı yoktur.

Üç ayrı soru ayrı yanıtlanır ve biri diğerinin kanıtı sayılmaz:

1. **Alıntı kaynakta var mı?** Belirteç dizisi olarak, sınırlarına saygıyla: ``5 cm`` alıntısı ``15 cm`` içinde
   bulunmaz; ``AB`` etiketi ``ABC`` içinde bulunmaz.
2. **Alıntı iddiayı ileri sürüyor mu?** Bir yan cümle içinde varlık etiketi ile değer arasında başka etiket yoksa
   ve yan cümle soru veya olumsuzlama değilse. ``AB kaç cm'dir?`` AB'den söz eder ama bir değer ileri sürmez;
   ``AB ≠ AC`` veya ``AB, AC'ye eşit değildir`` bir eşitlik ileri sürmez.
3. **Anlamsal gerektirme** bu modülün kapsamı dışındadır: yapısal eşleşme, cümlenin anlamının olguyu
   gerektirdiğini kanıtlamaz. Bu yüzden kabul edilen olgu yalnız ``exact_quote`` düzeyindedir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

MAX_TOKENS = 4000
_UPPER, _LOWER = "A-ZÇĞİÖŞÜ", "a-zçğıöşüâîû"
_TOKEN = re.compile(
    rf"[0-9]+(?:[.,][0-9]+)?"                             # sayı (yalnız ASCII rakam; ² gibi üst simgeler sayı değil)
    rf"|[{_UPPER}][{_LOWER}]+"                            # büyük harfle başlayan sözcük (Şekildeki, Ali)
    rf"|[{_UPPER}](?:_\{{?\d+\}}?)?(?:[{_UPPER}](?:_\{{?\d+\}}?)?)*"  # nokta etiketi dizisi (B, AB, ABC, P_1)
    rf"|[{_LOWER}]+"                                      # sözcük
    r"|\S"                                                # tek simge
)
NEGATION = {"değil", "değildir", "değildi", "olmayan", "olmaz", "olmadığı", "olmadığına", "hariç", "yoktur"}
NEGATION_SYMBOLS = {"≠"}
QUESTION = {"kaç", "kaçtır", "nedir", "hangisi", "hangisidir", "bulunuz", "bulun", "hesaplayınız", "hesaplayın",
            "kaçta", "kaçıncı"}
CLAUSE_BREAK = {",", ";", ".", "?", ":", "ise", "ve", "iken", "olduğuna", "göre"}
APOSTROPHES = {"'", "’"}


@dataclass(frozen=True)
class Token:
    text: str
    kind: str  # number | label | word | symbol

    @property
    def number(self) -> Fraction | None:
        return Fraction(self.text.replace(",", ".")) if self.kind == "number" else None


def lower(text: str) -> str:
    return (text or "").replace("İ", "i").replace("I", "ı").lower()


def tokens(text: str) -> list[Token]:
    out: list[Token] = []
    for match in _TOKEN.finditer(text or ""):
        value = match.group(0)
        if "0" <= value[0] <= "9":
            out.append(Token(value, "number"))
        elif value[0].isalpha() and value[0].isupper() and not (len(value) > 1 and value[1].islower()):
            out.append(Token(value, "label"))
        elif value[0].isalpha():
            out.append(Token(lower(value), "word"))
        else:
            out.append(Token(value, "symbol"))
        if len(out) >= MAX_TOKENS:
            break
    return out


def _key(token: Token) -> str:
    if token.kind == "number":
        return str(token.number)
    return token.text if token.kind == "label" else lower(token.text)


def _same(source: Token, quote: Token) -> bool:
    """Sayı ve etiket birebir; sözcük ise Türkçe ek alabildiği için kaynak sözcüğün başı olarak eşleşir
    (``derece`` ↔ ``derecedir``). ``5`` hiçbir zaman ``15`` ile, ``AB`` hiçbir zaman ``ABC`` ile eşleşmez."""
    if source.kind != quote.kind:
        return False
    if quote.kind == "word":
        return source.text.startswith(quote.text)
    return _key(source) == _key(quote)


def contains(source: str, quote: str) -> bool:
    """Alıntının belirteç dizisi kaynakta ardışık olarak geçiyor mu? (alt dize değil)"""
    needle = [t for t in tokens(quote) if t.text not in APOSTROPHES]
    hay = [t for t in tokens(source) if t.text not in APOSTROPHES]
    if not needle or len(needle) > len(hay):
        return False
    return any(all(_same(a, b) for a, b in zip(hay[i:i + len(needle)], needle))
               for i in range(len(hay) - len(needle) + 1))


def clauses(text: str) -> list[list[Token]]:
    """Yan cümleler: virgül, noktalı virgül, nokta, iki nokta, soru işareti ve bağlaçlarda bölünür.
    Soru işareti, kapattığı yan cümleye eklenir (soru olduğu bilinsin)."""
    out: list[list[Token]] = []
    current: list[Token] = []
    found = tokens(text)
    depth = 0
    for index, token in enumerate(found):
        depth += {"(": 1, ")": -1}.get(token.text, 0)
        depth = max(depth, 0)
        previous = found[index - 1] if index else None
        following = found[index + 1] if index + 1 < len(found) else None
        # Parantez içindeki virgül (A(1, 2)) ve etiket sayımı (A, B ve C) yan cümle sınırı değildir.
        joins_labels = previous is not None and following is not None and previous.kind == following.kind == "label"
        if token.kind in {"symbol", "word"} and lower(token.text) in CLAUSE_BREAK and not (
                (depth and token.text == ",") or (token.text in {",", "ve"} and joins_labels)):
            if token.text == "?":
                current.append(token)
            if current:
                out.append(current)
            current = []
            continue
        current.append(token)
    if current:
        out.append(current)
    return out


def is_question(clause: list[Token]) -> bool:
    return any(t.text == "?" or (t.kind == "word" and t.text in QUESTION) for t in clause)


def is_negated(clause: list[Token]) -> bool:
    return any(t.text in NEGATION_SYMBOLS or (t.kind == "word" and (t.text in NEGATION or t.text.startswith("değil")))
               for t in clause)


def label_index(clause: list[Token], *names: str) -> int | None:
    return next((i for i, t in enumerate(clause) if t.kind == "label" and t.text in names), None)


def has_label(clause: list[Token], *names: str) -> bool:
    return label_index(clause, *names) is not None


def has_word(clause: list[Token], *stems: str) -> bool:
    return any(t.kind == "word" and t.text.startswith(stems) for t in clause)


def value_near(clause: list[Token], start: int, value: Fraction) -> bool:
    """Etiketin hemen ardından veya önünden, araya başka etiket veya sayı girmeden aynı sayı geliyor mu?"""
    for direction in (1, -1):
        index = start + direction
        while 0 <= index < len(clause):
            token = clause[index]
            if token.kind == "label":
                break
            if token.kind == "number":
                if token.number == value:
                    return True
                break
            index += direction
    return False


def numbers(clause: list[Token]) -> list[Fraction]:
    return [t.number for t in clause if t.kind == "number"]  # type: ignore[misc]


def asserting(text: str) -> list[list[Token]]:
    """Soru ve olumsuzlama içermeyen yan cümleler (bir olgu ileri sürebilecek olanlar)."""
    return [c for c in clauses(text) if not is_question(c) and not is_negated(c)]


def negated(text: str) -> list[list[Token]]:
    return [c for c in clauses(text) if is_negated(c)]


def number_value(text: str) -> Fraction | None:
    """Yalın sayı (``3``, ``2,5``, ``-4``, ``3/2``); değilse None."""
    match = re.fullmatch(r"\s*(-?)\s*(\d+(?:[.,]\d+)?)(?:\s*/\s*(\d+))?\s*", text or "")
    if not match:
        return None
    value = Fraction(match.group(2).replace(",", "."))
    if match.group(3):
        if int(match.group(3)) == 0:
            return None
        value /= int(match.group(3))
    return -value if match.group(1) else value
