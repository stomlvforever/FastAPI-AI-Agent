"""Tests for article permission behavior (owner/admin)."""

import pytest
import pytest_asyncio

from app.core.security import create_access_token, get_password_hash
from app.db.models.user import User


@pytest_asyncio.fixture()
async def admin_user(db_session):
    user = User(
        email="article-admin@example.com",
        hashed_password=get_password_hash("adminpass123"),
        full_name="Article Admin",
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture()
async def other_user(db_session):
    user = User(
        email="other-user@example.com",
        hashed_password=get_password_hash("otherpass123"),
        full_name="Other User",
        role="user",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture()
def admin_headers(admin_user: User) -> dict[str, str]:
    token = create_access_token(subject=admin_user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def other_headers(other_user: User) -> dict[str, str]:
    token = create_access_token(subject=other_user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_can_delete_article(client, auth_headers, admin_headers):
    create_resp = await client.post(
        "/api/v1/articles",
        json={
            "title": "owner article",
            "description": "test",
            "body": "markdown body",
            "tag_names": [],
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    slug = create_resp.json()["slug"]

    delete_resp = await client.delete(f"/api/v1/articles/{slug}", headers=admin_headers)
    assert delete_resp.status_code == 200

    get_resp = await client.get(f"/api/v1/articles/{slug}", headers=auth_headers)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_non_owner_non_admin_cannot_delete_article(client, auth_headers, other_headers):
    create_resp = await client.post(
        "/api/v1/articles",
        json={
            "title": "owner article 2",
            "description": "test",
            "body": "markdown body",
            "tag_names": [],
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    slug = create_resp.json()["slug"]

    delete_resp = await client.delete(f"/api/v1/articles/{slug}", headers=other_headers)
    assert delete_resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_update_article(client, auth_headers, admin_headers):
    create_resp = await client.post(
        "/api/v1/articles",
        json={
            "title": "original title",
            "description": "test",
            "body": "markdown body",
            "tag_names": [],
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    slug = create_resp.json()["slug"]

    update_resp = await client.put(
        f"/api/v1/articles/{slug}",
        json={"title": "updated by admin"},
        headers=admin_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "updated by admin"
