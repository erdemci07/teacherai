"""Ücretli sağlayıcı çağrısından sonraki doğrulama (TA-009 §21).

Ders ve etkileşim hattında MathAI doğrulaması ücretli sağlayıcı çağrısından *sonra* gelir. Bu noktada ``mathai_busy``
dönmek ödenmiş sonucu atar; kullanıcı aynı ``Idempotency-Key`` ile yeniden denerse 409 alır (sonuç saklanmaz), yeni
anahtarla denerse ikinci kez ödenir. Bu yüzden bu çağrılar işaretlenir: sınırlı ve daha uzun bir kuyruk beklemesi
kullanır ve kuyruk doluluk sınırına takılmaz (eşzamanlı ücretli istek sayısı zaten HTTP yuvalarıyla sınırlıdır).
Hesaplama zaman aşımı ve süreç üst sınırı değişmez.
"""

from __future__ import annotations

import threading
from functools import wraps

_STATE = threading.local()


def active() -> bool:
    return bool(getattr(_STATE, "after_paid_call", False))


def after_paid_call(fn):
    """``fn``'yi çağıran iş parçacığında "ücretli çağrı sonrası" işaretiyle çalıştırır (yeniden girişe dayanıklı)."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        previous = active()
        _STATE.after_paid_call = True
        try:
            return fn(*args, **kwargs)
        finally:
            _STATE.after_paid_call = previous

    return wrapper
