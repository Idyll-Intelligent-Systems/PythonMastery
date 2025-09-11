from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers import ws
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


def _sample_messages():
    return [
        {
            "id": 1,
            "from": "alice@example.com",
            "subject": "Welcome to VEZEPyEmail",
            "snippet": "Thanks for trying the demo inbox.",
            "date": "2025-09-11 10:05",
            "labels": ["Inbox"],
            "unread": True,
            "starred": False,
        },
        {
            "id": 2,
            "from": "noreply@game.example",
            "subject": "Your daily rewards",
            "snippet": "Claim your coins and boosts.",
            "date": "2025-09-11 09:00",
            "labels": ["Promotions"],
            "unread": False,
            "starred": True,
        },
        {
            "id": 3,
            "from": "bob@example.com",
            "subject": "Lunch tomorrow?",
            "snippet": "Let me know what works.",
            "date": "2025-09-10 17:42",
            "labels": ["Inbox"],
            "unread": False,
            "starred": False,
        },
    ]
if jmap is not None:
    app.include_router(jmap.router, tags=["jmap"])
app.include_router(ws.router, tags=["ws"])


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("inbox.html", {"request": request, "messages": _sample_messages()})

@app.get("/ui/inbox", response_class=HTMLResponse)
async def ui_inbox(request: Request):
    return templates.TemplateResponse("inbox.html", {"request": request, "messages": _sample_messages()})


@app.get("/ui/message/{msg_id}", response_class=HTMLResponse)
async def ui_message(request: Request, msg_id: int):
    msgs = _sample_messages()
    msg = next((m for m in msgs if m["id"] == msg_id), None)
    return templates.TemplateResponse("message.html", {"request": request, "message": msg})

@app.get("/health")
async def health():
    return {"status": "ok"}
