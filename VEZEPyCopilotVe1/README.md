# 🤖 VEZEPyCopilotVe1 — Hardcore ASI for VEZE UniQVerse (Python-only)

**Roles**

* **Helm Copilot:** surfaces tiles, routes users to services, executes cross-service actions.
* **Support Bot:** triages requests, resolves via tools (Email, Commerce, RAG, Sports, Social, XEngine).
* **Player ASI:** plans strategies, reacts to game events, generates NPC/ally behaviors.

**Tech**

* FastAPI + Jinja2 UI (Copilot console)
* Tools/adapters (HTTP) to other VEZE services
* Multi-agent orchestrator (Router → Specialist Agents)
* Memory: Redis (short-term), Postgres (sessions/logs)
* Optional semantic memory: FAISS (mini)
* Streaming: **SSE** and **WebSocket**
* Events: Redis Streams (`copilot.task.created`, `copilot.action.executed`, `copilot.game.plan`)
* Metrics: Prometheus `/metrics`
* Discovery for Helm: `/.veze/service.json`
* Docker + CI + tests

---

## Repo layout

```
VEZEPyCopilotVe1/
├─ README.md
├─ .env.example
├─ pyproject.toml
├─ Dockerfile
├─ .github/workflows/ci.yml
├─ app/
│  ├─ main.py
│  ├─ settings.py
│  ├─ deps.py
│  ├─ ui/templates/{base.html,index.html,chat.html,tools.html}
│  ├─ routers/
│  │  ├─ pages.py
│  │  ├─ chat.py          # /chat (REST + SSE) + /ws
│  │  ├─ actions.py       # tool/action endpoints (optional proxy)
│  │  ├─ discovery.py
│  │  └─ health.py
│  ├─ core/
│  │  ├─ orchestrator.py  # Router → Agents → Tools
│  │  ├─ agents.py        # HelmAgent, SupportAgent, GameAgent
│  │  ├─ planner.py       # task planning (GRASP-like)
│  │  ├─ memory.py        # Redis short-term, Postgres long-term
│  │  ├─ policy.py        # guardrails
│  │  └─ schema.py        # pydantic models
│  ├─ tools/
│  │  ├─ email.py         # VEZEPyEmail adapter
│  │  ├─ commerce.py      # VEZEPyCommerce adapter
│  │  ├─ rag.py           # VEZEPyRAG adapter
│  │  ├─ xengine.py       # VEZEPyXEngine adapter
│  │  ├─ game.py          # VEZEPyGame adapter
│  │  ├─ social.py        # VEZEPySocial adapter
│  │  ├─ sports.py        # VEZEPySports adapter
│  │  ├─ bus.py           # Redis Streams emitter
│  │  └─ utils.py
│  └─ db/
│     ├─ database.py
│     ├─ models.py        # Session, Message, ToolCall, TicketLink, PlanStep
│     └─ seed.py
└─ tests/{test_health.py,test_router_smoke.py}
```

---

## .env.example

```env
ENV=dev
PORT=8016
DATABASE_URL=postgresql+asyncpg://veze:veze@localhost:5432/veze_copilot
REDIS_URL=redis://localhost:6379/7
# service endpoints (Helm proxies resolve to these or service DNS)
SVC_EMAIL=http://veze_email:8005
SVC_COMMERCE=http://veze_commerce:8012
SVC_RAG=http://veze_rag:8014
SVC_GAME=http://veze_game:8008
SVC_XENGINE=http://veze_xengine:8006
SVC_SPORTS=http://veze_sports:8009
SVC_SOCIAL=http://veze_social:8007
```

---

## pyproject.toml

```toml
[project]
name = "veze-copilot"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "jinja2>=3.1",
  "pydantic>=2.8",
  "SQLAlchemy>=2.0",
  "asyncpg>=0.29",
  "redis>=5.0",
  "httpx>=0.27",
  "prometheus-fastapi-instrumentator>=7.0.0",
  "python-multipart>=0.0.9",
  "sse-starlette>=2.0.0"
]
[project.optional-dependencies]
dev = ["pytest>=8.3","pytest-asyncio>=0.23","ruff>=0.5","black>=24.8","mypy>=1.11"]
```

---

## app/settings.py

```python
import os
from pydantic import BaseModel

class Settings(BaseModel):
    env: str = os.getenv("ENV","dev")
    port: int = int(os.getenv("PORT","8016"))
    db_url: str = os.getenv("DATABASE_URL","postgresql+asyncpg://veze:veze@localhost:5432/veze_copilot")
    redis_url: str = os.getenv("REDIS_URL","redis://localhost:6379/7")
    svc_email: str = os.getenv("SVC_EMAIL","http://veze_email:8005")
    svc_commerce: str = os.getenv("SVC_COMMERCE","http://veze_commerce:8012")
    svc_rag: str = os.getenv("SVC_RAG","http://veze_rag:8014")
    svc_game: str = os.getenv("SVC_GAME","http://veze_game:8008")
    svc_xengine: str = os.getenv("SVC_XENGINE","http://veze_xengine:8006")
    svc_sports: str = os.getenv("SVC_SPORTS","http://veze_sports:8009")
    svc_social: str = os.getenv("SVC_SOCIAL","http://veze_social:8007")
settings = Settings()
```

---

## app/db/models.py

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, ForeignKey, JSON, DateTime, Text
from datetime import datetime

class Base(DeclarativeBase): ...

class Session(Base):
    __tablename__="sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    kind: Mapped[str] = mapped_column(String(24))  # helm|support|player
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Message(Base):
    __tablename__="messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    role: Mapped[str] = mapped_column(String(8))   # user|assistant|system
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ToolCall(Base):
    __tablename__="tool_calls"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    tool: Mapped[str] = mapped_column(String(64))
    args: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class PlanStep(Base):
    __tablename__="plan_steps"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    step_no: Mapped[int]
    desc: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(16), default="pending")  # pending|done|failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

---

## app/db/database.py & deps.py

```python
# database.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
def session_maker(db_url:str):
    engine = create_async_engine(db_url, future=True, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

```python
# deps.py
from app.settings import settings
from app.db.database import session_maker
import redis.asyncio as redis

def get_session():
    return session_maker(settings.db_url)()

def get_redis():
    return redis.from_url(settings.redis_url)
```

---

## app/core/schema.py

```python
from pydantic import BaseModel
from typing import List, Dict, Optional

class ChatTurn(BaseModel):
    session_id: Optional[int] = None
    user_id: int
    mode: str = "support"  # helm|support|player
    message: str

class ChatChunk(BaseModel):
    type: str
    data: Dict
```

---

## app/core/policy.py (minimal guardrails)

```python
def sanitize_user_text(text:str)->str:
    return text.strip()[:4000]

BLOCKLIST = ["credit card", "password", "seed phrase"]

def policy_check(text:str)->bool:
    t = text.lower()
    return not any(b in t for b in BLOCKLIST)
```

---

## app/tools/utils.py & bus.py

```python
# utils.py
import httpx
async def post_json(url:str, json:dict, timeout:int=20):
    async with httpx.AsyncClient(timeout=timeout) as c:
        r = await c.post(url, json=json)
        r.raise_for_status()
        return r.json()
async def get_json(url:str, timeout:int=20):
    async with httpx.AsyncClient(timeout=timeout) as c:
        r = await c.get(url)
        r.raise_for_status()
        return r.json()
```

```python
# bus.py
import json, redis.asyncio as redis
class Bus:
    def __init__(self, r:redis.Redis): self.r = r
    async def emit(self, evt:str, payload:dict):
        await self.r.xadd("veze.copilot", {"event": evt, "payload": json.dumps(payload)})
```

---

## app/tools/adapters (examples)

**email.py**

```python
from app.settings import settings
from app.tools.utils import post_json

async def send_email(to:str, subject:str, body:str):
    # assume VEZEPyEmail exposes a simple send endpoint or JMAP adapter
    return {"queued": True, "to": to, "subject": subject}
```

**commerce.py**

```python
from app.tools.utils import get_json, post_json
from app.settings import settings

async def list_products():
    return await get_json(f"{settings.svc_commerce}/catalog")

async def checkout(cart_id:int, handle:str|None=None):
    return await post_json(f"{settings.svc_commerce}/checkout/{cart_id}", {"user_handle": handle or ""})
```

**rag.py**

```python
from app.tools.utils import get_json
from app.settings import settings
async def ask(q:str):
    return await get_json(f"{settings.svc_rag}/ask?q={q}")
```

**xengine.py**

```python
from app.tools.utils import post_json
from app.settings import settings
async def npc_response(context:str, query:str):
    return await post_json(f"{settings.svc_xengine}/npc_response", {"context": context, "query": query})
```

**game.py**

```python
from app.tools.utils import post_json
from app.settings import settings
async def plan_boss_strategy(player_handle:str, boss:str):
    return await post_json(f"{settings.svc_xengine}/boss_adapt_strategy",
                           {"player_username": player_handle, "boss_type": boss})
```

---

## app/core/agents.py (router + specialists)

```python
from typing import Dict, Any
from app.tools import rag, commerce, email, xengine, game

class HelmAgent:
    async def handle(self, text:str) -> Dict[str,Any]:
        if "store" in text or "buy" in text:
            products = await commerce.list_products()
            return {"kind":"nav","to":"VEZEPyCommerce","data":products}
        if "knowledge" in text or "docs" in text:
            res = await rag.ask("what docs are available?")
            return {"kind":"nav","to":"VEZEPyRAG","data":res}
        return {"kind":"nav","to":"Helm","data":{"tip":"Say 'store', 'docs', 'email'..."}}

class SupportAgent:
    async def handle(self, text:str) -> Dict[str,Any]:
        if "refund" in text or "order" in text:
            return {"kind":"support","topic":"commerce","steps":["Locate order","Authorize refund","Send receipt"]}
        if "email" in text or "invite" in text:
            ok = await email.send_email("support@veze", "Ticket", text)
            return {"kind":"support","topic":"email","queued":ok}
        answer = await rag.ask(text)
        return {"kind":"answer","data":answer}

class GameAgent:
    async def handle(self, text:str) -> Dict[str,Any]:
        if "strategy" in text or "boss" in text:
            strat = await game.plan_boss_strategy("pilot_handle", "DinoBoss")
            return {"kind":"plan","data":strat}
        resp = await xengine.npc_response(f"Game context: {text}", text[:50])
        return {"kind":"npc","data":resp}
```

---

## app/core/planner.py (simple task planner)

```python
from typing import List, Dict

def plan_steps(goal:str) -> List[Dict]:
    steps=[]
    if "buy" in goal or "purchase" in goal:
        steps = [{"do":"catalog.list"},{"do":"cart.create"},{"do":"cart.add"},{"do":"checkout"}]
    elif "email" in goal:
        steps = [{"do":"email.compose"},{"do":"email.send"}]
    elif "boss" in goal or "strategy" in goal:
        steps = [{"do":"game.analyze"},{"do":"game.plan"},{"do":"game.execute"}]
    else:
        steps = [{"do":"rag.search"},{"do":"summarize"}]
    for i,s in enumerate(steps): s["step"]=i+1
    return steps
```

---

## app/core/memory.py

```python
import json
from app.deps import get_redis
from datetime import timedelta

class ShortMemory:
    def __init__(self, r): self.r=r
    async def append(self, session_id:int, role:str, content:str):
        key=f"copilot:hist:{session_id}"
        await self.r.rpush(key, json.dumps({"role":role,"content":content}))
        await self.r.expire(key, int(timedelta(days=1).total_seconds()))
    async def get(self, session_id:int, n:int=10):
        key=f"copilot:hist:{session_id}"
        vals = await self.r.lrange(key, -n, -1)
        return [json.loads(v) for v in vals]
```

---

## app/core/orchestrator.py

```python
from typing import Dict, Any
from app.core.agents import HelmAgent, SupportAgent, GameAgent
from app.core.policy import sanitize_user_text, policy_check
from app.core.planner import plan_steps

class Orchestrator:
    def __init__(self):
        self.helm = HelmAgent(); self.support = SupportAgent(); self.game = GameAgent()

    async def route(self, mode:str, text:str) -> Dict[str,Any]:
        text = sanitize_user_text(text)
        if not policy_check(text): return {"kind":"error","msg":"Request blocked by policy"}
        if mode == "helm": return await self.helm.handle(text)
        if mode == "player": return await self.game.handle(text)
        return await self.support.handle(text)

    async def plan(self, goal:str):
        return {"plan": plan_steps(goal)}
```

---

## app/routers/chat.py (REST, SSE, WS)

```python
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from app.core.orchestrator import Orchestrator
from app.core.schema import ChatTurn
from app.deps import get_redis
from app.tools.bus import Bus
import asyncio, json

router = APIRouter()
orc = Orchestrator()

@router.post("/chat")
async def chat(turn: ChatTurn, r=Depends(get_redis)):
    bus = Bus(r)
    res = await orc.route(turn.mode, turn.message)
    await bus.emit("copilot.task.executed", {"mode": turn.mode, "res_kind": res.get("kind")})
    return {"reply": res}

@router.get("/chat/stream")
async def chat_stream(request: Request, mode:str, q:str, r=Depends(get_redis)):
    async def eventgen():
        bus = Bus(r)
        yield {"event":"start","data": json.dumps({"mode":mode})}
        res = await orc.route(mode, q)
        await bus.emit("copilot.task.executed", {"mode":mode,"stream":True})
        yield {"event":"chunk","data": json.dumps(res)}
        yield {"event":"end","data": "{}"}
    return EventSourceResponse(eventgen())

@router.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            res = await orc.route(payload.get("mode","support"), payload.get("message",""))
            await websocket.send_text(json.dumps({"reply":res}))
    except Exception:
        await websocket.close()
```

---

## app/routers/pages.py (UI)

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return request.app.state.tpl.TemplateResponse("index.html", {"request": request})

@router.get("/chat", response_class=HTMLResponse)
async def chat(request: Request):
    return request.app.state.tpl.TemplateResponse("chat.html", {"request": request})

@router.get("/tools", response_class=HTMLResponse)
async def tools(request: Request):
    return request.app.state.tpl.TemplateResponse("tools.html", {"request": request})
```

---

## app/routers/discovery.py / health.py

```python
# discovery.py
from fastapi import APIRouter
router = APIRouter()
@router.get("/.veze/service.json")
async def svc():
    return {
      "name":"VEZEPyCopilotVe1","category":"copilot","status":"green",
      "routes":[{"label":"Copilot","href":"/chat"},{"label":"Tools","href":"/tools"}],
      "scopes":["copilot.read","copilot.exec"],
      "events":["copilot.task.created","copilot.action.executed","copilot.game.plan"]
    }
```

```python
# health.py
from fastapi import APIRouter
router = APIRouter()
@router.get("/health") async def health(): return {"status":"ok"}
```

---

## app/ui/templates (minimal dark UI)

`base.html`

```html
<!doctype html><html><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>VEZEPyCopilotVe1</title>
<style>
body{font-family:system-ui;background:#0b0f18;color:#e6edf3;margin:0}
header,footer{padding:12px 20px;background:#0d1117;border-bottom:1px solid #1f2937}
.grid{display:grid;gap:12px;padding:20px}.card{background:#0d1117;border:1px solid #1f2937;padding:16px;border-radius:12px}
input,button,textarea{background:#0d1117;color:#e6edf3;border:1px solid #1f2937;border-radius:8px;padding:8px}
.btn{padding:8px 12px;background:#1f6feb;color:#fff;border-radius:8px}
a{color:#58a6ff;text-decoration:none}
</style></head><body>
<header><b>VEZEPyCopilotVe1</b> — <a href="/">Home</a> · <a href="/chat">Chat</a> · <a href="/tools">Tools</a></header>
<main class="grid">{% block content %}{% endblock %}</main>
<footer>© VEZE UniQVerse</footer>
</body></html>
```

`index.html`

```html
{% extends "base.html" %}{% block content %}
<div class="card">
  <h2>Copilot for VEZE Helm • Support • Player ASI</h2>
  <p>Ask for navigation, support, or game strategy. Example: “buy nebula skin”, “refund order 123”, “boss strategy”.</p>
</div>
{% endblock %}
```

`chat.html`

```html
{% extends "base.html" %}{% block content %}
<div class="card">
  <h3>Chat</h3>
  <select id="mode">
    <option value="support">Support</option>
    <option value="helm">Helm</option>
    <option value="player">Player ASI</option>
  </select>
  <input id="q" placeholder="Type your request"/><button class="btn" onclick="go()">Send</button>
  <pre id="out" style="white-space:pre-wrap;margin-top:12px;"></pre>
  <button class="btn" onclick="stream()">Stream (SSE)</button>
</div>
<script>
async function go(){
  const mode=document.getElementById('mode').value, q=document.getElementById('q').value;
  const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({user_id:1,mode,message:q})});
  const d=await r.json(); document.getElementById('out').textContent=JSON.stringify(d,null,2);
}
function stream(){
  const mode=document.getElementById('mode').value, q=document.getElementById('q').value;
  const es=new EventSource('/chat/stream?mode='+mode+'&q='+encodeURIComponent(q));
  const out=document.getElementById('out'); out.textContent="";
  es.onmessage=(e)=>{ out.textContent+=e.data+"\n"; };
  es.addEventListener('chunk',(e)=>{ out.textContent+="\nCHUNK: "+e.data; });
  es.addEventListener('end',()=>{ es.close(); });
}
</script>
{% endblock %}
```

`tools.html`

```html
{% extends "base.html" %}{% block content %}
<div class="card"><h3>Connected Services</h3>
<ul>
  <li>VEZEPyCommerce — Catalog, Checkout</li>
  <li>VEZEPyRAG — Search/Ask with citations</li>
  <li>VEZEPyEmail — Send/Receive</li>
  <li>VEZEPyXEngine — Generative/NPC/Trends</li>
  <li>VEZEPyGame — Player ASI hooks</li>
</ul>
</div>
{% endblock %}
```

---

## app/main.py

```python
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from app.routers import pages, chat, actions, discovery, health

app = FastAPI(title="VEZEPyCopilotVe1")
app.state.tpl = Jinja2Templates(directory="app/ui/templates")

app.include_router(pages.router, tags=["ui"])
app.include_router(chat.router, tags=["chat"])
app.include_router(discovery.router, tags=["discovery"])
app.include_router(health.router, tags=["health"])

app.mount("/static", StaticFiles(directory="app/ui/templates"), name="static")
Instrumentator().instrument(app).expose(app)
```

*(If you don’t need `/actions.py` proxy, omit it.)*

---

## Dockerfile

```dockerfile
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml .
RUN pip install --upgrade pip && pip install -e .
COPY . .
EXPOSE 8016
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8016"]
```

---

## CI

```yaml
name: CI
on: [push, pull_request]
jobs:
  build-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -e .[dev]
      - run: ruff check .
      - run: black --check .
      - run: mypy .
      - run: pytest -q
```

---

## tests

```python
# tests/test_health.py
from fastapi.testclient import TestClient
from app.main import app
def test_health():
    c = TestClient(app)
    assert c.get("/health").json()["status"]=="ok"
```

```python
# tests/test_router_smoke.py
from fastapi.testclient import TestClient
from app.main import app

def test_chat_support_route():
    c = TestClient(app)
    r = c.post("/chat", json={"user_id":1,"mode":"support","message":"refund help"})
    assert r.status_code == 200
```

---

## README.md (quickstart)

````markdown
# VEZEPyCopilotVe1

Hardcore ASI Copilot for VEZE UniQVerse:
- Helm Copilot (navigation & cross-service actions)
- Support bot (triage + tools)
- Player ASI (game strategies & NPC/ally behaviors)

## Run
```bash
cp .env.example .env
pip install -e .[dev]
uvicorn app.main:app --reload --port 8016
````

UI: `http://localhost:8016/chat` • SSE: `/chat/stream` • WS: `/ws` • Metrics: `/metrics` • Discovery: `/.veze/service.json`

## Configure service URLs

Set `SVC_*` vars to the deployed VEZE services (Email/Commerce/RAG/Game/XEngine/etc).

```

---

## How it works

1) **Router → Agents**  
`/chat` sends the prompt to **Orchestrator.route(mode, text)** → routes to **HelmAgent**, **SupportAgent**, or **GameAgent**.

2) **Agents → Tools**  
Agents call tool adapters (**RAG**, **Commerce**, **Email**, **XEngine**, **Game**) via HTTP.

3) **Planning**  
`/chat?mode=player&message="boss strategy…”` uses **GameAgent** + **XEngine** for adaptive plans.  
`/chat?mode=helm&message="buy nebula skin"` uses **HelmAgent** → **Commerce** list/checkout flow.

4) **Streaming**  
**SSE** endpoint emits `start → chunk → end`. **WS** supports bidirectional chat.

5) **Memory & Telemetry**  
Short-term chat memory in Redis (24h TTL). Events on Redis Streams `veze.copilot`. Prometheus metrics auto-exposed.

---

## Helm integration

- Tile: **“VEZEPyCopilotVe1 — Copilot”**  
- Discovery: `GET /.veze/service.json`  
- Common proxy paths:
  - `/proxy/copilot/chat` → `http://veze_copilot:8016/chat`
  - `/proxy/copilot/chat/stream` → `http://veze_copilot:8016/chat/stream`

---
```
