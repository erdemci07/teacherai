"""Matematik strateji kaydı ve belirlenimci uygulanabilirlik (TA-008 §20). Saf Python; SymPy gerekmez.

Strateji *önerisidir*, kısıt değildir: kısıtlar yalnız yetkili onaylı MethodPolicy v2'den gelir. Uygulanabilirlik
sorunun yapısal özelliklerinden (``features``) hesaplanır; anahtar sözcük eşleşmesi yetmez. Kayıttaki bütün
stratejiler AI taslağıdır (``draft``); öğretmen deneyimi olarak sunulmaz.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..education.mathematics import StrategyRef

DATA = Path(__file__).with_name("data") / "strategies.json"
# Strateji → yöntem politikasının yasaklayabileceği yapı (curriculum.registry.PROSE/AST yapıları).
REQUIRES_CONSTRUCT = {"quadratic_formula": "quadratic_formula", "derivative_test": "derivative"}


@dataclass(frozen=True)
class Strategy:
    id: str
    title_tr: str
    topics: tuple[str, ...]
    applies_when: str
    grades: tuple[int, int]
    alternatives: tuple[str, ...]
    status: str
    advantages_tr: str
    limitations_tr: str


@lru_cache
def registry() -> dict[str, Strategy]:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    out = {}
    for raw in data["strategies"]:
        if raw["status"] not in {"draft", "approved"}:
            raise ValueError(f"Geçersiz strateji durumu: {raw['id']}")
        if raw["status"] == "approved":
            raise ValueError("Strateji kaydında onay yalnız öğretmen inceleme akışıyla verilir (TA-008: onaylı 0).")
        out[raw["id"]] = Strategy(raw["id"], raw["title_tr"], tuple(raw["topics"]), raw["applies_when"],
                                  tuple(raw["grades"]), tuple(raw["alternatives"]), raw["status"],
                                  raw["advantages_tr"], raw["limitations_tr"])
    for item in out.values():
        missing = set(item.alternatives) - set(out)
        if missing:
            raise ValueError(f"Tanımsız alternatif strateji: {item.id} → {missing}")
    return out


def recommend(features: set[str], grade: int | None, forbidden: set[str] = frozenset(), limit: int = 4) -> list[StrategyRef]:
    """Yapısal özelliklere uyan stratejiler; sınıf uygunluğu ve onaylı politika yasağı ayrı işaretlenir."""
    out = []
    for item in registry().values():
        if item.applies_when not in features:
            continue
        construct = REQUIRES_CONSTRUCT.get(item.id)
        if construct and construct in forbidden:
            out.append(StrategyRef(id=item.id, status=item.status, applicable=True, reason="forbidden_by_approved_policy",
                                   suitable_for_grade=False))
            continue
        suitable = None if grade is None else item.grades[0] <= grade <= item.grades[1]
        out.append(StrategyRef(id=item.id, status=item.status, applicable=True,
                               reason=f"structure:{item.applies_when}", suitable_for_grade=suitable))
    out.sort(key=lambda ref: (ref.suitable_for_grade is False, ref.id))
    return out[:limit]
