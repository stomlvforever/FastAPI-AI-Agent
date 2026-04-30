"""验证码相关 Pydantic Schema。

定义验证码发送和校验请求结构。"""

from pydantic import BaseModel, EmailStr


class SendCodeRequest(BaseModel):
    """发送验证码请求"""
    email: EmailStr


class VerifyCodeRequest(BaseModel):
    """校验验证码请求"""
    email: EmailStr
    code: str

