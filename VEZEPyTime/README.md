---

#VEZEPyQuantumTime — Quantum + Relativity Simulation Hub

**Use-cases:**

* Quantum circuit simulation (single/multi-qubit, basic gates, measurement)
* Time dilation & relativistic calculators (SR/GR approximations)
* “Quantum-time sandbox” experiments (param sweeps, Monte-Carlo)
* Live visual stream (WS) of amplitudes and Bloch vectors
* Scenario library & results registry (reproducibility)

## Architecture

* **Gateway/UI:** FastAPI + Jinja2 (experiments UI, circuit editor, results dashboards); WebSocket `/ws/live` for simulation frames.
* **Services:** `circuits`, `relativity`, `experiments`, `results`, `compute` (workers).
* **Streaming:** Redis Streams: `qt.experiment.submitted`, `qt.sim.frame`, `qt.sim.finished`, `qt.error`.
* **Data:** Postgres (circuits, runs, frames, artifacts), object store (optional) for plots; Redis (cache/streams).
* **ML/Compute:** NumPy-based state-vector simulator; Monte-Carlo sampling; simple GR approximations; anomaly detection on runs (sklearn).
* **Security:** OIDC stub, JWT, RBAC (`researcher`, `viewer`, `admin`); audit events.
* **Obs:** OTEL traces; Prometheus metrics (run time, frames/sec, queue depth).

## Repo layout

```
VEZEPyQuantumTime/
├─ pyproject.toml
├─ Dockerfile
├─ .github/workflows/ci.yml
├─ app/
│  ├─ main.py
│  ├─ ui/templates/{base.html,index.html,run.html}
│  └─ routers/{public.py,circuits.py,relativity.py,experiments.py,ws.py}
├─ db/
│  ├─ database.py
│  ├─ models.py
│  └─ migrations/
├─ qt/
│  ├─ circuits.py        # gate ops, compose, simulate
│  ├─ relativity.py      # SR time dilation, gravitational approx
│  ├─ frames.py          # frame encoding for WS
│  └─ ml_anomaly.py      # optional run anomaly score
├─ streaming/
│  ├─ producer.py
│  └─ sim_worker.py      # consumes experiments, emits frames
├─ ops/runbook.md
└─ tests/test_health.py
```

## Key files

### `pyproject.toml`

```toml
[project]
name = "veze-quantumtime"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115", "uvicorn[standard]>=0.30", "jinja2>=3.1",
  "pydantic>=2.8", "SQLAlchemy>=2.0", "asyncpg>=0.29", "alembic>=1.13",
  "redis>=5.0", "numpy>=1.26", "scikit-learn>=1.5",
  "prometheus-client>=0.20", "opentelemetry-sdk>=1.27.0",
  "opentelemetry-instrumentation-fastapi>=0.48b0",
  "opentelemetry-exporter-otlp>=1.27.0"
]
[project.optional-dependencies]
dev = ["ruff>=0.5","black>=24.8","mypy>=1.11","pytest>=8.3","pytest-asyncio>=0.23"]
```

### `db/models.py`

```python
from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, JSON, Float, LargeBinary

class Base(DeclarativeBase): ...

class Circuit(Base):
    __tablename__ = "circuits"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(140), unique=True)
    qubits: Mapped[int]
    gates_json: Mapped[dict] = mapped_column(JSON)   # [{op:"H", target:0}, ...]

class Experiment(Base):
    __tablename__ = "experiments"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(40))    # "quantum" | "relativity"
    params: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    submitted_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    result_id: Mapped[int | None]

class Frame(Base):
    __tablename__ = "frames"
    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int]
    step: Mapped[int]
    payload: Mapped[bytes] = mapped_column(LargeBinary)  # np array serialized
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class Result(Base):
    __tablename__ = "results"
    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int]
    metrics: Mapped[dict] = mapped_column(JSON)      # {fidelity, duration_ms, anomaly}
    artifact_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
```

### `qt/circuits.py` (tiny state-vector sim)

```python
import numpy as np

H = (1/np.sqrt(2))*np.array([[1,1],[1,-1]], dtype=complex)
X = np.array([[0,1],[1,0]], dtype=complex)
Z = np.array([[1,0],[0,-1]], dtype=complex)
I = np.eye(2, dtype=complex)

def kron_n(op, target, n):
    ops = [I]*n; ops[target] = op
    out = ops[0]
    for k in ops[1:]: out = np.kron(out, k)
    return out

def apply_gate(state, op, target, n):
    U = kron_n(op, target, n)
    return U @ state

def cnot(state, control, target, n):
    # build projector form
    zero = np.array([[1,0],[0,0]], dtype=complex)
    one  = np.array([[0,0],[0,1]], dtype=complex)
    P0 = kron_n(zero, control, n)
    P1 = kron_n(one,  control, n)
    X_t = kron_n(X, target, n)
    U = P0 + P1 @ X_t
    return U @ state

def run_circuit(qubits:int, gates:list[dict[str,object]]):
    state = np.zeros((2**qubits,), dtype=complex); state[0] = 1.0+0j
    for step, g in enumerate(gates, start=1):
        op = g["op"].upper()
        if op=="H": state = apply_gate(state, H, int(g["target"]), qubits)
        elif op=="X": state = apply_gate(state, X, int(g["target"]), qubits)
        elif op=="Z": state = apply_gate(state, Z, int(g["target"]), qubits)
        elif op=="CNOT": state = cnot(state, int(g["control"]), int(g["target"]), qubits)
        yield step, state
```

### `qt/relativity.py` (SR/GR approximations)

```python
import math
C = 299_792_458.0

def time_dilation_sr(t_proper: float, v: float) -> float:
    gamma = 1.0/math.sqrt(1.0 - (v*v)/(C*C))
    return gamma * t_proper

def gravitational_time_dilation(t_proper: float, M: float, r: float, G: float = 6.674e-11) -> float:
    # Schwarzschild outside a non-rotating mass (approx). t_far = t_proper / sqrt(1 - 2GM/(rc^2))
    factor = math.sqrt(1.0 - (2*G*M)/(r*C*C))
    return t_proper / max(factor, 1e-9)
```

### `streaming/sim_worker.py`

```python
import asyncio, json, os, redis.asyncio as redis, numpy as np, pickle, time
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import update, select
from db.models import Experiment, Frame, Result
from qt.circuits import run_circuit
from qt.relativity import time_dilation_sr, gravitational_time_dilation

REDIS_URL = os.getenv("REDIS_URL","redis://localhost:6379/0")
DATABASE_URL = os.getenv("DATABASE_URL","postgresql+asyncpg://user:pass@localhost:5432/veze_qt")
r = redis.from_url(REDIS_URL)
engine = create_async_engine(DATABASE_URL)
Session = async_sessionmaker(engine, expire_on_commit=False)

async def main():
    group, consumer = "qt", "sim1"
    try: await r.xgroup_create("qt.experiment.submitted", group, id="$", mkstream=True)
    except Exception: pass
    while True:
        xs = await r.xreadgroup(group, consumer, {"qt.experiment.submitted":">"}, count=10, block=5000)
        for _, msgs in xs or []:
            for msg_id, data in msgs:
                payload = json.loads(data["payload"])
                exp_id = payload["experiment_id"]
                t0 = time.time()
                try:
                    async with Session() as s:
                        res = await s.execute(select(Experiment).where(Experiment.id==exp_id))
                        exp = res.scalars().first()
                        if not exp: raise RuntimeError("missing experiment")
                        if exp.kind == "quantum":
                            q = exp.params["qubits"]; gates = exp.params["gates"]
                            step = 0
                            for step, state in run_circuit(q, gates):
                                f = Frame(experiment_id=exp_id, step=step, payload=pickle.dumps(state))
                                s.add(f); await s.commit()
                                await r.xadd("qt.sim.frame", {"payload": json.dumps({"experiment_id": exp_id, "step": step})})
                            metrics = {"steps": step, "duration_ms": int(1000*(time.time()-t0))}
                        else:
                            t = exp.params["t"]; v = exp.params.get("v", 0); M = exp.params.get("M"); r_m = exp.params.get("r")
                            if M and r_m: dil = gravitational_time_dilation(t, M, r_m)
                            else: dil = time_dilation_sr(t, v)
                            metrics = {"dilated_t": dil, "duration_ms": int(1000*(time.time()-t0))}
                        result = Result(experiment_id=exp_id, metrics=metrics, artifact_urls=[])
                        s.add(result); await s.commit(); exp.status="finished"; exp.result_id=result.id; await s.commit()
                    await r.xadd("qt.sim.finished", {"payload": json.dumps({"experiment_id": exp_id})})
                except Exception as e:
                    await r.xadd("qt.error", {"payload": json.dumps({"experiment_id": exp_id, "error": str(e)})})
                await r.xack("qt.experiment.submitted", group, msg_id)

if __name__ == "__main__":
    asyncio.run(main())
```

### `app/routers/experiments.py` (submit & view)

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.database import get_session
from db.models import Experiment, Result
from streaming.producer import emit

router = APIRouter()

@router.post("/experiments/quantum", status_code=202)
async def submit_quantum(qubits:int, gates:list[dict], session: AsyncSession = Depends(get_session)):
    exp = Experiment(kind="quantum", params={"qubits":qubits,"gates":gates})
    session.add(exp); await session.commit(); await session.refresh(exp)
    await emit("qt.experiment.submitted", {"experiment_id": exp.id})
    return {"experiment_id": exp.id, "status": "queued"}

@router.post("/experiments/relativity", status_code=202)
async def submit_rel(t: float, v: float | None = None, M: float | None = None, r: float | None = None, session: AsyncSession = Depends(get_session)):
    params = {"t":t}; 
    if v is not None: params["v"]=v
    if M is not None and r is not None: params["M"]=M; params["r"]=r
    exp = Experiment(kind="relativity", params=params)
    session.add(exp); await session.commit(); await session.refresh(exp)
    await emit("qt.experiment.submitted", {"experiment_id": exp.id})
    return {"experiment_id": exp.id, "status":"queued"}

@router.get("/results/{experiment_id}")
async def get_result(experiment_id: int, session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(Result).where(Result.experiment_id==experiment_id))
    r = res.scalars().first()
    return {"result": r.metrics if r else None}
```

### `app/routers/ws.py` (frames → browser)

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as redis, os, json

router = APIRouter()
r = redis.from_url(os.getenv("REDIS_URL","redis://localhost:6379/0"))

@router.websocket("/ws/live")
async def ws_live(ws: WebSocket, experiment_id: int):
    await ws.accept()
    group, consumer = f"ws{experiment_id}", "c1"
    stream = "qt.sim.frame"
    try:
        await r.xgroup_create(stream, group, id="$")
    except Exception: pass
    try:
        while True:
            xs = await r.xreadgroup(group, consumer, {stream: ">"}, count=20, block=5000)
            for _, msgs in xs or []:
                for msg_id, data in msgs:
                    ev = json.loads(data["payload"])
                    if ev["experiment_id"] == experiment_id:
                        await ws.send_json(ev)
                    await r.xack(stream, group, msg_id)
    except WebSocketDisconnect:
        return
```

### `app/main.py` (wire)

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers import public, circuits, relativity, experiments, ws

app = FastAPI(title="VEZEPyQuantumTime")
app.include_router(public.router, tags=["public"])
app.include_router(circuits.router, prefix="/circuits", tags=["circuits"])
app.include_router(relativity.router, prefix="/relativity", tags=["relativity"])
app.include_router(experiments.router, tags=["experiments"])
app.include_router(ws.router, tags=["ws"])

app.mount("/static", StaticFiles(directory="app/ui/static"), name="static")
tpl = Jinja2Templates(directory="app/ui/templates")
app.state.tpl = tpl

@app.get("/health")
async def health(): return {"status":"ok"}
```

*(Add simple `public.py` and templates similar to prior services.)*

### `streaming/producer.py`

```python
import redis.asyncio as redis, os, json
r = redis.from_url(os.getenv("REDIS_URL","redis://localhost:6379/0"))
async def emit(kind: str, payload: dict): await r.xadd(kind, {"payload": json.dumps(payload)})
```

### CI, Docker, tests, runbook

* **CI**: same matrix pattern; ruff → mypy → pytest → SBOM.
* **Dockerfile**: uvicorn app.
* **tests/test\_health.py**: simple health check.
* **ops/runbook.md**:

  ```bash
  pip install -e .[dev]
  alembic upgrade head
  uvicorn app.main:app --reload
  python streaming/sim_worker.py
  # Submit:
  curl -X POST 'http://localhost:8000/experiments/quantum?qubits=2' \
       -H 'Content-Type: application/json' -d '[{"op":"H","target":0},{"op":"CNOT","control":0,"target":1}]'
  ```

---
