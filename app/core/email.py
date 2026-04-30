"""邮件工具模块。

封装 SMTP/FastAPI-Mail 发送能力，供验证码、通知和异步任务调用。"""

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from loguru import logger

from app.core.config import settings
from app.db.models.user import User


mail_conf = ConnectionConfig(
    MAIL_USERNAME=settings.mail_username,
    MAIL_PASSWORD=settings.mail_password,
    MAIL_FROM=settings.mail_from,
    MAIL_PORT=settings.mail_port,
    MAIL_SERVER=settings.mail_server,
    MAIL_STARTTLS=settings.mail_starttls,
    MAIL_SSL_TLS=settings.mail_ssl_tls,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
)


async def send_notification_email_to_address(
    to_email: str,
    subject: str,
    content: str,
) -> None:
    """Send a notification email to a raw email address."""
    logger.info("[EMAIL] send notification -> {}", to_email)
    message = MessageSchema(
        subject=subject,
        recipients=[to_email],
        body=f"<h3>{subject}</h3><p>{content}</p>",
        subtype=MessageType.html,
    )
    await FastMail(mail_conf).send_message(message)


async def send_notification_email(
    to_user: User,
    subject: str,
    content: str,
) -> None:
    """Backward-compatible wrapper using a User model."""
    await send_notification_email_to_address(to_user.email, subject, content)


async def send_verification_email(to_email: str, code: str) -> None:
    """Send verification code email."""
    subject = f"[{settings.app_name}] Verification Code"
    body = (
        f"<h3>Your verification code: <strong>{code}</strong></h3>"
        f"<p>Expires in {settings.verify_code_expire_seconds // 60} minutes.</p>"
        "<p>If this was not you, please ignore this message.</p>"
    )

    logger.info("[EMAIL] send verification -> {}", to_email)
    message = MessageSchema(
        subject=subject,
        recipients=[to_email],
        body=body,
        subtype=MessageType.html,
    )
    await FastMail(mail_conf).send_message(message)

