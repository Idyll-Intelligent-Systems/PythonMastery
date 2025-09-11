import pytest
from httpx import AsyncClient
from VEZEPyEmail.app.main import app as email_app
from VEZEPyGame.app.main import app as game_app
import os


@pytest.mark.asyncio
async def test_game_email_chain_demo_token(monkeypatch):
    # Enable demo token bypass
    monkeypatch.setenv("VEZE_JWT_DEMO", "1")
    # Ensure game points to email app base URL (for httpx ASGI we use mounted client)
    # Here we directly call game proxy which calls real email service via base_url default (127.0.0.1)
    # For unit-like integration, we simulate email first
    async with AsyncClient(app=email_app, base_url="http://127.0.0.1:8004") as email_client:
        # Seed an inbox by calling inbox page (which auto-creates mailbox)
        await email_client.get("/ui/inbox")

    async with AsyncClient(app=game_app, base_url="http://test") as game_client:
        r = await game_client.get(
            "/email/mail",
            params={"user": "demo@vezeuniqverse.com", "access_token": "demo"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["user"].endswith("@vezeuniqverse.com")
        assert isinstance(data.get("messages"), list)
