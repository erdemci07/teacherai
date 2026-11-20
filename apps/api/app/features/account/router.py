from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from apps.api.app.features.auth.dependencies import require_user
from apps.api.app.features.auth.schemas import AuthenticatedUser

from .service import AccountDeletionService

router = APIRouter(prefix="/account", tags=["account"])


def get_account_deletion(request: Request) -> AccountDeletionService:
    return request.app.state.container.account_deletion


Service = Annotated[AccountDeletionService, Depends(get_account_deletion)]
User = Annotated[AuthenticatedUser, Depends(require_user)]


class DeletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: Literal[True]


class ReceiptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    uid: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    receipt: str = Field(min_length=16, max_length=128)


class DeletionStatus(BaseModel):
    status: Literal["pending", "in_progress", "completed", "failed"]
    completed_steps: list[str]
    failed_step: str | None = None
    attempts: int = 0
    updated_at: datetime | None = None
    # Yalnız silmeyi başlatan ilk yanıtta döner; Auth silindikten sonra sonucu sorgulamak içindir.
    receipt: str | None = None


def _respond(request: Request, code: int, data: dict):
    payload = DeletionStatus.model_validate(data).model_dump(mode="json", exclude_none=False)
    if code == 500:
        return JSONResponse(status_code=500, content={
            "success": False, "error": "account_deletion_incomplete",
            "detail": "Hesap silme tamamlanamadı. Tekrar deneyebilirsin.",
            "request_id": getattr(request.state, "request_id", None), "data": payload,
        })
    return JSONResponse(status_code=code, content={"success": True, "data": payload})


@router.post("/deletion", status_code=200)
async def start_deletion(request: Request, body: DeletionRequest, user: User, service: Service):
    code, data = await run_in_threadpool(service.start_or_resume, user)
    return _respond(request, code, data)


@router.get("/deletion")
async def deletion_status(request: Request, user: User, service: Service):
    data = await run_in_threadpool(service.status, user.uid)
    if not data:
        raise HTTPException(404, "Silme kaydı bulunamadı.")
    return _respond(request, 200, data)


@router.post("/deletion/receipt")
async def deletion_receipt(request: Request, body: ReceiptRequest, service: Service):
    """Oturum gerektirmez; yalnız makbuzu bilen, yalnız o kaydın sonucunu görebilir."""
    result = await run_in_threadpool(service.reconcile_with_receipt, body.uid, body.receipt)
    if not result:
        raise HTTPException(404, "Silme kaydı bulunamadı.")
    return _respond(request, *result)
