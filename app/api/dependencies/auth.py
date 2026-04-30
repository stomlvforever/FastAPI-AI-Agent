"""认证与授权依赖模块。

提供 FastAPI 的认证依赖注入：
- get_current_user：从 Bearer Token 解析当前登录用户
- require_admin：验证当前用户为管理员
- CurrentUser / AdminUser：类型安全的依赖注入别名

认证流程：
  1. OAuth2PasswordBearer 从 Authorization header 提取 Bearer token
  2. decode_token() 解析 JWT，验证签名和过期时间
  3. 检查 token type 必须是 "access"（防止 Refresh Token 冒充）
  4. 通过 sub 字段（邮箱）查找数据库中的 User 对象
  5. 返回 User → 被路由函数通过 CurrentUser 别名注入

双 Token 防护：
  - Access Token (type="access") → 用于 API 请求
  - Refresh Token (type="refresh") → 仅用于刷新端点
  - 此依赖强制检查 type=="access"，即使 Refresh Token 签名有效也会被拒绝
"""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.api.dependencies.db import SessionDep
from app.core.config import settings
from app.core.security import decode_token
from app.db.models.user import User
from app.repositories.user_repo import UserRepository

# ============================================================================
# OAuth2 Password Bearer 流
# ============================================================================
# 告诉 FastAPI 从 HTTP Header "Authorization: Bearer <token>" 中提取 token
# tokenUrl：Swagger UI 的 Authorize 按钮跳转到这个登录端点
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")


def _credentials_exception() -> HTTPException:
    """返回 401 Unauthorized 异常。
    统一的认证失败响应——不暴露具体失败原因（如"用户不存在"/"密码错误"），
    防止攻击者通过不同的错误信息探测有效账户。"""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
    )


# ============================================================================
# 认证依赖：从 Bearer Token 解析当前用户
# ============================================================================


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],  # 从 Header 提取的 Bearer token
    session: SessionDep,                              # 数据库会话（用于查询用户）
) -> User:
    """从 JWT Bearer Token 中解析当前登录用户。

    校验链（按顺序，任一失败 → 401）：
    1. JWT 签名校验（decode_token → PyJWTError）
    2. Token 类型校验（type 必须为 "access"，防止 Refresh Token 冒充）
    3. Subject 存在性检查（sub 字段不能为空）
    4. 用户存在性检查（数据库中是否存在该邮箱的用户）
    """
    # 步骤 1：解码 JWT
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        raise _credentials_exception()

    # 步骤 2：Token 类型校验（双 Token 防护的关键）
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type: access token required",
        )

    # 步骤 3：提取 subject（本项目中 subject = 用户邮箱）
    subject = payload.get("sub")
    if not subject:
        raise _credentials_exception()

    # 步骤 4：验证用户存在且活跃
    # 注意：这里暂未检查 is_active，如需封禁后阻止访问，可在此处加 is_active 检查
    user = await UserRepository(session).get_by_email(subject)
    if not user:
        raise _credentials_exception()
    return user


# ============================================================================
# 依赖注入别名（类型安全 + 简洁用法）
# ============================================================================

# 路由函数中写 `current_user: CurrentUser` 即可获得当前登录用户
CurrentUser = Annotated[User, Depends(get_current_user)]


# ============================================================================
# 权限依赖：管理员身份校验
# ============================================================================


async def require_admin(
    current_user: CurrentUser,  # 先执行 get_current_user 获取用户
) -> User:
    """管理员权限依赖——只允许 admin 角色的用户通过。

    注意 require_admin 依赖 CurrentUser，形成链式依赖：
    require_admin → CurrentUser → get_current_user → SessionDep

    非管理员返回 403 Forbidden（而非 401 Unauthorized），
    语义区别：401=未认证（你是谁？），403=已认证但没权限（你没资格）。
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


# 路由函数中写 `admin: AdminUser` 即可获得经过管理员校验的当前用户
# AdminUser 已隐含了 CurrentUser 的认证流程
AdminUser = Annotated[User, Depends(require_admin)]
