import pytest
from httpx import AsyncClient, ASGITransport
from VEZEPyEmail.app.main import app


@pytest.mark.asyncio
async def test_email_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/health")
        assert r.status_code == 200
        assert r.json().get("status") == "ok"
