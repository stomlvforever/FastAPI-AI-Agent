"""评论数据访问层（Comment Repository）。

封装 Comment 模型的数据库操作：按 Item 查询、创建、删除。

索引利用：
- WHERE item_id=? → 走 ix_comments_item_id 索引
- ORDER BY created_at → 走 ix_comments_created_at 索引
- WHERE author_id=? → 走 ix_comments_author_id 索引（删除用户时的级联查询）
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.comment import Comment


class CommentRepository:
    """评论数据访问层——封装 Comment 表的所有数据库操作。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ========================================================================
    # 查询方法
    # ========================================================================

    async def get(self, comment_id: int) -> Comment | None:
        """按主键获取评论。"""
        return await self.session.get(Comment, comment_id)

    async def get_by_id(self, comment_id: int) -> Comment | None:
        """按 ID 获取评论——语义清晰的别名。"""
        return await self.session.get(Comment, comment_id)

    async def list_by_item(self, item_id: int) -> list[Comment]:
        """获取某个 Item 下的所有评论——按创建时间正序（最早的在前面）。

        查询计划：
        WHERE item_id=? ORDER BY created_at ASC
        → PostgreSQL 用 ix_comments_item_id 索引定位 + 内存排序（数据量小时）
        → 或使用复合索引 (item_id, created_at) 直接扫描（需单独创建）
        """
        result = await self.session.execute(
            select(Comment)
            .where(Comment.item_id == item_id)
            .order_by(Comment.created_at.asc())
        )
        return list(result.scalars().all())

    # ========================================================================
    # 写方法
    # ========================================================================

    async def create(self, item_id: int, author_id: int, body: str) -> Comment:
        """创建新评论——关联到指定 Item 和作者。"""
        comment = Comment(item_id=item_id, author_id=author_id, body=body)
        self.session.add(comment)
        await self.session.commit()
        await self.session.refresh(comment)
        return comment

    async def delete(self, comment: Comment) -> Comment:
        """删除评论——同步完成后返回被删除的评论对象。"""
        await self.session.delete(comment)
        await self.session.commit()
        return comment
