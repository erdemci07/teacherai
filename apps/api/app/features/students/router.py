from typing import Annotated
from fastapi import APIRouter,Depends,Response,status
from apps.api.app.core.dependencies import get_student_service
from apps.api.app.features.auth.dependencies import require_user
from apps.api.app.features.auth.schemas import AuthenticatedUser
from apps.api.app.schemas.responses import ApiResponse
from apps.api.app.features.memory.schemas import StudentMemory
from .schemas import *
from .service import StudentService
router=APIRouter(prefix="/students/me",tags=["students"])
User=Annotated[AuthenticatedUser,Depends(require_user)];Service=Annotated[StudentService,Depends(get_student_service)]
@router.put("/profile",response_model=ApiResponse[StudentProfile])
def profile(body:ProfileInput,user:User,service:Service):return ApiResponse(data=service.profile(user,body))
@router.post("/lessons",response_model=ApiResponse[LessonRecord])
def save_lesson(body:SaveLessonRequest,user:User,service:Service):return ApiResponse(data=service.save_lesson(user,body.result))
@router.get("/history",response_model=ApiResponse[list[LessonRecord]])
def history(user:User,service:Service):return ApiResponse(data=service.history(user))
@router.get("/memory",response_model=ApiResponse[StudentMemory])
def memory(user:User,service:Service):return ApiResponse(data=service.memory_summary(user))
@router.delete("/memory",status_code=status.HTTP_204_NO_CONTENT)
def reset_memory(user:User,service:Service):service.reset(user);return Response(status_code=204)
@router.get("/dashboard",response_model=ApiResponse[DashboardSummary])
def dashboard(user:User,service:Service):return ApiResponse(data=service.dashboard(user))
