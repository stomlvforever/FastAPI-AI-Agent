"""评论 ORM 模型。

定义评论表字段，以及与 Item（被评论对象）和 User（评论者）之间的多对一关联。

索引策略：
- item_id 索引：加速 WHERE item_id=? 查询（查看某 Item 下的所有评论）
- author_id 索引：加速级联删除（删除用户时找其评论）和查询某用户的所有评论
- created_at 索引：加速 ORDER BY created_at 排序

注意：PostgreSQL 不会自动为外键列创建索引（这点与 MySQL 不同），
      所以所有 FK 列都显式添加了 index=True。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Comment(Base):
    """评论表——用户对 Item 的评论。"""

    __tablename__ = "comments"

    # ---- 主键 ----
    id: Mapped[int] = mapped_column(primary_key=True)

    # ---- 基本字段 ----
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # 评论内容：TEXT 类型，支持较长文本

    # ---- 外键（附索引） ----
    item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,  # 加速 WHERE item_id=? 的查询
    )
    # 所属 Item：ondelete="CASCADE" 删除 Item 时自动清理其所有评论

    author_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,  # 加速级联删除和"某用户的所有评论"查询
    )
    # 评论作者：ondelete="CASCADE" 删除用户时自动清理其所有评论

    # ---- 时间戳 ----
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    # 创建时间：index=True 加速按时间排序

    # ============================================================================
    # Relationships
    # ============================================================================

    # 多对一：评论 → Item（被评论对象）
    item: Mapped["Item"] = relationship("Item", back_populates="comments")

    # 多对一：评论 → User（评论者）
    author: Mapped["User"] = relationship("User", back_populates="comments")
