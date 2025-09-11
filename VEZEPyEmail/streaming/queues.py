import os
import json

try:
    import redis.asyncio as redis  # type: ignore
except Exception:  # allow import without redis installed for now
    redis = None  # type: ignore


async def _redis():
    if redis is None:
        class Dummy:
            async def xadd(self, *_args, **_kwargs):
                return None

        return Dummy()
    return redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


async def enqueue_inbound(payload: dict):
    r = await _redis()
    await r.xadd("inbound.events", {"p": json.dumps(payload)})


async def enqueue_outbound(payload: dict):
    r = await _redis()
    await r.xadd("outbound.queue", {"p": json.dumps(payload)})


async def enqueue_bounce(payload: dict):
    r = await _redis()
    await r.xadd("bounce.queue", {"p": json.dumps(payload)})
