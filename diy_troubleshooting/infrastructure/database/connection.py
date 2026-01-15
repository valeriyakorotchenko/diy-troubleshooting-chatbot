"""
Database Connection Manager.

This module handles the low-level details of connecting to PostgreSQL.
It exposes an async engine and session factory for use by repositories.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from ...config import settings

# Transform the DATABASE_URL to use the asyncpg driver.
_async_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

async_engine = create_async_engine(_async_url, echo=False)

async_session_factory = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    """
    Idempotent initialization.
    Creates tables if they do not exist.
    Useful for local dev or simple deployments.
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
