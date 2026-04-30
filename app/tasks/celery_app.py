"""Celery 应用配置模块。

配置 broker、backend、序列化方式和示例任务。"""

from celery import Celery

from app.core.config import settings


celery_app = Celery(
    "fastapi_chuxue",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.notification_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    timezone="UTC",
    enable_utc=True,
)

