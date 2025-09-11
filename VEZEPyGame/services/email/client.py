from typing import Optional, Dict, Any
import os
import httpx


class EmailClient:
    def __init__(self, base_url: Optional[str] = None, timeout: float = 5.0):
        self.base_url = base_url or os.getenv("EMAIL_BASE_URL", "http://127.0.0.1:8004")
        self._timeout = timeout

    async def get_messages(self, user: str) -> Dict[str, Any]:
        url = f"{self.base_url}/api/messages"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.get(url, params={"user": user})
            r.raise_for_status()
            return r.json()
