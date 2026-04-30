"""关注数据访问层（Follow Repository）。

封装用户关注/取消关注的关系操作和查询。

查询模式：
- 粉丝列表（followers）：WHERE following_id=?  → 谁关注了我
- 关注列表（following）：WHERE follower_id=?    → 我关注了谁
- 是否已关注（is_following）：按联合 PK 检查是否存在记录

性能说明：
- is_following 用 PK 索引 (follower_id, following_id)，O(log n)
- list_following 用 PK 索引（左前缀 follower_id），高效
- list_followers 需要用 ix_followers_following_id 索引（右前缀）
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.follower import Follower
from app.db.models.user import User


class FollowRepository:
    """关注数据访问层——封装 Follower 关联表的所有操作。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ========================================================================
    # 状态查询
    # ========================================================================

    async def is_following(self, follower_id: int, following_id: int) -> bool:
        """判断 follower 是否已关注 following。
        按联合 PK 查询，O(log n) 性能。"""
        result = await self.session.execute(
            select(Follower).where(
                Follower.follower_id == follower_id,
                Follower.following_id == following_id,
            )
        )
        return result.scalar_one_or_none() is not None

    # ========================================================================
    # 关系操作（幂等）
    # ========================================================================

    async def follow(self, follower_id: int, following_id: int) -> None:
        """关注用户——幂等操作。
        先检查是否已关注 → 已关注则跳过（不报错）。"""
        exists = await self.is_following(follower_id, following_id)
        if exists:
            return  # 幂等：已关注则不做任何操作
        follow = Follower(follower_id=follower_id, following_id=following_id)
        self.session.add(follow)
        await self.session.commit()

    async def unfollow(self, follower_id: int, following_id: int) -> None:
        """取消关注——幂等操作。
        DELETE 无匹配行时不报错。"""
        stmt = delete(Follower).where(
            Follower.follower_id == follower_id,
            Follower.following_id == following_id,
        )
        await self.session.execute(stmt)
        await self.session.commit()

    # ========================================================================
    # 列表查询
    # ========================================================================

    async def list_followers(self, user_id: int, skip: int = 0, limit: int = 100) -> list[User]:
        """获取某用户的粉丝列表（关注了 user_id 的人）。

        SQL 逻辑：
        SELECT users.* FROM users
        JOIN followers ON followers.follower_id = users.id
        WHERE followers.following_id = user_id

        索引利用：ix_followers_following_id 索引覆盖 WHERE following_id=? 条件。
        """
        result = await self.session.execute(
            select(User)
            .join(Follower, Follower.follower_id == User.id)
            .where(Follower.following_id == user_id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_following(self, user_id: int, skip: int = 0, limit: int = 100) -> list[User]:
        """获取某用户的关注列表（user_id 关注了谁）。

        SQL 逻辑：
        SELECT users.* FROM users
        JOIN followers ON followers.following_id = users.id
        WHERE followers.follower_id = user_id

        索引利用：PK 索引 (follower_id, following_id) 的 follower_id 前缀。
        """
        result = await self.session.execute(
            select(User)
            .join(Follower, Follower.following_id == User.id)
            .where(Follower.follower_id == user_id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_following_ids(self, follower_id: int) -> set[int]:
        """获取某用户关注的所有用户 ID（返回 set[int]）。
        用于高效判断多个用户中哪些已被关注——一次性获取全部 ID，避免 N+1。"""
        result = await self.session.execute(
            select(Follower.following_id).where(Follower.follower_id == follower_id)
        )
        return set(result.scalars().all())
