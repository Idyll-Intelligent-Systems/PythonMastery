import pytest
from httpx import AsyncClient, ASGITransport
from VEZEPyGame.app.main import app


@pytest.mark.asyncio
async def test_game_email_proxy_missing_params():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/email/mail")
        assert r.status_code == 422  # validation error due to missing user
