"""后台任务接口。

提供 Celery 异步任务触发和任务状态查询能力。"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from app.api.dependencies.auth import CurrentUser
from app.services.task_dispatch_service import TaskDispatchService

router = APIRouter()


class QueueEmailRequest(BaseModel):
    email: EmailStr


@router.post("/tasks/email", status_code=202)
async def queue_email(payload: QueueEmailRequest, current_user: CurrentUser):
    """Queue a welcome email via Celery worker（需要登录）。"""
    service = TaskDispatchService()
    try:
        task_id = service.queue_notification_email(
            to_email=payload.email,
            subject="Welcome to fastapi_chuxue",
            content="Your email task has been queued.",
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Failed to queue task: {exc}") from exc

    return {"queued": True, "task_id": task_id, "email": payload.email}


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str, current_user: CurrentUser):
    """Get Celery task execution status by task_id（需要登录）。"""
    return TaskDispatchService().get_task_status(task_id)

