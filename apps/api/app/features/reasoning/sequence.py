"""Sınırlı nükleik asit dizisi denetimi: yön, baz eşleşmesi ve kodon (TA-004).

Yalnızca A, C, G, T (DNA) ve A, C, G, U (RNA) bazları ile açıkça yazılmış 5′/3′ yönleri desteklenir.
Kalıp iplikten mRNA, tamamlayıcı baz eşleşmesi kuralıyla (A–U, T–A, C–G, G–C) ve ters yönde üretilir.
Bu kural evrensel ve belgelenmiştir; gen ifadesi, okuma çerçevesi seçimi veya protein işlevi denetlenmez.
"""

from __future__ import annotations

import re

_PAIR_TO_RNA = {"A": "U", "T": "A", "C": "G", "G": "C"}
MAX_BASES = 300


class SequenceError(ValueError):
    pass


def parse_strand(text: str) -> tuple[str, str]:
    """(baz dizisi, yön) — yön ``5to3`` veya ``3to5``. Yön yazılmamışsa tahmin edilmez."""
    normalized = text.replace("′", "'").replace("’", "'").replace("‘", "'").strip()
    match = re.fullmatch(r"([35])'\s*-?\s*([ACGTU\s]+?)\s*-?\s*([35])'", normalized)
    if not match or {match.group(1), match.group(3)} != {"3", "5"}:
        raise SequenceError("orientation_missing")
    bases = re.sub(r"\s+", "", match.group(2))
    if not bases or len(bases) > MAX_BASES or ("T" in bases and "U" in bases):
        raise SequenceError("invalid_bases")
    return bases, "5to3" if match.group(1) == "5" else "3to5"


def transcribe_template(text: str) -> str:
    """Kalıp DNA ipliğinden 5′→3′ yönünde mRNA."""
    bases, direction = parse_strand(text)
    if "U" in bases:
        raise SequenceError("template_must_be_dna")
    rna = "".join(_PAIR_TO_RNA[base] for base in bases)
    # 3′→5′ yazılmış kalıp, aynı sırada 5′→3′ mRNA verir; 5′→3′ kalıp ters çevrilir.
    return rna if direction == "3to5" else rna[::-1]


def codon(rna: str, position: int) -> str:
    if position < 1 or len(rna) < position * 3:
        raise SequenceError("codon_out_of_range")
    return rna[(position - 1) * 3: position * 3]
