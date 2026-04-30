"""收藏数据访问层（Favorite Repository）。

封装用户收藏文章的数据库操作：查询、添加、删除。

幂等设计：
- add() 方法先检查是否已存在 → 存在则返回已有记录（created=False）
  不存在则创建（created=True）
- remove() 方法对不存在的记录也不报错（delete 无匹配行 ≠ 异常）
- 这种设计让 Agent 工具和 API 调用方无需事先检查收藏状态
"""

from sqlalchemy import case, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.article import Article
from app.db.models.favorite import Favorite


class FavoriteRepository:
    """收藏数据访问层——封装 Favorite 关联表的所有操作。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: int, article_id: int) -> Favorite | None:
        """按联合主键 (user_id, article_id) 查询收藏记录。
        使用 PK 索引，查询性能最优。"""
        result = await self.session.execute(
            select(Favorite).where(
                Favorite.user_id == user_id,
                Favorite.article_id == article_id,
            )
        )
        return result.scalar_one_or_none()

    async def add(self, user_id: int, article_id: int) -> tuple[Favorite, bool]:
        """收藏文章——幂等操作。

        返回元组 (favorite, created)：
        - created=True：新建收藏记录
        - created=False：记录已存在（幂等保护）

        注意：不检查 article_id 是否有效——由调用方保证文章存在。"""
        existing = await self.get(user_id, article_id)
        if existing:
            return existing, False  # 已收藏，返回已有记录
        favorite = Favorite(user_id=user_id, article_id=article_id)
        self.session.add(favorite)
        await self.session.execute(
            update(Article)
            .where(Article.id == article_id)
            .values(favorites_count=Article.favorites_count + 1)
        )
        await self.session.commit()
        return favorite, True  # 新建收藏

    async def remove(self, user_id: int, article_id: int) -> bool:
        """取消收藏——幂等操作。
        如果没收藏（无匹配行），DELETE 语句正常执行但不会出错。"""
        existing = await self.get(user_id, article_id)
        if not existing:
            return False

        stmt = delete(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.article_id == article_id,
        )
        await self.session.execute(stmt)
        await self.session.execute(
            update(Article)
            .where(Article.id == article_id)
            .values(
                favorites_count=case(
                    (Article.favorites_count > 0, Article.favorites_count - 1),
                    else_=0,
                )
            )
        )
        await self.session.commit()
        return True
