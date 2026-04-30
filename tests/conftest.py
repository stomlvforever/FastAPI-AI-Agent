"""
Pytest fixtures for async API testing.

Key concepts:
- fixture: a reusable "setup" function that pytest auto-injects into tests
- AsyncClient: like a browser, but in code - sends HTTP requests to our app
- We override get_db so tests use a SEPARATE test database (not your real data!)
- Each test function gets a CLEAN database (tables created before, dropped after)
"""
import os
os.environ["ENVIRONMENT"] = "test"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.db.base import Base
from app.db.models import User, Item, Tag, Comment  # noqa: F401 - 确保所有模型被注册到 metadata

# ---------- Test Database Setup ----------
# Use a separate test database to avoid touching your real data
TEST_DB_URL = settings.db_url.replace("/fastapi_chuxue", "/fastapi_chuxue_test")

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(bind=test_engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture()
async def db_session():
    """
    Create all tables before each test, drop them after.
    This ensures every test starts with a CLEAN database.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession):
    """
    An HTTP client that talks to our FastAPI app,
    but with the database swapped to test DB.
    """
    from app.db.session import get_db
    from app.main import app

    # Override: when the app asks for a DB session, give it our test session
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Clean up: remove the override
    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def test_user(db_session: AsyncSession):
    """
    Create a test user in the database, return the User object.
    Like registering 'testuser@example.com' before each test.
    """
    user = User(
        email="testuser@example.com",
        hashed_password=get_password_hash("testpass123"),
        full_name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture()
def auth_headers(test_user: User) -> dict[str, str]:
    """
    Generate a valid JWT token for the test user.
    Returns headers like: {"Authorization": "Bearer eyJ..."}
    So we don't have to login before every test.
    """
    token = create_access_token(subject=test_user.email)
    return {"Authorization": f"Bearer {token}"}
