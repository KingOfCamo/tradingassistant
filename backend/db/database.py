"""Database connection and session management."""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings

engine = create_async_engine(settings.get_async_database_url(), echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def create_all_tables():
    """Create all tables — used on Railway where we can't run alembic manually."""
    import backend.db.models  # noqa: F401 — import to register models with Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
