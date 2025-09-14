## Quickstart: Local Dev

Spin up all VEZE services (UniQVerse, Game, Email, XEngine):

```bash
docker compose build
docker compose up
```

Portal: [http://localhost:8000](http://localhost:8000)
All endpoints available via Helm/compose.
**Python-only** FastAPI portal named **VEZEPyUniQVerse** that acts as the entrypoint website to all VEZE services (VEZEPyGame, VEZEPyEmail, VEZEPyWeb, VEZEPySports, VEZEPySocial, etc.).
Work inside the repo **VEZEPyUniQVerse/**
All business logic must be in Python; client visuals can use **static CSS and a small vanilla JS file** (no build tools). Use **Jinja2** for templates.

### Default ports (compose)

- Portal (UniQVerse): 8000 (override with UNI_PORT)
- Game: 8002 (override with GAME_PORT)
- Email: 8004 (override with EMAIL_PORT)
- XEngine: 8006 (override with XENGINE_PORT)

You can change host ports by exporting these env vars before `docker compose up`.

## 0) Requirements

* Python 3.11+, FastAPI, Uvicorn, Jinja2, pydantic v2, redis (future), prometheus-client (metrics), opentelemetry (hook ready).
* No Node build. One small `static/js/blackhole.js` allowed for animations.
* Config-driven service registry via **`config/services.json`** and **env** overrides.

## 1) Create project layout

```
VEZEPyUniQVerse/
├─ pyproject.toml
├─ Dockerfile
├─ app/
│  ├─ main.py
│  ├─ deps.py
│  ├─ config.py
│  ├─ routers/
│  │  ├─ pages.py          # routes: /, /helm, /copilot, /verse, /express, /health, /metrics
│  │  └─ ws.py             # WebSocket: /ws/copilot (echo stub)
│  └─ ui/
│     ├─ templates/
│     │  ├─ base.html
│     │  ├─ index.html     # landing (Black Hole / Nebula)
│     │  ├─ helm.html      # VEZE Helm (services grid)
│     │  ├─ copilot.html   # VEZE Copilot (chat UI)
│     │  ├─ verse.html     # VEZE Verse (about/team)
│     │  └─ express.html   # VEZE Express (X/IG/WA links)
│     └─ static/
│        ├─ css/theme.css
│        └─ js/blackhole.js
├─ config/
│  └─ services.json
└─ tests/
   └─ test_health.py
```

## 2) Files and contents

### `pyproject.toml`

Create a minimal project config:

```toml
[build-system]
requires = ["setuptools>=68","wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "veze-uniqverse-portal"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "jinja2>=3.1",
  "pydantic>=2.8",
  "prometheus-client>=0.20",
  "opentelemetry-sdk>=1.27.0",
  "opentelemetry-instrumentation-fastapi>=0.48b0",
  "opentelemetry-exporter-otlp>=1.27.0",
  "python-multipart>=0.0.9"
]

[project.optional-dependencies]
dev = ["ruff>=0.5","black>=24.8","mypy>=1.11","pytest>=8.3","pytest-asyncio>=0.23"]
```

### `app/config.py`

```python
from pydantic import BaseModel
from pathlib import Path
import json, os

class Service(BaseModel):
    name: str
    display: str
    url: str
    icon: str | None = None
    description: str | None = None

def load_services() -> list[Service]:
    cfg = Path("config/services.json")
    data = json.loads(cfg.read_text())
    # env override: VEZE_SERVICE_<NAME>=URL
    for s in data:
        env_key = f"VEZE_SERVICE_{s['name'].upper()}"
        if os.getenv(env_key):
            s["url"] = os.getenv(env_key)
    return [Service(**s) for s in data]
```

### `config/services.json`

(Preload the common services; URLs can be local or your deployed hosts.)

```json
[
  {"name":"web","display":"VEZEPyWeb","url":"http://localhost:8001","icon":"🌐","description":"Web CMS & portals"},
  {"name":"game","display":"VEZEPyGame","url":"http://localhost:8002","icon":"🎮","description":"Gaming platform"},
  {"name":"cgrow","display":"VEZEPyCGrow","url":"http://localhost:8003","icon":"💼","description":"Career growth & ATS"},
  {"name":"sports","display":"VEZEPySports","url":"http://localhost:8004","icon":"🏟️","description":"Sports & fantasy"},
  {"name":"email","display":"VEZEPyEmail","url":"http://localhost:8005","icon":"✉️","description":"Mail @vezeuniqverse.com"},
  {"name":"social","display":"VEZEPySocial","url":"http://localhost:8006","icon":"👥","description":"Community & feeds"}
]
```

### `app/deps.py`

```python
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

REQS = Counter("veze_requests_total","Total HTTP requests", ["path"])

def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

### `app/routers/pages.py`

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.deps import REQS, metrics_response
from app.config import load_services

router = APIRouter()

@router.get("/health")
async def health(): return {"status":"ok"}

@router.get("/metrics")
async def metrics(): return metrics_response()

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    REQS.labels("/").inc()
    return request.app.state.tpl.TemplateResponse("index.html", {"request": request})

@router.get("/helm", response_class=HTMLResponse)
async def helm(request: Request):
    REQS.labels("/helm").inc()
    services = load_services()
    return request.app.state.tpl.TemplateResponse("helm.html", {"request": request, "services": services})

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
    return request.app.state.tpl.TemplateResponse("express.html", {"request": request})
```

### `app/routers/ws.py`

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
router = APIRouter()
clients: set[WebSocket] = set()

@router.websocket("/ws/copilot")
async def ws_copilot(ws: WebSocket):
    await ws.accept(); clients.add(ws)
    try:
        await ws.send_json({"role":"system","text":"VEZE Copilot online. Ask about any VEZE service."})
        while True:
            msg = await ws.receive_text()
            # Echo stub; replace with your LLM backend
            await ws.send_json({"role":"assistant","text":f"Echo: {msg}"})
    except WebSocketDisconnect:
        clients.discard(ws)
```

### `app/main.py`

```python
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.routers import pages, ws

app = FastAPI(title="VEZEPyUniQVerse")

app.include_router(pages.router, tags=["pages"])
app.include_router(ws.router, tags=["ws"])

app.mount("/static", StaticFiles(directory="app/ui/static"), name="static")
app.state.tpl = Jinja2Templates(directory="app/ui/templates")

@app.get("/health")
async def health(): return {"status":"ok"}
```

### `app/ui/templates/base.html`

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>VEZEPyUniQVerse</title>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <link rel="stylesheet" href="/static/css/theme.css"/>
</head>
<body class="space-bg">
  <nav class="veze-nav">
    <a href="/" class="brand">VEZE UniQVerse</a>
    <div class="menu">
      <a href="/helm">VEZE Helm</a>
      <a href="/copilot">VEZE Copilot</a>
      <a href="/verse">VEZE Verse</a>
      <a href="/express">VEZE Express</a>
    </div>
  </nav>
  <canvas id="blackhole"></canvas>
  <script src="/static/js/blackhole.js"></script>

  <main class="content">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

### `app/ui/templates/index.html` (Landing)

```html
{% extends "base.html" %}
{% block content %}
<section class="hero">
  <h1>VEZEPyUniQVerse</h1>
  <p>One account. All VEZE services. Across space & time.</p>
  <div class="cta">
    <a href="/helm" class="btn">Enter VEZE Helm</a>
    <a href="/copilot" class="btn secondary">Ask VEZE Copilot</a>
  </div>
</section>
{% endblock %}
```

### `app/ui/templates/helm.html` (VEZE Helm)

```html
{% extends "base.html" %}
{% block content %}
<h2>VEZE Helm — Services</h2>
<div class="grid">
  {% for s in services %}
  <a class="card" href="{{ s.url }}" target="_blank" rel="noopener">
    <div class="icon">{{ s.icon }}</div>
    <div class="title">{{ s.display }}</div>
    <div class="desc">{{ s.description }}</div>
  </a>
  {% endfor %}
</div>
{% endblock %}
```

### `app/ui/templates/copilot.html` (VEZE Copilot)

```html
{% extends "base.html" %}
{% block content %}
<h2>VEZE Copilot — ASI Assistant</h2>
<div id="chat">
  <div id="log"></div>
  <form id="send">
    <input id="msg" placeholder="Ask about any VEZE service…"/>
    <button type="submit">Send</button>
  </form>
</div>
<script>
const log = document.getElementById('log');
const ws = new WebSocket((location.protocol==='https:'?'wss':'ws')+'://'+location.host+'/ws/copilot');
ws.onmessage = (e)=>{ const m=JSON.parse(e.data); const p=document.createElement('p'); p.textContent = (m.role||'')+': '+m.text; log.appendChild(p); };
document.getElementById('send').onsubmit = (ev)=>{ ev.preventDefault(); ws.send(document.getElementById('msg').value); document.getElementById('msg').value=''; };
</script>
{% endblock %}
```

### `app/ui/templates/verse.html` (About)

```html
{% extends "base.html" %}
{% block content %}
<h2>VEZE Verse</h2>
<p>Idyll-Intelligent-Systems · VEZE UniQVerse core team.</p>
<ul>
  <li>Vision: Unified Python-first super-app across domains.</li>
  <li>Stack: FastAPI, Jinja2, Redis, Postgres, OTEL.</li>
  <li>Domains: Web, Game, CGrow, Sports, Email, Social, and more…</li>
</ul>
{% endblock %}
```

### `app/ui/templates/express.html` (Social hub)

```html
{% extends "base.html" %}
{% block content %}
<h2>VEZE Express — Social</h2>
<ul class="links">
  <li><a href="https://x.com" target="_blank" rel="noopener">X (Twitter)</a></li>
  <li><a href="https://instagram.com" target="_blank" rel="noopener">Instagram</a></li>
  <li><a href="https://wa.me/" target="_blank" rel="noopener">WhatsApp</a></li>
</ul>
{% endblock %}
```

### `app/ui/static/css/theme.css`

Use **pure CSS** to render starfield/nebula/black hole feel + “spaceship UI” nav.

```css
:root {
  --bg1: radial-gradient(closest-side, rgba(0,0,0,0.9), rgba(0,0,0,0.98));
  --nebula: radial-gradient(60% 80% at 20% 30%, rgba(120,0,200,.25), transparent),
            radial-gradient(50% 70% at 80% 60%, rgba(0,180,255,.18), transparent);
}
html,body {height:100%; margin:0; color:#e8f0ff; font-family: ui-sans-serif, system-ui, Segoe UI, Roboto, Helvetica, Arial;}
.space-bg {background: var(--bg1), var(--nebula), #000; overflow:hidden;}
#blackhole {position:fixed; inset:0; z-index:0;}
.veze-nav{position:fixed; z-index:3; top:0; left:0; right:0; display:flex; justify-content:space-between; padding:14px 24px; backdrop-filter: blur(6px); background: rgba(10,10,20,.35); border-bottom: 1px solid rgba(255,255,255,.08);}
.veze-nav a{color:#cfe8ff; text-decoration:none; margin:0 10px;}
.brand{font-weight:700; letter-spacing:.5px}
.content{position:relative; z-index:2; padding-top:96px; padding-bottom:48px; max-width:1100px; margin:0 auto; }
.hero{display:flex; flex-direction:column; align-items:center; gap:16px; padding:80px 20px;}
.hero h1{font-size:56px; margin:0;}
.btn{padding:12px 18px; border-radius:14px; border:1px solid rgba(255,255,255,.2);}
.btn.secondary{opacity:.8}
.grid{display:grid; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); gap:16px; margin-top:20px;}
.card{background:rgba(20,20,35,.5); border:1px solid rgba(255,255,255,.1); border-radius:18px; padding:16px; text-decoration:none; color:#e8f0ff; transition: transform .2s ease, background .2s;}
.card:hover{transform: translateY(-4px); background: rgba(30,30,60,.55);}
.icon{font-size:28px;}
.links li{margin:8px 0;}
```

### `app/ui/static/js/blackhole.js`

A tiny canvas particle warp (no frameworks). Keep it small.

```javascript
const c = document.getElementById('blackhole');
const ctx = c.getContext('2d');
let w,h, stars=[]; function rs(){w= c.width = innerWidth; h= c.height = innerHeight; stars = Array.from({length: Math.min(500, Math.floor(w*h/4000))},()=>({x:Math.random()*w, y:Math.random()*h, z:Math.random()*1+0.2}));}
addEventListener('resize', rs); rs();
function tick(t){
  ctx.clearRect(0,0,w,h);
  // subtle nebula glow
  const g = ctx.createRadialGradient(w*0.5,h*0.5,10,w*0.5,h*0.5, Math.max(w,h)*0.6);
  g.addColorStop(0,'rgba(0,0,0,0)');
  g.addColorStop(1,'rgba(0,0,0,0.8)');
  ctx.fillStyle=g; ctx.fillRect(0,0,w,h);
  // black hole swirl
  ctx.save();
  ctx.translate(w/2,h/2); ctx.rotate((t*0.00005)% (Math.PI*2));
  ctx.beginPath(); for(let i=0;i<40;i++){ ctx.strokeStyle=`rgba(80,120,255,${0.03+i*0.002})`; ctx.arc(0,0, 40+i*6, 0, Math.PI*2); ctx.stroke(); }
  ctx.restore();
  // stars warp
  ctx.fillStyle='rgba(200,230,255,0.9)';
  for(const s of stars){
    const dx = (w/2 - s.x), dy=(h/2 - s.y), d=Math.hypot(dx,dy);
    const pull = 0.02/(1+d/400); s.x += dx*pull*s.z; s.y += dy*pull*s.z;
    const twinkle = (Math.sin(t*0.002 + d*0.05)+1)/2;
    ctx.globalAlpha = 0.4 + 0.6*twinkle;
    ctx.fillRect(s.x, s.y, 1.2+s.z, 1.2+s.z);
  }
  ctx.globalAlpha=1.0; requestAnimationFrame(tick);
}
requestAnimationFrame(tick);
```

### `Dockerfile`

```dockerfile
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml .
RUN pip install --upgrade pip && pip install -e .
COPY . .
EXPOSE 8000
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
```

### `tests/test_health.py`

```python
from fastapi.testclient import TestClient
from app.main import app

def test_health():
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
```

## 3) Behavior

* **Landing (`/`)**: Black hole + nebula animated background; CTA buttons.
* **VEZE Helm (`/helm`)**: Grid of service cards reading `config/services.json` (env overrides `VEZE_SERVICE_<NAME>`).
* **VEZE Copilot (`/copilot`)**: Minimal chat UI using **WS `/ws/copilot`** (echo stub).
* **VEZE Verse (`/verse`)**: About/team.
* **VEZE Express (`/express`)**: Social links page.
* **/metrics**: Prometheus metrics. **/health**: healthcheck.

## 4) Run

```bash
pip install -e .[dev]
uvicorn app.main:app --reload
# open http://localhost:8000
```

## 5) Link services

Set envs (optional):

```bash
export VEZE_SERVICE_GAME=https://your-game-host
export VEZE_SERVICE_EMAIL=https://your-email-host
# ...
```

**End of instructions. Generate every file above exactly at the specified paths, then show me a short “Done” summary.**
