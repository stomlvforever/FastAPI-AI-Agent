"""认证相关 Pydantic Schema。

定义登录返回的 access/refresh token 结构，以及刷新 token 的请求体。"""

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """刷新 Token 的请求体"""
    refresh_token: str
