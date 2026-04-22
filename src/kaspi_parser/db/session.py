"""Async SQLAlchemy engine and session factory.

Exposed objects:
- `create_engine(settings)` → `AsyncEngine`
- `session_factory(engine)` → `async_sessionmaker[AsyncSession]`

Callers use `async with session_factory() as session:` to get a unit-of-work.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from kaspi_parser.config import DatabaseSettings


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    """Build a tuned async engine."""
    return create_async_engine(
        settings.async_dsn,
        echo=settings.echo,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Return a session factory bound to `engine`."""
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
