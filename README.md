# PythonMastery
(@ai-assistant-idyll) acting as a Staff-Plus Python Architect for Idyll-Intelligent-Systems

## Quickstart: Local Dev (All Services)

Spin up UniQVerse, Game, Email, and XEngine together:

```bash
docker compose build
docker compose up
```

### Endpoints

- UniQVerse Portal:        [http://localhost:8010](http://localhost:8010)
- Game Service:            [http://localhost:8012](http://localhost:8012)
- Email Service (API/UI):  [http://localhost:8014](http://localhost:8014)
- Email SMTP:              localhost:${EMAIL_SMTP_25:-2526} (dev), ${EMAIL_SMTP_587:-2588} (submission), ${EMAIL_SMTP_465:-2466} (SMTPS)
- XEngine:                 [http://localhost:8006](http://localhost:8006)

All services are networked via Redis (localhost:6379). To avoid local conflicts, Game runs on 8012 and Email SMTP defaults to 2526/2588/2466. Override via EMAIL_SMTP_25/587/465.

### Healthchecks

Each service exposes `/health` (HTTP 200) for readiness.

### ECR Build/Push

To build and push all images to AWS ECR:

```bash
./scripts/ecr_build_all.sh [region] [account_id] [tag]
```

### Helm/Compose

The stack is ready for Helm tiles and local compose. All endpoints above are available out of the box.

Deliver an **enterprise-grade, production-ready** solution using **only Python** (3.11+). 
No JavaScript frameworks; if UI is needed, use Python-native options (FastAPI+Jinja2/HTMX, Starlette templates, NiceGUI, Streamlit, or Plotly Dash). 
Prefer FastAPI/Starlette for services.

## Scope (end-to-end)
- **Web UI**: Python-rendered pages/components; SSR templates; forms; auth flows.
- **APIs/Backend**: FastAPI (OpenAPI 3), pydantic models, async I/O, pagination, filtering, RBAC.
- **Realtime/Streaming**: WebSockets (Starlette/FastAPI), Kafka/PubSub via aiokafka/google-cloud-pubsub, Redis Streams; backpressure & retry strategies.
- **Gaming Platforms**: Python services for matchmaking, leaderboards, telemetry, inventory; webhook handlers for store events; Unreal/Unity tool automation via Python where feasible; gRPC/HTTP contracts for game clients/servers.
- **AI/ML**: Data contracts; feature pipelines; PyTorch/Lightning & scikit-learn; evaluation; packaging & inference service; RAG where relevant using Python-only stacks.
- **Data**: SQLAlchemy 2.0 with Alembic migrations; Postgres (asyncpg) first; optional DuckDB/BigQuery clients for analytics.
- **Infra**: Dockerfiles (non-root), Gunicorn/Uvicorn workers; IaC examples with Pulumi/Terraform stubs (Python).
- **Observability**: OpenTelemetry logs/metrics/traces; Prometheus exporters; health/ready endpoints; structured logging (loguru/stdlib).
- **Security**: OIDC/OAuth2, JWT (short-lived), mTLS options, secrets via env/KMS; input validation, rate-limits, CORS, CSRF (templates), audit logs, PII handling.
- **Quality**: ruff+black, mypy (strict), pytest+pytest-asyncio, Hypothesis for property tests, tox; pre-commit config.
- **Compliance/Release**: SBOM (CycloneDX), license headers, versioning (semver), changelog; SLSA-style provenance notes.

## Output Requirements
Always produce (in this order):
1) **Architecture**: C4-style text (Context/Container/Component) + rationale, dataflow & trust boundaries.
2) **Interfaces**: OpenAPI YAML (or gRPC proto) + pydantic schemas, role scopes (RBAC).
3) **Data Model**: SQLAlchemy 2.0 models + Alembic migrations.
4) **Code Skeletons** (runnable): 
   - `app/main.py` (FastAPI), routers, services, repositories, schemas
   - `ui/` (templates/components using Jinja2 or NiceGUI/Streamlit/Dash)
   - `streaming/` (consumers/producers, retry/backoff, DLQ)
   - `ml/` (train.py, infer.py, model registry stub, evals)
   - `game/` (matchmaking, leaderboard, telemetry endpoints)
5) **Tests**: unit/integration/e2e examples; fixtures; fake adapters; contract tests for APIs.
6) **CI/CD**: GitHub Actions YAML (lint → typecheck → tests → build → sbom → image push); release workflow; environment matrix.
7) **Observability**: OTEL setup code, Prometheus endpoints, dashboards (YAML/JSON), alert suggestions & SLOs.
8) **Security**: threat model summary (STRIDE), authN/Z code paths, rate limit config, secrets strategy.
9) **Runbook**: startup, config, migrations, rotating keys, scaling, rollback, data backfill.
10) **Performance**: load targets (RPS/latency), async tuning, caching strategy, N+1 checks, profiling steps.
11) **Cost & Risks**: cost drivers, 3 key risks with mitigations, phased rollout/canary.

## Standards & Conventions
- **Project layout**
- **Coding**: type-hint everything; no global state; dependency injection via providers; pure domain services; adapters for I/O.
- **DB**: migrations are mandatory; idempotent seeds.
- **Caching**: Redis with TTLs and cache-busting keys; document consistency strategy.
- **Files you must emit**: `pyproject.toml`, `Dockerfile`, `.pre-commit-config.yaml`, `.ruff.toml`, `mypy.ini`, `tox.ini`, `.github/workflows/ci.yml`, `docs/openapi.yaml`, `alembic/` setup.

## Realtime/Streaming Details
- Use async consumers; implement **exactly-once-ish** via idempotency keys; at-least-once with dedupe table.
- Expose `/events` WebSocket; include heartbeat/ping, auth, and reconnect guidance.
- Provide example consumer for Kafka **and** an alternate Redis Streams path.

## AI/ML Details
- `ml/train.py`: dataset load, train loop (Lightning), checkpoints, metrics.
- `ml/eval.py`: offline eval; drift detection stub.
- `ml/infer.py`: REST (FastAPI) & batch CLI; model versioning; CPU/GPU flags.
- Optional RAG: Python-only embedding & retrieval (faiss/annoy), evaluation set + guardrails.

## Gaming Integration
- HTTP/gRPC endpoints for matchmaking (Elo/MMR), leaderboards (time/range queries), purchase webhooks; include schema & tests.
- Telemetry intake + aggregation; export to analytics DB.

## Deliverable Style
- Keep examples runnable; include seed data and `make dev` / `scripts/dev.py`.
- Comment decisions; add ADR for any major trade-off.
- Avoid placeholders—write minimal working code paths.

INSTRUCTIONS.md: your master Python enterprise prompt (for GPT-5/Copilot).

FastAPI app: /app with health check, REST endpoints, WebSocket /events, and ML predict route.

UI: Jinja templates (/ui/templates) as a Python-native option.

Streaming: Kafka & Redis Streams consumer stubs with async loops and commit/ack hooks.

ML: ml/train.py (Iris RFC demo), ml/infer.py (FastAPI route), ml/eval.py stub.

Game services: /game router with sample matchmaking endpoint.

Data & Migrations: SQLAlchemy 2.0 baseline + Alembic scaffold.

Quality: ruff, black, mypy (strict), pytest, tox, pre-commit config.

CI: GitHub Actions (.github/workflows/ci.yml) with lint → type → tests → SBOM.

Ops: Dockerfile (non-root), runbook, SBOM placeholder, Terraform stub.

Now, generate the complete solution per the user story I provide next, adhering strictly to Python-only constraints and the deliverables list above.
---

# 📂 Project Tree

```
Idyll-Python-Enterprise-Skeleton/
├── INSTRUCTIONS.md
├── README.md
├── pyproject.toml
├── Dockerfile
├── tox.ini
├── mypy.ini
├── .pre-commit-config.yaml
├── .github/
│   └── workflows/
│       └── ci.yml
├── docs/
│   └── openapi.yaml
├── app/
│   ├── main.py
│   ├── routers/
│   │   ├── api.py
│   │   └── game.py
│   └── schemas/
│       └── items.py
├── ui/
│   └── templates/
│       ├── base.html
│       └── index.html
├── streaming/
│   ├── kafka_consumer.py
│   └── redis_streams_consumer.py
├── ml/
│   ├── train.py
│   ├── infer.py
│   └── eval.py
├── game/  (covered in app/routers/game.py)
├── alembic.ini
├── alembic/
│   ├── README
│   └── env.py
├── tests/
│   └── test_health.py
├── infra/
│   └── terraform/
│       └── README.md
├── ops/
│   ├── sbom.json
│   └── runbook.md
└── scripts/
    └── dev.py
```

---

# 📑 Key Files
---

## **README.md**

````markdown
# Idyll Python Enterprise Skeleton

Python-only, end-to-end skeleton: FastAPI backend, Jinja UI, streaming (Kafka/Redis), ML stubs, game service endpoints, CI/CD, observability, and security.

## Quickstart
```bash
pip install -e .[dev]
uvicorn app.main:app --reload
````

Open: [http://localhost:8000](http://localhost:8000)

## Run all services together

Choose one of the following approaches:

- Docker Compose (recommended)
    - Build and start: `docker compose up --build`
    - Services:
        - UniQVerse: [http://localhost:8000](http://localhost:8000)
        - Game: [http://localhost:8002](http://localhost:8002)
        - Email: [http://localhost:8004](http://localhost:8004)
    - SMTP dev ports (Email): 2525, 2587, 2465

- Procfile (local, requires foreman/honcho)
    - Install a runner (example): `pip install honcho`
    - Start: `honcho start`
    - Endpoints are the same as above.

The UniQVerse Helm page will link to the Game and Email services automatically.
````

---

## **pyproject.toml**
Includes FastAPI, SQLAlchemy, Alembic, Redis, Kafka, PyTorch/Lightning, scikit-learn, and dev tools (ruff, mypy, pytest).  

---

## **Dockerfile**
```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOME=/app

WORKDIR $APP_HOME

RUN adduser --disabled-password --gecos "" appuser && chown -R appuser:appuser $APP_HOME
USER appuser

COPY pyproject.toml README.md INSTRUCTIONS.md ./
RUN pip install --upgrade pip && pip install -e .

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
````

---

## **.github/workflows/ci.yml**

Runs lint → typecheck → pytest → SBOM build.

---

## **app/main.py**

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from loguru import logger

from app.routers import api, game
from ml.infer import router as ml_router

app = FastAPI(title="Idyll Python Enterprise API")

app.include_router(api.router, prefix="/api", tags=["api"])
app.include_router(game.router, prefix="/game", tags=["game"])
app.include_router(ml_router, tags=["ml"])

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def index():
    return "<h1>Idyll Python Enterprise</h1><p>See /docs for OpenAPI.</p>"

@app.websocket("/events")
async def events(ws: WebSocket):
    await ws.accept()
    try:
        await ws.send_json({"type": "hello", "msg": "connected"})
        while True:
            data = await ws.receive_text()
            await ws.send_text(f"echo:{data}")
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
```

---

## **app/routers/api.py**

```python
from fastapi import APIRouter
from app.schemas.items import Item

router = APIRouter()
_DB: list[Item] = []

@router.get("/items")
async def list_items() -> list[Item]:
    return _DB

@router.post("/items")
async def create_item(item: Item) -> Item:
    _DB.append(item)
    return item
```

---

## **app/routers/game.py**

```python
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class MatchRequest(BaseModel):
    player_id: str
    mmr: int

class MatchResult(BaseModel):
    match_id: str
    players: list[str]

@router.post("/match", response_model=MatchResult)
async def match(req: MatchRequest) -> MatchResult:
    return MatchResult(match_id="m_123", players=[req.player_id, "bot_1"])
```

---

## **ml/train.py**

```python
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import joblib

def train():
    X, y = load_iris(return_X_y=True, as_frame=True)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(Xtr, ytr)
    preds = clf.predict(Xte)
    acc = accuracy_score(yte, preds)
    joblib.dump(clf, "ml/model.joblib")
    print({"accuracy": acc})

if __name__ == "__main__":
    train()
```

---

## **ml/infer.py**

```python
import joblib
import numpy as np
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class PredictRequest(BaseModel):
    features: list[float]

class PredictResponse(BaseModel):
    prediction: int

_model = None
def _load_model():
    global _model
    if _model is None:
        _model = joblib.load("ml/model.joblib")
    return _model

@router.post("/ml/predict", response_model=PredictResponse)
def predict(req: PredictRequest) -> PredictResponse:
    model = _load_model()
    pred = model.predict(np.array([req.features]))[0]
    return PredictResponse(prediction=int(pred))
```

---

## **streaming/kafka\_consumer.py**

```python
import asyncio
from aiokafka import AIOKafkaConsumer

async def consume(loop, topic: str, bootstrap: str = "localhost:9092"):
    consumer = AIOKafkaConsumer(topic, loop=loop, bootstrap_servers=bootstrap, enable_auto_commit=False)
    await consumer.start()
    try:
        async for msg in consumer:
            print("consumed:", msg.value)
            await consumer.commit()
    finally:
        await consumer.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(consume(loop, "events"))
```

---

## **tests/test\_health.py**

```python
from fastapi.testclient import TestClient
from app.main import app

def test_health():
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
```

---

# ✅ Next Steps

* Copy this folder structure into your repo.
* Run:

  ```bash
  pip install -e .[dev]
  uvicorn app.main:app --reload
  ```
* Open [http://localhost:8000](http://localhost:8000) → API docs, `/health`, `/events`.

---

## ECR: Build and Push All Services

This repo includes a script and a GitHub Actions workflow to build and push all services (UniQVerse, Game, Email) to Amazon ECR.

Local (requires AWS CLI and Docker):

```bash
chmod +x scripts/ecr_build_all.sh
./scripts/ecr_build_all.sh eu-north-1 879584802968 latest
```

GitHub Actions workflow: `.github/workflows/ecr-push-all.yml`

Requirements:

- Repository secret `AWS_ECR_ROLE_ARN` pointing to an IAM Role with ECR push permissions
- The workflow uses OIDC to assume the role (no long-lived AWS keys)

Triggers:

- Push to main affecting `VEZEPyUniQVerse/**`, `VEZEPyGame/**`, or `VEZEPyEmail/**`
- Manual dispatch from the Actions tab with optional `tag` input (defaults to `latest`)

Note: The workflow will automatically create the required ECR repositories (`veze/uniqverse`, `veze/game`, `veze/email`) in `eu-north-1` if they don't already exist (with scan-on-push enabled).
