from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.routers import public, ws
from services.matchmaking.api import router as mm_router
from services.leaderboards.api import router as lb_router
from services.telemetry.api import router as tel_router
from services.inventory.api import router as inv_router
from services.ml.api import router as ml_router
from services.email.api import router as mail_router

app = FastAPI(title="VEZEPyGame")
templates = Jinja2Templates(directory="app/ui/templates")
try:
    templates.env.auto_reload = True
except Exception:
    pass
app.mount("/static", StaticFiles(directory="app/ui/static"), name="static")
app.include_router(public.router, tags=["public"])
app.include_router(ws.router, tags=["ws"])
app.include_router(mm_router, prefix="/matchmaking", tags=["matchmaking"])
app.include_router(lb_router, prefix="/leaderboards", tags=["leaderboards"])
app.include_router(tel_router, prefix="/telemetry", tags=["telemetry"])
app.include_router(inv_router, prefix="/inventory", tags=["inventory"])
app.include_router(ml_router, prefix="/ml", tags=["ml"])
app.include_router(mail_router, prefix="/email", tags=["email"])


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("ui.html", {"request": request})

@app.get("/ui", response_class=HTMLResponse)
def ui_home(request: Request):
    return templates.TemplateResponse("ui.html", {"request": request})

@app.get("/health")
def health():
    return {"status": "ok"}
