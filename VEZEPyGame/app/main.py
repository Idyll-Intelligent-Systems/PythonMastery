from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
try:
    from VEZEPyGame.app.routers import public, ws  # type: ignore
    from VEZEPyGame.services.matchmaking.api import router as mm_router  # type: ignore
    from VEZEPyGame.services.leaderboards.api import router as lb_router  # type: ignore
    from VEZEPyGame.services.telemetry.api import router as tel_router  # type: ignore
    from VEZEPyGame.services.inventory.api import router as inv_router  # type: ignore
    from VEZEPyGame.services.ml.api import router as ml_router  # type: ignore
    from VEZEPyGame.services.email.api import router as mail_router  # type: ignore
except Exception:
    # Fallback for Docker image where packages are top-level modules
    from app.routers import public, ws
    from services.matchmaking.api import router as mm_router
    from services.leaderboards.api import router as lb_router
    from services.telemetry.api import router as tel_router
    from services.inventory.api import router as inv_router
    from services.ml.api import router as ml_router
    from services.email.api import router as mail_router
from pathlib import Path

app = FastAPI(title="VEZEPyGame")
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "ui" / "templates"
STATIC_DIR = BASE_DIR / "ui" / "static"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
try:
    templates.env.auto_reload = True
except Exception:
    pass
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
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
