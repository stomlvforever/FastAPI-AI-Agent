"""add performance indexes

Revision ID: a3f7b9c12d45
Revises: 8f0c9d3e1b2a
Create Date: 2025-01-01 00:00:00.000000

为所有高频查询缺失的索引补齐：
  - FK 列索引（PostgreSQL 不自动创建）
  - 排序列索引（ORDER BY created_at）
  - 联合 PK 第二列单独索引（反向查询 / COUNT 子查询）
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a3f7b9c12d45"
down_revision = "8f0c9d3e1b2a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ===== items 表 =====
    # 高优先级：FK 列 owner_id，加速 WHERE owner_id=? （get_items_by_user）
    op.create_index("ix_items_owner_id", "items", ["owner_id"])
    # 中优先级：排序列 created_at，加速 ORDER BY created_at
    op.create_index("ix_items_created_at", "items", ["created_at"])

    # ===== comments 表 =====
    # 高优先级：FK 列 item_id，加速 WHERE item_id=? （get_comments_by_item）
    op.create_index("ix_comments_item_id", "comments", ["item_id"])
    # 中优先级：FK 列 author_id，加速级联删除 + 反向查询
    op.create_index("ix_comments_author_id", "comments", ["author_id"])
    # 中优先级：排序列 created_at
    op.create_index("ix_comments_created_at", "comments", ["created_at"])

    # ===== favorites 表 =====
    # 高优先级：联合 PK 第二列 article_id，加速 COUNT(WHERE article_id=?) 收藏计数子查询
    op.create_index("ix_favorites_article_id", "favorites", ["article_id"])

    # ===== followers 表 =====
    # 高优先级：联合 PK 第二列 following_id，加速 get_followers JOIN + feed 查询
    op.create_index("ix_followers_following_id", "followers", ["following_id"])

    # ===== articles 表 =====
    # 中优先级：排序列 created_at，加速文章列表/Feed 默认排序
    op.create_index("ix_articles_created_at", "articles", ["created_at"])

    # ===== item_tags 关联表 =====
    # 低优先级：联合 PK 第二列 tag_id，加速反向查询（某 tag 下的所有 items）
    op.create_index("ix_item_tags_tag_id", "item_tags", ["tag_id"])

    # ===== article_tags 关联表 =====
    # 低优先级：联合 PK 第二列 tag_id，加速反向查询（某 tag 下的所有 articles）
    op.create_index("ix_article_tags_tag_id", "article_tags", ["tag_id"])


def downgrade() -> None:
    op.drop_index("ix_article_tags_tag_id", "article_tags")
    op.drop_index("ix_item_tags_tag_id", "item_tags")
    op.drop_index("ix_articles_created_at", "articles")
    op.drop_index("ix_followers_following_id", "followers")
    op.drop_index("ix_favorites_article_id", "favorites")
    op.drop_index("ix_comments_created_at", "comments")
    op.drop_index("ix_comments_author_id", "comments")
    op.drop_index("ix_comments_item_id", "comments")
    op.drop_index("ix_items_created_at", "items")
    op.drop_index("ix_items_owner_id", "items")
