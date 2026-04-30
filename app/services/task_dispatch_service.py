"""异步任务调度服务。

负责投递 Celery 任务并查询任务状态。"""

from celery.result import AsyncResult
from loguru import logger

from app.tasks.celery_app import celery_app


class TaskDispatchService:
    """Route-facing service to enqueue background jobs."""

    def queue_notification_email(self, to_email: str, subject: str, content: str) -> str:
        from app.tasks.notification_tasks import send_notification_email_task

        result = send_notification_email_task.delay(to_email, subject, content)
        return result.id

    def queue_notification_email_safe(self, to_email: str, subject: str, content: str) -> str | None:
        """Queue non-critical email without breaking core request flow."""
        try:
            return self.queue_notification_email(to_email, subject, content)
        except Exception as exc:
            logger.warning("failed to queue notification email to {}: {}", to_email, exc)
            return None

    def queue_verification_email(self, to_email: str, code: str) -> str:
        from app.tasks.notification_tasks import send_verification_email_task

        result = send_verification_email_task.delay(to_email, code)
        return result.id

    def queue_sms_code(self, phone: str, code: str) -> str:
        from app.tasks.notification_tasks import send_sms_code_task

        result = send_sms_code_task.delay(phone, code)
        return result.id

    def get_task_status(self, task_id: str) -> dict:
        result = AsyncResult(task_id, app=celery_app)
        data = {
            "task_id": task_id,
            "status": result.status,
            "ready": result.ready(),
            "successful": result.successful() if result.ready() else False,
        }
        if result.successful():
            data["result"] = result.result
        elif result.failed():
            data["error"] = str(result.result)
        return data


