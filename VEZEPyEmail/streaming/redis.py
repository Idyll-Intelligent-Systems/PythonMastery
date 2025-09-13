from __future__ import annotations
import os
from typing import Optional
from redis import asyncio as aioredis


def get_redis_url() -> Optional[str]:
    return os.getenv("REDIS_URL") or os.getenv("VEZE_REDIS_URL")


def get_redis() -> Optional[aioredis.Redis]:
    url = get_redis_url()
    if not url:
        return None
    return aioredis.from_url(url, decode_responses=True)
