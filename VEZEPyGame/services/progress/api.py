from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import json, os

router = APIRouter()

class QuestState(BaseModel):
    id: int
    have: Optional[float] = None
    need: Optional[float] = None
    done: Optional[bool] = None
    rewarded: Optional[bool] = None

class ProgressPayload(BaseModel):
    user_id: str
    xp: float
    level: int
    quests: List[QuestState]

# Storage: Redis if available, else in-memory
_mem: Dict[str, Dict[str, Any]] = {}
_redis = None

def _get_redis():
    global _redis
    if _redis is not None:
        return _redis
    try:
        import redis  # type: ignore
        url = os.getenv("REDIS_URL") or "redis://localhost:6379/0"
        _redis = redis.Redis.from_url(url, decode_responses=True)
    except Exception:
        _redis = None
    return _redis

def _key(user_id: str) -> str:
    return f"game:progress:{user_id}"

@router.get("/{user_id}")
def get_progress(user_id: str):
    r = _get_redis()
    if r is not None:
        try:
            data = r.get(_key(user_id))
            if not data:
                return {"user_id": user_id, "xp": 0, "level": 1, "quests": []}
            return json.loads(data)
        except Exception:
            pass
    # memory fallback
    return _mem.get(user_id, {"user_id": user_id, "xp": 0, "level": 1, "quests": []})

@router.post("/{user_id}")
def save_progress(user_id: str, payload: ProgressPayload):
    if payload.user_id != user_id:
        raise HTTPException(status_code=400, detail="user_id mismatch")
    record = payload.dict()
    r = _get_redis()
    if r is not None:
        try:
            r.set(_key(user_id), json.dumps(record))
            return {"status": "ok", "persisted": "redis"}
        except Exception:
            pass
    _mem[user_id] = record
    return {"status": "ok", "persisted": "memory"}
