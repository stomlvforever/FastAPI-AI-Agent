"""
Tests for Role-Based Access Control (RBAC).

Key idea:
- Regular user (role="user") -> gets 403 on admin endpoints
- Admin user (role="admin") -> gets 200 on admin endpoints
- Both can access normal endpoints

This demonstrates WHY roles matter:
without roles, any logged-in user could see everyone's data!
"""
import pytest
import pytest_asyncio

from app.core.security import create_access_token, get_password_hash
from app.db.models.user import User


@pytest_asyncio.fixture()
async def admin_user(db_session):
    """Create an admin user in the test database."""
    user = User(
        email="admin@example.com",
        hashed_password=get_password_hash("adminpass123"),
        full_name="Admin Boss",
        role="admin",  # <-- THE key difference!
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture()
def admin_headers(admin_user: User) -> dict[str, str]:
    """JWT headers for the admin user."""
    token = create_access_token(subject=admin_user.email)
    return {"Authorization": f"Bearer {token}"}


# ==================== Admin Endpoint Tests ====================

@pytest.mark.asyncio
async def test_admin_can_access_all_items(client, admin_headers):
    """Admin can access GET /api/v1/admin/all-items -> 200"""
    response = await client.get("/api/v1/admin/all-items", headers=admin_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_regular_user_cannot_access_admin_endpoint(client, auth_headers):
    """Regular user gets 403 Forbidden on admin endpoint"""
    response = await client.get("/api/v1/admin/all-items", headers=auth_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_cannot_access_admin_endpoint(client):
    """No token at all -> 401 Unauthorized"""
    response = await client.get("/api/v1/admin/all-items")
    assert response.status_code == 401


# ==================== Admin Can See All Users' Items ====================

@pytest.mark.asyncio
async def test_admin_sees_all_items(client, auth_headers, admin_headers):
    """
    Regular user creates items -> Admin can see them via admin endpoint.
    Regular user can NOT see other users' items via normal endpoint.
    """
    # Regular user creates 2 items
    await client.post(
        "/api/v1/items", json={"title": "User's task"}, headers=auth_headers
    )
    await client.post(
        "/api/v1/items", json={"title": "User's task 2"}, headers=auth_headers
    )

    # Admin creates 1 item
    await client.post(
        "/api/v1/items", json={"title": "Admin's task"}, headers=admin_headers
    )

    # Admin endpoint: sees ALL 3 items
    admin_resp = await client.get("/api/v1/admin/all-items", headers=admin_headers)
    assert admin_resp.status_code == 200
    assert len(admin_resp.json()) == 3

    # Regular user's normal endpoint: sees only their own 2 items
    user_resp = await client.get("/api/v1/items", headers=auth_headers)
    assert user_resp.status_code == 200
    assert len(user_resp.json()) == 2


# ==================== Role Shows in User Info ====================

@pytest.mark.asyncio
async def test_user_me_shows_role(client, auth_headers):
    """GET /api/v1/users/me should include role field"""
    response = await client.get("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "user"  # default role


@pytest.mark.asyncio
async def test_admin_me_shows_admin_role(client, admin_headers):
    """Admin's /users/me should show role='admin'"""
    response = await client.get("/api/v1/users/me", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["role"] == "admin"
