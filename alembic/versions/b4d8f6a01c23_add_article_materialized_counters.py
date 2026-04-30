"""add article materialized counters

Revision ID: b4d8f6a01c23
Revises: a3f7b9c12d45
Create Date: 2026-04-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b4d8f6a01c23"
down_revision: Union[str, None] = "a3f7b9c12d45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column("favorites_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "articles",
        sa.Column("comments_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "articles",
        sa.Column("references_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "articles",
        sa.Column("views_count", sa.Integer(), server_default="0", nullable=False),
    )

    op.execute(
        """
        UPDATE articles
        SET favorites_count = 0,
            comments_count = 0,
            references_count = 0,
            views_count = 0
        """
    )
    op.execute(
        """
        UPDATE articles
        SET favorites_count = favorite_counts.count_value
        FROM (
            SELECT article_id, COUNT(*) AS count_value
            FROM favorites
            GROUP BY article_id
        ) AS favorite_counts
        WHERE articles.id = favorite_counts.article_id
        """
    )

    op.create_index("ix_articles_created_at_id", "articles", ["created_at", "id"])
    op.create_index("ix_articles_favorites_count_id", "articles", ["favorites_count", "id"])
    op.create_index("ix_articles_comments_count_id", "articles", ["comments_count", "id"])
    op.create_index("ix_articles_references_count_id", "articles", ["references_count", "id"])
    op.create_index("ix_articles_views_count_id", "articles", ["views_count", "id"])


def downgrade() -> None:
    op.drop_index("ix_articles_views_count_id", table_name="articles")
    op.drop_index("ix_articles_references_count_id", table_name="articles")
    op.drop_index("ix_articles_comments_count_id", table_name="articles")
    op.drop_index("ix_articles_favorites_count_id", table_name="articles")
    op.drop_index("ix_articles_created_at_id", table_name="articles")

    op.drop_column("articles", "views_count")
    op.drop_column("articles", "references_count")
    op.drop_column("articles", "comments_count")
    op.drop_column("articles", "favorites_count")
