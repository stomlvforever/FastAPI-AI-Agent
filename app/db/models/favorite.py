"""收藏 ORM 模型。

定义用户收藏文章的关联关系。

设计要点：
1. 联合主键 (user_id, article_id)：保证同一用户不会重复收藏同一篇文章
2. PK 索引只覆盖左前缀 user_id：
   - WHERE user_id=? → 走 PK 索引（回表查收藏列表）
   - WHERE article_id=? → 不走 PK 索引（需要统计某文章的收藏数时）
   → 所以显式创建了 ix_favorites_article_id 索引
3. 此表用途：
   - 支持文章详情中的"已收藏/未收藏"状态
   - 历史数据校准时按 article_id 统计收藏数
   - 用户的收藏列表
"""

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Favorite(Base):
    """收藏关联表——记录用户收藏了哪些文章。"""

    __tablename__ = "favorites"

    # ---- 联合主键 ----
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # 收藏者：ondelete="CASCADE" 删除用户时清理收藏记录

    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    # 被收藏的文章：ondelete="CASCADE" 删除文章时清理收藏记录

    # ---- 表级约束 ----
    # 显式索引：PK 索引是 (user_id, article_id)，对 article_id 的查询走不了 PK 索引
    # 以下索引用于收藏数回填和校准任务（WHERE article_id=? / GROUP BY article_id）
    __table_args__ = (
        Index("ix_favorites_article_id", "article_id"),
    )
