"""认证接口（Auth Routes）。

提供登录、双 Token 签发和 Token 刷新等认证相关 API。

端点：
- POST /auth/login    — 用户名+密码登录，返回 Access + Refresh Token
- POST /auth/refresh  — 用 Refresh Token 换新的 Access Token

安全措施：
- 登录接口限流 5/min（防暴力破解）
- 刷新接口限流 10/min（防滥用刷新）
- OAuth2PasswordRequestForm 是 FastAPI 内置的认证表单格式
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencies.db import SessionDep
from app.rate_limit.limiter import limiter
from app.repositories.user_repo import UserRepository
from app.schemas.auth import RefreshRequest, Token
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/auth/login", response_model=Token)
@limiter.limit("5/minute")  # 敏感接口：登录限流 5 次/分钟
async def login(
    request: Request,       # limiter.limit 装饰器需要 Request 参数来获取客户端 IP
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
):
    """用户登录——校验邮箱和密码，返回双 Token。

    OAuth2PasswordRequestForm 要求 Content-Type: application/x-www-form-urlencoded
    或 JSON 格式的 username / password 字段。
    username 字段在本项目中实际存储的是邮箱。

    登录失败返回 401（认证失败）或 403（账户已封禁）。
    成功返回 Token 模型：{"access_token": "...", "refresh_token": "...", "token_type": "bearer"}
    """
    auth_service = AuthService(UserRepository(session))
    user = await auth_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # 检查账户是否被封禁
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive (banned). Please contact admin.",
        )

    # 签发双 Token（Access + Refresh）
    tokens = auth_service.create_tokens(user.email)
    return Token(**tokens)


@router.post("/auth/refresh", response_model=Token)
@limiter.limit("10/minute")  # 刷新接口限流 10 次/分钟（比登录宽松）
async def refresh_token(
    request: Request,
    response: Response,
    payload: RefreshRequest,  # Pydantic 模型：{"refresh_token": "..."}
    session: SessionDep,
):
    """用 Refresh Token 换取新的 Access Token——无需重新登录。

    RefreshRequest 模型包含一个 refresh_token 字段，
    由 Pydantic 自动验证 JSON body 格式。

    校验链（在 AuthService.refresh_access_token 中）：
    1. JWT 签名校验
    2. type 检查（必须为 "refresh"）
    3. 用户存在 + 活跃检查
    4. 签发新的 Access Token（Refresh Token 不变）

    ValueError 捕获后转为 401 响应。
    """
    auth_service = AuthService(UserRepository(session))

    try:
        tokens = await auth_service.refresh_access_token(payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    return Token(**tokens)
