from fastapi import APIRouter, HTTPException, Query, Depends, Request
from typing import List, Dict
from pydantic import BaseModel
from db.repository import (
    get_mailbox_id_for_user,
    list_messages_for_mailbox,
    get_message_for_mailbox,
    mark_read,
    toggle_star,
    set_labels,
)
from db.database import get_session
from fastapi.responses import StreamingResponse, HTMLResponse
import asyncio
from app.security import require_scopes
from streaming.redis import get_redis

router = APIRouter()
async def _publish(evt: dict, user: str | None = None):
    try:
        r = get_redis()
        if not r:
            return
        import json
        data = json.dumps(evt)
        await r.publish("email:events", data)
        if user:
            await r.publish(f"email:events:{user}", data)
    except Exception:
        pass


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
class LabelsIn(BaseModel):
    labels: List[str]


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
    await _publish({"type": "mail.read", "id": message_id})
    return {"ok": True}


@router.post("/messages/{message_id}/star")
async def star_message(
    message_id: int,
    _=Depends(auth_user),
    session=Depends(get_session),
):
    res = await toggle_star(session, message_id)
    await _publish({"type": "mail.star", "id": message_id, "starred": bool(res.get("starred", False))})
    return res


@router.post("/messages/{message_id}/labels")
async def update_labels(
    message_id: int,
    payload: LabelsIn,
    _=Depends(auth_user),
    session=Depends(get_session),
):
    res = await set_labels(session, message_id, payload.labels)
    await _publish({"type": "mail.labels", "id": message_id})
    return res


@router.get("/messages/{message_id}/row", response_class=HTMLResponse)
async def message_row(
    message_id: int,
    request: Request,
    _=Depends(auth_user),
    session=Depends(get_session),
):
    # Render a single message row partial for HTMX swaps
    # Load the message from the user's mailbox slice
    # For simplicity fetch the mailbox by query user if provided
    user = request.query_params.get("user") or "demo@vezeuniqverse.com"
    mailbox_id = await get_mailbox_id_for_user(user, session)
    # Fetch directly by id within this user's mailbox to avoid pagination misses
    m = await get_message_for_mailbox(session, mailbox_id, message_id)
    if not m:
        raise HTTPException(status_code=404, detail="Message not found")
    # Jinja environment from main app
    from app.main import templates  # lazy import to avoid cycles
    # Ensure 'from' key present for partial template
    if "from" not in m and "from_" in m:
        m["from"] = m["from_"]
    return templates.TemplateResponse("_message_row.html", {"request": request, "m": m})


@router.get("/events")
async def sse_events(user: str | None = None, _=Depends(auth_user)):
    async def event_stream():
        # Prefer Redis pubsub if available; fallback to heartbeat
        r = get_redis()
        if r:
            channel = "email:events:%s" % user if user else "email:events"
            pubsub = r.pubsub()
            await pubsub.subscribe(channel)
            try:
                async for message in pubsub.listen():
                    if message and message.get("type") == "message":
                        data = message.get("data")
                        yield f"data: {data}\n\n"
            finally:
                await pubsub.unsubscribe(channel)
        else:
            while True:
                yield f"data: {{\"type\": \"heartbeat\", \"ts\": \"{asyncio.get_event_loop().time()}\"}}\n\n"
                await asyncio.sleep(15)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}
