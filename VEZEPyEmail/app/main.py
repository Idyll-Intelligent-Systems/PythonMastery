from fastapi import FastAPI, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers import ws
from app.routers import api as email_api
from pathlib import Path
try:
    from app.routers import jmap
except Exception:  # jmap may not exist yet in some minimal runs
    jmap = None

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "ui" / "templates"
STATIC_DIR = BASE_DIR / "ui" / "static"

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables exist (useful for tests/dev)
    from db.database import engine
    from db.base import Base
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        # Best-effort; tests may run alembic separately
        pass
    yield
    # No teardown needed


app = FastAPI(title="VEZEPyEmail JMAP & Webmail", lifespan=lifespan)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
try:
    templates.env.auto_reload = True
except Exception:
    pass
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


from db.database import get_session, engine
from db.base import Base
from db.repository import get_or_create_mailbox, list_messages_for_mailbox, mark_read, create_message
if jmap is not None:
    app.include_router(jmap.router, tags=["jmap"])
app.include_router(ws.router, tags=["ws"])
app.include_router(email_api.router, prefix="/api", tags=["api"])


async def _ensure_seed(session, user: str) -> None:
    """Seed initial welcome messages for a new or empty inbox."""
    mbox = await get_or_create_mailbox(session, user)
    msgs = await list_messages_for_mailbox(session, mbox.id, limit=1)
    if msgs:
        return
    base_links = (
        "- Portal: http://127.0.0.1:8000/\n"
        "- XEngine: http://127.0.0.1:8000/xengine/\n"
        "- Game: http://127.0.0.1:8002/\n"
        "- Email: http://127.0.0.1:8004/\n"
    )
    await create_message(
        session,
        mailbox_id=mbox.id,
        subject="Welcome to VEZE UniQVerse 🚀",
        from_addr="welcome@vezeuniqverse.com",
        snippet=(
            "Welcome aboard! Explore services, pick your accent, and try the XEngine dashboard.\n" + base_links
        ),
        labels=["Inbox"],
        flags=["Seen"],
    )
    await create_message(
        session,
        mailbox_id=mbox.id,
        subject="Getting Started Tips",
        from_addr="guide@vezeuniqverse.com",
        snippet=(
            "Use the portal to discover features. Toggle live data on XEngine and try posting in sandbox!\n" + base_links
        ),
        labels=["Inbox", "Tips"],
        flags=[],
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, session=Depends(get_session)):
    user = request.query_params.get("user") or "demo@vezeuniqverse.com"
    await _ensure_seed(session, user)
    mbox = await get_or_create_mailbox(session, user)
    msgs = await list_messages_for_mailbox(session, mbox.id, limit=50)
    return templates.TemplateResponse(request, "inbox.html", {"messages": msgs})

@app.get("/ui/inbox", response_class=HTMLResponse)
async def ui_inbox(request: Request, session=Depends(get_session)):
    user = request.query_params.get("user") or "demo@vezeuniqverse.com"
    q = request.query_params.get("q")
    offset = int(request.query_params.get("offset") or 0)
    await _ensure_seed(session, user)
    mbox = await get_or_create_mailbox(session, user)
    msgs = await list_messages_for_mailbox(session, mbox.id, limit=50, offset=offset, q=q)
    return templates.TemplateResponse(request, "inbox.html", {"messages": msgs})


@app.get("/ui/message/{msg_id}", response_class=HTMLResponse)
async def ui_message(request: Request, msg_id: int, session=Depends(get_session)):
    # mark unread on open
    await mark_read(session, msg_id)
    # simple load from current inbox slice for render context
    user = request.query_params.get("user") or "demo@vezeuniqverse.com"
    mbox = await get_or_create_mailbox(session, user)
    msgs = await list_messages_for_mailbox(session, mbox.id, limit=50)
    msg = next((m for m in msgs if m["id"] == msg_id), None)
    return templates.TemplateResponse(request, "message.html", {"message": msg})

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ui/compose", response_class=HTMLResponse)
async def ui_compose(request: Request):
    return templates.TemplateResponse(request, "compose.html", {})


@app.post("/ui/compose")
async def ui_compose_post(
    request: Request,
    session=Depends(get_session),
    to: str = Form(...),
    subject: str = Form("(no subject)"),
    body: str = Form(""),
):
    # For dev: send as if from the demo user and store in recipient inbox as new message
    from_addr = "demo@vezeuniqverse.com"
    user = to.strip() or "demo@vezeuniqverse.com"
    mbox = await get_or_create_mailbox(session, user)
    snippet = (body or "").splitlines()[0][:240]
    await create_message(
        session,
        mailbox_id=mbox.id,
        subject=subject or "(no subject)",
        from_addr=from_addr,
        snippet=snippet,
        labels=["Inbox"],
        flags=[],
    )
    # Redirect back to inbox of the recipient
    return RedirectResponse(url=f"/ui/inbox?user={user}", status_code=303)
