from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any

router = APIRouter()


class Event(BaseModel):
    event: str
    ts: float
    user_id: str | None = None
    payload: dict[str, Any] | None = None


@router.post("/bulk")
async def bulk(events: list[Event]):
    # Minimal dev stub: simply count
    return {"accepted": len(events)}
