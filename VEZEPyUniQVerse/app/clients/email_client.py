from __future__ import annotations
import os
from typing import Optional
import httpx
from httpx import ASGITransport


def _email_base_url() -> str:
    # Prefer shared service registry env if set, then EMAIL_BASE_URL, then default
    return (
        os.getenv("VEZE_SERVICE_EMAIL")
        or os.getenv("EMAIL_BASE_URL")
        or "http://127.0.0.1:8004"
    )


async def provision_mailbox(user_email: str, access_token: Optional[str] = None) -> dict:
    """
    Provision an email mailbox by invoking the Email service messages API.
    The Email app lazily creates a mailbox for the user on first access.
    """
    base_url = _email_base_url()
    params = {"user": user_email}
    if access_token:
        params["access_token"] = access_token
    # Prefer in-process ASGI for tests if available
    use_asgi = os.getenv("EMAIL_ASGI") == "1" or "PYTEST_CURRENT_TEST" in os.environ
    if use_asgi:
        try:
            from VEZEPyEmail.app.main import app as email_app  # type: ignore

            transport = ASGITransport(app=email_app)
            async with httpx.AsyncClient(transport=transport, base_url=base_url, timeout=5.0) as client:
                r = await client.get("/api/messages", params=params)
                r.raise_for_status()
                return r.json()
        except Exception:
            # fallback to real HTTP client below
            pass

    async with httpx.AsyncClient(base_url=base_url, timeout=5.0) as client:
        r = await client.get("/api/messages", params=params)
        r.raise_for_status()
        return r.json()
