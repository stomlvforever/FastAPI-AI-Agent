"""认证业务服务（Auth Service）。

负责登录校验、双 Token 签发、Refresh Token 校验和续期等认证相关业务逻辑。

分层定位：
  API 路由（auth.py） → AuthService → UserRepository + Security 工具函数

核心流程：
  1. 登录：authenticate_user() 查用户 + 验密码 → create_tokens() 签发双 Token
  2. 刷新：refresh_access_token() 解码 Refresh Token → 验用户状态 → 发新 Access Token
"""

import jwt

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.repositories.user_repo import UserRepository


class AuthService:
    """认证服务——处理登录、Token 签发和刷新。"""

    def __init__(self, repo: UserRepository):
        # 通过构造函数注入 UserRepository，遵循依赖反转原则
        self.repo = repo

    async def authenticate_user(self, email: str, password: str):
        """认证用户：根据邮箱查找用户并校验密码。

        返回：
        - User 对象（认证成功）
        - None（认证失败——邮箱不存在或密码不匹配）

        安全设计：失败时不区分"用户不存在"和"密码错误"，
        两个分支统一返回 None，防止攻击者通过错误消息探测有效邮箱。
        """
        user = await self.repo.get_by_email(email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    def create_tokens(self, subject: str) -> dict[str, str]:
        """生成双 Token——Access Token + Refresh Token。

        subject 通常为用户邮箱（唯一标识），写入两个 Token 的 sub 字段。
        Access Token 用于 API 请求认证，Refresh Token 用于续期。
        两个 Token 的 type 字段不同（access vs refresh），防止混用。
        """
        return {
            "access_token": create_access_token(subject),
            "refresh_token": create_refresh_token(subject),
        }

    async def refresh_access_token(self, refresh_token: str) -> dict[str, str]:
        """用 Refresh Token 换取新的 Access Token。

        安全校验链（任一失败 → ValueError）：
        1. JWT 签名和过期时间校验（decode_token）
        2. Token 类型校验（type 必须为 "refresh"）——防止用 Access Token 来刷新
        3. Subject 存在性检查
        4. 用户存在性检查（可能被管理员删除）
        5. 账户状态检查（is_active）——被封禁的用户无法刷新

        返回：
        {"access_token": "...", "refresh_token": "..."}
        refresh_token 保持不变（不轮换），直到其自然过期。
        """
        # 步骤 1：解码 Refresh Token
        try:
            payload = decode_token(refresh_token)
        except jwt.PyJWTError as exc:
            raise ValueError("Invalid or expired refresh token") from exc

        # 步骤 2：类型校验——确保是 refresh token 而非 access token
        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type: expected refresh token")

        # 步骤 3：提取 subject
        subject = payload.get("sub")
        if not subject:
            raise ValueError("Invalid refresh token: missing subject")

        # 步骤 4-5：验证用户存在且活跃
        user = await self.repo.get_by_email(subject)
        if not user:
            raise ValueError("User not found")
        if not user.is_active:
            raise ValueError("User account is inactive")

        # 签发新的 Access Token（Refresh Token 不变，不轮换）
        return {
            "access_token": create_access_token(subject),
            "refresh_token": refresh_token,
        }
