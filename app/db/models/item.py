"""Item ORM 模型。

定义 Item 表（待办事项风格的资源管理），支持：
- 属性：标题、描述、优先级（1-5）、状态（pending/done）
- 所有权：每个 Item 属于一个 User（通过 owner_id 外键）
- 标签：与 Tag 的多对多关系（通过 item_tags 关联表）
- 评论：与 Comment 的一对多关系（一个 Item 有多条评论）

索引策略：
- owner_id 索引：加速 WHERE owner_id=? 查询（最常用的过滤条件）
- created_at 索引：加速 ORDER BY created_at 排序

关联关系：
- lazy="selectin"：对 tags 和 comments 使用预加载策略，一次 IN 查询加载所有关联数据
- cascade="all, delete-orphan"：删除 Item 时自动删除其所有评论（级联删除）
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.tag import item_tags  # 导入多对多关联表


class Item(Base):
    """Item 表——待办事项风格的资源记录。"""

    __tablename__ = "items"

    # ---- 主键 ----
    id: Mapped[int] = mapped_column(primary_key=True)

    # ---- 基本字段 ----
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # 标题：不能为空

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 描述：可选字段

    priority: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    # 优先级：1=高, 2=中, 3-5=从高到低（默认 3）

    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending"
    )
    # 状态：pending=待办, done=已完成（默认 pending）

    # ---- 外键 ----
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    # 所属用户：index=True 加速按拥有者过滤的查询

    # ---- 时间戳 ----
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    # 创建时间：index=True 加速按时间排序

    # ============================================================================
    # Relationships
    # ============================================================================

    # 多对一：Item → 拥有者（User）
    owner: Mapped["User"] = relationship("User", back_populates="items")

    # 多对多：Item → 标签（通过 item_tags 关联表）
    # lazy="selectin"：查询 Item 时一并加载标签，避免 N+1
    tags: Mapped[list["Tag"]] = relationship(
        "Tag", secondary=item_tags, back_populates="items", lazy="selectin",
    )

    # 一对多：Item → 评论列表
    # cascade="all, delete-orphan"：删除 Item 时自动级联删除其所有评论
    # lazy="selectin"：查询 Item 时一并加载评论
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="item", cascade="all, delete-orphan", lazy="selectin",
    )
