from random import uniform
from time import sleep

from fastapi import HTTPException
from google.api_core.exceptions import Aborted


def commit(db, update, max_attempts=5):
    """SDK işlem çakışmalarını en çok max_attempts kez dener; tükenen kilidi bir kez yeni işlemle dener.

    Toplam deneme sınırlıdır: 2 x max_attempts. Sonra 503 döner ve sağlayıcı çağrılmaz.
    """
    for attempt in range(2):
        try:
            return update(db.transaction(max_attempts=max_attempts))
        except (ValueError, Aborted) as exc:
            if not isinstance(exc, Aborted) and not isinstance(exc.__cause__, Aborted):
                raise
            if attempt:
                raise HTTPException(503, "Storage busy. Retry shortly.") from None
            sleep(uniform(0.05, 0.20))
