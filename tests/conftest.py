"""Pytest fixtures and configuration."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.postgres import Base, get_db
from app.main import app
from app.models.sql.user import User

# Test database URL (use SQLite for testing)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
)

# Create test session factory
test_session_factory = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)




@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with test_session_factory() as session:
        yield session

    # Drop tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with overridden dependencies."""

    async def override_get_db():
        yield db_session

    # Mock Redis
    mock_redis = MagicMock()
    mock_redis.ping = AsyncMock(return_value=True)
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()
    mock_redis.delete = AsyncMock()
    # Add other Redis methods as needed

    # Mock MongoDB
    mock_mongodb = MagicMock()
    mock_collection = MagicMock()

    # Stateful mock for jobs
    stored_jobs = {}

    async def mock_insert_one(doc):
        job_id = doc.get("_id") or str(uuid4())
        stored_jobs[job_id] = doc
        return MagicMock(inserted_id=job_id)

    async def mock_find_one(query):
        job_id = query.get("_id")
        return stored_jobs.get(job_id)

    mock_collection.insert_one = AsyncMock(side_effect=mock_insert_one)
    mock_collection.find_one = AsyncMock(side_effect=mock_find_one)

    # Mock for cursor-like chaining: collection.find().sort().skip().limit()
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor

    # Async iterator for cursor
    async def mock_cursor_iter(self):
        for job in list(stored_jobs.values()):
            yield job

    mock_cursor.__aiter__ = mock_cursor_iter
    mock_cursor.to_list = AsyncMock(return_value=list(stored_jobs.values()))

    mock_collection.find.return_value = mock_cursor

    async def mock_count_documents(query):
        return len(stored_jobs)

    mock_collection.count_documents = AsyncMock(side_effect=mock_count_documents)
    mock_collection.update_one = AsyncMock()

    mock_mongodb.job_results = mock_collection
    mock_mongodb.__getitem__.return_value = mock_collection

    with (
        patch("app.db.redis.redis_client", MagicMock()),
        patch("app.db.redis.get_redis", return_value=MagicMock()),
        patch("app.db.redis.cache_get", AsyncMock(return_value=None)),
        patch("app.db.redis.cache_set", AsyncMock()),
        patch("app.db.redis.cache_delete", AsyncMock()),
        patch("app.api.v1.auth.cache_set", AsyncMock()),
        patch("app.api.v1.auth.cache_delete", AsyncMock()),
        patch("app.db.mongodb.mongodb_database", mock_mongodb),
        patch("app.db.mongodb.get_mongodb", return_value=mock_mongodb),
        patch("app.db.mongodb.get_job_results_collection", return_value=mock_collection),
    ):
        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    from app.core.security import hash_password

    user = User(
        id=uuid4(),
        email="test@example.com",
        username="testuser",
        hashed_password=hash_password("testpass123"),
        full_name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user: User) -> dict:
    """Create authentication headers for test user."""
    from app.core.security import create_access_token

    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sync_client() -> Generator[TestClient, None, None]:
    """Create synchronous test client."""
    with TestClient(app) as c:
        yield c
