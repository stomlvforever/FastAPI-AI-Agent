"""验证码接口。

提供邮箱或短信验证码发送与校验能力。"""

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.cache.redis import get_redis
from app.rate_limit.limiter import limiter
from app.schemas.verification import SendCodeRequest, VerifyCodeRequest
from app.services.task_dispatch_service import TaskDispatchService
from app.services.verification_service import VerificationService

router = APIRouter()


@router.post("/auth/send-code", status_code=202)
@limiter.limit("3/minute")
async def send_verification_code(request: Request, response: Response, payload: SendCodeRequest):
    """Generate code and queue verification email task."""
    redis = await get_redis()
    verify_service = VerificationService(redis)

    try:
        code = await verify_service.send_code(payload.email)
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    task_service = TaskDispatchService()
    try:
        task_id = task_service.queue_verification_email(payload.email, code)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Failed to queue email task: {exc}") from exc

    return {
        "message": "Verification code queued",
        "email": payload.email,
        "task_id":                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          task_id,
    }


@router.post("/auth/verify-code")
async def verify_code(payload: VerifyCodeRequest):
    """Verify code from Redis."""
    redis = await get_redis()
    service = VerificationService(redis)

    valid = await service.verify_code(payload.email, payload.code)
    if not valid:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    return {"message": "Code verified successfully", "email": payload.email}


class SendSmsCodeRequest(BaseModel):
    phone: str


@router.post("/auth/send-sms-code", status_code=202)
@limiter.limit("3/minute")
async def send_sms_code(request: Request, response: Response, payload: SendSmsCodeRequest):
    """Generate code and queue SMS task."""
    redis = await get_redis()
    verify_service = VerificationService(redis)

    try:
        code = await verify_service.send_code(payload.phone)
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    task_service = TaskDispatchService()
    try:
        task_id = task_service.queue_sms_code(payload.phone, code)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Failed to queue SMS task: {exc}") from exc

    return {
        "message": "SMS code queued",
        "phone": payload.phone,
        "task_id": task_id,
    }

