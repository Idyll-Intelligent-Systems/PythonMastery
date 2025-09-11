

# VEZEPySports — Sports Analytics & Fan Engagement (Python-only)

## Architecture (C4-brief)

* **Gateway & UI (FastAPI + Jinja2/Plotly Dash option)**: public fixtures, live dashboards, fantasy interactions, ticketing, OpenAPI.
* **Domain services**: `leagues`, `ingest`, `stats`, `fantasy`, `ticketing`, `notifications`.
* **Streaming**: Redis Streams topics — `match.ingested`, `stat.update`, `fantasy.score.update`, `ticket.issued`.
* **Data**: Postgres (SQLAlchemy 2.0 + Alembic), Redis (cache/streams), optional DuckDB for offline analytics.
* **ML**: player performance prediction, injury risk classifier, fantasy optimizer (greedy/ILP); joblib registry.
* **Realtime**: WebSocket `/ws/live` for live scores & play-by-play.
* **Security**: OIDC (Authlib), short-lived JWT, RBAC (`fan`, `analyst`, `admin`), CSRF on forms, rate limits on fantasy submissions.
* **Observability**: OpenTelemetry tracing, Prometheus metrics (request latency, WS clients, ingest lag), structured logs.

---

## Repository layout

```
VEZEPySports/
├─ pyproject.toml
├─ Dockerfile
├─ .github/workflows/ci.yml
├─ docs/openapi.yaml
├─ app/
│  ├─ main.py
│  ├─ ui/templates/{base.html,fixtures.html,live.html,fantasy.html}
│  └─ routers/{public.py,leagues.py,matches.py,stats.py,fantasy.py,ticketing.py,ws.py}
├─ db/
│  ├─ database.py
│  ├─ models.py
│  └─ migrations/   (alembic)
├─ schemas/
│  ├─ core.py
│  └─ fantasy.py
├─ streaming/
│  ├─ producer.py
│  ├─ ingest_worker.py
│  ├─ stats_aggregator.py
│  └─ fantasy_scoring_worker.py
├─ ml/
│  ├─ performance.py
│  ├─ injury.py
│  └─ optimizer.py
├─ ops/{runbook.md,dashboards/latency.json,sbom.json}
└─ tests/test_health.py
```

---

## pyproject.toml

```toml
[build-system]
requires = ["setuptools>=68","wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "veze-sports"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "pydantic>=2.8",
  "SQLAlchemy>=2.0",
  "asyncpg>=0.29",
  "alembic>=1.13",
  "jinja2>=3.1",
  "redis>=5.0",
  "httpx>=0.27",
  "loguru>=0.7",
  "prometheus-client>=0.20",
  "opentelemetry-sdk>=1.27.0",
  "opentelemetry-instrumentation-fastapi>=0.48b0",
  "opentelemetry-exporter-otlp>=1.27.0",
  "authlib>=1.3",
  "python-multipart>=0.0.9",
  "numpy>=1.26",
  "pandas>=2.2",
  "joblib>=1.4",
  "scikit-learn>=1.5",
]

[project.optional-dependencies]
dev = ["ruff>=0.5","black>=24.8","mypy>=1.11","pytest>=8.3","pytest-asyncio>=0.23","hypothesis>=6.104"]
```

---

## app/main.py

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routers import public, leagues, matches, stats, fantasy, ticketing, ws

app = FastAPI(title="VEZEPySports")

app.include_router(public.router, tags=["public"])
app.include_router(leagues.router, prefix="/leagues", tags=["leagues"])
app.include_router(matches.router, prefix="/matches", tags=["matches"])
app.include_router(stats.router, prefix="/stats", tags=["stats"])
app.include_router(fantasy.router, prefix="/fantasy", tags=["fantasy"])
app.include_router(ticketing.router, prefix="/ticketing", tags=["ticketing"])
app.include_router(ws.router, tags=["ws"])

@app.get("/health")
async def health(): return {"status": "ok"}

app.mount("/static", StaticFiles(directory="app/ui/static"), name="static")
```

---

## db/database.py

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

DATABASE_URL = "postgresql+asyncpg://user:pass@localhost:5432/veze_sports"
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_session() -> AsyncSession:
    async with SessionLocal() as s:
        yield s
```

---

## db/models.py (core entities)

```python
from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import ForeignKey, String, Text, JSON, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY

class Base(DeclarativeBase): pass

class League(Base):
    __tablename__ = "leagues"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(140), unique=True)
    sport: Mapped[str] = mapped_column(String(80))

class Team(Base):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"), index=True)
    name: Mapped[str] = mapped_column(String(140))
    UniqueConstraint("league_id","name", name="uq_team_league_name")

class Player(Base):
    __tablename__ = "players"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    name: Mapped[str] = mapped_column(String(140))
    position: Mapped[str] = mapped_column(String(40))

class Match(Base):
    __tablename__ = "matches"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"), index=True)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    start_ts: Mapped[datetime]
    status: Mapped[str] = mapped_column(String(20), default="scheduled")  # scheduled|live|final

class PlayEvent(Base):
    __tablename__ = "play_events"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    t: Mapped[datetime]
    type: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON)

class BoxScore(Base):
    __tablename__ = "boxscores"
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), primary_key=True)
    totals_json: Mapped[dict] = mapped_column(JSON)   # team totals & per-player stats

class FantasyTeam(Base):
    __tablename__ = "fantasy_teams"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int]
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"))
    roster_player_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer:=int))  # simple roster

class FantasyScore(Base):
    __tablename__ = "fantasy_scores"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fantasy_team_id: Mapped[int] = mapped_column(ForeignKey("fantasy_teams.id"))
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    points: Mapped[float]
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    user_id: Mapped[int]
    price_cents: Mapped[int]
    status: Mapped[str] = mapped_column(String(20), default="issued")
```

---

## schemas/core.py (Pydantic)

```python
from pydantic import BaseModel
from datetime import datetime

class LeagueOut(BaseModel):
    id: int; name: str; sport: str

class MatchOut(BaseModel):
    id: int; league_id: int; home_team_id: int; away_team_id: int; start_ts: datetime; status: str

class BoxScoreOut(BaseModel):
    match_id: int
    totals_json: dict
```

---

## app/routers/leagues.py

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.database import get_session
from db.models import League
from schemas.core import LeagueOut

router = APIRouter()

@router.get("", response_model=list[LeagueOut])
async def list_leagues(session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(League).order_by(League.name))
    return [LeagueOut.model_validate(l.__dict__) for l in res.scalars().all()]
```

---

## app/routers/matches.py

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.database import get_session
from db.models import Match
from schemas.core import MatchOut

router = APIRouter()

@router.get("", response_model=list[MatchOut])
async def fixtures(league_id: int | None = None, session: AsyncSession = Depends(get_session)):
    stmt = select(Match).order_by(Match.start_ts)
    if league_id: stmt = stmt.where(Match.league_id == league_id)
    res = await session.execute(stmt)
    return [MatchOut.model_validate(m.__dict__) for m in res.scalars().all()]
```

---

## app/routers/stats.py

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.database import get_session
from db.models import BoxScore
from schemas.core import BoxScoreOut

router = APIRouter()

@router.get("/boxscore/{match_id}", response_model=BoxScoreOut)
async def get_boxscore(match_id: int, session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(BoxScore).where(BoxScore.match_id == match_id))
    bs = res.scalars().first()
    if not bs: raise HTTPException(404, "boxscore not found")
    return BoxScoreOut(match_id=bs.match_id, totals_json=bs.totals_json)
```

---

## schemas/fantasy.py

```python
from pydantic import BaseModel

class FantasyTeamIn(BaseModel):
    user_id: int
    league_id: int
    roster_player_ids: list[int]

class FantasySubmitIn(BaseModel):
    fantasy_team_id: int
    match_id: int
```

---

## app/routers/fantasy.py

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.database import get_session
from db.models import FantasyTeam, FantasyScore
from schemas.fantasy import FantasyTeamIn, FantasySubmitIn
from streaming.producer import emit

router = APIRouter()

@router.post("/team", status_code=201)
async def create_team(body: FantasyTeamIn, session: AsyncSession = Depends(get_session)):
    ft = FantasyTeam(**body.model_dump())
    session.add(ft); await session.commit(); await session.refresh(ft)
    return {"id": ft.id}

@router.post("/submit", status_code=202)
async def submit(body: FantasySubmitIn, session: AsyncSession = Depends(get_session)):
    fs = FantasyScore(fantasy_team_id=body.fantasy_team_id, match_id=body.match_id, points=0.0)
    session.add(fs); await session.commit()
    await emit("fantasy.score.update", {"fantasy_team_id": body.fantasy_team_id, "match_id": body.match_id})
    return {"accepted": True}
```

---

## app/routers/ticketing.py

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_session
from db.models import Ticket
from pydantic import BaseModel
from streaming.producer import emit

router = APIRouter()

class IssueReq(BaseModel): match_id: int; user_id: int; price_cents: int

@router.post("/issue", status_code=201)
async def issue(req: IssueReq, session: AsyncSession = Depends(get_session)):
    t = Ticket(**req.model_dump())
    session.add(t); await session.commit(); await session.refresh(t)
    await emit("ticket.issued", {"ticket_id": t.id, "match_id": t.match_id})
    return {"ticket_id": t.id, "status": t.status}
```

---

## app/routers/ws.py (live updates)

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
router = APIRouter()

clients: set[WebSocket] = set()

@router.websocket("/ws/live")
async def live(ws: WebSocket):
    await ws.accept(); clients.add(ws)
    try:
        await ws.send_json({"type": "hello"})
        while True:
            await ws.receive_text()  # client pings
    except WebSocketDisconnect:
        clients.discard(ws)

async def broadcast(msg: dict):
    for c in list(clients):
        try: await c.send_json(msg)
        except Exception: clients.discard(c)
```

---

## streaming/producer.py

```python
import redis.asyncio as redis, os, json
REDIS_URL = os.getenv("REDIS_URL","redis://localhost:6379/0")
r = redis.from_url(REDIS_URL)

async def emit(kind: str, payload: dict):
    await r.xadd(kind, {"payload": json.dumps(payload)})
```

---

## streaming/ingest\_worker.py (vendor → events)

```python
import asyncio, json, os
import redis.asyncio as redis
import httpx
from datetime import datetime, timezone

REDIS_URL = os.getenv("REDIS_URL","redis://localhost:6379/0")
VENDOR_URL = os.getenv("VENDOR_URL","http://localhost:9999/fake-feed")  # replace with real
STREAM = "match.ingested"

async def main():
    r = redis.from_url(REDIS_URL)
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            # poll vendor feed
            try:
                resp = await client.get(VENDOR_URL)
                for ev in resp.json():  # ev: {match_id, t, type, payload}
                    ev["t"] = datetime.now(timezone.utc).isoformat()
                    await r.xadd(STREAM, {"payload": json.dumps(ev)})
            except Exception as e:
                print("ingest error:", e)
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## streaming/stats\_aggregator.py (events → boxscore & WS)

```python
import asyncio, json, os
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from db.models import BoxScore
from app.routers.ws import broadcast  # if same process
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL","postgresql+asyncpg://user:pass@localhost:5432/veze_sports")
engine = create_async_engine(DATABASE_URL)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def apply_event(totals: dict, ev: dict) -> dict:
    # naive example: increment score by event type
    if ev["type"] == "score.home": totals["home"]["points"] += ev["payload"].get("points", 0)
    if ev["type"] == "score.away": totals["away"]["points"] += ev["payload"].get("points", 0)
    return totals

async def main():
    r = redis.from_url(os.getenv("REDIS_URL","redis://localhost:6379/0"))
    group, consumer = "aggregator","w1"
    for s in ["match.ingested","stat.update"]:
        try: await r.xgroup_create(s, group, id="$", mkstream=True)
        except Exception: pass

    async with SessionLocal() as session:
        while True:
            xs = await r.xreadgroup(group, consumer, {"match.ingested":">","stat.update":">"}, count=64, block=5000)
            for stream, msgs in xs or []:
                for msg_id, data in msgs:
                    ev = json.loads(data["payload"])
                    match_id = int(ev["match_id"])
                    res = await session.execute(select(BoxScore).where(BoxScore.match_id==match_id))
                    bs = res.scalars().first()
                    if not bs:
                        bs = BoxScore(match_id=match_id, totals_json={"home":{"points":0},"away":{"points":0}})
                        session.add(bs)
                    bs.totals_json = await apply_event(bs.totals_json, ev)
                    await session.commit()
                    try:
                        await broadcast({"type":"boxscore.update","match_id":match_id,"totals":bs.totals_json})
                    except Exception:
                        pass
                    await r.xack(stream, group, msg_id)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## streaming/fantasy\_scoring\_worker.py

```python
import asyncio, json, os
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, update
from db.models import FantasyScore

DATABASE_URL = os.getenv("DATABASE_URL","postgresql+asyncpg://user:pass@localhost:5432/veze_sports")
engine = create_async_engine(DATABASE_URL)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def main():
    r = redis.from_url(os.getenv("REDIS_URL","redis://localhost:6379/0"))
    group, consumer = "fantasy","w1"
    for s in ["fantasy.score.update","stat.update"]:
        try: await r.xgroup_create(s, group, id="$", mkstream=True)
        except Exception: pass

    async with SessionLocal() as session:
        while True:
            xs = await r.xreadgroup(group, consumer, {"fantasy.score.update":">","stat.update":">"}, count=50, block=5000)
            for stream, msgs in xs or []:
                for msg_id, data in msgs:
                    ev = json.loads(data["payload"])
                    # naive: add random delta or simple rule
                    q = await session.execute(select(FantasyScore).where(
                        (FantasyScore.fantasy_team_id==ev.get("fantasy_team_id")) &
                        (FantasyScore.match_id==ev.get("match_id"))
                    ))
                    fs = q.scalars().first()
                    if fs:
                        fs.points = (fs.points or 0.0) + 1.0
                        await session.commit()
                    await r.xack(stream, group, msg_id)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## ml/performance.py (stub) & ml/injury.py & ml/optimizer.py

```python
# performance.py
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
import joblib, numpy as np

def train_performance(X: np.ndarray, y: np.ndarray):
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)
    m = RandomForestRegressor(n_estimators=200, random_state=42).fit(Xtr, ytr)
    joblib.dump(m, "ml/models/perf.joblib")
    return float(m.score(Xte, yte))

def predict_performance(x: list[float]) -> float:
    m = joblib.load("ml/models/perf.joblib")
    return float(m.predict([x])[0])

# injury.py
from sklearn.linear_model import LogisticRegression
import joblib, numpy as np

def train_injury(X: np.ndarray, y: np.ndarray):
    m = LogisticRegression(max_iter=300).fit(X, y)
    joblib.dump(m, "ml/models/injury.joblib")

def prob_injury(x: list[float]) -> float:
    m = joblib.load("ml/models/injury.joblib")
    import numpy as np
    return float(m.predict_proba(np.array([x]))[0,1])

# optimizer.py (greedy example)
def fantasy_greedy(points_by_player: dict[int,float], roster_size: int = 5) -> list[int]:
    return [pid for pid, _ in sorted(points_by_player.items(), key=lambda kv: kv[1], reverse=True)[:roster_size]]
```

---

## docs/openapi.yaml (minimal)

```yaml
openapi: 3.0.3
info: { title: VEZEPySports API, version: 0.1.0 }
paths:
  /health:
    get: { summary: Health, responses: { "200": { description: OK } } }
  /leagues:
    get: { summary: List leagues, responses: { "200": { description: OK } } }
  /matches:
    get: { summary: Fixtures, responses: { "200": { description: OK } } }
  /stats/boxscore/{match_id}:
    get: { summary: Boxscore, responses: { "200": { description: OK } } }
  /fantasy/team:
    post: { summary: Create fantasy team, responses: { "201": { description: Created } } }
  /fantasy/submit:
    post: { summary: Submit fantasy scoring, responses: { "202": { description: Accepted } } }
  /ws/live:
    get: { summary: WebSocket upgrade, responses: { "101": { description: Switching Protocols } } }
```

---

## .github/workflows/ci.yml

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

## Dockerfile

```dockerfile
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser:appuser /app
USER appuser
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .
COPY . .
EXPOSE 8000
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
```

---

## tests/test\_health.py

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

## ops/runbook.md (essentials)

* **Dev up**

  ```bash
  pip install -e .[dev]
  uvicorn app.main:app --reload
  ```
* **DB**

  ```bash
  alembic upgrade head
  ```
* **Workers**

  ```bash
  python streaming/ingest_worker.py
  python streaming/stats_aggregator.py
  python streaming/fantasy_scoring_worker.py
  ```
* **Smoke tests**

  * `GET /leagues`, `GET /matches` (fixtures)
  * Start `ingest_worker` → see `stats_aggregator` generate `boxscores` and WS `boxscore.update`
  * Create fantasy team → `POST /fantasy/submit` → scoring worker updates rows
* **SLOs**: live stat p95 < 250ms; ingest-to-WS fanout < 2s; fantasy score calc < 500ms.

---
