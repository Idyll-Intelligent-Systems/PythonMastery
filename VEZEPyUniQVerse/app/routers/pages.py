from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from urllib.parse import urlparse

from app.config import load_services
from app.deps import REQS, metrics_response

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/metrics")
async def metrics():
    return metrics_response()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    REQS.labels("/").inc()
    return request.app.state.tpl.TemplateResponse("index.html", {"request": request})


def _externalize_url(raw_url: str | None, request: Request, ui_path: str | None = None) -> str:
    """Return a link that works in GitHub Codespaces and local dev.

    - If running behind app.github.dev, convert localhost:PORT to
      https://<codespace>-PORT.app.github.dev[/ui_path]
    - Otherwise return the original URL (optionally with ui_path).
    """
    if not raw_url:
        raw_url = "/"
    p = urlparse(raw_url)
    port = p.port or (8000 if p.scheme in (None, "", "http") else None)
    path = ui_path or (p.path or "/")

    fwd_host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    if fwd_host.endswith(".app.github.dev") and "-" in fwd_host:
        # subdomain looks like: <codespace>-8000.app.github.dev
        subdomain, _, domain_rest = fwd_host.partition(".")
        prefix, sep, last = subdomain.rpartition("-")
        if sep and last.isdigit() and port:
            subdomain = f"{prefix}-{port}"
        return f"https://{subdomain}.{domain_rest}{path}"

    # default: return the original base, ensuring path
    host = p.hostname or "localhost"
    if p.port:
        return f"{p.scheme or 'http'}://{host}:{p.port}{path}"
    return f"{p.scheme or 'http'}://{host}{path}"


@router.get("/helm", response_class=HTMLResponse)
async def helm(request: Request):
    REQS.labels("/helm").inc()
    services = load_services()
    # Build display list with externalized, UI-friendly URLs
    cards = []
    for s in services:
        data = s.model_dump()
        ui_path = None
        if s.name == "email":
            ui_path = "/ui/inbox"
        elif s.name == "game":
            ui_path = "/ui"
        data["url"] = _externalize_url(s.url, request, ui_path)
        cards.append(data)
    return request.app.state.tpl.TemplateResponse(
        "helm.html", {"request": request, "services": cards}
    )


@router.get("/copilot", response_class=HTMLResponse)
async def copilot(request: Request):
    REQS.labels("/copilot").inc()
    return request.app.state.tpl.TemplateResponse("copilot.html", {"request": request})


@router.get("/verse", response_class=HTMLResponse)
async def verse(request: Request):
    REQS.labels("/verse").inc()
    return request.app.state.tpl.TemplateResponse("verse.html", {"request": request})


@router.get("/express")
async def express():
    # Redirect to a simple page listing links (or external socials)
    return RedirectResponse(url="/express/home")


@router.get("/express/home", response_class=HTMLResponse)
async def express_home(request: Request):
    REQS.labels("/express/home").inc()
    return request.app.state.tpl.TemplateResponse("express.html", {"request": request})
