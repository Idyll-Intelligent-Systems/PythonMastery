from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Index, Float, UniqueConstraint
from sqlalchemy.sql import func
from db.base import Base


class Mailbox(Base):
    __tablename__ = "mailboxes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_email: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(64), default="INBOX")
    __table_args__ = (UniqueConstraint("user_email", "name", name="uq_mailbox_user_name"),)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mailbox_id: Mapped[int] = mapped_column(ForeignKey("mailboxes.id"), index=True)
    subject: Mapped[str] = mapped_column(String(512))
    from_addr: Mapped[str] = mapped_column(String(255))
    snippet: Mapped[str] = mapped_column(Text, default="")
    labels: Mapped[str] = mapped_column(String(255), default="")  # comma-separated labels
    date: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    flags: Mapped[str] = mapped_column(String(255), default="")  # comma-separated flags (e.g., "Seen,Starred")
    size: Mapped[int] = mapped_column(Integer, default=0)
    spam_score: Mapped[float] = mapped_column(Float, default=0.0)

Index("ix_messages_subject", Message.subject)
Index("ix_messages_from", Message.from_addr)
