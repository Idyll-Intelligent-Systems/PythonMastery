import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_messages_requires_token():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get("/api/messages", params={"user": "test@vezeuniqverse.com"})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_messages_ok():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get(
            "/api/messages",
            params={"user": "test@vezeuniqverse.com", "access_token": "demo"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["user"] == "test@vezeuniqverse.com"
        assert isinstance(data["messages"], list)
