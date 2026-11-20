from typing import Annotated

from fastapi import Depends, Request
from starlette.concurrency import run_in_threadpool

from apps.api.app.features.auth.dependencies import require_user
from apps.api.app.features.auth.schemas import AuthenticatedUser

from .guard import AccountDeletionInProgress, deletion_started


async def active_user(request: Request, user: Annotated[AuthenticatedUser, Depends(require_user)]) -> AuthenticatedUser:
    """Silme süreci başlamış hesabın yazma isteklerini erken 409 ile reddeder."""
    if await run_in_threadpool(deletion_started, request.app.state.container.account_deletion.db, user.uid):
        raise AccountDeletionInProgress
    return user
