from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class Service(BaseModel):
    name: str
    display: str | None = None
    url: str | None = None
    icon: str | None = None
    description: str | None = None


def _load_json_file(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_services() -> list[Service]:
    """
    Load services from config/services.json.
    Optional env override: VEZE_SERVICES_JSON (inline JSON array) or VEZE_SERVICES_PATH.
    """
    env_json = os.getenv("VEZE_SERVICES_JSON")
    if env_json:
        try:
            data = json.loads(env_json)
            return [Service(**s) for s in data]
        except Exception:
            # fall back to file if env override malformed
            pass

    cfg_path = os.getenv("VEZE_SERVICES_PATH")
    path = Path(cfg_path) if cfg_path else Path("config/services.json")
    data = _load_json_file(path)
    return [Service(**s) for s in data]
