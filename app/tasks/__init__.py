"""Celery 任务包。

导出 Celery 应用和任务函数，方便服务层统一调度。"""

from app.tasks.celery_app import celery_app
from app.tasks.notification_tasks import (
    send_notification_email_task,
    send_sms_code_task,
    send_verification_email_task,
)

__all__ = [
    "celery_app",
    "send_notification_email_task",
    "send_verification_email_task",
    "send_sms_code_task",
]


