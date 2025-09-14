# VEZEPyGame — End-to-End (Python Only)

## 1) Architecture (C4-in-brief)

* **Gateway & UI (FastAPI + Jinja2/NiceGUI)**: Auth, sessions, docs, admin dashboards, player portal.
* **Game Services (FastAPI microservices)**

  * **Matchmaking**: queues, ELO/MMR, party matchmaking, regions.
  * **Leaderboards**: Redis ZSET hot path + Postgres durability.
  * **Telemetry**: ingestion of client/server events, anti-cheat signals.
  * **Inventory/Store/Webhooks**: purchases, entitlements, refunds.
  * **ML Service**: skill prediction, bot detection, churn/risk scoring.
* **Streaming**: Redis Streams *or* Kafka (both adapters) for events; fan-out to websockets.
* **Data**: Postgres (SQLAlchemy 2.0 + Alembic), Redis (cache, queues, streams), optional DuckDB for offline analytics.
* **Observability**: OpenTelemetry (traces/metrics), Prometheus client, structured logs.
* **Security**: OAuth2/OIDC (`authlib`), short-lived JWT, RBAC, rate-limits, audit log.

## 2) Repository Layout

```
VEZEPyGame/
├─ INSTRUCTIONS.md
├─ pyproject.toml
├─ Dockerfile
├─ .github/workflows/ci.yml
├─ docs/
│  ├─ openapi.yaml
│  └─ adr-0001-architecture.md
├─ config/
│  ├─ settings.py
│  └─ logging.py
├─ app/                    # Gateway + UI
│  ├─ main.py
│  ├─ auth.py              # OIDC, JWT
│  ├─ ui/
│  │  ├─ templates/{base.html,admin.html,portal.html}
│  │  └─ views.py
│  └─ routers/{public.py,admin.py,ws.py}
├─ services/
│  ├─ matchmaking/
│  │  ├─ api.py
│  │  ├─ mmr.py
│  │  ├─ queue.py
│  │  └─ models.py         # SQLAlchemy models for matches
│  ├─ leaderboards/
│  │  ├─ api.py
│  │  └─ repo.py           # Redis ZSET + Postgres sync
│  ├─ telemetry/
│  │  ├─ api.py
│  │  └─ ingest_worker.py
│  ├─ inventory/
│  │  ├─ api.py
│  │  └─ webhooks.py       # store callbacks
│  └─ ml/
│     ├─ api.py            # predict_skill, detect_bot
│     ├─ train.py
│     ├─ eval.py
│     └─ registry.py
├─ streaming/
│  ├─ redis_consumer.py
│  ├─ kafka_consumer.py
│  └─ producers.py
├─ db/
│  ├─ models.py            # users, profiles, sessions, matches, purchases
│  └─ migrations/          # alembic
├─ ops/
│  ├─ runbook.md
│  ├─ dashboards/          # grafana json
│  └─ sbom.json
└─ tests/
   ├─ test_health.py
   ├─ test_matchmaking.py
   ├─ test_leaderboards.py
   └─ test_ml_predict.py
```

## 3) Data Model (SQLAlchemy 2.0 summary)

* `User(id, external_id, display_name, region, roles[], created_at)`
* `Match(id, region, mode, status, created_at, finished_at)`
* `MatchParticipant(id, match_id, user_id, team, mmr_before, mmr_after, result)`
* `Leaderboard(id, season, mode, created_at)`
* `LeaderboardEntry(id, leaderboard_id, user_id, score, rank, updated_at)`
* `Purchase(id, user_id, item_sku, amount, currency, status, provider_ref, created_at)`
* `Event(id, kind, payload_json, user_id?, created_at)`  *(audit/telemetry envelope)*
* `ModelVersion(id, name, path, metrics_json, created_at)`

## 4) Key APIs (FastAPI)

**Matchmaking**

* `POST /matchmaking/enqueue` `{user_id, mmr, mode, region, party_id?}`
* `POST /matchmaking/dequeue` `{user_id}`
* `POST /matchmaking/match` → returns `{match_id, players, teams}`
  **Leaderboards**
* `GET /leaderboards/{season}/{mode}?limit=100&offset=0`
* `POST /leaderboards/submit` `{user_id, score, season, mode}`
  **Telemetry**
* `POST /telemetry/bulk` `[ { event, ts, user_id?, payload } ... ]` (batched; rate-limited)
  **Inventory & Webhooks**
* `GET /inventory/{user_id}`
* `POST /store/webhook` (signature-verified provider callback)
  **ML**
* `POST /ml/predict_skill` `{features}` → `{skill}`
* `POST /ml/detect_bot` `{signals}` → `{is_bot, score}`

**Realtime**

* `WS /events` (rooms: region/mode/match\_id); pings + resumable tokens.

## 5) Matchmaking Core (Python-only)

**ELO/MMR update** (snippet):

```python
def elo_update(r_a: float, r_b: float, k: float, a_won: bool) -> tuple[float, float]:
    ea = 1 / (1 + 10 ** ((r_b - r_a) / 400))
    sa = 1.0 if a_won else 0.0
    sb = 1.0 - sa
    r_a2 = r_a + k * (sa - ea)
    r_b2 = r_b + k * (sb - (1 - ea))
    return r_a2, r_b2
```

**Queue with widening search window**:

```python
from dataclasses import dataclass
from time import time
from heapq import heappush, heappop

@dataclass(order=True)
class Ticket:
    enqueued_at: float
    user_id: str
    mmr: int
    region: str
    mode: str

class MatchQueue:
    def __init__(self): self._q: list[Ticket] = []
    def enqueue(self, t: Ticket): heappush(self._q, t)
    def try_match(self, max_delta: int = 50) -> list[Ticket] | None:
        # naive: pop two closest by time then mmr window expand
        if len(self._q) < 2: return None
        a = heappop(self._q)
        # find closest MMR within growing window based on wait time
        window = max_delta + int((time() - a.enqueued_at) / 5) * 25
        idx = next((i for i, t in enumerate(self._q) if abs(t.mmr - a.mmr) <= window and t.mode==a.mode and t.region==a.region), -1)
        if idx == -1:
            heappush(self._q, a)
            return None
        b = self._q.pop(idx)
        return [a, b]
```

## 6) Leaderboards (Redis ZSET + Postgres sink)

* Write path: `ZADD lb:{season}:{mode} score user_id`
* Read path: `ZREVRANGE` with `WITHSCORES` → page → (optional) join profile cache.
* Nightly sink: copy top N into Postgres for historical snapshots and analytics.

**Submit score**:

```python
import redis.asyncio as redis
r = redis.from_url("redis://localhost:6379")

async def submit_score(season: str, mode: str, user_id: str, score: float):
    key = f"lb:{season}:{mode}"
    await r.zadd(key, {user_id: score})
```

## 7) Telemetry & Anti-cheat

* Client/Server sends compact events; validated → queued to Redis Streams `telemetry`.
* Worker consumes → rules + ML checks → flags to `alerts` stream and persists `Event`.

**Redis Streams consumer**:

```python
async def consume(stream="telemetry", group="veze", name="w1"):
    rr = redis.from_url("redis://localhost:6379/0")
    try: await rr.xgroup_create(stream, group, id="$", mkstream=True)
    except Exception: pass
    while True:
        xs = await rr.xreadgroup(group, name, {stream: ">"}, count=64, block=4000)
        for _, msgs in xs or []:
            for msg_id, data in msgs:
                # TODO: validate, rules, ML call
                await rr.xack(stream, group, msg_id)
```

## 8) ML Service (skill/bot prediction)

* **Training**: offline (`train.py`) using historic matches/telemetry features.
* **Registry**: `models/ModelName/version/` with `latest.joblib` symlink.
* **Inference**: FastAPI route; CPU by default; GPU toggle via env.

**Predict skill**:

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import joblib, numpy as np
from pathlib import Path

router = APIRouter()
MODEL = Path("models/skill/latest.joblib")

class SkillReq(BaseModel):
    features: list[float]

class SkillRes(BaseModel):
    skill: float

def load():
    if not MODEL.exists(): raise HTTPException(503, "model not ready")
    return joblib.load(MODEL)

@router.post("/ml/predict_skill", response_model=SkillRes)
def predict_skill(r: SkillReq):
    m = load()
    s = float(m.predict(np.array([r.features]))[0])
    return SkillRes(skill=s)
```

## 9) Realtime (WebSocket rooms)

* Rooms by `{region}:{mode}` and `{match_id}`.
* Broadcast: matchmaking updates, countdowns, leaderboard deltas.
* Auth: token gate; close on idle; ping/pong; resumable cursor for streams.

## 10) Security (Python)

* OIDC (`authlib`) login → session cookie (HttpOnly, SameSite=Lax).
* Short-lived JWT for API calls; key rotation.
* RBAC: roles `admin`, `mod`, `player` via FastAPI dependencies.
* Rate limits: Redis token bucket for login, webhook, telemetry.
* Signatures: verify `store/webhook` with provider secret; replay protection.

## 11) Observability & SLOs

* OTEL FastAPI + Redis/Kafka instrumentation → OTLP exporter.
* Prometheus: request histograms, WS gauges, consumer lag, queue length, ML latency.
* **SLOs**: API p95 < 200ms; WS uptime 99.9%; match placement < 5s p95; ML infer < 150ms p95.

## 12) CI/CD (GitHub Actions)

* Jobs: lint (ruff) → typecheck (mypy) → tests (pytest+asyncio) → container build → SBOM (CycloneDX).
* Optional step: deploy to Cloud Run/App Runner; run alembic migrations; warmup ping.

---

## Deployment: Push Docker image to Amazon ECR

Prerequisites:

* AWS CLI v2 installed and configured with credentials that can push to the ECR repo
* Docker installed and running

Quick push using helper script:

```bash
./scripts/ecr_build_push.sh eu-north-1 879584802968 veze/game latest
```

Equivalent manual commands:

```bash
aws ecr get-login-password --region eu-north-1 | docker login --username AWS --password-stdin 879584802968.dkr.ecr.eu-north-1.amazonaws.com
docker build -t veze/game .
docker tag veze/game:latest 879584802968.dkr.ecr.eu-north-1.amazonaws.com/veze/game:latest
docker push 879584802968.dkr.ecr.eu-north-1.amazonaws.com/veze/game:latest
```

### GitHub Actions: Build and Push to ECR

This repo includes a reusable workflow to build and push the `VEZEPyGame` image to ECR on main pushes or manually via the Actions tab.

Workflow file: `.github/workflows/ecr-push.yml`

Secrets required:

* `AWS_ECR_ROLE_ARN` — An IAM role ARN with permissions to push to the ECR repo. The workflow uses OIDC to assume this role (no long-lived keys).

Manual dispatch (optional): provide a custom tag; defaults to `latest`.

Note: The workflow will automatically create the ECR repository (`veze/game`) in `eu-north-1` if it doesn't exist yet (scan-on-push enabled).

### UI Features: Mobile & Fullscreen

* Panels button to hide/show the right sidebar; fullscreen world when hidden; state persists.
* Mobile settings panel (⚙︎): haptics on/off, overlay opacity, scale, and mode (D-pad/Joystick).
* Per-user settings keyed by the Inventory user field; changing the user reloads their settings.
* Cooldown visuals: ring overlays + numeric countdowns on Q/E/Dodge; buttons disable during cooldown.
* Sidebar HUD includes Dodge cooldown text alongside Q/E.

## 13) Minimal FastAPI wiring (Gateway)

```python
# app/main.py
from fastapi import FastAPI
from app.routers import public, ws
from services.matchmaking.api import router as mm_router
from services.leaderboards.api import router as lb_router
from services.telemetry.api import router as tel_router
from services.inventory.api import router as inv_router
from services.ml.api import router as ml_router

app = FastAPI(title="VEZEPyGame")
app.include_router(public.router, tags=["public"])
app.include_router(ws.router, tags=["ws"])
app.include_router(mm_router, prefix="/matchmaking", tags=["matchmaking"])
app.include_router(lb_router, prefix="/leaderboards", tags=["leaderboards"])
app.include_router(tel_router, prefix="/telemetry", tags=["telemetry"])
app.include_router(inv_router, prefix="/inventory", tags=["inventory"])
app.include_router(ml_router, prefix="/ml", tags=["ml"])

@app.get("/health")
def health(): return {"status": "ok"}
```

---

## 14) Runbook (essentials)

* **Dev**

  ```bash
  pip install -e .[dev]
  uvicorn app.main:app --reload
  ```

  Launch Postgres & Redis (docker compose) and run `alembic upgrade head`.
* **Queues**: start `streaming/redis_consumer.py` for telemetry.
* **Matchmaking test**: enqueue 2 players → `/matchmaking/match`.
* **Leaderboards**: POST scores → GET season top-N.
* **ML**: train → save `models/skill/latest.joblib` → predict.

---
