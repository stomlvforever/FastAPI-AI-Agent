"""通知类 Celery 任务模块。

负责异步发送邮件、验证码和批量通知。"""

import asyncio

from celery.utils.log import get_task_logger

from app.core.email import send_notification_email_to_address, send_verification_email
from app.core.sms import get_sms_provider
from app.tasks.celery_app import celery_app

logger = get_task_logger(__name__)


def _run_async(coro):
    """Run async code from sync Celery tasks."""
    return asyncio.run(coro)


@celery_app.task(
    name="notifications.send_notification_email",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def send_notification_email_task(to_email: str, subject: str, content: str) -> dict:
    """发送通知邮件任务。"""
    _run_async(send_notification_email_to_address(to_email, subject, content))
    logger.info("notification email sent to %s", to_email)
    return {"to_email": to_email, "subject": subject}


@celery_app.task(
    name="notifications.send_verification_email",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def send_verification_email_task(to_email: str, code: str) -> dict:
    """发送验证码邮件任务。"""
    _run_async(send_verification_email(to_email, code))
    logger.info("verification email sent to %s", to_email)
    return {"to_email": to_email}


@celery_app.task(
    name="notifications.send_sms_code",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def send_sms_code_task(phone: str, code: str) -> dict:
    """发送短信验证码任务。"""
    provider = get_sms_provider()
    ok = _run_async(provider.send_sms(phone, code))
    if not ok:
        raise RuntimeError("SMS provider returned failure")
    logger.info("verification sms sent to %s", phone)
    return {"phone": phone}


