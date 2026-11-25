"""Sayma, olasılık ve betimsel istatistik (TA-008 §18). Kesin rasyonel aritmetik (``fractions``); SymPy gerekmez.

Sıralı/sırasız seçim ve yerine koyarak/koymadan çekiliş ayrıdır. Bütün çıktıların eşit olasılıklı olduğu
varsayılmaz: ağırlıklar açıkça verilir. Bağımsızlık ve ayrıklık ayrı kavramlardır. Sayım sınırlıdır.
"""

from __future__ import annotations

import itertools
import math
from collections import Counter
from fractions import Fraction

MAX_OUTCOMES = 20000
MAX_N = 60


class ProbabilityError(ValueError):
    pass


def permutations(n: int, k: int) -> int:
    _check(n, k)
    return math.perm(n, k)


def combinations(n: int, k: int) -> int:
    _check(n, k)
    return math.comb(n, k)


def _check(n: int, k: int):
    if not (0 <= k <= n <= MAX_N):
        raise ProbabilityError("invalid_counts")


def draw_space(items: dict[str, int], draws: int, replacement: bool, ordered: bool = True):
    """Torbadan çekiliş örnek uzayı: (sonuç dizisi, olasılık). Her bilye eşit olasılıklıdır (açık varsayım)."""
    pool = [color for color, count in items.items() for _ in range(count)]
    if not pool or draws < 1 or (not replacement and draws > len(pool)):
        raise ProbabilityError("invalid_draw")
    total = len(pool) ** draws if replacement else math.perm(len(pool), draws)
    if total > MAX_OUTCOMES:
        raise ProbabilityError("sample_space_too_large")
    sequences = itertools.product(range(len(pool)), repeat=draws) if replacement else itertools.permutations(range(len(pool)), draws)
    counter: Counter = Counter()
    for sequence in sequences:
        outcome = tuple(pool[i] for i in sequence)
        counter[outcome if ordered else tuple(sorted(outcome))] += 1
    return {outcome: Fraction(count, total) for outcome, count in counter.items()}


def probability(space: dict, event) -> Fraction:
    return sum((p for outcome, p in space.items() if event(outcome)), Fraction(0))


def conditional(space: dict, event, given) -> Fraction:
    denominator = probability(space, given)
    if denominator == 0:
        raise ProbabilityError("conditioning_on_impossible_event")
    return probability(space, lambda o: event(o) and given(o)) / denominator


def independent(space: dict, a, b) -> bool:
    return probability(space, lambda o: a(o) and b(o)) == probability(space, a) * probability(space, b)


def mutually_exclusive(space: dict, a, b) -> bool:
    return probability(space, lambda o: a(o) and b(o)) == 0


def validate_distribution(probabilities: list[Fraction]) -> str | None:
    """Bozuk olasılık: negatif, 1'den büyük veya toplamı 1 olmayan dağılım."""
    if any(p < 0 or p > 1 for p in probabilities):
        return "probability_out_of_range"
    if sum(probabilities, Fraction(0)) != 1:
        return "total_not_one"
    return None


def describe(values: list[Fraction | int]) -> dict:
    """Ortalama, ortanca, tepe değer(ler), açıklık, kitle ve örneklem varyansı (kesin)."""
    if not values or len(values) > 10000:
        raise ProbabilityError("invalid_data")
    data = sorted(Fraction(v) for v in values)
    n = len(data)
    mean = sum(data, Fraction(0)) / n
    median = data[n // 2] if n % 2 else (data[n // 2 - 1] + data[n // 2]) / 2
    counts = Counter(data)
    top = max(counts.values())
    modes = sorted(value for value, count in counts.items() if count == top) if top > 1 else []
    squares = sum(((v - mean) ** 2 for v in data), Fraction(0))
    return {"n": n, "mean": mean, "median": median, "modes": modes, "range": data[-1] - data[0],
            "population_variance": squares / n, "sample_variance": squares / (n - 1) if n > 1 else None}


def table_totals_consistent(table: list[list[int]], row_totals: list[int] | None, column_totals: list[int] | None,
                            grand_total: int | None) -> list[str]:
    """Çapraz tablo toplamları tutarlı mı? Tutarsızlık nedenleri listesi (boş: tutarlı)."""
    problems = []
    if row_totals is not None and [sum(row) for row in table] != row_totals:
        problems.append("row_totals_mismatch")
    if column_totals is not None and [sum(col) for col in zip(*table)] != column_totals:
        problems.append("column_totals_mismatch")
    if grand_total is not None and sum(map(sum, table)) != grand_total:
        problems.append("grand_total_mismatch")
    return problems
