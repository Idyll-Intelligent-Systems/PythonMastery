from __future__ import annotations
import os
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from db.base import Base

DB_URL = os.getenv("EMAIL_DB_URL", "sqlite+aiosqlite:///./email.db")
engine = create_async_engine(DB_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

_initialized = False


async def _ensure_tables_once() -> None:
    global _initialized
    if _initialized:
        return
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        # best-effort; if migrations manage schema, ignore
        pass
    else:
        _initialized = True


async def get_session() -> AsyncIterator[AsyncSession]:
    await _ensure_tables_once()
    session = SessionLocal()
    try:
        yield session
    finally:
        await session.close()
