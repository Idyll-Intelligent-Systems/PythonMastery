import pytest
import httpx
import os, sys, subprocess
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
EMAIL_ROOT = os.path.abspath(os.path.join(THIS_DIR, os.pardir))
email_dir = os.path.abspath(os.path.join(EMAIL_ROOT))
db_path = os.path.join(email_dir, "test_email_api.db")
os.environ.setdefault("EMAIL_DB_URL", f"sqlite+aiosqlite:///{db_path}")
try:
    subprocess.check_call([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=email_dir)
except Exception:
    # if migration unavailable, continue; some envs may not have alembic
    pass
try:
    # Fallback: ensure tables exist
    import sqlalchemy as sa
    from VEZEPyEmail.db.base import Base
    engine = sa.create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
except Exception:
    pass
from VEZEPyEmail.app.main import app


@pytest.mark.asyncio
async def test_messages_requires_token():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/messages", params={"user": "test@vezeuniqverse.com"})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_messages_ok():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(
            "/api/messages",
            params={"user": "test@vezeuniqverse.com", "access_token": "demo"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["user"] == "test@vezeuniqverse.com"
        assert isinstance(data["messages"], list)
