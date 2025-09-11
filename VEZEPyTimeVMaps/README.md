# VEZEPyTimeVMaps — Multiverse Maps + Quantum-Physics-Aware Routing

**Concept:** a “multiverse map” where routes, positions and worlds exist across **space × time × timeline branches**. It integrates:

* **VEZEPyQuantumTime** (circuits + SR/GR time dilation)
* **VEZEPyMaps** (reverse geocode, routing, ETA, live positions)
* **VEZEPyGame** hooks (world layers, zones, shards)

It produces **branch-aware routes**, **relativistic ETAs**, and **live WS frames** (quantum steps + map updates).

---

## Architecture (C4-brief)

* **Gateway/UI (FastAPI + Jinja2/Jinja partials)**: landing, multiverse map, route planner, experiment runner, admin.
* **Domain services**

  * `worlds` — universes/world layers/shards + access control
  * `quantum` — circuits, SR/GR, experiment orchestration
  * `geo` — gazetteer, segments, territories
  * `routing` — A\*/Dijkstra over **(node, timeline)** graph; relativistic ETA
  * `replay` — time scrubbing: rewind/fast-forward positions and boxscores of events
* **Streaming (Redis Streams)**

  * `tv.experiment.submitted`, `tv.sim.frame`, `tv.sim.finished`
  * `tv.position.update` (world\_id, timeline\_id, vehicle\_id, pos)
  * `tv.route.requested`, `tv.route.computed`
* **Data**

  * Postgres (SQLAlchemy 2.0 + Alembic): places, segments, worlds, timelines, circuits, experiments, frames, results, routes, replays
  * Redis: cache + streams
  * Optional DuckDB for analytics
* **Security**: OIDC (stub), JWT, RBAC (`player`, `analyst`, `admin`)
* **Obs**: OTEL + Prometheus (`/metrics`)

---

## Repository layout

```
VEZEPyTimeVMaps/
├─ pyproject.toml
├─ Dockerfile
├─ .github/workflows/ci.yml
├─ app/
│  ├─ main.py
│  ├─ ui/templates/{base.html,index.html,plan.html,run.html,worlds.html}
│  └─ routers/{public.py,worlds.py,quantum.py,geo.py,routing.py,replay.py,ws.py}
├─ db/
│  ├─ database.py
│  ├─ models.py
│  └─ migrations/
├─ core/
│  ├─ circuits.py       # quantum ops (ported from VEZEPyQuantumTime)
│  ├─ relativity.py     # SR/GR
│  ├─ graph.py          # (node,timeline) routing; A*
│  ├─ eta.py            # relativistic ETA
│  └─ frames.py         # encode/decode frames
├─ streaming/
│  ├─ producer.py
│  ├─ sim_worker.py     # quantum sim
│  └─ routing_worker.py # heavy path computation
├─ ops/runbook.md
└─ tests/test_health.py
```

---

## Core data model (SQLAlchemy 2.0)

```python
# db/models.py
from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float, JSON, LargeBinary, Index

class Base(DeclarativeBase): ...

class World(Base):
    __tablename__ = "worlds"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    rules: Mapped[dict] = mapped_column(JSON, default=dict)  # physics toggles, gravity, etc.

class Timeline(Base):
    __tablename__ = "timelines"
    id: Mapped[int] = mapped_column(primary_key=True)
    world_id: Mapped[int]
    label: Mapped[str] = mapped_column(String(120))
    parent_id: Mapped[int | None] = mapped_column()
    branch_op: Mapped[str | None] = mapped_column(String(80))  # how branch formed (circuit hash, event)

class Place(Base):
    __tablename__ = "places"
    id: Mapped[int] = mapped_column(primary_key=True)
    world_id: Mapped[int]
    name: Mapped[str] = mapped_column(String(200))
    lat: Mapped[float]; lon: Mapped[float]
    props: Mapped[dict] = mapped_column(JSON, default=dict)

class Segment(Base):
    __tablename__ = "segments"
    id: Mapped[int] = mapped_column(primary_key=True)
    world_id: Mapped[int]; a_place_id: Mapped[int]; b_place_id: Mapped[int]
    length_m: Mapped[float]; speed_kph: Mapped[float]
    base_drag: Mapped[float] = mapped_column(default=0.0)  # world physics modifier

class Circuit(Base):
    __tablename__ = "circuits"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(140), unique=True)
    qubits: Mapped[int]; gates_json: Mapped[dict]

class Experiment(Base):
    __tablename__ = "experiments"
    id: Mapped[int] = mapped_column(primary_key=True)
    world_id: Mapped[int]; timeline_id: Mapped[int]
    kind: Mapped[str]  # "quantum" | "sr" | "gr"
    params: Mapped[dict]; status: Mapped[str] = mapped_column(String(20), default="queued")
    submitted_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    result_id: Mapped[int | None]

class Frame(Base):
    __tablename__ = "frames"
    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int]; step: Mapped[int]; payload: Mapped[bytes]

class Result(Base):
    __tablename__ = "results"
    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int]; metrics: Mapped[dict] = mapped_column(JSON); artifacts: Mapped[list[str]] = mapped_column(JSON, default=list)

class RoutePlan(Base):
    __tablename__ = "route_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    world_id: Mapped[int]; timeline_id: Mapped[int]; origin_id: Mapped[int]; dest_id: Mapped[int]
    path_nodes: Mapped[list[int]] = mapped_column(JSON)
    distance_m: Mapped[float]; eta_seconds: Mapped[float]; physics_note: Mapped[str] = mapped_column(String(160), default="")
Index("ix_places_world", Place.world_id)
Index("ix_segments_world", Segment.world_id)
```

---

## Quantum + Routing fusion (key ideas)

* **Node state:** a node is `(place_id, timeline_id)`. Edges are **segments within the same timeline** plus optional **branch gateways** (time-branch transfers) with costs defined by experiment results (e.g., decoherence penalty).
* **Relativistic ETA:** For each edge, adjust speed by SR/GR factors:

  * SR: `gamma = 1/sqrt(1 - v^2/c^2)`, **proper time** differs from coordinate time.
  * GR: factor from mass/radius (`√(1 - 2GM/(rc^2))`).
* **World rules:** Per-world modifiers (drag, gravity multipliers, allowed max v).
* **A\* heuristic:** great-circle distance / max speed (per world) on the same timeline; add cost for timeline jumps.

---

## Core algorithms (Python)

### 1) State-vector gates (short) & SR/GR

(Reuse from your Quantum/Time services; shown abbreviated here.)

```python
# core/relativity.py
import math
C = 299_792_458.0
def gamma_from_v(v: float) -> float: return 1.0 / math.sqrt(max(1e-12, 1.0 - (v*v)/(C*C)))
def sr_proper_seconds(coord_seconds: float, v: float) -> float:
    return coord_seconds / gamma_from_v(v)

def gr_coord_from_proper(t_proper: float, M: float, r: float, G: float = 6.674e-11) -> float:
    factor = math.sqrt(max(1e-12, 1.0 - (2*G*M)/(r*C*C)))
    return t_proper / factor
```

### 2) Multiverse routing graph with timeline jumps

```python
# core/graph.py
import heapq, math
from typing import Dict, Tuple, List, Optional

class Edge:
    __slots__ = ("to","length_m","speed_kph","jump_penalty_s","note")
    def __init__(self, to:int, length_m:float, speed_kph:float, jump_penalty_s:float=0.0, note:str=""):
        self.to=to; self.length_m=length_m; self.speed_kph=speed_kph; self.jump_penalty_s=jump_penalty_s; self.note=note

def build_multiverse_graph(segments, jumps) -> Dict[int, List[Edge]]:
    """
    segments: iterable of (node_a, node_b, length_m, speed_kph)
      node = global numeric id representing (place_id, timeline_id)
    jumps: iterable of (node_a, node_b, penalty_s, note)
    """
    g: Dict[int, List[Edge]] = {}
    for a,b,l,spd in segments:
        g.setdefault(a, []).append(Edge(b,l,spd))
        g.setdefault(b, []).append(Edge(a,l,spd))
    for a,b,pen,note in jumps:
        g.setdefault(a, []).append(Edge(b,0.0,1.0, jump_penalty_s=pen, note=note))
    return g

def a_star(g: Dict[int,List[Edge]], start:int, goal:int, heuristic) -> Optional[Tuple[List[int], float]]:
    dist={start:0.0}; prev={}; pq=[(heuristic(start), start)]
    while pq:
        _, u = heapq.heappop(pq)
        if u==goal: break
        du = dist[u]
        for e in g.get(u,[]):
            # edge time (ideal) + penalty
            v_mps = max(1.0, e.speed_kph/3.6)
            te = (e.length_m / v_mps) + e.jump_penalty_s
            nd = du + te
            if e.to not in dist or nd < dist[e.to]:
                dist[e.to]=nd; prev[e.to]=u
                heapq.heappush(pq,(nd+heuristic(e.to), e.to))
    if goal not in dist: return None
    path=[goal]; cur=goal
    while cur!=start: cur=prev[cur]; path.append(cur)
    path.reverse()
    return path, dist[goal]
```

### 3) Relativistic ETA blending per world physics

```python
# core/eta.py
from core.relativity import sr_proper_seconds, gr_coord_from_proper

def relativistic_eta(edges, world_rules: dict) -> float:
    """
    edges: [(length_m, speed_kph, meta)] meta may include v (m/s), M, r
    """
    total = 0.0
    max_speed = world_rules.get("max_speed_mps", 100.0)
    for length_m, speed_kph, meta in edges:
        v = min(max_speed, max(1.0, speed_kph/3.6))
        coord_t = length_m / v
        if meta.get("sr"):
            coord_t = sr_proper_seconds(coord_t, v=v)  # proper time experienced by traveler
        if meta.get("gr"):
            M = meta["gr"]["M"]; r = meta["gr"]["r"]
            coord_t = gr_coord_from_proper(coord_t, M=M, r=r)
        drag = world_rules.get("base_drag", 0.0)
        total += coord_t * (1.0 + drag)
    return total
```

---

## FastAPI app (selected routers)

### `app/main.py`

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers import public, worlds, quantum, geo, routing, replay, ws

app = FastAPI(title="VEZEPyTimeVMaps")
app.include_router(public.router, tags=["public"])
app.include_router(worlds.router, prefix="/worlds", tags=["worlds"])
app.include_router(quantum.router, prefix="/quantum", tags=["quantum"])
app.include_router(geo.router, prefix="/geo", tags=["geo"])
app.include_router(routing.router, prefix="/routing", tags=["routing"])
app.include_router(replay.router, prefix="/replay", tags=["replay"])
app.include_router(ws.router, tags=["ws"])

app.mount("/static", StaticFiles(directory="app/ui/static"), name="static")
app.state.tpl = Jinja2Templates(directory="app/ui/templates")

@app.get("/health")
async def health(): return {"status":"ok"}
```

### `app/routers/routing.py` (branch-aware route + relativistic ETA)

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.database import get_session
from db.models import Place, Segment, World, Timeline, RoutePlan
from core.graph import build_multiverse_graph, a_star
from core.eta import relativistic_eta

router = APIRouter()

def node_id(place_id:int, timeline_id:int) -> int:
    # pack two ints into one (simple)
    return (timeline_id << 32) | place_id

@router.get("/plan")
async def plan_route(world_id:int, timeline_id:int, origin_place_id:int, dest_place_id:int, session: AsyncSession = Depends(get_session)):
    # Load world rules, segments in timeline
    w = (await session.execute(select(World).where(World.id==world_id))).scalars().first()
    if not w: raise HTTPException(404,"world")
    segs = (await session.execute(select(Segment).where(Segment.world_id==world_id))).scalars().all()

    segments = [(node_id(s.a_place_id, timeline_id), node_id(s.b_place_id, timeline_id), s.length_m, s.speed_kph) for s in segs]
    # Optional: allow one jump to sibling timeline with penalty
    jumps = []  # [(node_a,node_b,penalty_s,"branch")]
    g = build_multiverse_graph(segments, jumps)

    start = node_id(origin_place_id, timeline_id)
    goal  = node_id(dest_place_id, timeline_id)
    def h(n:int)->float: return 0.0  # plug heuristic if you store coordinates per node
    r = a_star(g, start, goal, h)
    if not r: raise HTTPException(404,"no path")
    path, coord_time = r

    # Collect edges with meta for relativistic adjustment
    idx = {(node_id(s.a_place_id,timeline_id), node_id(s.b_place_id,timeline_id)): (s.length_m, s.speed_kph, {"sr": True}) for s in segs}
    idx.update({(node_id(s.b_place_id,timeline_id), node_id(s.a_place_id,timeline_id)): (s.length_m, s.speed_kph, {"sr": True}) for s in segs})
    edges = [idx[(path[i], path[i+1])] for i in range(len(path)-1)]
    eta_s = relativistic_eta(edges, w.rules or {})

    rp = RoutePlan(world_id=world_id, timeline_id=timeline_id, origin_id=origin_place_id, dest_id=dest_place_id,
                   path_nodes=path, distance_m=sum(e[0] for e in edges), eta_seconds=eta_s, physics_note="SR applied")
    session.add(rp); await session.commit(); await session.refresh(rp)
    return {"route_id": rp.id, "distance_m": rp.distance_m, "eta_seconds": int(rp.eta_seconds), "path_nodes": rp.path_nodes}
```

### `app/routers/quantum.py` (submit experiments that can affect routing penalties/jumps)

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_session
from db.models import Experiment
from streaming.producer import emit

router = APIRouter()

@router.post("/experiment", status_code=202)
async def submit_experiment(world_id:int, timeline_id:int, kind:str, params:dict, session: AsyncSession = Depends(get_session)):
    exp = Experiment(world_id=world_id, timeline_id=timeline_id, kind=kind, params=params)
    session.add(exp); await session.commit(); await session.refresh(exp)
    await emit("tv.experiment.submitted", {"experiment_id": exp.id})
    return {"experiment_id": exp.id, "status":"queued"}
```

### `app/routers/ws.py` (live frames + positions)

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as redis, os, json

router = APIRouter()
r = redis.from_url(os.getenv("REDIS_URL","redis://localhost:6379/0"))

@router.websocket("/ws/live")
async def live(ws: WebSocket, world_id:int, timeline_id:int):
    await ws.accept()
    groups = [("tv.sim.frame", f"sim-{world_id}-{timeline_id}"), ("tv.position.update", f"pos-{world_id}-{timeline_id}")]
    for stream, group in groups:
        try: await r.xgroup_create(stream, group, id="$", mkstream=True)
        except Exception: pass
    try:
        while True:
            xs = await r.xreadgroup(groups[0][1], "w1", {"tv.sim.frame":">"}, count=50, block=1000)
            ys = await r.xreadgroup(groups[1][1], "w1", {"tv.position.update":">"}, count=50, block=1000)
            for _, msgs in (xs or []):
                for mid, data in msgs:
                    ev = json.loads(data["payload"])
                    if ev.get("world_id")==world_id and ev.get("timeline_id")==timeline_id:
                        await ws.send_json({"type":"sim", **ev}); await r.xack("tv.sim.frame", groups[0][1], mid)
            for _, msgs in (ys or []):
                for mid, data in msgs:
                    ev = json.loads(data["payload"])
                    if ev.get("world_id")==world_id and ev.get("timeline_id")==timeline_id:
                        await ws.send_json({"type":"pos", **ev}); await r.xack("tv.position.update", groups[1][1], mid)
    except WebSocketDisconnect:
        return
```

---

## Workers

### `streaming/sim_worker.py` (quantum frames → tv.sim.frame)

(Adapted from QuantumTime; emits with `world_id`, `timeline_id`.)

```python
import asyncio, json, os, pickle, redis.asyncio as redis
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from db.models import Experiment, Frame, Result
from core.circuits import run_circuit
from core.relativity import sr_proper_seconds, gr_coord_from_proper

r = redis.from_url(os.getenv("REDIS_URL","redis://localhost:6379/0"))
# ... engine, Session ...

async def main():
    group, consumer = "tv", "sim1"
    try: await r.xgroup_create("tv.experiment.submitted", group, id="$", mkstream=True)
    except Exception: pass
    while True:
        xs = await r.xreadgroup(group, consumer, {"tv.experiment.submitted":">"}, count=10, block=5000)
        for _, msgs in xs or []:
            for mid, data in msgs:
                ev = json.loads(data["payload"]); exp_id = ev["experiment_id"]
                # load experiment, run either quantum state frames or SR/GR metrics
                # emit frames with world_id/timeline_id
                # ...
                await r.xack("tv.experiment.submitted", group, mid)

if __name__ == "__main__": asyncio.run(main())
```

### `streaming/routing_worker.py` (heavy route computations async)

Consumes `tv.route.requested` and stores `RoutePlan`; optional if you want async route planning.

---

## pyproject.toml (deps)

```toml
[project]
name = "veze-timevmaps"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115","uvicorn[standard]>=0.30","jinja2>=3.1",
  "pydantic>=2.8","SQLAlchemy>=2.0","asyncpg>=0.29","alembic>=1.13",
  "redis>=5.0","numpy>=1.26","pandas>=2.2",
  "prometheus-client>=0.20","opentelemetry-sdk>=1.27.0",
  "opentelemetry-instrumentation-fastapi>=0.48b0","opentelemetry-exporter-otlp>=1.27.0"
]
[project.optional-dependencies]
dev=["ruff>=0.5","black>=24.8","mypy>=1.11","pytest>=8.3","pytest-asyncio>=0.23"]
```

---

## Dockerfile

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
      - run: python -m pip install --upgrade pip
      - run: pip install -e .[dev]
      - run: ruff check .
      - run: mypy .
      - run: pytest -q
      - name: SBOM
        run: pip install cyclonedx-bom && cyclonedx-py -o ops/sbom.json || true
```

---

## tests/test\_health.py

```python
from fastapi.testclient import TestClient
from app.main import app
def test_health():
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
```

---

## ops/runbook.md (quick)

```bash
# Dev
pip install -e .[dev]
alembic upgrade head
uvicorn app.main:app --reload

# Workers
python streaming/sim_worker.py
# (optional) python streaming/routing_worker.py

# Try:
# 1) Create world & timeline (POST /worlds) – or seed SQL.
# 2) Submit experiment (quantum or SR/GR):
curl -X POST 'http://localhost:8000/quantum/experiment?world_id=1&timeline_id=1&kind=quantum' \
  -H 'Content-Type: application/json' -d '{"qubits":2,"gates":[{"op":"H","target":0},{"op":"CNOT","control":0,"target":1}]}'

# 3) Plan route:
curl 'http://localhost:8000/routing/plan?world_id=1&timeline_id=1&origin_place_id=10&dest_place_id=42'

# 4) Live stream:
#   ws://localhost:8000/ws/live?world_id=1&timeline_id=1
```

---

## Hook into VEZEPyUniQVerse

* Add a **Helm card**: `VEZEPyTimeVMaps` with icon 🕒🗺️
* Add `/proxy/timevmaps/*` passthrough in the hub so UniQVerse can call `/routing/plan`, `/quantum/experiment`, `/ws/live`.
* Optional: **NiceGUI** dashboards embedded in UniQVerse for a single-pane view.

---
