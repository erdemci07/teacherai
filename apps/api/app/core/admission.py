from typing import Annotated

from apps.api.app.core.usage import PAID_OPERATIONS, UsageLimitExceeded
from apps.api.app.features.account.guard import (
    AccountDeletionInProgress,
    deletion_started,
)
from apps.api.app.features.auth.dependencies import require_user
from apps.api.app.features.auth.schemas import AuthenticatedUser
from fastapi import Depends, Header, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from .gateway import begin_accounting, end_accounting


def admitted(operation: str):
    async def dependency(
        request: Request,
        user: Annotated[AuthenticatedUser, Depends(require_user)],
        idempotency_key: Annotated[str | None, Header(max_length=128)] = None,
    ):
        container = request.app.state.container
        if await run_in_threadpool(deletion_started, container.account_deletion.db, user.uid):
            raise AccountDeletionInProgress
        activity = operation
        if operation == "interact":
            try:
                body = await request.json()
            except ValueError:
                raise HTTPException(422, "Invalid interaction request.") from None
            if isinstance(body, dict) and body.get("action") == "understood":
                activity = "understood"
        if activity in PAID_OPERATIONS and not container.settings.ai_enabled:
            raise HTTPException(503, "AI temporarily unavailable.")
        scope = begin_accounting(
            request.state.request_id,
            container.settings,
            container.usage_tracker,
            user.uid,
            max_calls=container.settings.provider_call_budget(activity),
        )
        try:
            try:
                await run_in_threadpool(
                    container.usage_tracker.record, user.uid, activity, idempotency_key
                )
            except (UsageLimitExceeded, HTTPException, AccountDeletionInProgress):
                raise
            except Exception:
                raise HTTPException(503, "Usage service unavailable.") from None
            yield user
        finally:
            end_accounting(scope)

    return dependency
