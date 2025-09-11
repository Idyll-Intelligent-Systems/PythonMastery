from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Dict
from pydantic import BaseModel
from db.repository import (
    get_mailbox_id_for_user,
    list_messages_for_mailbox,
    mark_read,
    toggle_star,
    set_labels,
)
from db.database import get_session
from fastapi.responses import StreamingResponse
import asyncio
from app.security import require_scopes

router = APIRouter()


class MessageOut(BaseModel):
    id: int
    subject: str
    from_: str | None = None
    date: str
    snippet: str | None = None
    labels: List[str] | None = None
    flags: List[str] | None = None
    size: int | None = None
    spam_score: float | None = None
    unread: bool | None = None


auth_user = require_scopes(["email.read"])  # validates JWT and scope


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
async def list_messages(
    user: str = Query(..., description="User email, must be @vezeuniqverse.com"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, description="Search subject/from contains"),
    _=Depends(auth_user),
    session=Depends(get_session),
):
    if "@" not in user:
        raise HTTPException(status_code=400, detail="Invalid email")
    local, domain = user.split("@", 1)
    if domain.lower() != "vezeuniqverse.com":
        raise HTTPException(status_code=403, detail="Unsupported domain")
    mailbox_id = await get_mailbox_id_for_user(user, session)
    msgs = await list_messages_for_mailbox(session, mailbox_id, limit=limit, offset=offset, q=q)
    # Transform field name 'from' -> 'from_'
    output = [
        MessageOut(
            id=m["id"],
            subject=m.get("subject"),
            from_=m.get("from"),
            date=m.get("date", ""),
            snippet=m.get("snippet"),
            labels=m.get("labels", []),
            flags=m.get("flags", []),
            size=m.get("size"),
            spam_score=m.get("spam_score"),
            unread=m.get("unread", True),
        ).model_dump()
        for m in msgs
    ]
    return {"user": user, "messages": output}


@router.post("/messages/{message_id}/read")
async def set_read(
    message_id: int,
    _=Depends(auth_user),
    session=Depends(get_session),
):
    await mark_read(session, message_id)
    return {"ok": True}


@router.post("/messages/{message_id}/star")
async def star_message(
    message_id: int,
    _=Depends(auth_user),
    session=Depends(get_session),
):
    return await toggle_star(session, message_id)


@router.post("/messages/{message_id}/labels")
async def update_labels(
    message_id: int,
    labels: List[str],
    _=Depends(auth_user),
    session=Depends(get_session),
):
    return await set_labels(session, message_id, labels)


@router.get("/events")
async def sse_events(_=Depends(auth_user)):
    async def event_stream():
        # Simple heartbeat for now; replace with Redis pubsub or DB triggers
        while True:
            yield f"data: {{\"type\": \"heartbeat\", \"ts\": \"{asyncio.get_event_loop().time()}\"}}\n\n"
            await asyncio.sleep(15)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}
