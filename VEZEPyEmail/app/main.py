from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
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
if jmap is not None:
    app.include_router(jmap.router, tags=["jmap"])
app.include_router(ws.router, tags=["ws"])


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("inbox.html", {"request": request})

@app.get("/ui/inbox", response_class=HTMLResponse)
async def ui_inbox(request: Request):
    return templates.TemplateResponse("inbox.html", {"request": request})

@app.get("/health")
async def health():
    return {"status": "ok"}
