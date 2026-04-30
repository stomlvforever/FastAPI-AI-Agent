"""用户数据访问层（User Repository）。

封装 User 模型的数据库操作：查询、创建、更新等。

事务管理说明：
- create() 和 update() 内部调用了 session.commit()
- 这意味着每次 Repository 调用即是独立的数据库事务
- 优点：调用方无需关心事务边界，简单直观
- 缺点：无法将多次 Repository 操作组合到一个事务中（需改进点）
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User


class UserRepository:
    """用户数据访问层——封装 User 表的所有数据库操作。

    每个方法接收一个 AsyncSession，通过构造函数注入。
    会话由 get_db() 依赖函数创建，自动管理生命周期。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ========================================================================
    # 查询方法
    # ========================================================================

    async def get(self, user_id: int) -> User | None:
        """按主键获取用户——通用别名，为统一命名约定而保留。"""
        return await self.session.get(User, user_id)

    async def get_by_id(self, user_id: int) -> User | None:
        """按主键获取用户——语义明确的命名。"""
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        """按邮箱查询用户——邮箱是唯一索引（unique=True），用于登录和注册检查。
        使用 scalar_one_or_none()：最多一条结果，无结果返回 None，
        多条结果抛异常（邮箱 unique 约束保证不会多条）。"""
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def list(self, skip: int = 0, limit: int = 100) -> list[User]:
        """分页查询用户列表——offset/limit 实现基本分页。
        注意：此方法不做 total 计数，调用方需自行处理分页元数据。"""
        result = await self.session.execute(select(User).offset(skip).limit(limit))
        return list(result.scalars().all())

    # ========================================================================
    # 写方法（每方法独立事务）
    # ========================================================================

    async def create(self, email: str, hashed_password: str, full_name: str | None) -> User:
        """创建新用户。

        执行步骤：
        1. 创建 User ORM 实例（此时未持久化，id 为 None）
        2. session.add(user)：标记对象为"待插入"状态
        3. session.commit()：刷新事务，INSERT 语句写入数据库
        4. session.refresh(user)：重新从数据库加载对象，获取自增 id 等数据库生成字段

        refresh 的必要性：
        SQLAlchemy 在执行 INSERT 后会用 RETURNING 获取数据库生成的值，
        但 expires_on_commit=False 只在对象未脱离 session 时生效。
        refresh 保证后续代码能读到完整的 id/created_at 等字段。
        """
        user = User(email=email, hashed_password=hashed_password, full_name=full_name)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update(self, user: User, data: dict) -> User:
        """按字典更新用户字段。

        实现方式：遍历 data 的 key/value，用 setattr 逐字段赋值。
        优点：灵活，Service 层只需传入要更新的字段即可
        注意：不校验字段是否存在（传不存在的属性名会直接设到对象上并持久化）
        """
        for key, value in data.items():
            setattr(user, key, value)
        await self.session.commit()
        await self.session.refresh(user)
        return user
