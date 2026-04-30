"""add_articles_favorites_followers

Revision ID: 8f0c9d3e1b2a
Revises: 5c076dcc4211
Create Date: 2026-02-15 00:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8f0c9d3e1b2a"
down_revision: Union[str, None] = "5c076dcc4211"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Articles
    op.create_table(
        "articles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(op.f("ix_articles_slug"), "articles", ["slug"], unique=True)
    op.create_index(op.f("ix_articles_author_id"), "articles", ["author_id"], unique=False)

    # Article-Tag association
    op.create_table(
        "article_tags",
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )

    # Favorites
    op.create_table(
        "favorites",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
    )

    # Followers
    op.create_table(
        "followers",
        sa.Column("follower_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("following_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("followers")
    op.drop_table("favorites")
    op.drop_table("article_tags")
    op.drop_index(op.f("ix_articles_author_id"), table_name="articles")
    op.drop_index(op.f("ix_articles_slug"), table_name="articles")
    op.drop_table("articles")
