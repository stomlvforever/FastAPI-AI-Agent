"""标签 ORM 模型。

定义标签表和 Item-Tag 多对多关联表（item_tags）。

标签是一种全局共享的分类词，用于组织和过滤 Items 和 Articles：
- 每个标签有唯一的名称
- 一个 Item 可以有多个标签，一个标签可以关联多个 Item（多对多）
- 关联表使用轻量级 Table 定义（非 ORM 类），只存储外键对

关联表设计：
- 联合主键 (item_id, tag_id)：保证同一 Item 不会重复挂同一个 Tag
- ondelete="CASCADE"：删除 Item 或 Tag 时自动清理关联记录
- Index("ix_item_tags_tag_id", "tag_id")：
  PK 索引只覆盖左前缀 item_id，tag_id 的单独查询需要额外索引
"""

from sqlalchemy import Column, ForeignKey, Index, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# ============================================================================
# 关联表：items ↔ tags（多对多）
# ============================================================================
# 使用 Table 而非 ORM 类——关联表不需要独立 CRUD，仅作为连接 bridge
# 定义在 Tag 类之前，因为 Item 模型的 tags 字段需要引用它
item_tags = Table(
    "item_tags",
    Base.metadata,
    # 联合主键：item_id + tag_id，确保同一关系不会重复
    Column("item_id", Integer, ForeignKey("items.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    # 为 tag_id 单独建索引：
    # 联合 PK B-tree 按 (item_id, tag_id) 排序 → 对 tag_id 的等值/范围查询走不了 PK 索引
    # 需要独立索引支持"某标签下有多少 Item"这类反查
    Index("ix_item_tags_tag_id", "tag_id"),
)


class Tag(Base):
    """标签表——存储全局标签名称。"""

    __tablename__ = "tags"

    # ---- 主键 ----
    id: Mapped[int] = mapped_column(primary_key=True)

    # ---- 基本字段 ----
    name: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    # 标签名：unique 保证不重复，index 加速按名称查找

    # ============================================================================
    # Relationships
    # ============================================================================

    # 多对多：Tag → Items（通过 item_tags 关联表）
    # back_populates="tags"：对应 Item 模型中的 tags 字段
    items: Mapped[list["Item"]] = relationship(
        "Item", secondary=item_tags, back_populates="tags"
    )
