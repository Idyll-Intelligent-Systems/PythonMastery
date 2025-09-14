from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
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
    from VEZEPyGame.services.maps.api import router as maps_router  # type: ignore
    from VEZEPyGame.services.social.api import router as social_router  # type: ignore
    from VEZEPyGame.services.time.api import router as time_router  # type: ignore
    from VEZEPyGame.services.timevmaps.api import router as timevmaps_router  # type: ignore
    from VEZEPyGame.services.commerce.api import router as commerce_router  # type: ignore
    from VEZEPyGame.services.progress.api import router as progress_router  # type: ignore
except Exception:
    # Fallback for Docker image where packages are top-level modules
    from app.routers import public, ws
    from services.matchmaking.api import router as mm_router
    from services.leaderboards.api import router as lb_router
    from services.telemetry.api import router as tel_router
    from services.inventory.api import router as inv_router
    from services.ml.api import router as ml_router
    from services.email.api import router as mail_router
    from services.maps.api import router as maps_router
    from services.social.api import router as social_router
    from services.time.api import router as time_router
    from services.timevmaps.api import router as timevmaps_router
    from services.commerce.api import router as commerce_router
    from services.progress.api import router as progress_router
from pathlib import Path
from services.registry_cache import snapshot_status
from services.registry_cache import snapshot_status, list_services
import httpx
import os, time

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
app.include_router(maps_router, prefix="/maps", tags=["maps"])
app.include_router(social_router, prefix="/social", tags=["social"])
app.include_router(time_router, prefix="/time", tags=["time"])
app.include_router(timevmaps_router, prefix="/timevmaps", tags=["timevmaps"])
app.include_router(commerce_router, prefix="/commerce", tags=["commerce"])
app.include_router(progress_router, prefix="/progress", tags=["progress"])

# Asset version for cache-busting
ASSET_V = os.getenv("GAME_ASSET_V") or str(int(time.time()))


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "ui.html", {"asset_v": ASSET_V})

@app.get("/ui", response_class=HTMLResponse)
def ui_home(request: Request):
    return templates.TemplateResponse(request, "ui.html", {"asset_v": ASSET_V})

@app.get("/leaderboards", response_class=HTMLResponse)
def ui_leaderboards(request: Request):
    return templates.TemplateResponse(request, "leaderboards.html", {"asset_v": ASSET_V})

@app.get("/inventory", response_class=HTMLResponse)
def ui_inventory(request: Request):
    return templates.TemplateResponse(request, "inventory.html", {"asset_v": ASSET_V})

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/registry/health")
async def registry_health():
    return {"services": await snapshot_status()}

@app.get("/registry/services")
async def registry_services():
    return {"services": list_services()}


@app.get("/news/trends", response_class=JSONResponse)
async def news_trends():
    """Server-side proxy to XEngine trends to avoid browser CORS issues."""
    # Prefer internal Docker DNS service name
    targets = [
        "http://xengine:8006/api/trends",
        "http://veze_xengine:8006/api/trends",
    ]
    for url in targets:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(url)
                if r.status_code == 200:
                    return JSONResponse(r.json())
        except Exception:
            continue
    # Fallback: empty list
    return {"trends": []}
