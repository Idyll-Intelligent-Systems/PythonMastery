import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_game_email_proxy_missing_params():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get("/email/mail")
        assert r.status_code == 422  # validation error due to missing user
