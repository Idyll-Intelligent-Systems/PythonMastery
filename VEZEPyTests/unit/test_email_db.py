import os
from pathlib import Path
import subprocess
import sys
import pytest


@pytest.fixture()
def temp_db_url(tmp_path):
    # Use a unique sqlite file per test
    dbfile = tmp_path / "email_test.db"
    return f"sqlite+aiosqlite:///{dbfile}"


@pytest.fixture()
def set_env(temp_db_url, monkeypatch):
    monkeypatch.setenv("EMAIL_DB_URL", temp_db_url)
    # Alembic ini uses sqlite+aiosqlite relative path; override via env var in command
    yield


async def _alembic_upgrade_head(cwd):
    cmd = [sys.executable, "-m", "alembic", "upgrade", "head"]
    subprocess.check_call(cmd, cwd=cwd)


async def _alembic_downgrade_base(cwd):
    cmd = [sys.executable, "-m", "alembic", "downgrade", "base"]
    subprocess.check_call(cmd, cwd=cwd)


@pytest.mark.asyncio
async def test_mark_read_and_search(set_env):
    email_dir = os.path.join(os.getcwd(), "VEZEPyEmail")
    # Bring DB up
    await _alembic_upgrade_head(email_dir)
    # Fallback create tables if needed
    try:
        import sqlalchemy as sa
        from VEZEPyEmail.db.base import Base  # type: ignore
        dbfile = os.environ["EMAIL_DB_URL"].split("///",1)[1]
        engine = sa.create_engine(f"sqlite:///{dbfile}")
        Base.metadata.create_all(engine)
    except Exception:
        pass

    # Now use repository to create and query
    from VEZEPyEmail.db.database import SessionLocal  # type: ignore
    from VEZEPyEmail.db.repository import (  # type: ignore
        get_or_create_mailbox, create_message, list_messages_for_mailbox, mark_read
    )

    async with SessionLocal() as session:
        mbox = await get_or_create_mailbox(session, "tester@vezeuniqverse.com")
        # create 3 messages
        ids = []
        ids.append(await create_message(session, mbox.id, subject="Hello World", from_addr="a@vezeuniqverse.com", snippet="hi"))
        ids.append(await create_message(session, mbox.id, subject="Status Update", from_addr="pm@vezeuniqverse.com", snippet="update"))
        ids.append(await create_message(session, mbox.id, subject="Promotion", from_addr="ads@vezeuniqverse.com", snippet="sale", labels=["Promotions"]))
        await session.commit()

        # search by subject
        res = await list_messages_for_mailbox(session, mbox.id, q="Status")
        assert len(res) == 1 and res[0]["subject"] == "Status Update"

        # unread default
        res_all = await list_messages_for_mailbox(session, mbox.id)
        assert any(m["unread"] for m in res_all)

        # mark first read
        await mark_read(session, ids[0])
        await session.commit()
        res_after = await list_messages_for_mailbox(session, mbox.id)
        first = next(m for m in res_after if m["id"] == ids[0])
        assert first["unread"] is False

    # Tear down DB schema
    await _alembic_downgrade_base(email_dir)
