from __future__ import annotations
import asyncio
import os
from dataclasses import dataclass
from typing import Dict, List
import httpx
from .registry import resolve


@dataclass
class ServiceStatus:
    name: str
    url: str
    healthy: bool
    detail: str | None = None
    requires_auth: bool | None = None


async def check_health(name: str, default_url: str, timeout: float = 2.0) -> ServiceStatus:
    base = resolve(name, default_url)
    url = base.rstrip("/") + "/health"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
            ok = r.status_code == 200 and (r.json().get("status") == "ok")
            requires_auth: bool | None = None
            # Simple auth gating probe for known protected APIs
            if name == "email":
                try:
                    probe = await client.get(base.rstrip("/") + "/api/messages", params={"user": "probe@vezeuniqverse.com"})
                    if probe.status_code in (401, 403):
                        requires_auth = True
                    elif probe.status_code == 200:
                        requires_auth = False
                except Exception:
                    pass
            elif name == "social":
                try:
                    probe = await client.get(base.rstrip("/") + "/feed")
                    if probe.status_code in (401, 403):
                        requires_auth = True
                    elif probe.status_code == 200:
                        requires_auth = False
                except Exception:
                    pass
            elif name == "maps":
                try:
                    probe = await client.get(base.rstrip("/") + "/routes")
                    if probe.status_code in (401, 403):
                        requires_auth = True
                    elif probe.status_code == 200:
                        requires_auth = False
                except Exception:
                    pass
            return ServiceStatus(name=name, url=base, healthy=ok, detail=None if ok else str(r.status_code), requires_auth=requires_auth)
    except Exception as e:
        return ServiceStatus(name=name, url=base, healthy=False, detail=str(e))


async def snapshot_status() -> List[Dict]:
    game = os.getenv("GAME_BASE_URL", "http://127.0.0.1:8002")
    targets = {
        "uniqverse": os.getenv("UNIQVERSE_BASE_URL", "http://127.0.0.1:8000"),
        "game": game,
        "email": os.getenv("EMAIL_BASE_URL", "http://127.0.0.1:8004"),
        # Domain routers under game
        "maps": f"{game.rstrip('/')}/maps",
        "social": f"{game.rstrip('/')}/social",
        "time": f"{game.rstrip('/')}/time",
        "timevmaps": f"{game.rstrip('/')}/timevmaps",
        "commerce": f"{game.rstrip('/')}/commerce",
    }
    results = await asyncio.gather(*(check_health(n, u) for n, u in targets.items()))
    return [s.__dict__ for s in results]


def list_services() -> List[Dict]:
    """Return a registry of services with display names and suggested UI paths.

    Some domains are routed through the Game app for now (maps, social, time, commerce).
    """
    uniqverse = resolve("uniqverse", os.getenv("UNIQVERSE_BASE_URL", "http://127.0.0.1:8000"))
    game = resolve("game", os.getenv("GAME_BASE_URL", "http://127.0.0.1:8002"))
    email = resolve("email", os.getenv("EMAIL_BASE_URL", "http://127.0.0.1:8004"))
    return [
        {"name": "uniqverse", "display": "VEZEPyUniQVerse", "url": uniqverse, "ui_path": "/", "requires_auth": False, "icon": "🪐", "description": "Portal & Helm"},
        {"name": "game", "display": "VEZEPyGame", "url": game, "ui_path": "/ui", "requires_auth": False, "icon": "🎮", "description": "Matchmaking & leaderboards"},
        {"name": "email", "display": "VEZEPyEmail", "url": email, "ui_path": "/ui/inbox", "requires_auth": True, "icon": "✉️", "description": "Webmail & SMTP"},
        {"name": "maps", "display": "VEZEPyMaps", "url": game, "ui_path": "/maps/routes?origin=A&dest=B", "requires_auth": False, "icon": "🗺️", "description": "Routes & navigation"},
        {"name": "social", "display": "VEZEPySocial", "url": game, "ui_path": "/social/feed", "requires_auth": False, "icon": "👥", "description": "Community & feeds"},
        {"name": "time", "display": "VEZEPyTime", "url": game, "ui_path": "/time/now", "requires_auth": False, "icon": "⏱️", "description": "Time services"},
        {"name": "timevmaps", "display": "VEZEPyTimeVMaps", "url": game, "ui_path": "/timevmaps/routes", "requires_auth": False, "icon": "🕰️", "description": "Temporal maps"},
        {"name": "commerce", "display": "VEZEPyCommerce", "url": game, "ui_path": "/commerce/catalog", "requires_auth": False, "icon": "🛒", "description": "Catalog & orders"},
    ]
