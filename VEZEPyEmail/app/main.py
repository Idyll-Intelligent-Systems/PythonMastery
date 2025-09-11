from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers import ws
from app.routers import api as email_api
try:
    from app.routers import jmap
except Exception:  # jmap may not exist yet in some minimal runs
    jmap = None

app = FastAPI(title="VEZEPyEmail JMAP & Webmail")
templates = Jinja2Templates(directory="app/ui/templates")
try:
    templates.env.auto_reload = True
except Exception:
    pass
app.mount("/static", StaticFiles(directory="app/ui/static"), name="static")


from db.database import get_session
from db.repository import get_or_create_mailbox, list_messages_for_mailbox, mark_read
if jmap is not None:
    app.include_router(jmap.router, tags=["jmap"])
app.include_router(ws.router, tags=["ws"])
app.include_router(email_api.router, prefix="/api", tags=["api"])


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, session=Depends(get_session)):
    user = request.query_params.get("user") or "demo@vezeuniqverse.com"
    mbox = await get_or_create_mailbox(session, user)
    msgs = await list_messages_for_mailbox(session, mbox.id, limit=50)
    return templates.TemplateResponse("inbox.html", {"request": request, "messages": msgs})

@app.get("/ui/inbox", response_class=HTMLResponse)
async def ui_inbox(request: Request, session=Depends(get_session)):
    user = request.query_params.get("user") or "demo@vezeuniqverse.com"
    q = request.query_params.get("q")
    offset = int(request.query_params.get("offset") or 0)
    mbox = await get_or_create_mailbox(session, user)
    msgs = await list_messages_for_mailbox(session, mbox.id, limit=50, offset=offset, q=q)
    return templates.TemplateResponse("inbox.html", {"request": request, "messages": msgs})


@app.get("/ui/message/{msg_id}", response_class=HTMLResponse)
async def ui_message(request: Request, msg_id: int, session=Depends(get_session)):
    # mark unread on open
    await mark_read(session, msg_id)
    # simple load from current inbox slice for render context
    user = request.query_params.get("user") or "demo@vezeuniqverse.com"
    mbox = await get_or_create_mailbox(session, user)
    msgs = await list_messages_for_mailbox(session, mbox.id, limit=50)
    msg = next((m for m in msgs if m["id"] == msg_id), None)
    return templates.TemplateResponse("message.html", {"request": request, "message": msg})

@app.get("/health")
async def health():
    return {"status": "ok"}
