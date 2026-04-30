"""Item 数据访问层（Item Repository）。

封装 Item 模型的数据库操作：按拥有者查询（含筛选/排序）、创建、更新、删除。

排序白名单机制：
- 只允许按 priority / created_at / title 排序
- 目的：防止恶意传入任意 SQL 列名（纵深防御，ORM 层面虽然相对安全）
- 不在白名单中的 sort_by 值 → 回退到默认排序列（priority）

索引利用：
- WHERE owner_id=? → 走 ix_items_owner_id 索引
- ORDER BY created_at → 走 ix_items_created_at 索引（避免 filesort）
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.item import Item


class ItemRepository:
    """Item 数据访问层——封装 Item 表的所有数据库操作。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ========================================================================
    # 查询方法
    # ========================================================================

    async def get(self, item_id: int) -> Item | None:
        """按主键获取 Item。"""
        return await self.session.get(Item, item_id)

    async def list_by_owner(
        self, owner_id: int, skip: int = 0, limit: int = 100,
        priority: int | None = None, status: str | None = None,
        sort_by: str = "priority", order: str = "asc",
    ) -> list[Item]:
        """按拥有者查询 Item 列表——支持优先级和状态过滤、动态排序。

        参数：
        - owner_id: 拥有者用户 ID（必填——保证所有权隔离）
        - priority: 按优先级过滤（None=不过滤）
        - status: 按状态过滤（None=不过滤）
        - sort_by: 排序列（白名单校验）
        - order: 排序方向（asc / desc）
        """
        # 基础查询：按拥有者过滤
        query = select(Item).where(Item.owner_id == owner_id)

        # 可选过滤条件
        if priority is not None:
            query = query.where(Item.priority == priority)
        if status is not None:
            query = query.where(Item.status == status)

        # ---- 动态排序（白名单） ----
        # 只允许按这三个列排序，减少 SQL 注入风险和意外的全表扫描
        allowed_sort = {
            "priority": Item.priority,
            "created_at": Item.created_at,
            "title": Item.title,
        }
        sort_column = allowed_sort.get(sort_by, Item.priority)  # 默认按优先级
        if order == "desc":
            sort_column = sort_column.desc()

        query = query.order_by(sort_column).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # ========================================================================
    # 写方法
    # ========================================================================

    async def create(
        self,
        owner_id: int,
        title: str,
        description: str | None,
        priority: int = 3,
        status: str = "pending",
    ) -> Item:
        """创建新 Item——自动归属指定用户。"""
        item = Item(
            owner_id=owner_id, title=title, description=description,
            priority=priority, status=status,
        )
        self.session.add(item)
        await self.session.commit()
        # refresh 获取自增 id 和 server_default 填充的 created_at
        await self.session.refresh(item)
        return item

    async def update(self, item: Item, data: dict) -> Item:
        """按字典更新 Item 字段——只更新传入的字段。"""
        for key, value in data.items():
            setattr(item, key, value)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def delete(self, item: Item) -> Item:
        """删除 Item——ORM cascade 级联删除关联的 Comment 记录。"""
        await self.session.delete(item)
        await self.session.commit()
        return item
