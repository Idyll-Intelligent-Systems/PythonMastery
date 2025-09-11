import pytest
from httpx import AsyncClient
from VEZEPyEmail.app.main import app as email_app
from VEZEPyGame.app.main import app as game_app


@pytest.mark.asyncio
async def test_chain():
    # Enable demo token bypass in env if needed via monkeypatch in real runner
    async with AsyncClient(app=email_app, base_url="http://127.0.0.1:8004") as email_client:
        await email_client.get("/ui/inbox")  # seed mailbox

    async with AsyncClient(app=game_app, base_url="http://test") as game_client:
        r = await game_client.get("/email/mail", params={"user": "demo@vezeuniqverse.com", "access_token": "demo"})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data.get("messages"), list)
