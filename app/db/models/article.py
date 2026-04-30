"""文章 ORM 模型。

定义文章表字段、与用户的作者关系、与标签的多对多关系。

slug 机制：
- slug 是文章的唯一 URL 标识（如 "hello-world"）
- 创建文章时由 python-slugify 从标题自动生成
- unique=True + index=True：保证 URL 唯一性，支持按 slug 快速查找

标签多对多关系：
- 使用 SQLAlchemy Core Table 定义关联表 article_tags（非 ORM 类，更轻量）
- Article.tags = relationship(secondary=article_tags, lazy="selectin")
- lazy="selectin"：在查询文章时用一次额外的 IN 子查询加载所有标签，避免 N+1
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# ============================================================================
# 关联表：articles ↔ tags（多对多）
# ============================================================================
# 使用 SQLAlchemy Core 的 Table（而非 ORM 类），因为关联表不需要单独的业务实体
# 联合主键 (article_id, tag_id) 保证同一文章不会重复挂同一个标签
# ondelete="CASCADE"：删除文章/标签时自动清理关联记录
# Index("ix_article_tags_tag_id", "tag_id")：
#   联合 PK 的 B-tree 索引只覆盖左前缀 article_id
#   对 tag_id 的单独查询（如"某标签下有哪些文章"）需要额外索引
article_tags = Table(
    "article_tags",
    Base.metadata,
    Column("article_id", Integer, ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_article_tags_tag_id", "tag_id"),
)


class Article(Base):
    """文章表——博客系统的核心实体。"""

    __tablename__ = "articles"
    __table_args__ = (
        Index("ix_articles_created_at_id", "created_at", "id"),
        Index("ix_articles_favorites_count_id", "favorites_count", "id"),
        Index("ix_articles_comments_count_id", "comments_count", "id"),
        Index("ix_articles_references_count_id", "references_count", "id"),
        Index("ix_articles_views_count_id", "views_count", "id"),
    )

    # ---- 主键 ----
    id: Mapped[int] = mapped_column(primary_key=True)

    # ---- 基本字段 ----
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # 文章标题：不能为空

    slug: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    # URL 友好的标识符：从标题自动生成，unique 保证 URL 唯一性

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 文章摘要/描述：可选字段

    body: Mapped[str] = mapped_column(Text, nullable=False)
    # 文章正文：TEXT 类型，支持长文本

    # ---- 外键 ----
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 作者 ID：index=True 加速按作者过滤文章的查询

    # ---- 时间戳 ----
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    # 创建时间：index=True 加速按创建时间排序

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # 最后更新时间：onupdate=func.now() 在 UPDATE 时自动刷新

    # ---- 物化计数字段 ----
    favorites_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # 收藏数：收藏/取消收藏时同步维护，列表排序直接读取该列

    comments_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # 文章评论数：预留给文章评论业务，避免列表实时聚合评论表

    references_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # 被引用次数：预留给引用业务，避免列表实时聚合引用表

    views_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # 阅读数：用于热门排序或运营统计

    # ============================================================================
    # Relationships
    # ============================================================================

    # 多对一：文章 → 作者（User）
    author: Mapped["User"] = relationship("User", back_populates="articles")

    # 多对多：文章 → 标签（通过 article_tags 关联表）
    # lazy="selectin"：查询文章时一并加载标签，一次额外 IN 查询替代 N+1
    tags: Mapped[list["Tag"]] = relationship(
        "Tag",
        secondary=article_tags,
        lazy="selectin",
    )
