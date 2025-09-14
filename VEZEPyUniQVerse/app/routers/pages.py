from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from urllib.parse import urlparse

from app.config import load_services, Service
from app.clients.registry_client import fetch_registry_health, fetch_registry_services
from app.clients.email_client import provision_mailbox
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
    return request.app.state.tpl.TemplateResponse(request, "index.html", {})


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
    # Auto-provision if a veze_user cookie is present (idempotent) and demo token enabled
    x_user_id = request.cookies.get("veze_user")
    provisioned_now = False
    if x_user_id and request.cookies.get("veze_mail_provisioned") not in {"1", "true", "True"}:
        email = f"{x_user_id}@vezeuniqverse.com"
        import os as _os
        token = "demo" if _os.getenv("VEZE_JWT_DEMO") in {"1", "true", "True"} else None
        try:
            await provision_mailbox(email, access_token=token)
            provisioned_now = True
        except Exception:
            # Ignore auto-provision errors to keep Helm rendering
            pass

    # Prefer Game registry for centralized discovery
    services_raw: list[dict] | None = None
    try:
        reg_services = await fetch_registry_services()
        services_raw = list(reg_services.get("services", []))
    except Exception:
        services_raw = None

    cards = []
    if services_raw:
        # Also get health mapping to annotate
        status_map: dict[str, dict] = {}
        try:
            reg = await fetch_registry_health()
            for s in (reg or {}).get("services", []):
                status_map[s.get("name")] = s
        except Exception:
            pass

        for s in services_raw:
            name = s.get("name")
            base = s.get("url")
            ui_path = s.get("ui_path")
            data = {
                "name": name,
                "display": s.get("display") or name,
                "url": _externalize_url(base, request, ui_path),
            }
            if s.get("icon"):
                data["icon"] = s.get("icon")
            if s.get("description"):
                data["description"] = s.get("description")
            if name in status_map:
                data["healthy"] = bool(status_map[name].get("healthy"))
                if status_map[name].get("requires_auth") is not None:
                    data["requires_auth"] = bool(status_map[name]["requires_auth"])
            cards.append(data)
    else:
        # Fallback to local config/services.json
        services = load_services()
        # Try to enrich with health statuses from Game registry
        status_map: dict[str, bool] = {}
        try:
            reg = await fetch_registry_health()
            for s in (reg or {}).get("services", []):
                status_map[s.get("name")] = bool(s.get("healthy"))
        except Exception:
            pass
        for s in services:
            data = s.model_dump()
            ui_path = None
            if s.name == "email":
                ui_path = "/ui/inbox"
            elif s.name == "game":
                ui_path = "/ui"
            data["url"] = _externalize_url(s.url, request, ui_path)
            # Attach health status if available (by matching known names)
            name_map = {"game": "game", "email": "email", "web": "uniqverse", "social": "social", "maps": "maps"}
            key = name_map.get(s.name, s.name)
            if key in status_map:
                data["healthy"] = status_map[key]
            cards.append(data)

    resp = request.app.state.tpl.TemplateResponse(request, "helm.html", {"services": cards})
    if provisioned_now:
        resp.set_cookie(key="veze_mail_provisioned", value="1", httponly=False, samesite="lax")
    return resp


@router.get("/copilot", response_class=HTMLResponse)
async def copilot(request: Request):
    REQS.labels("/copilot").inc()
    return request.app.state.tpl.TemplateResponse(request, "copilot.html", {})


@router.get("/verse", response_class=HTMLResponse)
async def verse(request: Request):
    REQS.labels("/verse").inc()
    return request.app.state.tpl.TemplateResponse(request, "verse.html", {})


@router.get("/express")
async def express():
    # Redirect to a simple page listing links (or external socials)
    return RedirectResponse(url="/express/home")


@router.get("/express/home", response_class=HTMLResponse)
async def express_home(request: Request):
    REQS.labels("/express/home").inc()
    return request.app.state.tpl.TemplateResponse(request, "express.html", {})


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
        REQS.labels("/login").inc()
        # Simple inline form using base template
        return request.app.state.tpl.TemplateResponse(
            request,
            "base.html",
            {
                "content": """
                        <section class=\"hero\">
                            <h2>VEZE Login</h2>
                            <form method=\"post\" action=\"/login\"> 
                                <label>X User ID</label>
                                <input name=\"x_user_id\" placeholder=\"enter your user id\" required />
                                <button type=\"submit\">Login</button>
                            </form>
                        </section>
                        """,
                },
        )
