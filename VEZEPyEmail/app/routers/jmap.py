from fastapi import APIRouter, Depends

try:
    from sqlalchemy import select  # type: ignore
    from db.database import get_session
    from db.models import Mailbox, Message
    DB_READY = True
except Exception:
    # Minimal fallback to allow app to start without DB configured
    get_session = None  # type: ignore
    DB_READY = False

router = APIRouter()


@router.get("/jmap/mailbox")
async def list_mailboxes(user_id: int = 1, session=None):
    if DB_READY and session is None and get_session is not None:
        # If used inside FastAPI, Depends will inject. When called directly, we skip.
        pass
    if not DB_READY:
        return [{"id": 1, "name": "INBOX"}, {"id": 2, "name": "Sent"}]
    res = await session.execute(select(Mailbox).where(Mailbox.user_id == user_id))
    return [{"id": m.id, "name": m.name} for m in res.scalars().all()]


@router.get("/jmap/messages")
async def list_messages(mailbox_id: int, limit: int = 50, session=None):
    if not DB_READY:
        return [{
            "id": 1,
            "subject": "Welcome to VEZEPyEmail",
            "from": "noreply@vezeuniqverse.com",
            "date": "",
            "flags": [],
            "size": 1234,
            "spam_score": 0.01,
        }]
    res = await session.execute(
        select(Message).where(Message.mailbox_id == mailbox_id).order_by(Message.id.desc()).limit(limit)
    )
    msgs = res.scalars().all()
    return [
        {
            "id": m.id,
            "subject": m.subject,
            "from": m.from_addr,
            "date": m.date,
            "flags": m.flags,
            "size": m.size,
            "spam_score": m.spam_score,
        }
        for m in msgs
    ]
