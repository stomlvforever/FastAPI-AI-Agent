"""
Tests for Item CRUD API endpoints.

Each test function name starts with test_ so pytest can find it.
The fixtures (client, auth_headers, test_user) are auto-injected by pytest
from conftest.py - you don't need to call them manually!

Run all tests:
    python -m pytest tests/test_items.py -v

Run a single test:
    python -m pytest tests/test_items.py::test_create_item -v
"""
import pytest


# ==================== CREATE ====================

@pytest.mark.asyncio
async def test_create_item(client, auth_headers):
    """POST /api/v1/items - create with all fields"""
    response = await client.post(
        "/api/v1/items",
        json={"title": "Buy milk", "priority": 1, "status": "pending"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Buy milk"
    assert data["priority"] == 1
    assert data["status"] == "pending"
    assert "id" in data  # DB should assign an ID


@pytest.mark.asyncio
async def test_create_item_defaults(client, auth_headers):
    """POST /api/v1/items - priority defaults to 3, status defaults to 'pending'"""
    response = await client.post(
        "/api/v1/items",
        json={"title": "Lazy task"},  # no priority, no status
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["priority"] == 3       # default
    assert data["status"] == "pending"  # default


@pytest.mark.asyncio
async def test_create_item_no_auth(client):
    """POST /api/v1/items without token -> 401"""
    response = await client.post(
        "/api/v1/items",
        json={"title": "Should fail"},
    )
    assert response.status_code == 401


# ==================== READ (LIST) ====================

@pytest.mark.asyncio
async def test_list_items_empty(client, auth_headers):
    """GET /api/v1/items - empty when no items created"""
    response = await client.get("/api/v1/items", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_items(client, auth_headers):
    """GET /api/v1/items - returns created items"""
    # Create 2 items first
    await client.post("/api/v1/items", json={"title": "A"}, headers=auth_headers)
    await client.post("/api/v1/items", json={"title": "B"}, headers=auth_headers)

    response = await client.get("/api/v1/items", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_list_items_filter_by_status(client, auth_headers):
    """GET /api/v1/items?status=done - only returns matching items"""
    await client.post("/api/v1/items", json={"title": "Todo", "status": "pending"}, headers=auth_headers)
    await client.post("/api/v1/items", json={"title": "Done", "status": "done"}, headers=auth_headers)

    # Filter by status=done
    response = await client.get("/api/v1/items?status=done", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["title"] == "Done"


@pytest.mark.asyncio
async def test_list_items_filter_by_priority(client, auth_headers):
    """GET /api/v1/items?priority=1 - only returns high priority items"""
    await client.post("/api/v1/items", json={"title": "Urgent", "priority": 1}, headers=auth_headers)
    await client.post("/api/v1/items", json={"title": "Chill", "priority": 3}, headers=auth_headers)

    response = await client.get("/api/v1/items?priority=1", headers=auth_headers)
    items = response.json()
    assert len(items) == 1
    assert items[0]["title"] == "Urgent"


# ==================== READ (SINGLE) ====================

@pytest.mark.asyncio
async def test_get_item(client, auth_headers):
    """GET /api/v1/items/{id} - returns the specific item"""
    create_resp = await client.post(
        "/api/v1/items", json={"title": "Find me"}, headers=auth_headers
    )
    item_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Find me"


@pytest.mark.asyncio
async def test_get_item_not_found(client, auth_headers):
    """GET /api/v1/items/99999 - returns 404"""
    response = await client.get("/api/v1/items/99999", headers=auth_headers)
    assert response.status_code == 404


# ==================== UPDATE ====================

@pytest.mark.asyncio
async def test_update_item_status(client, auth_headers):
    """PUT /api/v1/items/{id} - update status from pending to done"""
    create_resp = await client.post(
        "/api/v1/items", json={"title": "Finish me"}, headers=auth_headers
    )
    item_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "pending"

    # Update only status
    update_resp = await client.put(
        f"/api/v1/items/{item_id}",
        json={"status": "done"},
        headers=auth_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "done"
    assert update_resp.json()["title"] == "Finish me"  # title unchanged


@pytest.mark.asyncio
async def test_update_item_priority(client, auth_headers):
    """PUT /api/v1/items/{id} - update priority"""
    create_resp = await client.post(
        "/api/v1/items", json={"title": "Reprioritize"}, headers=auth_headers
    )
    item_id = create_resp.json()["id"]

    update_resp = await client.put(
        f"/api/v1/items/{item_id}",
        json={"priority": 1},
        headers=auth_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["priority"] == 1


# ==================== DELETE ====================

@pytest.mark.asyncio
async def test_delete_item(client, auth_headers):
    """DELETE /api/v1/items/{id} - removes the item"""
    create_resp = await client.post(
        "/api/v1/items", json={"title": "Delete me"}, headers=auth_headers
    )
    item_id = create_resp.json()["id"]

    # Delete
    del_resp = await client.delete(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert del_resp.status_code == 200

    # Verify it's gone
    get_resp = await client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_item_not_found(client, auth_headers):
    """DELETE /api/v1/items/99999 - returns 404"""
    response = await client.delete("/api/v1/items/99999", headers=auth_headers)
    assert response.status_code == 404


# ==================== SORTING ====================

@pytest.mark.asyncio
async def test_sort_by_priority_asc(client, auth_headers):
    """Default sort: priority ascending (1 first, 3 last)"""
    await client.post("/api/v1/items", json={"title": "Low", "priority": 3}, headers=auth_headers)
    await client.post("/api/v1/items", json={"title": "High", "priority": 1}, headers=auth_headers)
    await client.post("/api/v1/items", json={"title": "Mid", "priority": 2}, headers=auth_headers)

    resp = await client.get("/api/v1/items?sort_by=priority&order=asc", headers=auth_headers)
    items = resp.json()
    assert [i["title"] for i in items] == ["High", "Mid", "Low"]


@pytest.mark.asyncio
async def test_sort_by_priority_desc(client, auth_headers):
    """Sort by priority descending (3 first, 1 last)"""
    await client.post("/api/v1/items", json={"title": "Low", "priority": 3}, headers=auth_headers)
    await client.post("/api/v1/items", json={"title": "High", "priority": 1}, headers=auth_headers)
    await client.post("/api/v1/items", json={"title": "Mid", "priority": 2}, headers=auth_headers)

    resp = await client.get("/api/v1/items?sort_by=priority&order=desc", headers=auth_headers)
    items = resp.json()
    assert [i["title"] for i in items] == ["Low", "Mid", "High"]


@pytest.mark.asyncio
async def test_sort_by_title(client, auth_headers):
    """Sort by title alphabetically"""
    await client.post("/api/v1/items", json={"title": "Cherry"}, headers=auth_headers)
    await client.post("/api/v1/items", json={"title": "Apple"}, headers=auth_headers)
    await client.post("/api/v1/items", json={"title": "Banana"}, headers=auth_headers)

    resp = await client.get("/api/v1/items?sort_by=title&order=asc", headers=auth_headers)
    items = resp.json()
    assert [i["title"] for i in items] == ["Apple", "Banana", "Cherry"]


@pytest.mark.asyncio
async def test_sort_by_created_at_desc(client, auth_headers):
    """Sort by created_at descending (newest first)"""
    await client.post("/api/v1/items", json={"title": "First"}, headers=auth_headers)
    await client.post("/api/v1/items", json={"title": "Second"}, headers=auth_headers)
    await client.post("/api/v1/items", json={"title": "Third"}, headers=auth_headers)

    resp = await client.get("/api/v1/items?sort_by=created_at&order=desc", headers=auth_headers)
    items = resp.json()
    assert items[0]["title"] == "Third"
    assert items[-1]["title"] == "First"
