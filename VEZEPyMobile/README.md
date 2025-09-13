# 📱 VEZEPyMobile — Standalone Mobile Runtime for VEZE UniQVerse

* ✅ eSIM activation with **VEZEPyESim** (default operator: **VEZEPyVez**)
* ✅ Mobile **line identity** (MSISDN/ICCID/QoS/Balance)
* ✅ **Voice & Video calls** (WebRTC **signaling** over WebSockets; media P2P)
* ✅ **Mobile Messages** (1:1 / thread via WS)
* ✅ **Launcher UI** for VEZEPy Chat/Email/Sports/Commerce/Social/Copilot/Cabs/Garage/Player/Meta/BMVe
* ✅ **Prometheus metrics**, **Helm discovery**, **Docker**, **CI**, **Postgres/SQLite** (dev)

---

## 1) Repository layout

```
VEZEPyMobile/
├─ README.md
├─ .env.example
├─ pyproject.toml
├─ Dockerfile
├─ .github/workflows/ci.yml
└─ app/
   ├─ main.py
   ├─ settings.py
   ├─ deps.py
   ├─ db/
   │  ├─ database.py
   │  └─ models.py
   ├─ core/
   │  ├─ esim.py
   │  ├─ signaling.py
   │  └─ messages.py
   ├─ routers/
   │  ├─ discovery.py
   │  ├─ health.py
   │  ├─ mobile.py
   │  ├─ calls.py
   │  ├─ sms.py
   │  ├─ apps.py
   │  └─ ui.py
   └─ ui/templates/
      ├─ base.html
      ├─ home.html
      ├─ dialer.html
      ├─ video.html
      └─ chat.html
```

---

## 2) `.env.example`

```env
ENV=dev
PORT=8030
# DB: use SQLite for dev, switch to Postgres in prod
DATABASE_URL=sqlite+aiosqlite:///./veze_mobile.db
# DATABASE_URL=postgresql+asyncpg://veze:veze@localhost:5432/veze_mobile

REDIS_URL=redis://localhost:6379/10

# peer services (only ESIM is required)
SVC_ESIM=http://localhost:8021

# Default operator
DEFAULT_OPERATOR_CODE=VEZEPyVez

# Optional tiles (leave as-is if not running yet)
SVC_CHAT=http://localhost:8003
SVC_EMAIL=http://localhost:8005
SVC_SPORTS=http://localhost:8009
SVC_COMMERCE=http://localhost:8012
SVC_SOCIAL=http://localhost:8007
SVC_COPILOT=http://localhost:8016
SVC_CABS=http://localhost:8026
SVC_GARAGE=http://localhost:8027
SVC_PLAYER=http://localhost:8028
SVC_META=http://localhost:8029
SVC_BMVE=http://localhost:8031
```

---

## 3) `pyproject.toml`

```toml
[project]
name = "veze-mobile"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "jinja2>=3.1",
  "pydantic>=2.8",
  "SQLAlchemy>=2.0",
  "aiosqlite>=0.20",
  "asyncpg>=0.29",        # only if you point to Postgres
  "redis>=5.0",
  "httpx>=0.27",
  "prometheus-fastapi-instrumentator>=7.0.0",
  "sse-starlette>=2.0.0",
  "python-multipart>=0.0.9",
  "itsdangerous>=2.2"
]
[project.optional-dependencies]
dev = ["pytest>=8.3","pytest-asyncio>=0.23","ruff>=0.5","black>=24.8","mypy>=1.11"]
```

---

## 4) `app/settings.py`

```python
import os
from pydantic import BaseModel

class Settings(BaseModel):
    env: str = os.getenv("ENV","dev")
    port: int = int(os.getenv("PORT","8030"))
    db_url: str = os.getenv("DATABASE_URL","sqlite+aiosqlite:///./veze_mobile.db")
    redis_url: str = os.getenv("REDIS_URL","redis://localhost:6379/10")
    svc_esim: str = os.getenv("SVC_ESIM","http://localhost:8021")
    default_operator_code: str = os.getenv("DEFAULT_OPERATOR_CODE","VEZEPyVez")
    # tiles (optional)
    svc_chat: str = os.getenv("SVC_CHAT","http://localhost:8003")
    svc_email: str = os.getenv("SVC_EMAIL","http://localhost:8005")
    svc_sports: str = os.getenv("SVC_SPORTS","http://localhost:8009")
    svc_commerce: str = os.getenv("SVC_COMMERCE","http://localhost:8012")
    svc_social: str = os.getenv("SVC_SOCIAL","http://localhost:8007")
    svc_copilot: str = os.getenv("SVC_COPILOT","http://localhost:8016")
    svc_cabs: str = os.getenv("SVC_CABS","http://localhost:8026")
    svc_garage: str = os.getenv("SVC_GARAGE","http://localhost:8027")
    svc_player: str = os.getenv("SVC_PLAYER","http://localhost:8028")
    svc_meta: str = os.getenv("SVC_META","http://localhost:8029")
    svc_bmve: str = os.getenv("SVC_BMVE","http://localhost:8031")

settings = Settings()
```

---

## 5) `app/db/database.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

def session_maker(db_url: str):
    engine = create_async_engine(db_url, future=True, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine
```

## 6) `app/db/models.py`

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, JSON, Text
from datetime import datetime

class Base(DeclarativeBase): ...

class MobileLine(Base):
    __tablename__="mobile_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64))              # logical owner/device ref
    eid: Mapped[str] = mapped_column(String(64))                    # eSIM EID
    msisdn: Mapped[str] = mapped_column(String(24), unique=True)    # UniQVerse number
    iccid: Mapped[str] = mapped_column(String(32))                  # active profile
    operator_code: Mapped[str] = mapped_column(String(32))
    qos_tier: Mapped[str] = mapped_column(String(16), default="standard")
    balance: Mapped[int] = mapped_column(Integer, default=100)
    state: Mapped[str] = mapped_column(String(16), default="active")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class CallRoom(Base):
    __tablename__="call_rooms"
    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[str] = mapped_column(String(48), unique=True)
    host_msisdn: Mapped[str] = mapped_column(String(24))
    callee_msisdn: Mapped[str] = mapped_column(String(24))
    kind: Mapped[str] = mapped_column(String(8), default="voice")   # voice|video
    state: Mapped[str] = mapped_column(String(16), default="ringing")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Message(Base):
    __tablename__="messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[str] = mapped_column(String(48))
    sender_msisdn: Mapped[str] = mapped_column(String(24))
    recipient_msisdn: Mapped[str] = mapped_column(String(24))
    text: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

---

## 7) `app/deps.py`

```python
from app.settings import settings
from app.db.database import session_maker
import redis.asyncio as redis
import httpx

SessionMaker, Engine = session_maker(settings.db_url)

async def get_session():
    async with SessionMaker() as s:
        yield s

def get_bus():
    return redis.from_url(settings.redis_url)

def get_http():
    return httpx.AsyncClient(timeout=20)
```

---

## 8) Core helpers

### `app/core/esim.py`

```python
import httpx
from app.settings import settings

async def attach_enable_profile(eid: str, operator_code: str | None = None) -> dict:
    op = operator_code or settings.default_operator_code
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{settings.svc_esim}/profiles/issue", params={"eid": eid, "operator_code": op})
        r.raise_for_status()
        iccid = r.json()["iccid"]
        e = await c.post(f"{settings.svc_esim}/profiles/{iccid}/enable")
        e.raise_for_status()
        return {"iccid": iccid, "operator": op, "state": "enabled"}
```

### `app/core/signaling.py`

```python
import json
from typing import Dict, Set
from starlette.websockets import WebSocket

class CallHub:
    def __init__(self):
        self.rooms: Dict[str, Set[WebSocket]] = {}

    async def join(self, room_id: str, ws: WebSocket):
        await ws.accept()
        self.rooms.setdefault(room_id, set()).add(ws)

    async def leave(self, room_id: str, ws: WebSocket):
        try: self.rooms.get(room_id, set()).discard(ws)
        except: pass

    async def broadcast(self, room_id: str, payload: dict, sender: WebSocket | None = None):
        for peer in list(self.rooms.get(room_id, set())):
            if peer is not sender:
                await peer.send_text(json.dumps(payload))

hub = CallHub()
```

### `app/core/messages.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Message
from datetime import datetime

async def persist_message(session: AsyncSession, thread_id: str, sender: str, recipient: str, text: str):
    m = Message(thread_id=thread_id, sender_msisdn=sender, recipient_msisdn=recipient, text=text, meta={}, sent_at=datetime.utcnow())
    session.add(m); await session.commit()
    return m.id
```

---

## 9) Routers

### `app/routers/discovery.py`

```python
from fastapi import APIRouter
router = APIRouter()

@router.get("/.veze/service.json")
async def svc():
    return {
      "name":"VEZEPyMobile","category":"mobile","status":"green",
      "routes":[
        {"label":"Home","href":"/ui/home"},
        {"label":"Dialer","href":"/ui/dialer"},
        {"label":"Messages","href":"/ui/chat"}
      ],
      "events":["mobile.activated","call.created","msg.sent"]
    }
```

### `app/routers/health.py`

```python
from fastapi import APIRouter
router = APIRouter()

@router.get("/health")
async def health(): return {"status":"ok"}
```

### `app/routers/mobile.py`  (activation & line info)

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.deps import get_session, get_bus
from app.core.esim import attach_enable_profile
from app.db.models import MobileLine

router = APIRouter()

@router.post("/mobile/activate")
async def activate_line(device_id: str, eid: str, msisdn: str, session: AsyncSession = Depends(get_session), bus=Depends(get_bus)):
    # ensure unique msisdn
    exists = (await session.execute(select(MobileLine).where(MobileLine.msisdn == msisdn))).scalar_one_or_none()
    if exists: raise HTTPException(400, "MSISDN already active")
    prof = await attach_enable_profile(eid)
    line = MobileLine(device_id=device_id, eid=eid, msisdn=msisdn, iccid=prof["iccid"], operator_code=prof["operator"], balance=100)
    session.add(line); await session.commit()
    await bus.xadd("veze.mobile", {"type":"mobile.activated","msisdn":msisdn,"iccid":prof["iccid"]})
    return {"msisdn": msisdn, "iccid": prof["iccid"], "operator": prof["operator"], "state": prof["state"], "balance": 100}

@router.get("/mobile/line/{msisdn}")
async def get_line(msisdn: str, session: AsyncSession = Depends(get_session)):
    row = (await session.execute(select(MobileLine).where(MobileLine.msisdn == msisdn))).scalar_one_or_none()
    if not row: raise HTTPException(404, "not found")
    return {"msisdn": row.msisdn, "iccid": row.iccid, "operator": row.operator_code, "qos": row.qos_tier, "state": row.state, "balance": row.balance}
```

### `app/routers/calls.py` (create + WS signaling)

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.deps import get_session, get_bus
from app.db.models import CallRoom
from app.core.signaling import hub
import uuid, json

router = APIRouter()

@router.post("/calls/create")
async def create_call(host_msisdn: str, callee_msisdn: str, kind: str = "voice", session: AsyncSession = Depends(get_session), bus=Depends(get_bus)):
    room_id = uuid.uuid4().hex[:12]
    r = CallRoom(room_id=room_id, host_msisdn=host_msisdn, callee_msisdn=callee_msisdn, kind=kind, state="ringing")
    session.add(r); await session.commit()
    await bus.xadd("veze.mobile", {"type":"call.created","room":room_id,"kind":kind})
    return {"room_id": room_id, "kind": kind}

@router.websocket("/ws/call/{room_id}")
async def ws_call(ws: WebSocket, room_id: str):
    await hub.join(room_id, ws)
    try:
        while True:
            msg = await ws.receive_text()
            # Accept raw JSON (SDP/ICE) and relay
            payload = json.loads(msg)
            await hub.broadcast(room_id, payload, sender=ws)
    except WebSocketDisconnect:
        await hub.leave(room_id, ws)
```

### `app/routers/sms.py` (messages + WS threads)

```python
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from app.deps import get_session, get_bus
from app.core.messages import persist_message
from app.core.signaling import hub
import json

router = APIRouter()

@router.post("/messages/send")
async def send_message(thread_id: str, sender_msisdn: str, recipient_msisdn: str, text: str, session: AsyncSession = Depends(get_session), bus=Depends(get_bus)):
    mid = await persist_message(session, thread_id, sender_msisdn, recipient_msisdn, text)
    await hub.broadcast(f"msg:{thread_id}", {"type": "message", "thread": thread_id, "from": sender_msisdn, "text": text})
    await bus.xadd("veze.mobile", {"type":"msg.sent","thread":thread_id,"sender":sender_msisdn})
    return {"id": mid, "status": "sent"}

@router.websocket("/ws/messages/{thread_id}")
async def ws_messages(ws: WebSocket, thread_id: str):
    room = f"msg:{thread_id}"
    await hub.join(room, ws)
    try:
        while True:
            raw = await ws.receive_text()
            # relay typing/read receipts if clients send them
            try: payload = json.loads(raw)
            except: payload = {"type":"relay","raw":raw}
            await hub.broadcast(room, payload, sender=ws)
    except WebSocketDisconnect:
        await hub.leave(room, ws)
```

### `app/routers/apps.py` (launcher tiles)

```python
from fastapi import APIRouter
from app.settings import settings

router = APIRouter()

@router.get("/apps")
async def list_apps():
    return [
      {"code":"chat","title":"VEZEPyChat","url":settings.svc_chat},
      {"code":"email","title":"VEZEPyEmail","url":settings.svc_email},
      {"code":"sports","title":"VEZEPySports","url":settings.svc_sports},
      {"code":"commerce","title":"VEZEPyECommerce","url":settings.svc_commerce},
      {"code":"social","title":"VEZEPySocial","url":settings.svc_social},
      {"code":"copilot","title":"VEZEPyCopilotVe1","url":settings.svc_copilot},
      {"code":"cabs","title":"VEZEPyCabs","url":settings.svc_cabs},
      {"code":"garage","title":"VEZEPyGarage","url":settings.svc_garage},
      {"code":"player","title":"VEZEPyPlayer","url":settings.svc_player},
      {"code":"meta","title":"VEZEPyUniQVerseMeta","url":settings.svc_meta},
      {"code":"bmve","title":"VEZEPyBMVe","url":settings.svc_bmve},
    ]
```

### `app/routers/ui.py` (server-rendered minimal mobile UI)

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.main import templates

router = APIRouter()

@router.get("/ui/home", response_class=HTMLResponse)
async def home(req: Request):
    return templates.TemplateResponse("home.html", {"request": req})

@router.get("/ui/dialer", response_class=HTMLResponse)
async def dialer(req: Request):
    return templates.TemplateResponse("dialer.html", {"request": req})

@router.get("/ui/video", response_class=HTMLResponse)
async def video(req: Request, room: str | None = None):
    return templates.TemplateResponse("video.html", {"request": req, "room": room or ""})

@router.get("/ui/chat", response_class=HTMLResponse)
async def chat(req: Request, thread: str | None = None):
    return templates.TemplateResponse("chat.html", {"request": req, "thread": thread or "t-demo"})
```

---

## 10) UI templates (minimal; copy into `app/ui/templates/`)

### `base.html`

```html
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>VEZEPyMobile</title>
  <style>
    body { background:#0b0f14; color:#d1e1ff; font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto; }
    .wrap { max-width:980px; margin:0 auto; padding:24px; }
    .btn { background:#1a2230; border:1px solid #2a3650; padding:10px 14px; border-radius:10px; color:#cfe3ff; cursor:pointer; }
    .grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(160px,1fr)); gap:16px; }
    .tile { background:#101826; border:1px solid #223050; border-radius:14px; padding:14px; }
    input,select { background:#0a1220; border:1px solid #223050; color:#cfe3ff; padding:8px; border-radius:8px; width:100%; }
    a { color:#7fb1ff; text-decoration:none; }
    .row { display:flex; gap:8px; align-items:center; }
  </style>
</head>
<body><div class="wrap">
  {% block body %}{% endblock %}
</div></body>
</html>
```

### `home.html`

```html
{% extends "base.html" %}
{% block body %}
<h2>📱 VEZEPyMobile — Launcher</h2>
<p>Quick links to VEZE services (set URLs in .env):</p>
<div class="grid" id="apps"></div>
<script>
async function loadApps(){
  const res = await fetch('/apps'); const data = await res.json();
  const grid = document.getElementById('apps');
  data.forEach(a=>{
    const d = document.createElement('div'); d.className='tile';
    d.innerHTML = `<h3>${a.title}</h3><p><a href="${a.url}" target="_blank">${a.url}</a></p>`;
    grid.appendChild(d);
  });
}
loadApps();
</script>
{% endblock %}
```

### `dialer.html`

```html
{% extends "base.html" %}
{% block body %}
<h2>📞 Dialer</h2>
<div class="tile">
  <div class="row">
    <input id="host" placeholder="Your MSISDN (e.g., +99001142)"/>
    <input id="callee" placeholder="Callee MSISDN (e.g., +99001177)"/>
    <select id="kind"><option>voice</option><option selected>video</option></select>
    <button class="btn" onclick="createCall()">Create</button>
  </div>
  <p id="info"></p>
</div>
<script>
async function createCall(){
  const host = document.getElementById('host').value;
  const callee = document.getElementById('callee').value;
  const kind = document.getElementById('kind').value;
  const r = await fetch('/calls/create',{method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({host_msisdn:host, callee_msisdn:callee, kind})});
  const j = await r.json(); document.getElementById('info').innerHTML = `Room: <b>${j.room_id}</b> → <a href="/ui/video?room=${j.room_id}">Open Video</a>`;
}
</script>
{% endblock %}
```

### `video.html` (basic two-party WebRTC; signaling via WS)

```html
{% extends "base.html" %}
{% block body %}
<h2>🎥 Video Call</h2>
<p>Room: <b id="roomId">{{ room }}</b></p>
<div class="row">
  <button class="btn" onclick="start(true)">Start as Caller</button>
  <button class="btn" onclick="start(false)">Start as Callee</button>
</div>
<video id="local" autoplay playsinline muted style="width:45%;border-radius:12px;border:1px solid #223050;"></video>
<video id="remote" autoplay playsinline style="width:45%;border-radius:12px;border:1px solid #223050;"></video>
<script>
let pc, ws, room = "{{ room }}";
async function start(isCaller){
  if(!room){ room = prompt("Room ID?"); document.getElementById('roomId').innerText=room; }
  ws = new WebSocket(`${location.protocol==="https:"?"wss":"ws"}://${location.host}/ws/call/${room}`);
  const stream = await navigator.mediaDevices.getUserMedia({video:true,audio:true});
  document.getElementById('local').srcObject = stream;
  pc = new RTCPeerConnection();
  stream.getTracks().forEach(t=>pc.addTrack(t,stream));
  pc.ontrack = ev => { document.getElementById('remote').srcObject = ev.streams[0]; };
  pc.onicecandidate = ev => { if(ev.candidate) ws.send(JSON.stringify({type:"candidate",candidate:ev.candidate})); };
  ws.onmessage = async (e)=>{
    const m = JSON.parse(e.data);
    if(m.type==="offer"){ await pc.setRemoteDescription(new RTCSessionDescription(m.offer));
      const ans = await pc.createAnswer(); await pc.setLocalDescription(ans);
      ws.send(JSON.stringify({type:"answer",answer:ans})); }
    else if(m.type==="answer"){ await pc.setRemoteDescription(new RTCSessionDescription(m.answer)); }
    else if(m.type==="candidate"){ try{ await pc.addIceCandidate(new RTCIceCandidate(m.candidate)); }catch{} }
  };
  if(isCaller){
    const offer = await pc.createOffer(); await pc.setLocalDescription(offer);
    ws.onopen = ()=> ws.send(JSON.stringify({type:"offer",offer}));
  }
}
</script>
{% endblock %}
```

### `chat.html` (WS thread)

```html
{% extends "base.html" %}
{% block body %}
<h2>💬 Messages</h2>
<div class="row">
  <input id="thread" value="{{ thread }}" placeholder="thread id (e.g., t-demo)"/>
  <button class="btn" onclick="join()">Join</button>
</div>
<div class="tile" id="log" style="min-height:200px;margin-top:10px;"></div>
<div class="row" style="margin-top:10px;">
  <input id="from" placeholder="from MSISDN"/>
  <input id="to" placeholder="to MSISDN"/>
</div>
<div class="row">
  <input id="txt" placeholder="message text"/>
  <button class="btn" onclick="send()">Send</button>
</div>
<script>
let ws, curThread = "{{ thread }}";
function log(s){ const d=document.getElementById('log'); const p=document.createElement('div'); p.innerHTML=s; d.appendChild(p); d.scrollTop=d.scrollHeight; }
function join(){
  if(ws) ws.close();
  curThread = document.getElementById('thread').value || "t-demo";
  ws = new WebSocket(`${location.protocol==="https:"?"wss":"ws"}://${location.host}/ws/messages/${curThread}`);
  ws.onmessage = (e)=>{ const m = JSON.parse(e.data); if(m.type==="message") log(`<b>${m.from}:</b> ${m.text}`); }
  log(`Joined thread ${curThread}`);
}
async function send(){
  const sender = document.getElementById('from').value;
  const recipient = document.getElementById('to').value;
  const text = document.getElementById('txt').value;
  await fetch('/messages/send',{method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({thread_id:curThread, sender_msisdn:sender, recipient_msisdn:recipient, text})});
}
join();
</script>
{% endblock %}
```

---

## 11) `app/main.py`

```python
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from app.routers import discovery, health, mobile, calls, sms, apps, ui
from app.deps import Engine
from app.db.models import Base

app = FastAPI(title="VEZEPyMobile")
templates = Jinja2Templates(directory="app/ui/templates")
app.state.tpl = templates

# Routers
app.include_router(discovery.router, tags=["discovery"])
app.include_router(health.router, tags=["health"])
app.include_router(mobile.router, tags=["mobile"])
app.include_router(calls.router, tags=["calls"])
app.include_router(sms.router, tags=["messages"])
app.include_router(apps.router, tags=["apps"])
app.include_router(ui.router, tags=["ui"])

# Static (reuse template dir for simplicity)
app.mount("/static", StaticFiles(directory="app/ui/templates"), name="static")

# Metrics
Instrumentator().instrument(app).expose(app)

# Auto-create tables (dev convenience)
@app.on_event("startup")
async def on_start():
    async with Engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

---

## 12) `Dockerfile`

```dockerfile
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml .
RUN pip install --upgrade pip && pip install -e .
COPY . .
EXPOSE 8030
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8030"]
```

---

## 13) CI (`.github/workflows/ci.yml`)

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
      - run: python -m compileall app
```

---

## 14) README.md (Quickstart)

```md
# VEZEPyMobile

Standalone Python mobile runtime for VEZE UniQVerse:
- eSIM activation with VEZEPyESim (default operator: **VEZEPyVez**)
- Calls & Video (WebRTC signaling via WS)
- Mobile Messages (WS threads)
- Mobile Launcher UI for VEZEPy services

## Run (dev)
cp .env.example .env
pip install -e .[dev]
uvicorn app.main:app --reload --port 8030

## Required peer
- VEZEPyESim running (default: http://localhost:8021)

## UI
- /ui/home    (launcher)
- /ui/dialer  (create call room)
- /ui/video?room=<roomId> (join call)
- /ui/chat    (threaded messages)

## APIs
- POST /mobile/activate?device_id=D1&eid=EID-1&msisdn=+99001142
- GET  /mobile/line/+99001142
- POST /calls/create {host_msisdn, callee_msisdn, kind:"video"}
- WS   /ws/call/{room_id}
- POST /messages/send {thread_id, sender_msisdn, recipient_msisdn, text}
- WS   /ws/messages/{thread_id}
- GET  /.veze/service.json
- GET  /metrics

## Notes
- SQLite used by default; switch DATABASE_URL to Postgres in .env for prod.
- Media is P2P browser WebRTC; server provides signaling only.
```

---

## 15) Sanity test (end-to-end)

```bash
# 0) Run ESIM service on 8021 (your existing VEZEPyESim)
# 1) Start mobile
uvicorn app.main:app --reload --port 8030

# 2) Activate a line
curl -X POST 'http://localhost:8030/mobile/activate?device_id=D-42&eid=EID-42&msisdn=+99001142'

# 3) Create a call room
curl -X POST 'http://localhost:8030/calls/create' \
  -H 'Content-Type: application/json' \
  -d '{"host_msisdn":"+99001142","callee_msisdn":"+99001177","kind":"video"}'

# 4) Open two browser tabs:
#    - /ui/video?room=<room_id> in tab A
#    - /ui/video?room=<room_id> in tab B
#    Press "Start as Caller" in one, "Start as Callee" in the other → video

# 5) Messaging
#    Open /ui/chat (thread e.g., t-demo) in two tabs, then:
curl -X POST 'http://localhost:8030/messages/send' \
  -H 'Content-Type: application/json' \
  -d '{"thread_id":"t-demo","sender_msisdn":"+99001142","recipient_msisdn":"+99001177","text":"Hello UniQVerse"}'
```

---

### Security & hardening (when you’re ready)

* Add simple Bearer/HMAC auth per API.
* Rate-limit `/calls/*` & `/messages/*` per MSISDN/IP.
* Use TURN servers for NAT traversal in production WebRTC.
* Tokenize MSISDN/ICCID (PII).
* Optional: moderate text via **VEZEPyCopilotVe1** before fan-out.

---
