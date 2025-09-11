from __future__ import annotations
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

DB_URL = os.getenv("EMAIL_DB_URL", "sqlite+aiosqlite:///./email.db")
engine = create_async_engine(DB_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    session = SessionLocal()
    try:
        yield session
    finally:
        await session.close()
