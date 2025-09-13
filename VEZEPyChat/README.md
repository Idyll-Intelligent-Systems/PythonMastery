# VEZEPyChat — Omnichannel Messaging Hub (Real-time chat + inbox + routing)

**Why this one?** It sits right between **VEZEPyEmail** (asynchronous mail) and **VEZEPyGame** (realtime core). VEZEPyChat gives you: live support, guild/party chat, DM, ticketing, and bot/ASI hooks—all under UniQVerse auth.

---

## 0) What you’ll get

* **FastAPI + Jinja2** web UI (no Node)
* **WebSocket** real-time rooms (party, guild, global, DM)
* **Inbox + Tickets** (async) with assignment & tags
* **Router** (skills-based; queues; SLA)
* **Moderation hooks** (toxicity placeholder; plug XEngine/Grok later)
* **Events** on Redis Streams (chat.message.created, ticket.updated…)
* **Postgres** (users, rooms, messages, tickets)
* **Prometheus/OTEL** metrics, Docker, CI, tests
* **Service discovery** for Helm tiles
* **@vezeuniqverse.com** optional gate for DMs to match your Email policy

---

## 1) Repository layout

```
VEZEPyChat/
├─ pyproject.toml
├─ Dockerfile
├─ .env.example
├─ .github/workflows/ci.yml
├─ app/
│  ├─ main.py
│  ├─ settings.py
│  ├─ deps.py
│  ├─ ui/templates/{base.html,index.html,rooms.html,inbox.html,ticket.html}
│  ├─ routers/
│  │  ├─ pages.py
│  │  ├─ rooms.py          # CRUD rooms, list members
│  │  ├─ messages.py       # REST send/list (non-WS)
│  │  ├─ tickets.py        # create/assign/update
│  │  ├─ ws.py             # /ws/rooms/{room_id}
│  │  ├─ discovery.py      # /.veze/service.json
│  │  └─ health.py
│  ├─ services/
│  │  ├─ bus.py            # Redis Streams helpers
│  │  ├─ moderation.py     # placeholder toxicity guard
│  │  └─ authz.py          # domain gate, roles
│  └─ db/
│     ├─ database.py
│     ├─ models.py
│     └─ migrations/
├─ tests/{test_health.py,test_rooms.py,test_messages.py}
└─ ops/runbook.md
```

---

## 2) pyproject.toml (deps)

```toml
[project]
name = "veze-chat"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115","uvicorn[standard]>=0.30","jinja2>=3.1",
  "pydantic>=2.8","SQLAlchemy>=2.0","asyncpg>=0.29","alembic>=1.13",
  "redis>=5.0","prometheus-fastapi-instrumentator>=7.0.0",
  "opentelemetry-sdk>=1.27.0","opentelemetry-instrumentation-fastapi>=0.48b0",
  "python-multipart>=0.0.9"
]
[project.optional-dependencies]
dev = ["pytest>=8.3","pytest-asyncio>=0.23","ruff>=0.5","black>=24.8","mypy>=1.11"]
```

---

## 3) .env.example

```env
ENV=dev
PORT=8010
DATABASE_URL=postgresql+asyncpg://veze:veze@localhost:5432/veze_chat
REDIS_URL=redis://localhost:6379/4
DOMAIN_GATE=vezeuniqverse.com
```

---

## 4) DB models (SQLAlchemy 2)

```python
# app/db/models.py
from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey, Text, JSON, Boolean, DateTime

class Base(DeclarativeBase): ...

class Room(Base):
    __tablename__="rooms"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    kind: Mapped[str] = mapped_column(String(16))  # global|guild|party|dm|support
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

class Message(Base):
    __tablename__="messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    user_id: Mapped[int]
    handle: Mapped[str] = mapped_column(String(80))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    flags: Mapped[dict] = mapped_column(JSON, default=dict)

class Ticket(Base):
    __tablename__="tickets"
    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(String(200))
    created_by: Mapped[int]
    status: Mapped[str] = mapped_column(String(16), default="open")  # open|assigned|solved
    assignee_id: Mapped[int | None]
    tags: Mapped[list] = mapped_column(JSON, default=list)
    last_msg_at: Mapped[datetime | None]
```

---

## 5) Settings / deps

```python
# app/settings.py
import os
from pydantic import BaseModel
class Settings(BaseModel):
    env: str = os.getenv("ENV","dev")
    port: int = int(os.getenv("PORT","8010"))
    db_url: str = os.getenv("DATABASE_URL","postgresql+asyncpg://veze:veze@localhost:5432/veze_chat")
    redis_url: str = os.getenv("REDIS_URL","redis://localhost:6379/4")
    domain_gate: str = os.getenv("DOMAIN_GATE","vezeuniqverse.com")
settings = Settings()
```

```python
# app/deps.py
from app.settings import settings
from app.db.database import SessionMaker
from app.services.bus import Bus
def get_session(): return SessionMaker(settings.db_url)
def get_bus(): return Bus(settings.redis_url)
```

---

## 6) Redis bus + moderation guard

```python
# app/services/bus.py
import json, redis.asyncio as redis
class Bus:
    def __init__(self, url:str): self.r = redis.from_url(url)
    async def emit(self, stream:str, payload:dict):
        await self.r.xadd(stream, {"payload": json.dumps(payload)})
```

```python
# app/services/moderation.py
BAD = ("kill yourself","slur1","slur2")
def check(text:str) -> dict:
    low = text.lower()
    hit = any(b in low for b in BAD)
    return {"ok": not hit, "labels": ["toxic"] if hit else []}
```

---

## 7) Routers (REST + WS)

### pages (UI)

```python
# app/routers/pages.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
router = APIRouter()
@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return request.app.state.tpl.TemplateResponse("index.html", {"request": request})
```

### rooms & messages

```python
# app/routers/rooms.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.db.database import get_async_session
from app.db.models import Room
router = APIRouter()

@router.post("/rooms")
async def create_room(name:str, kind:str="global", session=Depends(get_async_session)):
    r = Room(name=name, kind=kind)
    session.add(r); await session.commit(); await session.refresh(r)
    return {"id": r.id, "name": r.name, "kind": r.kind}

@router.get("/rooms")
async def list_rooms(session=Depends(get_async_session)):
    rows = (await session.execute(select(Room))).scalars().all()
    return [{"id":r.id,"name":r.name,"kind":r.kind} for r in rows]
```

```python
# app/routers/messages.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.db.database import get_async_session
from app.db.models import Message, Room
from app.services.moderation import check
from app.deps import get_bus
router = APIRouter()

@router.post("/rooms/{room_id}/messages")
async def send_message(room_id:int, user_id:int, handle:str, text:str,
                       session=Depends(get_async_session), bus=Depends(get_bus)):
    room = await session.get(Room, room_id)
    if not room: raise HTTPException(404,"Room not found")
    mod = check(text); 
    if not mod["ok"]: raise HTTPException(422, "Toxic content")
    msg = Message(room_id=room_id, user_id=user_id, handle=handle, text=text)
    session.add(msg); await session.commit(); await session.refresh(msg)
    await bus.emit("veze.chat", {"type":"chat.message.created","room_id":room_id,"message_id":msg.id,
                                 "user_id":user_id,"handle":handle,"text":text})
    return {"id": msg.id}
```

### tickets

```python
# app/routers/tickets.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from datetime import datetime
from app.db.database import get_async_session
from app.db.models import Ticket
from app.deps import get_bus
router = APIRouter()

@router.post("/tickets")
async def create_ticket(subject:str, created_by:int, session=Depends(get_async_session), bus=Depends(get_bus)):
    t = Ticket(subject=subject, created_by=created_by, status="open", last_msg_at=datetime.utcnow())
    session.add(t); await session.commit(); await session.refresh(t)
    await bus.emit("veze.chat", {"type":"ticket.created","ticket_id":t.id,"subject":subject,"created_by":created_by})
    return {"id": t.id, "status": t.status}

@router.post("/tickets/{ticket_id}/assign")
async def assign_ticket(ticket_id:int, assignee_id:int, session=Depends(get_async_session), bus=Depends(get_bus)):
    t = await session.get(Ticket, ticket_id); 
    if not t: raise HTTPException(404,"Ticket not found")
    t.assignee_id = assignee_id; t.status = "assigned"; await session.commit()
    await bus.emit("veze.chat", {"type":"ticket.assigned","ticket_id":t.id,"assignee_id":assignee_id})
    return {"ok": True}
```

### WebSocket room

```python
# app/routers/ws.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as redis, os, json
router = APIRouter()
r = redis.from_url(os.getenv("REDIS_URL","redis://localhost:6379/4"))

@router.websocket("/ws/rooms/{room_id}")
async def room_ws(ws: WebSocket, room_id: int):
    await ws.accept()
    stream, group = "veze.chat", f"room-{room_id}"
    try: await r.xgroup_create(stream, group, id="$", mkstream=True)
    except Exception: pass
    try:
        while True:
            xs = await r.xreadgroup(group, "c1", {stream: ">"}, count=50, block=3000)
            for _, msgs in xs or []:
                for mid, data in msgs:
                    ev = json.loads(data["payload"])
                    if ev.get("room_id")==room_id and ev.get("type")=="chat.message.created":
                        await ws.send_json(ev)
                    await r.xack(stream, group, mid)
    except WebSocketDisconnect:
        return
```

### discovery & health

```python
# app/routers/discovery.py
from fastapi import APIRouter
router = APIRouter()
@router.get("/.veze/service.json")
async def svc():
    return {
      "name":"VEZEPyChat",
      "category":"communication",
      "status":"green",
      "routes":[{"label":"Chat Rooms","href":"/rooms"},{"label":"Inbox","href":"/inbox"}],
      "scopes":["chat.read","chat.write","ticket.manage"],
      "events":["chat.message.created","ticket.created","ticket.assigned"]
    }
```

---

## 8) Main app & metrics

```python
# app/main.py
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from app.routers import pages, rooms, messages, tickets, ws, discovery
app = FastAPI(title="VEZEPyChat")
app.state.tpl = Jinja2Templates(directory="app/ui/templates")
app.include_router(pages.router, tags=["ui"])
app.include_router(rooms.router, tags=["rooms"])
app.include_router(messages.router, tags=["messages"])
app.include_router(tickets.router, tags=["tickets"])
app.include_router(ws.router, tags=["ws"])
app.include_router(discovery.router, tags=["discovery"])
app.mount("/static", StaticFiles(directory="app/ui/templates"), name="static")
Instrumentator().instrument(app).expose(app)

@app.get("/health")
async def health(): return {"status":"ok"}
```

---

## 9) Domain gate (optional, match Game/Email policy)

```python
# app/services/authz.py
def allow_dm(email:str, domain:str) -> bool:
    return email.lower().endswith(f"@{domain.lower()}")
```

Use in DM creation endpoints to only allow **@vezeuniqverse.com** addresses.

---

## 10) UI quick notes

* `index.html`: room list + “Join”
* `rooms.html`: chat pane (fetch recent via REST) + WS live messages
* `inbox.html`: ticket list; click to open `ticket.html` (assign, comment)

(Keep it minimal; same space theme as UniQVerse.)

---

## 11) Docker, CI, tests

**Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --upgrade pip && pip install -e .
COPY . .
EXPOSE 8010
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8010"]
```

**CI**

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

**Tests**

```python
# tests/test_health.py
from fastapi.testclient import TestClient
from app.main import app
def test_health(): assert TestClient(app).get("/health").json()["status"]=="ok"
```

---

## 12) Helm integration

* **Tile**: “VEZEPyChat — Live & Inbox”
* **Discovery**: Helm reads `/.veze/service.json` and renders routes.
* **Proxy**: `GET /proxy/chat/rooms` → `http://veze_chat:8010/rooms`
* **Events**: subscribe to `veze.chat` and show ticker in Helm.

**Event shape**

```json
{"type":"chat.message.created","room_id":17,"message_id":442,"user_id":981,"handle":"@pilot","text":"Warp gate online"}
```

---

## 13) Copilot one-shot (paste at repo root)

> Scaffold **VEZEPyChat** as a Python-only FastAPI service with Postgres (SQLAlchemy + Alembic), Redis Streams, WebSocket room feeds, REST for rooms/messages/tickets, Jinja2 UI, Prometheus metrics, Dockerfile, CI, and unit tests exactly as specified in the blueprint. Implement a basic moderation guard and a service discovery endpoint. Print “VEZEPyChat ready”.

---

## 14) Cross-service hooks (ready now)

* **VEZEPyGame**

  * Party room per match: Game creates `Room(kind="party")`; posts killfeed events as chat lines.
  * System notices: Game emits `chat.message.created` for server announcements.

* **VEZEPyEmail**

  * Ticket updates → Email `/jmap/send` to reporter & assignee.
  * DM fallback: if user offline, convert DM → ticket with email notification.

* **VEZEPyXEngine**

  * Auto-moderation: send last N messages to `/npc_response` or sentiment to improve filters.
  * Trend-triggered channels (e.g., #quantum-alerts) fed by XEngine worker.

* **VEZEPyQNetworks**

  * Stamp chat frames with QNetworks headers for trace-overlays in Helm.

---
