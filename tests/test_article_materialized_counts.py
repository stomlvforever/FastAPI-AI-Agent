"""文章物化计数字段与分页排序测试。"""

import pytest
from sqlalchemy import select, update

from app.core.security import create_access_token, get_password_hash
from app.db.models.article import Article
from app.db.models.user import User


async def _create_article(client, headers, title: str) -> dict:
    response = await client.post(
        "/api/v1/articles",
        json={
            "title": title,
            "description": "materialized counter test",
            "body": "markdown body",
            "tag_names": [],
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


async def _article_counter(db_session, slug: str, column_name: str) -> int:
    column = getattr(Article, column_name)
    result = await db_session.execute(select(column).where(Article.slug == slug))
    return result.scalar_one()


async def _admin_headers(db_session) -> dict[str, str]:
    admin = User(
        email="counter-admin@example.com",
        hashed_password=get_password_hash("adminpass123"),
        full_name="Counter Admin",
        role="admin",
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    token = create_access_token(subject=admin.email)
    return {"Authorization": f"Bearer {token}"}


def test_article_model_has_materialized_counter_columns_and_indexes():
    """文章表声明物化计数字段，并为高频排序列提供稳定联合索引。"""
    columns = Article.__table__.columns
    for column_name in [
        "favorites_count",
        "comments_count",
        "references_count",
        "views_count",
    ]:
        assert column_name in columns
        assert columns[column_name].nullable is False

    index_names = {idx.name for idx in Article.__table__.indexes}
    assert "ix_articles_created_at_id" in index_names
    assert "ix_articles_favorites_count_id" in index_names
    assert "ix_articles_comments_count_id" in index_names
    assert "ix_articles_references_count_id" in index_names
    assert "ix_articles_views_count_id" in index_names


@pytest.mark.asyncio
async def test_favorite_and_unfavorite_sync_article_favorites_count_column(
    client,
    auth_headers,
    db_session,
):
    article = await _create_article(client, auth_headers, "counter sync article")
    slug = article["slug"]
    assert article["favorites_count"] == 0
    assert article["comments_count"] == 0
    assert article["references_count"] == 0
    assert article["views_count"] == 0

    favorite_response = await client.post(
        f"/api/v1/articles/{slug}/favorite",
        headers=auth_headers,
    )
    assert favorite_response.status_code == 200
    assert favorite_response.json()["favorites_count"] == 1
    assert await _article_counter(db_session, slug, "favorites_count") == 1

    duplicate_response = await client.post(
        f"/api/v1/articles/{slug}/favorite",
        headers=auth_headers,
    )
    assert duplicate_response.status_code == 200
    assert duplicate_response.json()["favorites_count"] == 1
    assert await _article_counter(db_session, slug, "favorites_count") == 1

    unfavorite_response = await client.delete(
        f"/api/v1/articles/{slug}/favorite",
        headers=auth_headers,
    )
    assert unfavorite_response.status_code == 200
    assert unfavorite_response.json()["favorites_count"] == 0
    assert await _article_counter(db_session, slug, "favorites_count") == 0

    duplicate_unfavorite_response = await client.delete(
        f"/api/v1/articles/{slug}/favorite",
        headers=auth_headers,
    )
    assert duplicate_unfavorite_response.status_code == 200
    assert duplicate_unfavorite_response.json()["favorites_count"] == 0
    assert await _article_counter(db_session, slug, "favorites_count") == 0


@pytest.mark.asyncio
async def test_article_list_sorts_by_count_and_falls_back_for_invalid_sort_by(
    client,
    auth_headers,
):
    high = await _create_article(client, auth_headers, "high favorite article")
    low = await _create_article(client, auth_headers, "low favorite article")

    favorite_response = await client.post(
        f"/api/v1/articles/{high['slug']}/favorite",
        headers=auth_headers,
    )
    assert favorite_response.status_code == 200

    count_sorted = await client.get(
        "/api/v1/articles?sort_by=favorites_count&order=desc&skip=0&limit=2",
        headers=auth_headers,
    )
    assert count_sorted.status_code == 200
    count_sorted_titles = [item["title"] for item in count_sorted.json()]
    assert count_sorted_titles[0] == high["title"]

    fallback_sorted = await client.get(
        "/api/v1/articles?sort_by=bad_field&order=desc&skip=0&limit=2",
        headers=auth_headers,
    )
    assert fallback_sorted.status_code == 200
    fallback_titles = [item["title"] for item in fallback_sorted.json()]
    assert fallback_titles[0] == low["title"]


@pytest.mark.asyncio
async def test_admin_recalculate_counters_repairs_materialized_columns(
    client,
    auth_headers,
    db_session,
):
    article = await _create_article(client, auth_headers, "counter repair article")
    slug = article["slug"]

    favorite_response = await client.post(
        f"/api/v1/articles/{slug}/favorite",
        headers=auth_headers,
    )
    assert favorite_response.status_code == 200

    await db_session.execute(
        update(Article)
        .where(Article.slug == slug)
        .values(favorites_count=99, comments_count=8, references_count=6)
    )
    await db_session.commit()

    headers = await _admin_headers(db_session)
    recalculate_response = await client.post(
        "/api/v1/articles/counters/recalculate",
        headers=headers,
    )
    assert recalculate_response.status_code == 200
    assert recalculate_response.json()["articles_checked"] == 1

    assert await _article_counter(db_session, slug, "favorites_count") == 1
    assert await _article_counter(db_session, slug, "comments_count") == 0
    assert await _article_counter(db_session, slug, "references_count") == 0
