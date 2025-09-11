from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict

router = APIRouter()


def _sample_messages(user: str) -> List[Dict]:
    # Simple demo messages addressed to the provided user
    return [
        {
            "id": 101,
            "to": user,
            "from": "noreply@vezeuniqverse.com",
            "subject": "Welcome to VEZEPyUniQVerse",
            "snippet": "You're all set. Explore the world and check your quests!",
            "date": "2025-09-11 10:05",
            "labels": ["Inbox"],
        },
        {
            "id": 102,
            "to": user,
            "from": "rewards@vezeuniqverse.com",
            "subject": "Daily Reward Available",
            "snippet": "Claim your shards and XP boost for today.",
            "date": "2025-09-11 09:00",
            "labels": ["Promotions"],
        },
    ]


@router.get("/messages")
async def list_messages(user: str = Query(..., description="User email, must be @vezeuniqverse.com")):
    if "@" not in user:
        raise HTTPException(status_code=400, detail="Invalid email")
    local, domain = user.split("@", 1)
    if domain.lower() != "vezeuniqverse.com":
        raise HTTPException(status_code=403, detail="Unsupported domain")
    return {"user": user, "messages": _sample_messages(user)}
