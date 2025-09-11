# VEZEPyWeb — End-to-End Python System

## 1) High-level architecture (C4-in-brief)

* **Context:** A unified site for Idyll-Intelligent-Systems to manage users, content, payments, realtime events, ML inference, and game services.
* **Containers (all Python):**

  * **Web/API Gateway** (FastAPI + Jinja2 or NiceGUI): serves UI + OpenAPI, terminates auth, fans out to internal services.
  * **Core Domain Service** (FastAPI): users, items, orders, payments, RBAC.
  * **Streaming Workers** (asyncio): consumers for Kafka *or* Redis Streams; event fan-out to WebSocket clients.
  * **ML Service** (FastAPI): model registry, training jobs (batch), online inference, RAG-ready hooks.
  * **Game Platform Service** (FastAPI): matchmaking, leaderboards, telemetry intake.
  * **Admin/Analytics UI** (Jinja2/NiceGUI/Plotly Dash): operational dashboards (metrics, traces, events, sales, churn).
  * **Data:** Postgres (SQLAlchemy 2.0 + Alembic), Redis (cache, sessions, streams), optional DuckDB for local analytics.
  * **Observability:** OpenTelemetry exporters + Prometheus client, structured logs.
* **Trust boundaries:** public web ↔ gateway (auth), gateway ↔ internal services (mTLS optional), services ↔ DB/Redis (network policies).

## 2) Tech choices (Python-only)

* **Framework:** FastAPI/Starlette (async), Jinja2/NiceGUI for UI, WebSocket for realtime.
* **Data:** SQLAlchemy 2.0 ORM, Alembic migrations, asyncpg, Redis 5.
* **Streaming:** aiokafka *or* Redis Streams (choose one per environment, keep both adapters).
* **ML:** scikit-learn + PyTorch/Lightning (optional), joblib model registry on disk/S3-like; faiss (optional) for vector search.
* **Auth:** OAuth2/OIDC via `authlib` (Python), JWT (short-lived), refresh via secure cookies; CSRF for forms.
* **Quality:** ruff, black, mypy(strict), pytest + pytest-asyncio, Hypothesis.
* **Ops:** Dockerfile (non-root), GitHub Actions CI, CycloneDX SBOM, OpenTelemetry, Prometheus.
* **No JS frameworks**—all UI rendered/interactive by Python (Jinja2 + HTMX-style snippets or NiceGUI/Plotly Dash).

## 3) Repository layout

```
VEZEPyWeb/
├─ INSTRUCTIONS.md                # your operator prompt for GPT-5
├─ pyproject.toml                 # deps (fastapi, sqlalchemy, redis, aiokafka, sklearn, torch…)
├─ Dockerfile
├─ .github/workflows/ci.yml
├─ docs/                          # openapi.yaml, ADRs, runbook, SLOs
│  ├─ openapi.yaml
│  └─ adr-0001-architecture.md
├─ config/
│  ├─ settings.py                 # Pydantic settings for env vars
│  └─ logging.py
├─ app/                           # Gateway (+ UI)
│  ├─ main.py                     # mounts routers & subapps, OTEL, metrics
│  ├─ deps.py
│  ├─ auth.py                     # oauth2/oidc, jwt, csrf
│  ├─ ui/                         # Jinja2/NiceGUI pages
│  │  ├─ templates/
│  │  │  ├─ base.html
│  │  │  ├─ home.html
│  │  │  └─ admin.html
│  │  └─ views.py
│  ├─ routers/
│  │  ├─ public.py                # health, status, docs index
│  │  ├─ users.py                 # profile, sessions
│  │  ├─ items.py                 # catalog
│  │  ├─ orders.py                # checkout/payments (webhooks)
│  │  ├─ ws.py                    # /events websocket
│  │  └─ admin.py                 # admin APIs
│  └─ security/
│     └─ rbac.py
├─ services/
│  ├─ core/                       # domain microservice (can be mounted or separate proc)
│  │  ├─ api.py
│  │  ├─ models.py                # SQLAlchemy models
│  │  ├─ repo.py
│  │  ├─ schemas.py               # pydantic
│  │  └─ migrations/ (alembic)
│  ├─ ml/
│  │  ├─ api.py                   # /ml/predict, /ml/models
│  │  ├─ train.py                 # offline training job
│  │  ├─ eval.py
│  │  └─ registry.py              # load/save model
│  └─ game/
│     ├─ api.py                   # matchmaking, leaderboards, telemetry
│     └─ mmr.py
├─ streaming/
│  ├─ kafka_consumer.py
│  ├─ redis_consumer.py
│  └─ producers.py
├─ data/
│  └─ seeds.py
├─ infra/
│  ├─ docker-compose.dev.yml      # local postgres+redis (optional)
│  └─ terraform/                  # stubs for cloud db/redis/run
├─ ops/
│  ├─ runbook.md
│  ├─ dashboards/                 # grafana/json, alerts
│  └─ sbom.json
└─ tests/
   ├─ test_health.py
   ├─ test_api_items.py
   └─ test_ml_predict.py
```

## 4) Core domain models (minimum set)

* `User(id, email, display_name, roles[], created_at)`
* `Item(id, name, price, stock, tags[], created_at)`
* `Order(id, user_id, total, status, created_at)`
* `Event(id, type, payload_json, created_at)` (audit/event log)
* `ModelVersion(id, name, path, metrics_json, created_at)`
* `Match(id, participants[], created_at)` and `Leaderboard(id, season, entries[])`

## 5) Key endpoints & realtime

**Gateway (FastAPI):**

* `GET /health`
* `GET /` (Jinja2: home), `GET /admin` (protected)
* `GET /api/items`, `POST /api/items`, `POST /api/orders/checkout`
* `WS /events`: authenticated live feed (ping/heartbeat, reconnect token)

**ML Service:**

* `POST /ml/predict` → `{"features":[...]}` → `{"prediction": ...}`
* `POST /ml/train` (admin-only) → kicks off offline job; updates `ModelVersion`

**Game Service:**

* `POST /game/match` → returns match\_id & roster
* `GET /game/leaderboard?season=...`
* `POST /game/telemetry` (bulk events, rate-limited)

**Streaming:**

* Consumers read `{topic: events}`; write to DB + push to WebSocket rooms
* Retry/backoff, DLQ stream (Redis `X` stream or Kafka `_dlq`)

## 6) Security (Python)

* **OIDC/OAuth2** with `authlib`: login via provider; session cookie (HttpOnly, SameSite=Lax) storing a short-lived session ID; backend keeps session → user mapping in Redis.
* **JWT** for API tokens (short TTL, rotated signing keys).
* **RBAC**: roles `admin`, `editor`, `user` enforced by dependencies (`Depends()`).
* **CSRF**: double-submit cookie for form POSTs (Jinja forms).
* **Rate limits**: simple `redis` counters on auth-sensitive routes.
* **PII**: minimize fields, audit logs via `Event`.

## 7) Observability

* **OpenTelemetry** FastAPI instrumentation → OTLP exporter
* **Prometheus** metrics: request latency, WS connections, consumer lag gauges
* **Dashboards**: request p95, error rate, consumer lag, GPU/CPU for ML

## 8) CI/CD (GitHub Actions)

* Jobs: `lint` → `typecheck` → `tests` → `build` → `sbom`
* Optional: build & push container, deploy to Cloud Run/App Runner
* Artifacts: `sbom.json`, coverage, OpenAPI bundle

---

## 9) Minimal code glue (copy-pasteable)

### `config/settings.py`

```python
from pydantic import BaseSettings, AnyUrl

class Settings(BaseSettings):
    APP_NAME: str = "VEZEPyWeb"
    ENV: str = "dev"
    DATABASE_URL: AnyUrl = "postgresql+asyncpg://user:pass@localhost:5432/veze"
    REDIS_URL: str = "redis://localhost:6379/0"
    OIDC_ISSUER: str = "https://accounts.example"
    OIDC_CLIENT_ID: str = "veze"
    OIDC_CLIENT_SECRET: str = "change_me"
    KAFKA_BOOTSTRAP: str = "localhost:9092"
    USE_KAFKA: bool = False  # else use Redis Streams
    SECRET_KEY: str = "dev-secret-change"
    JWT_TTL_SECONDS: int = 900

    class Config:
        env_file = ".env"

settings = Settings()
```

### `app/main.py` (mount subapps, WebSocket)

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import HTMLResponse
from config.settings import settings
from app.routers import public, users, items, orders, ws, admin
from services.ml.api import router as ml_router
from services.game.api import router as game_router

app = FastAPI(title=settings.APP_NAME)

app.include_router(public.router, tags=["public"])
app.include_router(users.router, prefix="/api", tags=["users"])
app.include_router(items.router, prefix="/api", tags=["items"])
app.include_router(orders.router, prefix="/api", tags=["orders"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(ml_router, tags=["ml"])
app.include_router(game_router, prefix="/game", tags=["game"])

@app.get("/", response_class=HTMLResponse)
async def home():
    return "<h1>VEZEPyWeb</h1><p>See /docs for API</p>"
```

### `app/routers/ws.py` (broadcast hub)

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
router = APIRouter()

_connections: set[WebSocket] = set()

@router.websocket("/events")
async def events(ws: WebSocket):
    await ws.accept()
    _connections.add(ws)
    try:
        await ws.send_json({"type": "hello", "msg": "connected"})
        while True:
            data = await ws.receive_text()
            await ws.send_json({"echo": data})
    except WebSocketDisconnect:
        _connections.discard(ws)
```

### `services/ml/api.py`

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import joblib, numpy as np
from pathlib import Path

router = APIRouter()
MODEL_PATH = Path("models/latest.joblib")

class PredictRequest(BaseModel):
    features: list[float]

class PredictResponse(BaseModel):
    prediction: int

def _load():
    if not MODEL_PATH.exists():
        raise FileNotFoundError("Model not found")
    return joblib.load(MODEL_PATH)

@router.post("/ml/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    model = _load()
    pred = model.predict(np.array([req.features]))[0]
    return PredictResponse(prediction=int(pred))
```

### `services/game/api.py`

```python
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class MatchRequest(BaseModel):
    player_id: str
    mmr: int

class MatchResponse(BaseModel):
    match_id: str
    players: list[str]

@router.post("/match", response_model=MatchResponse)
def match(req: MatchRequest):
    # naive pairing
    return MatchResponse(match_id="m_1", players=[req.player_id, "bot_42"])
```

### `streaming/redis_consumer.py` (simple, Python-only)

```python
import asyncio, json
import redis.asyncio as redis

async def run():
    r = redis.from_url("redis://localhost:6379/0")
    stream = "events"
    group = "veze"
    consumer = "worker-1"
    try:
        await r.xgroup_create(stream, group, id="$", mkstream=True)
    except Exception:
        pass
    while True:
        entries = await r.xreadgroup(group, consumer, streams={stream: ">"}, count=50, block=5000)
        for _, msgs in entries or []:
            for msg_id, data in msgs:
                # TODO: write to DB / fanout to websockets
                print("event:", msg_id, data)
                await r.xack(stream, group, msg_id)

if __name__ == "__main__":
    asyncio.run(run())
```

---

## 10) Runbook (essentials)

* **Dev up:**

  ```bash
  pip install -e .[dev]
  uvicorn app.main:app --reload
  ```

  Optional local services: `docker compose -f infra/docker-compose.dev.yml up -d`
* **Migrations:** `alembic upgrade head`
* **Train a demo model:** `python services/ml/train.py` → writes `models/latest.joblib`
* **Smoke tests:** `pytest -q`
* **WS test:** connect to `ws://localhost:8000/events` and send text; receive echoes
* **Deploy:** build Docker, push, run (Cloud Run / App Runner). Export OTEL to your collector.

## 11) SLOs & risks

* **SLO:** p95 request latency < 250ms; WS uptime > 99.9%; ML predict p95 < 200ms.
* **Risks & mitigations:**

  1. **Model drift** → scheduled eval, threshold alarm, auto-rollback to previous `ModelVersion`.
  2. **Backpressure in streams** → dynamic consumer concurrency; DLQ with triage dashboard.
  3. **Auth misconfig** → OIDC verifier unit tests + staging smoke login + short JWT TTL + key rotation.

---
