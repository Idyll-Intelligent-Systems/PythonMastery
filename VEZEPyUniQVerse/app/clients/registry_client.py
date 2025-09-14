from __future__ import annotations
import os
import httpx


async def fetch_registry_health(base_url: str | None = None) -> dict:
    base = base_url or os.getenv("VEZE_SERVICE_GAME") or os.getenv("GAME_BASE_URL") or "http://127.0.0.1:8002"
    url = base.rstrip("/") + "/registry/health"
    async with httpx.AsyncClient(timeout=3.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()


async def fetch_registry_services(base_url: str | None = None) -> dict:
    base = base_url or os.getenv("VEZE_SERVICE_GAME") or os.getenv("GAME_BASE_URL") or "http://127.0.0.1:8002"
    url = base.rstrip("/") + "/registry/services"
    async with httpx.AsyncClient(timeout=3.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()
