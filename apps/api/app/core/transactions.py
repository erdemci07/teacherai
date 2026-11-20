from random import uniform
from time import sleep

from fastapi import HTTPException
from google.api_core.exceptions import Aborted


def commit(db, update):
    """The SDK retries commit conflicts; retry an exhausted lock once as a new transaction."""
    for attempt in range(2):
        try:
            return update(db.transaction())
        except (ValueError, Aborted) as exc:
            if not isinstance(exc, Aborted) and not isinstance(exc.__cause__, Aborted):
                raise
            if attempt:
                raise HTTPException(503, "Storage busy. Retry shortly.") from None
            sleep(uniform(0.05, 0.20))
