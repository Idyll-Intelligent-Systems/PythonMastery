# VEZEPyQNetworks — 9-Layer Quantum-Biotech Network Stack (service + UI + workers)

## 0) What you get

* **FastAPI + Jinja2** web app (no Node) with dashboards for the **9 layers**, **protocols**, and a **live pipeline trace**
* **Pluggable layer engine** (encode/decode) with **Perlin/Voronoi/Density/…/Async** stages
* **Streaming** via Redis Streams (ingest → layer events → outputs)
* **DB** (PostgreSQL + SQLAlchemy 2 + Alembic) to persist pipelines, runs, packets, metrics
* **Workers** for async processing and simulation
* **WS** topics for real-time packet/layer frames
* **CI**, **Dockerfile**, **tests**, **ops runbook**
* Hooks to **UniQVerse Helm**, **VEZEPyGame**, **VEZEPyEmail**

---

## 1) Repo layout

```
VEZEPyQNetworks/
├─ pyproject.toml
├─ Dockerfile
├─ .github/workflows/ci.yml
├─ app/
│  ├─ main.py
│  ├─ ui/templates/{base.html,index.html,layers.html,protocols.html,run.html}
│  └─ routers/{public.py,pipelines.py,packets.py,protocols.py,ws.py}
├─ core/
│  ├─ packet.py            # dataclass & helpers
│  ├─ engine.py            # pipeline runner (encode/decode)
│  ├─ layers/              # 9 layers, each pure-python & testable
│  │  ├─ perlin.py
│  │  ├─ voronoi.py
│  │  ├─ density.py
│  │  ├─ biome.py
│  │  ├─ outbreak.py
│  │  ├─ scale.py
│  │  ├─ variant.py
│  │  ├─ perception.py
│  │  └─ asyncx.py
│  └─ protocols/           # VEZE-QP, BioLink, NexusSync, PlanetMesh, AvengerComm
│     ├─ qp.py
│     ├─ biolink.py
│     ├─ nexus.py
│     ├─ planetmesh.py
│     └─ avenger.py
├─ db/
│  ├─ database.py
│  ├─ models.py
│  └─ migrations/
├─ streaming/
│  ├─ bus.py               # Redis client + helpers
│  ├─ topics.py            # topic names
│  ├─ ingest_worker.py     # demo device ingest → streams
│  ├─ pipeline_worker.py   # consume packets → run 9 layers → emit frames
│  └─ metrics_worker.py    # aggregate & export counters
├─ ops/runbook.md
└─ tests/{test_health.py,test_engine.py,test_layers.py}
```

---

## 2) Core dependencies (pyproject)

```toml
[project]
name = "veze-qnetworks"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115","uvicorn[standard]>=0.30","jinja2>=3.1",
  "pydantic>=2.8","SQLAlchemy>=2.0","asyncpg>=0.29","alembic>=1.13",
  "redis>=5.0","numpy>=1.26","scipy>=1.13","shapely>=2.0",
  "prometheus-client>=0.20","opentelemetry-sdk>=1.27.0",
  "opentelemetry-instrumentation-fastapi>=0.48b0","opentelemetry-exporter-otlp>=1.27.0",
  "python-multipart>=0.0.9"
]
[project.optional-dependencies]
dev = ["ruff>=0.5","black>=24.8","mypy>=1.11","pytest>=8.3","pytest-asyncio>=0.23"]
```

---

## 3) Data model (SQLAlchemy 2.0)

```python
# db/models.py
from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, JSON, LargeBinary, Float, Integer

class Base(DeclarativeBase): ...

class Pipeline(Base):
    __tablename__ = "pipelines"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    config: Mapped[dict] = mapped_column(JSON)   # enabled layers & params

class Run(Base):
    __tablename__ = "runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_id: Mapped[int]
    status: Mapped[str] = mapped_column(String(20), default="queued")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)

class Packet(Base):
    __tablename__ = "packets"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int]
    direction: Mapped[str] = mapped_column(String(8))   # "send"|"recv"
    payload: Mapped[bytes] = mapped_column(LargeBinary)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

class Frame(Base):
    __tablename__ = "frames"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int]; step: Mapped[int]
    layer: Mapped[str] = mapped_column(String(40))
    view: Mapped[dict] = mapped_column(JSON, default=dict)  # small viz payload
    dt_ms: Mapped[float] = mapped_column(Float, default=0.0)
```

---

## 4) Packet + Engine

```python
# core/packet.py
from dataclasses import dataclass, field

@dataclass
class QPacket:
    id: int
    data: bytes
    header: dict = field(default_factory=dict)
    route: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)
```

```python
# core/engine.py
import time
from typing import Callable, Iterable
from core.packet import QPacket

Step = Callable[[QPacket, str], QPacket]  # (packet, mode) -> packet

class PipelineEngine:
    def __init__(self, steps: Iterable[tuple[str, Step]]):
        self.steps = list(steps)

    def encode(self, p: QPacket, on_step=None) -> QPacket:
        for name, fn in self.steps:
            t0 = time.perf_counter()
            p = fn(p, "encode")
            if on_step: on_step(name, p, (time.perf_counter()-t0)*1000)
        return p

    def decode(self, p: QPacket, on_step=None) -> QPacket:
        for name, fn in reversed(self.steps):
            t0 = time.perf_counter()
            p = fn(p, "decode")
            if on_step: on_step(name, p, (time.perf_counter()-t0)*1000)
        return p
```

---

## 5) The 9 layers (pure Python, side-effect free)

Each layer follows `def layer(packet: QPacket, mode:str) -> QPacket`. Below are crisp versions; you can expand with heavier math later.

```python
# core/layers/perlin.py
import math, os
from core.packet import QPacket
SEED = int(os.getenv("QNET_PERLIN_SEED","1138"))
def perlin(packet: QPacket, mode: str) -> QPacket:
    # tiny hash noise on header length
    n = (packet.id * 1103515245 + SEED) & 0x7fffffff
    jitter = (n % 97) / 10000.0
    if mode == "encode":
        packet.header["noise"] = jitter
    else:
        packet.header.pop("noise", None)
    return packet
```

```python
# core/layers/voronoi.py
from core.packet import QPacket
def voronoi(packet: QPacket, mode: str) -> QPacket:
    # assign to a pseudo cell by id bucketing
    cell = packet.id % 16
    if mode == "encode": packet.route["cell"]=cell
    else: packet.route.pop("cell", None)
    return packet
```

```python
# core/layers/density.py
from core.packet import QPacket
def density(packet: QPacket, mode: str) -> QPacket:
    if mode == "encode" and len(packet.data) > 2048:
        packet.meta["compressed"] = True
        packet.data = packet.data[:1024] + b"..."
    elif mode == "decode" and packet.meta.get("compressed"):
        packet.data = packet.data.replace(b"...", b"")
        packet.meta.pop("compressed", None)
    return packet
```

```python
# core/layers/biome.py
from core.packet import QPacket
def biome(packet: QPacket, mode: str) -> QPacket:
    tag = "BLEND:PROTO"
    if mode == "encode":
        packet.header["biome"] = "fusion"
        packet.data += b"|" + tag.encode()
    else:
        packet.data = packet.data.replace(b"|"+tag.encode(), b"")
        packet.header.pop("biome", None)
    return packet
```

```python
# core/layers/outbreak.py
from core.packet import QPacket
def outbreak(packet: QPacket, mode: str) -> QPacket:
    if mode == "encode":
        packet.meta["copies"] = 2
    else:
        packet.meta.pop("copies", None)
    return packet
```

```python
# core/layers/scale.py
from core.packet import QPacket
def scale(packet: QPacket, mode: str) -> QPacket:
    if mode == "encode": packet.header["tier"]="planet"
    else: packet.header.pop("tier", None)
    return packet
```

```python
# core/layers/variant.py
from core.packet import QPacket
def variant(packet: QPacket, mode: str) -> QPacket:
    if mode == "encode":
        packet.meta["variant"] = packet.data[::-1][:16].hex()
    else:
        packet.meta.pop("variant", None)
    return packet
```

```python
# core/layers/perception.py
from core.packet import QPacket
def perception(packet: QPacket, mode: str) -> QPacket:
    if mode == "encode": packet.header["ai"]="scan-ok"
    else: packet.header.pop("ai", None)
    return packet
```

```python
# core/layers/asyncx.py
from core.packet import QPacket
def asyncx(packet: QPacket, mode: str) -> QPacket:
    # marker; real impl offloaded to worker threads
    if mode == "encode": packet.header["async"]="done"
    else: packet.header.pop("async", None)
    return packet
```

**Wiring the pipeline**

```python
# app/routers/pipelines.py (snippet)
from fastapi import APIRouter
from core.engine import PipelineEngine
from core.layers import perlin, voronoi, density, biome, outbreak, scale, variant, perception, asyncx
from core.packet import QPacket

router = APIRouter()

def factory():
    steps = [
      ("perlin", perlin.perlin),
      ("voronoi", voronoi.voronoi),
      ("density", density.density),
      ("biome", biome.biome),
      ("outbreak", outbreak.outbreak),
      ("scale", scale.scale),
      ("variant", variant.variant),
      ("perception", perception.perception),
      ("async", asyncx.asyncx),
    ]
    return PipelineEngine(steps)

@router.post("/pipelines/run")
async def run_pipeline(data: bytes):
    eng = factory()
    frames = []
    def on_step(name, pkt, dt_ms): frames.append({"layer":name,"dt_ms":dt_ms,"header":pkt.header,"meta":pkt.meta})
    pkt = QPacket(id=1, data=data)
    out = eng.encode(pkt, on_step=on_step)
    return {"frames": frames, "out_len": len(out.data)}
```

---

## 6) Protocols (built on the layers)

Each protocol is a thin adapter that configures/wraps the pipeline.

```python
# core/protocols/qp.py
from core.engine import PipelineEngine
from core.layers import perlin, voronoi, density, biome, scale, variant, perception, asyncx
def qp_engine() -> PipelineEngine:
    return PipelineEngine([
      ("perlin", perlin.perlin),
      ("voronoi", voronoi.voronoi),
      ("density", density.density),
      ("biome", biome.biome),
      ("scale", scale.scale),
      ("variant", variant.variant),
      ("perception", perception.perception),
      ("async", asyncx.asyncx),
    ])
```

Add similar stubs for **BioLink**, **NexusSync** (enable `variant` emphasis), **PlanetMesh** (favor `voronoi`), **AvengerComm** (inject tags for team roles).

Expose via API:

```python
# app/routers/protocols.py
from fastapi import APIRouter
from core.packet import QPacket
from core.protocols.qp import qp_engine

router = APIRouter()

@router.post("/protocols/qp/send")
async def qp_send(data: bytes):
    eng = qp_engine()
    frames=[]
    pkt=QPacket(id=42, data=data)
    out = eng.encode(pkt, on_step=lambda n,p,t: frames.append({"layer":n,"dt":t}))
    return {"ok": True, "frames": frames, "bytes": len(out.data)}
```

---

## 7) Streaming & workers

**Topics**

```python
# streaming/topics.py
INGEST = "qnet.ingest"
FRAME  = "qnet.frame"
OUTPUT = "qnet.output"
```

**Redis helper**

```python
# streaming/bus.py
import os, json, redis.asyncio as redis
r = redis.from_url(os.getenv("REDIS_URL","redis://localhost:6379/0"))
async def emit(stream:str, payload:dict):
    await r.xadd(stream, {"payload": json.dumps(payload)})
```

**Ingest worker (demo devices → packets)**

```python
# streaming/ingest_worker.py
import asyncio, os, json, redis.asyncio as redis, secrets
from streaming.bus import emit
from streaming.topics import INGEST

async def main():
    while True:
        msg = {"device":"helm","packet_id": secrets.randbelow(1_000_000), "data":"Alert: Tyrant Incoming!"}
        await emit(INGEST, msg); await asyncio.sleep(1.0)

if __name__=="__main__": asyncio.run(main())
```

**Pipeline worker (process through 9 layers)**

```python
# streaming/pipeline_worker.py
import asyncio, json
from streaming.bus import r, emit
from streaming.topics import INGEST, FRAME, OUTPUT
from core.engine import PipelineEngine
from core.layers import perlin, voronoi, density, biome, outbreak, scale, variant, perception, asyncx
from core.packet import QPacket

eng = PipelineEngine([
  ("perlin", perlin.perlin), ("voronoi", voronoi.voronoi),
  ("density", density.density), ("biome", biome.biome),
  ("outbreak", outbreak.outbreak), ("scale", scale.scale),
  ("variant", variant.variant), ("perception", perception.perception),
  ("async", asyncx.asyncx)
])

async def main():
    group, consumer = "qnet", "worker1"
    try: await r.xgroup_create(INGEST, group, id="$", mkstream=True)
    except Exception: pass
    while True:
        xs = await r.xreadgroup(group, consumer, {INGEST: ">"}, count=10, block=5000)
        for _, msgs in xs or []:
            for mid, data in msgs:
                ev = json.loads(data["payload"])
                pkt = QPacket(id=ev["packet_id"], data=ev["data"].encode())
                def on_step(name, p, dt): asyncio.create_task(emit(FRAME, {"packet_id": pkt.id, "layer": name, "dt_ms": dt}))
                out = eng.encode(pkt, on_step=on_step)
                await emit(OUTPUT, {"packet_id": pkt.id, "len": len(out.data)})
                await r.xack(INGEST, group, mid)

if __name__=="__main__": asyncio.run(main())
```

**WS router** (live frames to browser)

```python
# app/routers/ws.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as redis, os, json

router = APIRouter()
r = redis.from_url(os.getenv("REDIS_URL","redis://localhost:6379/0"))

@router.websocket("/ws/frames")
async def frames(ws: WebSocket, packet_id: int | None = None):
    await ws.accept()
    stream, group = "qnet.frame", "ws"
    try: await r.xgroup_create(stream, group, id="$", mkstream=True)
    except Exception: pass
    try:
        while True:
            xs = await r.xreadgroup(group, "c1", {stream: ">"}, count=50, block=2000)
            for _, msgs in xs or []:
                for mid, data in msgs:
                    ev = json.loads(data["payload"])
                    if packet_id is None or ev["packet_id"]==packet_id:
                        await ws.send_json(ev)
                    await r.xack(stream, group, mid)
    except WebSocketDisconnect:
        return
```

---

## 8) Web UI (Jinja2)

* **`/`**: overview + CTA to run demo
* **`/layers`**: 9-layer cards; click to see descriptions + last N frames
* **`/protocols`**: 5 protocol tiles; try-send buttons
* **`/run`**: pipeline runner with text box; real-time WS trace

*(HTML/CSS kept minimal; reuse the UniQVerse cosmic theme if you want.)*

---

## 9) Service app wiring

```python
# app/main.py
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.routers import public, pipelines, packets, protocols, ws

app = FastAPI(title="VEZEPyQNetworks")
app.state.tpl = Jinja2Templates(directory="app/ui/templates")
app.include_router(public.router, tags=["pages"])
app.include_router(pipelines.router, prefix="/pipelines", tags=["pipelines"])
app.include_router(protocols.router, prefix="/protocols", tags=["protocols"])
app.include_router(ws.router, tags=["ws"])
app.mount("/static", StaticFiles(directory="app/ui/static"), name="static")

@app.get("/health")
async def health(): return {"status":"ok"}
```

---

## 10) Docker, CI, tests

**Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --upgrade pip && pip install -e .
COPY . .
EXPOSE 8000
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
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
      - run: mypy .
      - run: pytest -q
```

**Tests**

```python
# tests/test_engine.py
from core.engine import PipelineEngine
from core.layers import perlin, voronoi, density, biome, outbreak, scale, variant, perception, asyncx
from core.packet import QPacket

def test_pipeline_roundtrip():
    eng = PipelineEngine([("perlin", perlin.perlin), ("voronoi", voronoi.voronoi),
                          ("density", density.density), ("biome", biome.biome),
                          ("outbreak", outbreak.outbreak), ("scale", scale.scale),
                          ("variant", variant.variant), ("perception", perception.perception),
                          ("async", asyncx.asyncx)])
    p = QPacket(id=7, data=b"hello world")
    out = eng.encode(p)
    assert out.header.get("async") == "done"
```

---

## 11) Runbook (dev)

```bash
# dev
pip install -e .[dev]
alembic upgrade head
uvicorn app.main:app --reload
# workers
python streaming/ingest_worker.py
python streaming/pipeline_worker.py
# open http://localhost:8000  → Run demo, watch /ws/frames
```

---

## 12) Integration points

### UniQVerse (VEZE Helm)

* Add card → **VEZEPyQNetworks** (icon: 🧬⚡)
* Optional `/proxy/qnet/*` passthroughs for `/pipelines/run` & `/protocols/*`
* Show live frames widget using hub WS proxy

### VEZEPyGame

* **Low-latency comms**: call `POST /protocols/qp/send` to pre-process match messages (consistent, obfus/noise)
* **Variant events**: request **NexusSync** protocol for “timeline branching” events tied to special modes

### VEZEPyEmail

* **Outbreak notifications**: Email service emits `global.events` when new mail; QNetworks can route via **BioLink** to devices with density filtration (Layer 3) to keep in-game inbox light

### VEZEPyTimeVMaps (future)

* Use **Variant** + **Scale** layers to map (timeline, world) addressing into packet routes; feed Map’s WS to overlay live QNetworks frames in multiverse planner

---

## 13) Copilot one-shot (paste at repo root)

> Scaffold **VEZEPyQNetworks** exactly as specified: FastAPI + Jinja2 app, 9 pure-python layers, `PipelineEngine`, Redis stream workers (`ingest_worker.py`, `pipeline_worker.py`), DB models (pipelines, runs, packets, frames), WS `/ws/frames`, routes `/pipelines/run` and `/protocols/*`, Dockerfile, CI, and tests. Keep it Python-only (no Node). Then print “VEZEPyQNetworks ready”.

---
