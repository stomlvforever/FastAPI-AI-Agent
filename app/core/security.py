"""安全工具模块。

提供用户认证和安全相关的核心功能：
1. 密码哈希与校验：使用 bcrypt（通过 passlib），安全地存储和验证用户密码
2. JWT Token 创建：生成 Access Token 和 Refresh Token（双 Token 模式）
3. JWT Token /校验：解码和验证 token 签名及过期时间

双 Token 设计：
- Access Token：短生命周期（30分钟），用于所有 API 请求的认证
- Refresh Token：长生命周期（7天），仅用于换取新的 Access Token
- 每个 token 的 payload 中包含 type 字段，防止 Refresh Token 冒充 Access Token

安全要点：
- 密码使用 bcrypt 哈希存储，不可逆
- JWT 使用 HS256 算法签名，密钥由 SECRET_KEY 配置
- Token 类型校验在 auth 依赖层（auth.py 的 get_current_user） 中执行
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from passlib.context import CryptContext

from app.core.config import settings

# ============================================================================
# 密码哈希上下文
# ============================================================================
# bcrypt 是目前业界标准的密码哈希算法
# pbkdf2_sha256 是兼容兜底，用于 bcrypt 后端在当前 Python 环境不可用的情况
# deprecated="auto"：自动处理算法迁移（旧算法标记为废弃后，下次登录时自动升级哈希）
pwd_context = CryptContext(schemes=["bcrypt", "pbkdf2_sha256"], deprecated="auto")
fallback_pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def _is_bcrypt_backend_error(exc: Exception) -> bool:
    """识别 passlib 与当前 bcrypt 后端的兼容错误。"""
    return isinstance(exc, ValueError) and "password cannot be longer than 72 bytes" in str(exc)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与 bcrypt 哈希是否匹配。
    登录验证、密码修改确认等场景使用。"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except ValueError as exc:
        if _is_bcrypt_backend_error(exc):
            return fallback_pwd_context.verify(plain_password, hashed_password)
        raise


def get_password_hash(password: str) -> str:
    """生成密码的 bcrypt 哈希值。
    注册时和修改密码时调用，哈希后的值存入数据库 hashed_password 字段。
    注意：bcrypt 自带随机盐值，相同密码每次生成哈希也不同。"""
    try:
        return pwd_context.hash(password)
    except ValueError as exc:
        if _is_bcrypt_backend_error(exc):
            return fallback_pwd_context.hash(password)
        raise


# ============================================================================
# JWT Token 创建
# ============================================================================


def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
    extra: Optional[dict[str, Any]] = None,
) -> str:
    """生成 Access Token（短期令牌，用于 API 请求认证）。

    参数：
    - subject: JWT 的 sub 字段，本项目存储用户邮箱（唯一标识）
    - expires_delta: 自定义过期时间（不传则使用配置的默认值 30 分钟）
    - extra: 额外要写入 JWT payload 的字段（如用户角色等）

    Payload 结构：
    {
      "sub": "user@example.com",          # 主体标识
      "exp": 1234567890,                  # 过期时间（Unix timestamp）
      "type": "access",                   # Token 类型标记
      ... extra
    }
    """
    # 计算过期时间：优先用传入的 expires_delta，否则用配置的分钟数
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    # 构建 JWT payload
    to_encode: dict[str, Any] = {"sub": subject, "exp": expire, "type": "access"}
    if extra:
        to_encode.update(extra)
    # 签名并返回 JWT 字符串
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """生成 Refresh Token（长效令牌，仅用于刷新 Access Token）。

    与 Access Token 的区别：
    1. type="refresh"——在 auth 依赖中会校验 type，防止混用
    2. 默认 7 天有效期——比 Access Token 长得多
    3. 不附带额外信息——仅包含 sub、exp、type 三个字段

    使用流程：
    1. 登录时同时返回 access_token 和 refresh_token
    2. 前端在 API 请求 401 时用 refresh_token 调用 POST /auth/refresh
    3. 后端验证 refresh_token 的 type 和 sub 后签发新的 access_token
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(days=settings.refresh_token_expire_days)
    )
    to_encode: dict[str, Any] = {"sub": subject, "exp": expire, "type": "refresh"}
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


# ============================================================================
# JWT Token 解码
# ============================================================================


def decode_token(token: str) -> dict[str, Any]:
    """解码并验证 JWT Token。

    验证内容：
    1. 签名有效性（使用 secret_key 和 algorithm）
    2. 过期时间（exp 字段）
    3. 算法匹配（防止 alg=none 攻击）

    验证失败时 PyJWT 会抛出异常（在调用方处理）。
    """
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
