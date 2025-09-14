import pytest
from httpx import AsyncClient, ASGITransport
from VEZEPyUniQVerse.app.main import app


@pytest.mark.asyncio
async def test_uniqverse_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/health")
        assert r.status_code == 200
        assert r.json().get("status") == "ok"
