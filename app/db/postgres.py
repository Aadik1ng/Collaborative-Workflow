"""PostgreSQL database connection and session management."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Create async engine
engine = create_async_engine(
    settings.POSTGRES_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Create async session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    pass


async def init_postgres() -> None:
    """Initialize PostgreSQL connection and create tables."""
    async with engine.begin() as conn:
        # Import all models to register them with Base
        from app.models.sql import project, role, user, workspace  # noqa: F401

        await conn.run_sync(Base.metadata.create_all)


async def close_postgres() -> None:
    """Close PostgreSQL connection pool."""
    await engine.dispose()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
