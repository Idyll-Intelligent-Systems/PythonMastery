import os
import pytest
import httpx

# Ensure demo auth and ASGI usage for email client
os.environ.setdefault("VEZE_JWT_DEMO", "1")
os.environ.setdefault("EMAIL_ASGI", "1")

from VEZEPyUniQVerse.app.main import app


@pytest.mark.asyncio
async def test_provision_creates_mailbox():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/provision/testuser")
        assert r.status_code == 200
        data = r.json()
        assert data["user"] == "testuser@vezeuniqverse.com"
        assert data["provisioned"] is True
        assert isinstance(data.get("messages"), list)
