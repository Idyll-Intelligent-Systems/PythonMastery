from fastapi import APIRouter
from pydantic import BaseModel
import os

try:
    import redis.asyncio as redis  # type: ignore
except Exception:
    redis = None  # type: ignore


router = APIRouter()


async def _redis():
    if redis is None:
        class Dummy:
            async def zadd(self, *_args, **_kwargs):
                return 0

            async def zrevrange(self, *_args, **_kwargs):
                return []

        return Dummy()
    return redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


class SubmitReq(BaseModel):
    user_id: str
    score: float
    season: str
    mode: str


@router.post("/submit")
async def submit(r: SubmitReq):
    key = f"lb:{r.season}:{r.mode}"
    rr = await _redis()
    await rr.zadd(key, {r.user_id: r.score})
    return {"ok": True}


@router.get("/{season}/{mode}")
async def get_board(season: str, mode: str, limit: int = 100, offset: int = 0):
    rr = await _redis()
    key = f"lb:{season}:{mode}"
    items = await rr.zrevrange(key, offset, offset + limit - 1, withscores=True)
    return [{"user_id": u.decode() if hasattr(u, "decode") else u, "score": s} for u, s in items]
