from typing import Optional, Dict, Any
import os
import httpx
from httpx import ASGITransport
from ..registry import resolve


class EmailClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 5.0,
        http_client: Optional[httpx.AsyncClient] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        """
        Email service client.

        - base_url: Base URL for the email service (ignored for request path when using ASGI transport, but used as base_url for httpx).
        - timeout: Request timeout in seconds.
        - http_client: Optional prebuilt httpx.AsyncClient to use (primarily for tests/DI).
        - transport: Optional httpx transport; if provided, an AsyncClient will be constructed with it.
        """
        # Resolve base URL in priority: injected -> VEZE_SERVICE_EMAIL -> EMAIL_BASE_URL -> default
        self.base_url = base_url or resolve("email", os.getenv("EMAIL_BASE_URL", "http://127.0.0.1:8004"))
        self._timeout = timeout
        self._http_client = http_client
        self._transport = transport

    async def _make_client(self) -> httpx.AsyncClient:
        """Create an AsyncClient suitable for current environment.

        Prefers an injected client or transport; otherwise, if running under pytest
        (PYTEST_CURRENT_TEST) or EMAIL_ASGI=1 is set, it will attempt to use an
        in-process ASGI transport bound to VEZEPyEmail.app.main:app. Falls back
        to a real HTTP client otherwise.
        """
        if self._http_client is not None:
            return self._http_client
        if self._transport is not None:
            return httpx.AsyncClient(transport=self._transport, base_url=self.base_url, timeout=self._timeout)

        use_asgi = os.getenv("EMAIL_ASGI") == "1" or "PYTEST_CURRENT_TEST" in os.environ
        if use_asgi:
            try:
                # Import the in-process Email ASGI app used by tests
                from VEZEPyEmail.app.main import app as email_app

                transport = ASGITransport(app=email_app)
                return httpx.AsyncClient(transport=transport, base_url=self.base_url, timeout=self._timeout)
            except Exception:
                # If anything goes wrong, default to real HTTP client
                pass

        return httpx.AsyncClient(timeout=self._timeout, base_url=self.base_url)

    async def get_messages(self, user: str, access_token: str | None = None) -> Dict[str, Any]:
        params = {"user": user}
        if access_token:
            params["access_token"] = access_token
        async with await self._make_client() as client:
            # Use relative path; base_url is set on the client
            r = await client.get("/api/messages", params=params)
            r.raise_for_status()
            return r.json()
