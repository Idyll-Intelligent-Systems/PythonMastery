---

# VEZEPySocial — Social Media & Community (Python-only)

## Architecture (C4-brief)

* **Gateway & UI (FastAPI + Jinja2)**: auth/session, feeds, profiles, groups, moderation, OpenAPI docs.
* **Domain services**: `posts`, `comments`, `groups`, `moderation`, `search`, `notifications`.
* **Streaming**: Redis Streams topics — `post.created`, `comment.added`, `like.added`, `report.flagged`, `mod.decision`.
* **Data**: Postgres (SQLAlchemy 2.0 + Alembic), Redis (cache/sessions/streams).
* **ML**: feed ranking and comment toxicity (sklearn/PyTorch, joblib registry).
* **Realtime**: WebSocket `/ws/notifications` (live likes/replies/mod decisions).
* **Security**: OIDC (Authlib), short-lived JWT, RBAC (member/mod/admin), CSRF on forms, rate limits, audit events.
* **Observability**: OpenTelemetry tracing, Prometheus metrics, structured logs.

---

## Repo layout

```
VEZEPySocial/
├─ pyproject.toml
├─ Dockerfile
├─ .github/workflows/ci.yml
├─ docs/openapi.yaml
├─ app/
│  ├─ main.py
│  ├─ deps.py
│  ├─ auth.py
│  ├─ ui/templates/{base.html,feed.html,group.html,moderation.html}
│  └─ routers/{public.py,posts.py,comments.py,groups.py,moderation.py,ws.py}
├─ db/
│  ├─ database.py
│  ├─ models.py
│  └─ migrations/  (alembic)
├─ schemas/
│  ├─ core.py
│  └─ posts.py
├─ streaming/
│  ├─ producer.py
│  ├─ notifier_worker.py
│  └─ ranker_worker.py
├─ ml/
│  ├─ toxicity.py
│  ├─ feedrank.py
│  └─ registry.py
├─ ops/{runbook.md,dashboards/latency.json,sbom.json}
└─ tests/test_health.py
```

---

## pyproject.toml

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "veze-social"
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
  "scikit-learn>=1.5",
  "numpy>=1.26",
  "pandas>=2.2",
  "joblib>=1.4",
]

[project.optional-dependencies]
dev = ["ruff>=0.5","black>=24.8","mypy>=1.11","pytest>=8.3","pytest-asyncio>=0.23","hypothesis>=6.104"]
```

---

## app/main.py

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routers import public, posts, comments, groups, moderation, ws

app = FastAPI(title="VEZEPySocial")

# Routers
app.include_router(public.router, tags=["public"])
app.include_router(posts.router, prefix="/posts", tags=["posts"])
app.include_router(comments.router, prefix="/comments", tags=["comments"])
app.include_router(groups.router, prefix="/groups", tags=["groups"])
app.include_router(moderation.router, prefix="/moderation", tags=["moderation"])
app.include_router(ws.router, tags=["ws"])

@app.get("/health")
async def health(): return {"status": "ok"}

# Optional: static assets if you add images/css
app.mount("/static", StaticFiles(directory="app/ui/static"), name="static")
```

---

## db/database.py (async engine/session)

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

DATABASE_URL = "postgresql+asyncpg://user:pass@localhost:5432/veze_social"

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
```

---

## db/models.py (core tables)

```python
from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String, Text, JSON, Index

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class Profile(Base):
    __tablename__ = "profiles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    bio: Mapped[str | None] = mapped_column(Text())
    avatar_url: Mapped[str | None] = mapped_column(String(512))

class Post(Base):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    text: Mapped[str] = mapped_column(Text())
    media: Mapped[list[str]] = mapped_column(JSON, default=list)
    visibility: Mapped[str] = mapped_column(String(16), default="public")
    score: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
Index("ix_posts_user_created", Post.user_id, Post.created_at.desc())

class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text())
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("comments.id"))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class Like(Base):
    __tablename__ = "likes"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
Index("uq_like_post_user", Like.post_id, Like.user_id, unique=True)

class Group(Base):
    __tablename__ = "groups"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(140), unique=True)
    rules: Mapped[str | None] = mapped_column(Text())

class Membership(Base):
    __tablename__ = "memberships"
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), default="member")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(16))  # post/comment/user
    entity_id: Mapped[int] = mapped_column(index=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32))
    payload_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

---

## schemas/core.py (Pydantic)

```python
from pydantic import BaseModel, Field
from datetime import datetime

class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    roles: list[str]
    created_at: datetime

class PostIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    media: list[str] = []
    visibility: str = "public"

class PostOut(BaseModel):
    id: int
    user_id: int
    text: str
    media: list[str]
    visibility: str
    score: float
    created_at: datetime
```

---

## app/routers/posts.py

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_session
from db.models import Post
from schemas.core import PostIn, PostOut
from streaming.producer import emit

router = APIRouter()

@router.get("", response_model=list[PostOut])
async def list_posts(limit: int = 20, session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(Post).order_by(Post.created_at.desc()).limit(limit))
    return [PostOut.model_validate(p.__dict__) for p in res.scalars().all()]

@router.post("", response_model=PostOut, status_code=201)
async def create_post(payload: PostIn, session: AsyncSession = Depends(get_session), user_id: int = 1):
    p = Post(user_id=user_id, text=payload.text, media=payload.media, visibility=payload.visibility)
    session.add(p)
    await session.commit()
    await session.refresh(p)
    await emit("post.created", {"post_id": p.id, "user_id": user_id})
    return PostOut.model_validate(p.__dict__)
```

---

## app/routers/comments.py

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.database import get_session
from db.models import Comment
from pydantic import BaseModel
from streaming.producer import emit

router = APIRouter()

class CommentIn(BaseModel):
    post_id: int
    text: str
    parent_id: int | None = None

class CommentOut(BaseModel):
    id: int
    post_id: int
    user_id: int
    text: str

@router.get("", response_model=list[CommentOut])
async def list_comments(post_id: int, session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(Comment).where(Comment.post_id == post_id).order_by(Comment.created_at))
    return [CommentOut(id=c.id, post_id=c.post_id, user_id=c.user_id, text=c.text) for c in res.scalars().all()]

@router.post("", response_model=CommentOut, status_code=201)
async def create_comment(body: CommentIn, session: AsyncSession = Depends(get_session), user_id: int = 1):
    c = Comment(post_id=body.post_id, user_id=user_id, text=body.text, parent_id=body.parent_id)
    session.add(c); await session.commit(); await session.refresh(c)
    await emit("comment.added", {"post_id": c.post_id, "comment_id": c.id, "user_id": user_id})
    return CommentOut(id=c.id, post_id=c.post_id, user_id=c.user_id, text=c.text)
```

---

## app/routers/groups.py

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.database import get_session
from db.models import Group, Membership
from pydantic import BaseModel

router = APIRouter()

class GroupCreate(BaseModel): name: str; rules: str | None = None

@router.get("")
async def list_groups(session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(Group).order_by(Group.name))
    return [g.__dict__ for g in res.scalars().all()]

@router.post("", status_code=201)
async def create_group(body: GroupCreate, session: AsyncSession = Depends(get_session), user_id: int = 1):
    g = Group(name=body.name, rules=body.rules); session.add(g); await session.commit(); await session.refresh(g)
    session.add(Membership(group_id=g.id, user_id=user_id, role="owner")); await session.commit()
    return {"id": g.id, "name": g.name}
```

---

## app/routers/moderation.py

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from db.database import get_session
from db.models import Report, Post, Comment
from pydantic import BaseModel
from streaming.producer import emit

router = APIRouter()

class ReportIn(BaseModel):
    entity_type: str  # "post" | "comment"
    entity_id: int
    reason: str

@router.post("/report", status_code=202)
async def report(body: ReportIn, session: AsyncSession = Depends(get_session), user_id: int = 1):
    r = Report(entity_type=body.entity_type, entity_id=body.entity_id, reporter_id=user_id, reason=body.reason)
    session.add(r); await session.commit()
    await emit("report.flagged", r.__dict__)
    return {"ok": True}

@router.post("/decision/{entity_type}/{entity_id}")
async def decision(entity_type: str, entity_id: int, action: str, session: AsyncSession = Depends(get_session)):
    if action == "remove" and entity_type == "post":
        await session.execute(delete(Post).where(Post.id == entity_id)); await session.commit()
        await emit("mod.decision", {"entity_type": entity_type, "entity_id": entity_id, "action": action})
    # extend for comments/users
    return {"ok": True}
```

---

## app/routers/ws.py (WebSocket notifications)

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
router = APIRouter()

clients: set[WebSocket] = set()

@router.websocket("/ws/notifications")
async def notifications(ws: WebSocket):
    await ws.accept(); clients.add(ws)
    try:
        await ws.send_json({"type": "hello"})
        while True:
            await ws.receive_text()  # ignore client pings
    except WebSocketDisconnect:
        clients.discard(ws)

# simple broadcast hook (used by notifier_worker through HTTP if needed)
async def broadcast(payload: dict):
    for c in list(clients):
        try: await c.send_json(payload)
        except Exception: clients.discard(c)
```

---

## streaming/producer.py (emit events)

```python
import redis.asyncio as redis
import json, os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
r = redis.from_url(REDIS_URL)

async def emit(kind: str, payload: dict):
    stream = kind  # one stream per kind; or use single "events" with kind field
    await r.xadd(stream, {"payload": json.dumps(payload)})
```

---

## streaming/notifier\_worker.py (push events → WS)

```python
import asyncio, json, os
import redis.asyncio as redis
import httpx

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
APP_BASE = os.getenv("APP_BASE", "http://localhost:8000")

async def main():
    r = redis.from_url(REDIS_URL)
    group, consumer = "notifier", "worker-1"
    for stream in ["post.created","comment.added","like.added","mod.decision"]:
        try: await r.xgroup_create(stream, group, id="$", mkstream=True)
        except Exception: pass

    async with httpx.AsyncClient() as client:
        while True:
            xs = await r.xreadgroup(group, consumer, {s: ">" for s in ["post.created","comment.added","like.added","mod.decision"]}, count=50, block=5000)
            for stream, msgs in xs or []:
                for msg_id, data in msgs:
                    payload = json.loads(data["payload"])
                    # Here you could call an internal admin endpoint that calls ws.broadcast
                    # Or keep a side WS server publishing to clients; keeping simple: log only
                    print("notify:", stream, payload)
                    await r.xack(stream, group, msg_id)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## streaming/ranker\_worker.py (update feed scores)

```python
import asyncio, json, os, math, time
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select
from db.models import Post

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/veze_social")
engine = create_async_engine(DATABASE_URL)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_="AsyncSession")

def feed_score(age_s: float, likes: int, comments: int, reports: int) -> float:
    return 0.6/(1+age_s/3600) + 0.3*min(likes,50)/50 + 0.15*min(comments,30)/30 - 0.25*min(reports,5)/5

async def main():
    r = redis.from_url(os.getenv("REDIS_URL","redis://localhost:6379/0"))
    group, consumer = "ranker", "worker-1"
    for s in ["post.created","comment.added","like.added","report.flagged"]:
        try: await r.xgroup_create(s, group, id="$", mkstream=True)
        except Exception: pass

    async with SessionLocal() as session:  # type: ignore
        while True:
            xs = await r.xreadgroup(group, consumer, {s:">" for s in ["post.created","comment.added","like.added","report.flagged"]}, count=32, block=5000)
            for stream, msgs in xs or []:
                for msg_id, data in msgs:
                    payload = json.loads(data["payload"])
                    post_id = payload.get("post_id")
                    if not post_id: 
                        await r.xack(stream, group, msg_id); continue
                    # naive counts; you can denormalize counts on Post or keep counters in Redis
                    res = await session.execute(select(Post).where(Post.id == post_id))
                    p = res.scalars().first()
                    if p:
                        age_s = max(1.0, (time.time() - p.created_at.timestamp()))
                        # TODO: replace dummy counts with real aggregates
                        likes = 1 if stream=="like.added" else 0
                        comments = 1 if stream=="comment.added" else 0
                        reports = 1 if stream=="report.flagged" else 0
                        p.score = max(0.0, feed_score(age_s, likes, comments, reports))
                        await session.commit()
                    await r.xack(stream, group, msg_id)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## ml/toxicity.py (stub) & ml/feedrank.py

```python
# toxicity.py
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import joblib

def train_toxicity(texts: list[str], labels: list[int]):
    vec = TfidfVectorizer(ngram_range=(1,2), min_df=2)
    X = vec.fit_transform(texts)
    model = LogisticRegression(max_iter=200).fit(X, labels)
    joblib.dump((vec, model), "ml/models/toxicity.joblib")

def predict_toxicity(text: str) -> float:
    vec, model = joblib.load("ml/models/toxicity.joblib")
    return float(model.predict_proba(vec.transform([text]))[0,1])

# feedrank.py
def blended_score(recency_weight: float, interactions: float, quality: float, reports: float) -> float:
    return 0.6*recency_weight + 0.25*interactions + 0.20*quality - 0.25*reports
```

---

## docs/openapi.yaml (minimal)

```yaml
openapi: 3.0.3
info: { title: VEZEPySocial API, version: 0.1.0 }
paths:
  /health:
    get: { summary: Health, responses: { "200": { description: OK } } }
  /posts:
    get: { summary: List posts, responses: { "200": { description: OK } } }
    post: { summary: Create post, responses: { "201": { description: Created } } }
  /comments:
    post: { summary: Create comment, responses: { "201": { description: Created } } }
  /ws/notifications:
    get: { summary: WebSocket upgrade, responses: { "101": { description: Switching Protocols } } }
```

---

## .github/workflows/ci.yml (CI)

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
* **Redis Streams workers**

  ```bash
  python streaming/notifier_worker.py
  python streaming/ranker_worker.py
  ```
* **Smoke**

  * `POST /posts` → see in `GET /posts`
  * `POST /comments` → event triggers ranker
  * Connect WS `ws://localhost:8000/ws/notifications`

**SLOs**: feed p95 < 250ms, notification fanout < 2s, comment toxicity check < 300ms (cached model).

---
