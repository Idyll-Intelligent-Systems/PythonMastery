from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, List
import os

router = APIRouter()

try:
    import redis.asyncio as redis  # type: ignore
except Exception:
    redis = None  # type: ignore


async def _redis():
    if redis is None:
        class Dummy:
            async def hgetall(self, *_args, **_kwargs):
                return {}
            async def hincrby(self, *_args, **_kwargs):
                return 0
            async def hset(self, *_args, **_kwargs):
                return 0
        return Dummy()
    return redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


class AddItem(BaseModel):
    sku: str | None = None
    name: str | None = None
    qty: int = 1


def _normalize_items(raw: Dict) -> List[dict]:
    items: List[dict] = []
    for k, v in (raw or {}).items():
        sku = k.decode() if hasattr(k, "decode") else k
        try:
            qty = int(v.decode() if hasattr(v, "decode") else v)
        except Exception:
            qty = 0
        items.append({"sku": sku, "qty": qty})
    items.sort(key=lambda x: x.get("sku", ""))
    return items


@router.get("/{user_id}")
async def get_inventory(user_id: str):
    key = f"inv:{user_id}"
    rr = await _redis()
    raw = await rr.hgetall(key)
    if not raw:
        await rr.hset(key, mapping={"starter_pack": 1})
        raw = await rr.hgetall(key)
    items = _normalize_items(raw)
    return {"user_id": user_id, "items": items}


@router.post("/{user_id}")
async def add_item(user_id: str, item: AddItem):
    key = f"inv:{user_id}"
    sku = item.sku or item.name or "mystery"
    qty = max(1, int(item.qty))
    rr = await _redis()
    raw = await rr.hgetall(key)
    if not raw:
        await rr.hset(key, mapping={"starter_pack": 1})
    await rr.hincrby(key, sku, qty)
    raw2 = await rr.hgetall(key)
    items = _normalize_items(raw2)
    return {"ok": True, "user_id": user_id, "items": items}
