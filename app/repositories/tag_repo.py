"""标签数据访问层（Tag Repository）。

封装 Tag 模型的 CRUD 和 Item-Tag 多对多关联表的维护操作。

关联表操作说明：
item_tags 是用 SQLAlchemy Core Table 定义的（在 tag.py 中），不通过 ORM relationship 操作。
直接使用 Core 的 insert/delete 语句操作关联表——相比 ORM 的 append/remove：
1. 不需要先加载关联对象（节省一次 SELECT）
2. 直接 INSERT/DELETE 关联表行，性能更高
3. 适合"给 Item 加标签"这种高频操作
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.item import Item
from app.db.models.tag import Tag, item_tags


class TagRepository:
    """标签数据访问层——封装 Tag 表及 item_tags 关联表的所有操作。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ========================================================================
    # 标签 CRUD
    # ========================================================================

    async def get(self, tag_id: int) -> Tag | None:
        """按主键获取标签。"""
        return await self.session.get(Tag, tag_id)

    async def get_by_id(self, tag_id: int) -> Tag | None:
        """按 ID 获取标签——语义清晰的别名。"""
        return await self.session.get(Tag, tag_id)

    async def get_by_name(self, name: str) -> Tag | None:
        """按名称获取标签——name 列有 unique 索引，始终只返回一条。"""
        result = await self.session.execute(select(Tag).where(Tag.name == name))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Tag]:
        """获取所有标签——按名称字母序排列。"""
        result = await self.session.execute(select(Tag).order_by(Tag.name))
        return list(result.scalars().all())

    async def create(self, name: str) -> Tag:
        """创建新标签——name 唯一，重复会触发数据库 unique 约束错误。"""
        tag = Tag(name=name)
        self.session.add(tag)
        await self.session.commit()
        await self.session.refresh(tag)
        return tag

    async def delete(self, tag: Tag) -> Tag:
        """删除标签——ondelete="CASCADE" 会同步清理关联表中的记录。"""
        await self.session.delete(tag)
        await self.session.commit()
        return tag

    # ========================================================================
    # Item-Tag 关联操作（直接操作 Core Table）
    # ========================================================================

    async def add_tag_to_item(self, item_id: int, tag_id: int) -> None:
        """给 Item 添加一个标签——直接 INSERT 关联表。

        使用 Core Table 的 insert() 而非 ORM relationship：
        - 优点：一条 SQL，不需要先加载 Item 对象的 tags 列表
        - 缺点：联合 PK 冲突时会直接抛 IntegrityError，调用方需自行处理
        """
        stmt = item_tags.insert().values(item_id=item_id, tag_id=tag_id)
        await self.session.execute(stmt)
        await self.session.commit()

    async def remove_tag_from_item(self, item_id: int, tag_id: int) -> None:
        """从 Item 移除一个标签——直接 DELETE 关联表记录。

        使用 Core Table 的 delete()：按联合主键 (item_id, tag_id) 精确定位并删除。
        """
        stmt = delete(item_tags).where(
            item_tags.c.item_id == item_id,
            item_tags.c.tag_id == tag_id,
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def get_tags_for_item(self, item_id: int) -> list[Tag]:
        """获取某个 Item 的全部标签——通过关联表 JOIN 查询。

        SQL 等价于：
        SELECT tags.* FROM tags
        JOIN item_tags ON tags.id = item_tags.tag_id
        WHERE item_tags.item_id = ?
        ORDER BY tags.name

        索引利用：
        - item_tags PK (item_id, tag_id) → WHERE item_id=? 走 PK 索引（高效）
        - JOIN ON tag_id → 需要 ix_item_tags_tag_id 索引优化（如果数据量大）
        """
        stmt = (
            select(Tag)
            .join(item_tags, Tag.id == item_tags.c.tag_id)
            .where(item_tags.c.item_id == item_id)
            .order_by(Tag.name)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
