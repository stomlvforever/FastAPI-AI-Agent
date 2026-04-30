"""用户业务服务（User Service）。

负责用户注册、密码哈希、用户查询和列表等业务逻辑。

分层定位：
  API 路由（users.py） → UserService → UserRepository + Security 工具函数

注册流程：
  1. 接收 UserCreate 数据（由 Pydantic Schema 验证）
  2. 密码 → bcrypt 哈希（不存储明文）
  3. 调用 Repository 创建用户记录
"""

from app.core.security import get_password_hash
from app.repositories.user_repo import UserRepository
from app.schemas.user import UserCreate


class UserService:
    """用户业务服务——处理用户注册和查询。"""

    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def get_by_email(self, email: str):
        """按邮箱查询用户——用于登录、注册查重等场景。"""
        return await self.repo.get_by_email(email)

    async def register_user(self, payload: UserCreate):
        """注册新用户。

        步骤：
        1. 用 bcrypt 哈希密码
        2. 调用 Repository 创建记录（Repository 内部 commit + refresh）
        """
        hashed_password = get_password_hash(payload.password)
        return await self.repo.create(
            email=payload.email,
            hashed_password=hashed_password,
            full_name=payload.full_name,
        )

    async def list_users(self, skip: int = 0, limit: int = 100):
        """获取用户列表（分页）。管理员功能。"""
        return await self.repo.list(skip=skip, limit=limit)
