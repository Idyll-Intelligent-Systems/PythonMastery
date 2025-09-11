from __future__ import annotations
from typing import List, Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Mailbox, Message


async def get_or_create_mailbox(session: AsyncSession, user: str) -> Mailbox:
    res = await session.execute(select(Mailbox).where(Mailbox.user_email == user))
    mbox = res.scalars().first()
    if mbox:
        return mbox
    mbox = Mailbox(user_email=user, name="INBOX")
    session.add(mbox)
    await session.flush()
    return mbox


async def get_mailbox_id_for_user(user: str, session: AsyncSession | None = None) -> int:
    assert session is not None, "session is required"
    mbox = await get_or_create_mailbox(session, user)
    return mbox.id


def _unread_from_flags(flags: str) -> bool:
    parts = [p.strip() for p in (flags or "").split(",") if p.strip()]
    return "Seen" not in parts


async def list_messages_for_mailbox(
    session: AsyncSession,
    mailbox_id: int,
    limit: int = 50,
    offset: int = 0,
    q: Optional[str] = None,
) -> List[Dict]:
    stmt = select(Message).where(Message.mailbox_id == mailbox_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Message.subject.ilike(like)) | (Message.from_addr.ilike(like)))
    stmt = stmt.order_by(Message.id.desc()).limit(limit).offset(offset)
    res = await session.execute(stmt)
    msgs = res.scalars().all()
    out: List[Dict] = []
    for m in msgs:
        out.append(
            {
                "id": m.id,
                "mailbox_id": m.mailbox_id,
                "subject": m.subject,
                "from": m.from_addr,
                "date": (m.date.isoformat() if hasattr(m.date, "isoformat") else str(m.date)),
                "flags": [p for p in (m.flags or "").split(",") if p],
                "size": m.size,
                "spam_score": m.spam_score,
                "snippet": m.snippet or "",
                "unread": _unread_from_flags(m.flags or ""),
            }
        )
    return out


async def mark_read(session: AsyncSession, message_id: int) -> None:
    res = await session.execute(select(Message).where(Message.id == message_id))
    msg = res.scalars().first()
    if not msg:
        return
    flags = [p for p in (msg.flags or "").split(",") if p]
    if "Seen" not in flags:
        flags.append("Seen")
        msg.flags = ",".join(flags)
        await session.flush()
