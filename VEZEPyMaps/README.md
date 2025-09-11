# VEZEPyMaps — Geospatial Analytics & Routing (Python-only)

**Use-cases:**

* Reverse geocoding (local gazetteer)
* Routing (Dijkstra/A\* on road graph) + ETA
* Heatmaps / territory analytics (demand, coverage)
* Live map feeds (vehicle positions) via WS
* Batch geoprocessing & tiles cache (no PostGIS, pure Python libs)

## Architecture

* **Gateway/UI:** FastAPI + Jinja2; WS `/ws/live` for positions.
* **Services:** `geo_ingest`, `index`, `routing`, `analytics`, `tiles`.
* **Streaming:** `maps.position.update`, `maps.route.requested`, `maps.analytics.completed`.
* **Data:** Postgres (places, segments, territories), DuckDB (batch analytics), Redis (cache/streams), Shapely/pyproj for geometry; R-tree (optional, via `rtree` if available).
* **ML:** ETA regression stub (sklearn), demand forecasting for heatmaps.
* **Security/Obs:** OIDC stub, JWT; OTEL; Prometheus.

## Repo layout

```
VEZEPyMaps/
├─ pyproject.toml
├─ Dockerfile
├─ .github/workflows/ci.yml
├─ app/
│  ├─ main.py
│  ├─ ui/templates/{base.html,index.html,route.html,heatmap.html}
│  └─ routers/{public.py,geo.py,routing.py,analytics.py,ws.py}
├─ db/{database.py,models.py,migrations/}
├─ geo/
│  ├─ gazetteer.py      # reverse geocode index
│  ├─ graph.py          # road graph builder, Dijkstra/A*
│  ├─ eta.py            # ETA model stub
│  └─ tiles.py          # simple tile cache (PIL draw optional)
├─ streaming/{producer.py,position_worker.py}
├─ ops/runbook.md
└─ tests/test_health.py
```

## Key files

### `pyproject.toml`

```toml
[project]
name = "veze-maps"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115","uvicorn[standard]>=0.30","jinja2>=3.1",
  "pydantic>=2.8","SQLAlchemy>=2.0","asyncpg>=0.29","alembic>=1.13",
  "redis>=5.0","numpy>=1.26","pandas>=2.2","duckdb>=1.0.0",
  "shapely>=2.0","pyproj>=3.6",
  "prometheus-client>=0.20","opentelemetry-sdk>=1.27.0",
  "opentelemetry-instrumentation-fastapi>=0.48b0","opentelemetry-exporter-otlp>=1.27.0",
  "scikit-learn>=1.5"
]
[project.optional-dependencies]
dev = ["ruff>=0.5","black>=24.8","mypy>=1.11","pytest>=8.3","pytest-asyncio>=0.23"]
```

### `db/models.py`

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float, JSON
class Base(DeclarativeBase): ...

class Place(Base):
    __tablename__ = "places"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    lat: Mapped[float]
    lon: Mapped[float]
    props: Mapped[dict] = mapped_column(JSON, default=dict)

class Segment(Base):
    __tablename__ = "segments"
    id: Mapped[int] = mapped_column(primary_key=True)
    a_place_id: Mapped[int]
    b_place_id: Mapped[int]
    length_m: Mapped[float]
    speed_kph: Mapped[float]

class Territory(Base):
    __tablename__ = "territories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    polygon_wkt: Mapped[str]   # store WKT polygon (pure Python)
```

### `geo/graph.py` (Dijkstra routing)

```python
import heapq, math
from typing import Dict, Tuple, List

def build_graph(segments: list[Tuple[int,int,float,float]]) -> dict[int, list[Tuple[int,float,float]]]:
    # list[(a,b,length_m,speed_kph)] => adjacency {a:[(b,length,speed)], b:[(a,length,speed)]}
    g: Dict[int, list[Tuple[int,float,float]]] = {}
    for a,b,l,spd in segments:
        g.setdefault(a, []).append((b,l,spd))
        g.setdefault(b, []).append((a,l,spd))
    return g

def dijkstra(g: dict[int, list[Tuple[int,float,float]]], start: int, goal: int):
    dist = {start: 0.0}; prev = {}; pq = [(0.0, start)]
    while pq:
        d,u = heapq.heappop(pq)
        if u==goal: break
        if d!=dist[u]: continue
        for v,l,_ in g.get(u, []):
            nd = d + l
            if v not in dist or nd < dist[v]:
                dist[v] = nd; prev[v] = u; heapq.heappush(pq, (nd, v))
    if goal not in dist: return None
    path = [goal]; cur = goal
    while cur != start:
        cur = prev[cur]; path.append(cur)
    path.reverse()
    return path, dist[goal]
```

### `geo/eta.py` (ETA stub)

```python
def eta_seconds(path_edges: list[tuple[float,float]]) -> float:
    # edges: [(length_m, speed_kph)]
    total_s = 0.0
    for length_m, speed_kph in path_edges:
        v_mps = max(1.0, speed_kph/3.6)
        total_s += length_m / v_mps
    return total_s
```

### `app/routers/routing.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.database import get_session
from db.models import Place, Segment
from geo.graph import build_graph, dijkstra
from geo.eta import eta_seconds

router = APIRouter()

@router.get("/route")
async def route(origin_id: int, dest_id: int, session: AsyncSession = Depends(get_session)):
    segs = (await session.execute(select(Segment))).scalars().all()
    g = build_graph([(s.a_place_id, s.b_place_id, s.length_m, s.speed_kph) for s in segs])
    r = dijkstra(g, origin_id, dest_id)
    if not r: raise HTTPException(404, "no path")
    path, dist_m = r
    # assemble edge speeds
    idx = {(s.a_place_id,s.b_place_id): (s.length_m, s.speed_kph) for s in segs}
    idx.update({(s.b_place_id,s.a_place_id): (s.length_m, s.speed_kph) for s in segs})
    edges = [(idx[(path[i],path[i+1])]) for i in range(len(path)-1)]
    eta_s = eta_seconds(edges)
    return {"path": path, "distance_m": dist_m, "eta_seconds": int(eta_s)}
```

### `app/routers/geo.py` (reverse geocode)

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.database import get_session
from db.models import Place
import math

router = APIRouter()

def hav(lat1, lon1, lat2, lon2):
    R=6371000.0
    p1=math.radians(lat1); p2=math.radians(lat2)
    dphi=math.radians(lat2-lat1); dl=math.radians(lon2-lon1)
    a=math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(a))

@router.get("/reverse")
async def reverse(lat: float, lon: float, limit: int = 5, session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(Place))
    places = res.scalars().all()
    ranked = sorted(places, key=lambda p: hav(lat,lon,p.lat,p.lon))
    out = [{"id":p.id,"name":p.name,"lat":p.lat,"lon":p.lon} for p in ranked[:limit]]
    return {"candidates": out}
```

### `app/routers/ws.py` (live positions)

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as redis, os, json

router = APIRouter()
r = redis.from_url(os.getenv("REDIS_URL","redis://localhost:6379/0"))
STREAM="maps.position.update"

@router.websocket("/ws/live")
async def live(ws: WebSocket):
    await ws.accept()
    group, consumer = "maps", "ws1"
    try: await r.xgroup_create(STREAM, group, id="$", mkstream=True)
    except Exception: pass
    try:
        while True:
            xs = await r.xreadgroup(group, consumer, {STREAM: ">"}, count=50, block=5000)
            for _, msgs in xs or []:
                for msg_id, data in msgs:
                    await ws.send_json(json.loads(data["payload"]))
                    await r.xack(STREAM, group, msg_id)
    except WebSocketDisconnect:
        return
```

### `streaming/position_worker.py` (ingest positions → WS)

```python
import asyncio, os, json, random, redis.asyncio as redis
r = redis.from_url(os.getenv("REDIS_URL","redis://localhost:6379/0"))

async def main():
    # demo synthetic positions for vehicle ids 1..5
    points = {i: {"lat": 12.9+random.random()/100, "lon": 77.5+random.random()/100} for i in range(1,6)}
    while True:
        for vid, p in points.items():
            p["lat"] += (random.random()-0.5)/1000
            p["lon"] += (random.random()-0.5)/1000
            await r.xadd("maps.position.update", {"payload": json.dumps({"vehicle_id": vid, "pos": p})})
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
```

### `app/main.py` (wire)

```python
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.routers import public, geo, routing, analytics, ws

app = FastAPI(title="VEZEPyMaps")
app.include_router(public.router, tags=["public"])
app.include_router(geo.router, prefix="/geo", tags=["geo"])
app.include_router(routing.router, prefix="/routing", tags=["routing"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(ws.router, tags=["ws"])

app.mount("/static", StaticFiles(directory="app/ui/static"), name="static")
app.state.tpl = Jinja2Templates(directory="app/ui/templates")

@app.get("/health")
async def health(): return {"status":"ok"}
```

*(Add `public.py` and simple Jinja templates for `/` & dashboards.)*

### CI, Docker, tests, runbook

* **Dockerfile** like earlier.
* **CI** like earlier.
* **tests/test\_health.py** basic check.
* **ops/runbook.md**:

  ```bash
  pip install -e .[dev]
  alembic upgrade head
  uvicorn app.main:app --reload
  python streaming/position_worker.py
  # Try:
  curl 'http://localhost:8000/geo/reverse?lat=12.97&lon=77.59'
  curl 'http://localhost:8000/routing/route?origin_id=1&dest_id=42'
  # Connect WS: ws://localhost:8000/ws/live
  ```

---
