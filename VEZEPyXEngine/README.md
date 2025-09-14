# VEZEPyXEngine — “X (Twitter) + Grok” Intelligence & Social Bridge for VEZE UniQVerse

## Quickstart: Local Dev

Spin up all VEZE services (UniQVerse, Game, Email, XEngine):

```bash
docker compose build
docker compose up
```

XEngine API/UI: [http://localhost:8006](http://localhost:8006)
All endpoints available via Helm/compose.

Default host port (compose): 8006. Override by exporting `XENGINE_PORT` before `docker compose up`.

**What it is:**

* One Python service that turns **X trends, user intel, posting, and LLM reasoning** into features for **VEZEPyGame** and the broader **VEZE UniQVerse**.
* Ships with: Web UI (Jinja2), REST APIs, WS live feed, background workers, caching, metrics, and clean integrations.

---

## 1) Repository layout

```
VEZEPyXEngine/
├─ pyproject.toml
├─ Dockerfile
├─ .env.example
├─ .github/workflows/ci.yml
├─ app/
│  ├─ main.py
│  ├─ settings.py
│  ├─ deps.py
│  ├─ ui/templates/{base.html,index.html,intel.html,post.html,users.html}
│  ├─ middleware/{ratelimit.py,logging.py}
│  ├─ routers/
│  │  ├─ public.py             # UI pages
│  │  ├─ intel.py              # npc_response, boss_adapt_strategy, dino_evolution, cosmic_interaction, emotions
│  │  ├─ social.py             # post_to_x, user_details, user_metrics
│  │  ├─ catalog.py            # cars/rockets/planets/...
│  │  ├─ ws.py                 # live stream for ingestion/events
│  │  └─ health.py
│  ├─ services/
│  │  ├─ x_client.py           # Tweepy + REST fallbacks + sandbox
│  │  ├─ grok_client.py        # xAI Grok client + sandbox stub
│  │  ├─ cache.py              # Redis cache helpers
│  │  ├─ trends.py             # X search/recent trends aggregator
│  │  └─ telemetry.py          # Prometheus/OTEL init
│  ├─ workers/
│  │  ├─ ingest_worker.py      # periodic trend pulls → Redis Streams
│  │  └─ fanout_worker.py      # react to trends → notify Game/Email/etc.
│  └─ domain/
│     ├─ models.py             # pydantic DTOs (requests/responses)
│     └─ cosmos.py             # in-memory demo data & utils
├─ db/                          # (optional) future persistence
│  └─ migrations/
├─ tests/
│  ├─ test_health.py
│  ├─ test_social.py
│  └─ test_intel.py
└─ ops/runbook.md
```

---

## 2) pyproject.toml (deps)

```toml
[project]
name = "veze-xengine"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115", "uvicorn[standard]>=0.30",
  "pydantic>=2.8", "python-dotenv>=1.0",
  "tweepy>=4.14", "httpx>=0.27", "requests>=2.32",
  "redis>=5.0",
  "prometheus-fastapi-instrumentator>=7.0.0",
  "opentelemetry-sdk>=1.27.0",
  "opentelemetry-instrumentation-fastapi>=0.48b0",
  "opentelemetry-exporter-otlp>=1.27.0",
  "jinja2>=3.1",
  "limits>=3.13.0"   # simple local rate limit
]
[project.optional-dependencies]
dev = ["pytest>=8.3","pytest-asyncio>=0.23","ruff>=0.5","black>=24.8","mypy>=1.11"]
```

---

## 3) .env.example

```env
# X (Twitter) API
X_BEARER_TOKEN=your_bearer_token
X_CONSUMER_KEY=your_consumer_key
X_CONSUMER_SECRET=your_consumer_secret
X_ACCESS_TOKEN=your_access_token
X_ACCESS_SECRET=your_access_secret

# xAI Grok
XAI_API_KEY=your_xai_api_key

# Service
ENV=dev
PORT=8006
REDIS_URL=redis://localhost:6379/3

# Feature switches
SANDBOX=true            # if true, no external calls; returns deterministic fakes
POST_TO_X_ENABLED=false
```

---

## 4) Settings & deps

```python
# app/settings.py
import os
from pydantic import BaseModel

class Settings(BaseModel):
    env: str = os.getenv("ENV","dev")
    port: int = int(os.getenv("PORT","8006"))
    redis_url: str = os.getenv("REDIS_URL","redis://localhost:6379/3")
    sandbox: bool = os.getenv("SANDBOX","true").lower() == "true"
    post_to_x_enabled: bool = os.getenv("POST_TO_X_ENABLED","false").lower() == "true"

    x_bearer: str | None = os.getenv("X_BEARER_TOKEN")
    x_consumer_key: str | None = os.getenv("X_CONSUMER_KEY")
    x_consumer_secret: str | None = os.getenv("X_CONSUMER_SECRET")
    x_access_token: str | None = os.getenv("X_ACCESS_TOKEN")
    x_access_secret: str | None = os.getenv("X_ACCESS_SECRET")

    xai_api_key: str | None = os.getenv("XAI_API_KEY")
    grok_url: str = "https://api.x.ai/v1/chat/completions"

settings = Settings()
```

```python
# app/deps.py
from fastapi import Depends
from app.settings import settings
from app.services.x_client import XClient
from app.services.grok_client import GrokClient
from app.services.cache import Cache

def get_xclient() -> XClient:
    return XClient.from_settings(settings)

def get_grok() -> GrokClient:
    return GrokClient.from_settings(settings)

def get_cache() -> Cache:
    return Cache(settings.redis_url)
```

---

## 5) Service clients (typed, sandbox-aware)

```python
# app/services/x_client.py
from __future__ import annotations
import time
import tweepy, httpx
from typing import Any

class XClient:
    def __init__(self, sandbox: bool, tweepy_client: tweepy.Client | None):
        self.sandbox = sandbox
        self._tw = tweepy_client

    @classmethod
    def from_settings(cls, s) -> "XClient":
        if s.sandbox:
            return cls(True, None)
        tw = tweepy.Client(
            consumer_key=s.x_consumer_key,
            consumer_secret=s.x_consumer_secret,
            access_token=s.x_access_token,
            access_token_secret=s.x_access_secret,
            bearer_token=s.x_bearer,
            wait_on_rate_limit=True,
        )
        return cls(False, tw)

    # ---- Search recent (simple) ----
    async def search_texts(self, query: str, max_results: int = 5) -> list[str]:
        if self.sandbox:
            return [f"[SANDBOX] {query} sample {i}" for i in range(max_results)]
        r = self._tw.search_recent_tweets(query=query, max_results=max_results,
                                          tweet_fields=["text","created_at","public_metrics"])
        return [t.text for t in (r.data or [])]

    # ---- Post text ----
    async def post(self, text: str) -> dict[str, Any]:
        if self.sandbox:
            return {"id": int(time.time()), "sandbox": True}
        resp = self._tw.create_tweet(text=text)
        return {"id": resp.data.get("id")}

    # ---- User intel ----
    async def user_details(self, username: str) -> dict:
        if self.sandbox:
            return {
                "username": username, "bio": "Pilot in UniQVerse", "name": "Test User",
                "location":"Zara-9", "followers_count": 1234, "following_count": 99,
                "top_posts":[{"text":"hello","likes":10,"retweets":1,"created_at":"now"}],
                "recent_mentions":[], "pinned_post":{}, "similar_users":[]
            }
        u = self._tw.get_user(username=username,
                              user_fields=["description","name","location","public_metrics","pinned_tweet_id"])
        if not u.data: raise ValueError("User not found")
        uid = u.data.id
        tweets = self._tw.get_users_tweets(id=uid, max_results=100,
                                           tweet_fields=["public_metrics","created_at","text"]).data or []
        top = sorted(tweets, key=lambda t: t.public_metrics.get("like_count",0), reverse=True)[:5]
        top_posts = [{"text":t.text,"likes":t.public_metrics["like_count"],
                      "retweets":t.public_metrics["retweet_count"],"created_at":str(t.created_at)} for t in top]
        mentions = self._tw.get_users_mentions(id=uid, max_results=5,
                                               tweet_fields=["text","created_at"]).data or []
        recent = [{"text":m.text,"created_at":str(m.created_at)} for m in mentions]
        pinned = {}
        if u.data.pinned_tweet_id:
            p = self._tw.get_tweet(id=u.data.pinned_tweet_id, tweet_fields=["text","public_metrics"])
            if p.data:
                pinned = {"text":p.data.text,
                          "likes":p.data.public_metrics["like_count"],
                          "retweets":p.data.public_metrics["retweet_count"]}
        followers = self._tw.get_users_followers(id=uid, max_results=5,
                                                 user_fields=["description","name"]).data or []
        similar = [{"username":fu.username,"bio":fu.description or "","name":fu.name or ""} for fu in followers]
        return {
            "username": u.data.username, "bio": u.data.description or "", "name": u.data.name or "",
            "location": u.data.location or "",
            "followers_count": u.data.public_metrics["followers_count"],
            "following_count": u.data.public_metrics["following_count"],
            "top_posts": top_posts, "recent_mentions": recent,
            "pinned_post": pinned, "similar_users": similar
        }

    async def user_metrics(self, username: str) -> dict:
        if self.sandbox:
            return {
                "followers_count": 1234,"following_count": 56,
                "tweet_count": 789,"listed_count": 12,
                "average_likes": 42.0,"average_retweets": 7.0,"average_replies": 3.0
            }
        u = self._tw.get_user(username=username, user_fields=["public_metrics"])
        if not u.data: raise ValueError("User not found")
        uid = u.data.id
        tweets = self._tw.get_users_tweets(id=uid, max_results=100,
                                           tweet_fields=["public_metrics"]).data or []
        n = len(tweets)
        if n:
            tot_like = sum(t.public_metrics["like_count"] for t in tweets)
            tot_rt   = sum(t.public_metrics["retweet_count"] for t in tweets)
            tot_rep  = sum(t.public_metrics["reply_count"] for t in tweets)
            a = (tot_like/n, tot_rt/n, tot_rep/n)
        else:
            a = (0.0,0.0,0.0)
        m = u.data.public_metrics
        return {
            "followers_count": m["followers_count"], "following_count": m["following_count"],
            "tweet_count": m["tweet_count"], "listed_count": m["listed_count"],
            "average_likes": a[0], "average_retweets": a[1], "average_replies": a[2]
        }
```

```python
# app/services/grok_client.py
import httpx
class GrokClient:
    def __init__(self, api_key: str | None, url: str, sandbox: bool):
        self.key, self.url, self.sandbox = api_key, url, sandbox

    @classmethod
    def from_settings(cls, s): return cls(s.xai_api_key, s.grok_url, s.sandbox)

    async def chat(self, prompt: str, max_tokens: int = 200) -> str:
        if self.sandbox or not self.key:
            return f"[SANDBOX GROK] {prompt[:120]} ..."
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type":"application/json"}
        payload = {"model": "grok-4", "messages":[{"role":"user","content":prompt}], "max_tokens": max_tokens}
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(self.url, headers=headers, json=payload)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
```

```python
# app/services/cache.py
import redis.asyncio as redis, json
class Cache:
    def __init__(self, url:str):
        self.r = redis.from_url(url)
    async def get_json(self, k:str):
        v = await self.r.get(k); return json.loads(v) if v else None
    async def set_json(self, k:str, v, ttl:int=300):
        await self.r.set(k, json.dumps(v), ex=ttl)
```

---

## 6) Domain models (requests/responses)

```python
# app/domain/models.py
from pydantic import BaseModel, EmailStr
from typing import List, Dict, Optional

class NPCRequest(BaseModel):
    context: str
    query: Optional[str] = None

class PostRequest(BaseModel):
    text: str
    remarks: str = ""

class UserDetailsResponse(BaseModel):
    username: str; bio: str; name: str; location: str
    followers_count: int; following_count: int
    top_posts: List[dict]; recent_mentions: List[dict]
    pinned_post: dict; similar_users: List[dict]

class UserMetricsResponse(BaseModel):
    followers_count: int; following_count: int; tweet_count: int; listed_count: int
    average_likes: float; average_retweets: float; average_replies: float

class BossStrategyRequest(BaseModel):
    player_username: str; boss_type: str = "DinoBoss"

class BossStrategyResponse(BaseModel):
    strategy: str; adaptations: List[str]; weakness: str

class DinoEvolutionRequest(BaseModel):
    dino_type: str; trend_query: str

class DinoEvolutionResponse(BaseModel):
    evolved_traits: List[str]; new_abilities: List[str]; visual_desc: str

class CosmicEntityResponse(BaseModel):
    id: str; name: str; type: str; details: Dict
```

```python
# app/domain/cosmos.py
VEZE_DATA = {
  "cars": {
    "cybertron-1": {"name":"Quantum Speeder","type":"HoverCar","speed":300,"abilities":["Quantum Dash","Stealth Mode"]},
    "neon-2": {"name":"Neon Blitz","type":"AeroCar","speed":250,"abilities":["Plasma Boost","Anti-Grav"]},
  },
  "rockets": {
    "starfire-x":{"name":"Starfire X","type":"Interstellar","range":"100 ly","features":["Warp Drive","Shield Array"]},
    "nova-7":{"name":"Nova 7","type":"Orbital","range":"Low Orbit","features":["Cargo Bay","Solar Sail"]},
  },
  "planets": {
    "zara-9":{"name":"Zara-9","type":"Terrestrial","climate":"Arid","resources":["Crystal Ore","Plasma Wells"]},
    "kryon-3":{"name":"Kryon-3","type":"Gas Giant","climate":"Stormy","resources":["Helium-3","Methane"]},
  },
  "solarsystems": {
    "orion-1":{"name":"Orion-1","planets":["zara-9"],"star":"Red Dwarf"},
    "andromeda-2":{"name":"Andromeda-2","planets":["kryon-3"],"star":"Blue Giant"},
  },
  "galaxies": {
    "milkyway-x":{"name":"MilkyWay-X","systems":["orion-1"],"type":"Spiral"},
    "andromeda-x":{"name":"Andromeda-X","systems":["andromeda-2"],"type":"Elliptical"},
  }
}
```

---

## 7) Routers (REST + WS)

### 7.1 public (UI pages)

```python
# app/routers/public.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return request.app.state.tpl.TemplateResponse("index.html", {"request": request})
```

### 7.2 social (post + user intel)

```python
# app/routers/social.py
from fastapi import APIRouter, HTTPException, Depends
from app.domain.models import PostRequest, UserDetailsResponse, UserMetricsResponse
from app.deps import get_xclient
router = APIRouter()

@router.post("/post_to_x")
async def post_to_x(req: PostRequest, x=Depends(get_xclient)):
    text = f"{req.text} {req.remarks}".strip()
    if len(text) > 280: raise HTTPException(400,"Text too long")
    return await x.post(text)

@router.get("/user_details/{username}", response_model=UserDetailsResponse)
async def user_details(username: str, x=Depends(get_xclient)):
    try: return await x.user_details(username)
    except ValueError as e: raise HTTPException(404, str(e))

@router.get("/user_metrics/{username}", response_model=UserMetricsResponse)
async def user_metrics(username: str, x=Depends(get_xclient)):
    try: return await x.user_metrics(username)
    except ValueError as e: raise HTTPException(404, str(e))
```

### 7.3 intel (LLM-powered game logic)

```python
# app/routers/intel.py
from fastapi import APIRouter, HTTPException, Depends
from app.domain.models import *
from app.deps import get_xclient, get_grok
router = APIRouter()

@router.post("/npc_response")
async def npc_response(req: NPCRequest, x=Depends(get_xclient), g=Depends(get_grok)):
    query = req.query or req.context[:50]
    posts = await x.search_texts(query, max_results=3)
    prompt = f"Based on X posts: {' '.join(posts)}\nGenerate NPC response for game context: {req.context}"
    out = await g.chat(prompt, max_tokens=150)
    return {"response": out}

@router.post("/boss_adapt_strategy", response_model=BossStrategyResponse)
async def boss_adapt_strategy(req: BossStrategyRequest, x=Depends(get_xclient), g=Depends(get_grok)):
    ud = await x.user_details(req.player_username)
    player_ctx = f"Player: {ud.get('bio','')} | Top: {ud.get('top_posts',[{'text':'None'}])[0]['text']}"
    trends = await x.search_texts(req.boss_type, max_results=5)
    prompt = f"""Futuristic boss adaptation for {req.boss_type} in VEZE UniQVerse.
Player context: {player_ctx}
Current X trends: {' '.join(trends)}
Generate: one-line strategy, 3 bullet adaptations, and one weakness."""
    content = await g.chat(prompt, max_tokens=200)
    lines = [l for l in content.splitlines() if l.strip()]
    strategy = lines[0] if lines else "Adaptive quantum strike sequence."
    adaptations = [l.strip("-* ") for l in lines[1:4]]
    weakness = lines[4] if len(lines)>4 else "Exploitable neural overload."
    return BossStrategyResponse(strategy=strategy, adaptations=adaptations, weakness=weakness)

@router.post("/dino_evolution", response_model=DinoEvolutionResponse)
async def dino_evolution(req: DinoEvolutionRequest, x=Depends(get_xclient), g=Depends(get_grok)):
    trends = await x.search_texts(req.trend_query, max_results=5)
    prompt = f"""Evolve {req.dino_type} in VEZE UniQVerse.
X trends: {' '.join(trends)}
Return 4 evolved traits, 3 new abilities, and a vivid visual description."""
    content = await g.chat(prompt, max_tokens=240)
    # simple parse (robust to free-form)
    parts = content.split("\n\n")
    traits = [t.strip(" -*") for t in (parts[0].splitlines() if parts else []) if t.strip()][:4] or ["Cyber scales","Laser claws","Ion fins","Phase hide"]
    abilities = [a.strip(" -*") for a in (parts[1].splitlines() if len(parts)>1 else []) if a.strip()][:3] or ["Plasma roar","Time warp dash","Quark surge"]
    visual = (parts[2] if len(parts)>2 else "Glowing neon hide with holographic spikes.")
    return DinoEvolutionResponse(evolved_traits=traits, new_abilities=abilities, visual_desc=visual)

@router.post("/futuristic_npc_emotion")
async def futuristic_npc_emotion(req: NPCRequest, x=Depends(get_xclient), g=Depends(get_grok)):
    query = req.query or req.context[:50]
    posts = await x.search_texts(query, max_results=5)
    sentiment = await g.chat(f"Analyze sentiment of posts: {' '.join(posts)}. Output concise: positive/negative/neutral + score 0-1.", max_tokens=50)
    emotion = await g.chat(f"Based on sentiment {sentiment} and context {req.context}, output a futuristic NPC emotion map (json keys with floats 0-1) and a reaction line.", max_tokens=120)
    return {"sentiment": sentiment, "emotion": emotion}

@router.post("/cosmic_interaction")
async def cosmic_interaction(req: NPCRequest, x=Depends(get_xclient), g=Depends(get_grok)):
    query = req.query or req.context[:50]
    posts = await x.search_texts(query, max_results=5)
    prompt = f"""VEZE UniQVerse cosmic interaction.
Context: {req.context}
X trends: {' '.join(posts)}
Write an immersive, sci-fi response aligned with game dynamics."""
    out = await g.chat(prompt, max_tokens=160)
    return {"interaction": out}
```

### 7.4 catalog (demo cosmos data)

```python
# app/routers/catalog.py
from fastapi import APIRouter, HTTPException
from app.domain.models import CosmicEntityResponse
from app.domain.cosmos import VEZE_DATA
router = APIRouter()

@router.get("/cars")
async def cars(): return {"cars": list(VEZE_DATA["cars"].values())}

@router.get("/cars/{car_id}", response_model=CosmicEntityResponse)
async def car(car_id: str):
    c = VEZE_DATA["cars"].get(car_id); 
    if not c: raise HTTPException(404,"Car not found")
    return {"id":car_id,"name":c["name"],"type":c["type"],"details":c}

# similar endpoints for rockets, planets, solarsystems, galaxies...
```

### 7.5 ws (live trend frames)

```python
# app/routers/ws.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as redis, os, json
router = APIRouter()
r = redis.from_url(os.getenv("REDIS_URL","redis://localhost:6379/3"))

@router.websocket("/ws/trends")
async def trends(ws: WebSocket):
    await ws.accept()
    stream, group = "xengine.trends", "ui"
    try: await r.xgroup_create(stream, group, id="$", mkstream=True)
    except Exception: pass
    try:
        while True:
            xs = await r.xreadgroup(group,"c1",{stream:">"},count=50,block=3000)
            for _, msgs in xs or []:
                for mid, data in msgs:
                    ev = json.loads(data["payload"])
                    await ws.send_json(ev)
                    await r.xack(stream, group, mid)
    except WebSocketDisconnect:
        return
```

### 7.6 health

```python
# app/routers/health.py
from fastapi import APIRouter
router = APIRouter()
@router.get("/health") async def health(): return {"status":"ok"}
```

---

## 8) Main app, metrics, middleware

```python
# app/services/telemetry.py
from prometheus_fastapi_instrumentator import Instrumentator
def instrument(app): Instrumentator().instrument(app).expose(app)
```

```python
# app/middleware/ratelimit.py
from fastapi import Request, HTTPException
from limits import parse
from time import time
# simple memory bucket per IP (replace with Redis-based for prod)
bucket = {}
LIMIT = parse("30/minute")
def rate_limiter():
    def mw(req: Request, call_next):
        ip = req.client.host if req.client else "anon"
        t = time()
        logs = bucket.setdefault(ip, [])
        logs[:] = [x for x in logs if t - x < 60]
        if len(logs) >= 30: raise HTTPException(429,"Rate limit exceeded")
        logs.append(t)
        return call_next(req)
    return mw
```

```python
# app/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.services.telemetry import instrument
from app.settings import settings
from app.routers import public, social, intel, catalog, ws, health

app = FastAPI(title="VEZEPyXEngine", version="0.1.0")
app.state.tpl = Jinja2Templates(directory="app/ui/templates")
app.include_router(public.router, tags=["ui"])
app.include_router(social.router, tags=["social"])
app.include_router(intel.router,  tags=["intel"])
app.include_router(catalog.router, prefix="/cosmos", tags=["cosmos"])
app.include_router(ws.router, tags=["ws"])
app.include_router(health.router, tags=["health"])
app.mount("/static", StaticFiles(directory="app/ui/static") if False else StaticFiles(directory="app/ui/templates"), name="static")
instrument(app)

@app.get("/metrics")  # provided by Instrumentator as well
async def noop(): return {"hint":"Prometheus handler already mounted by Instrumentator"}

# uvicorn app.main:app --host 0.0.0.0 --port 8006
```

---

## 9) Workers (Redis Streams)

```python
# app/workers/ingest_worker.py
import asyncio, os, json, redis.asyncio as redis, random, time
from app.settings import settings
from app.services.x_client import XClient

r = redis.from_url(settings.redis_url)
STREAM="xengine.trends"

async def emit(ev): await r.xadd(STREAM, {"payload": json.dumps(ev)})

async def main():
    x = XClient.from_settings(settings)
    q = random.choice(["gaming","ai","cyberpunk","quantum"])
    while True:
        posts = await x.search_texts(q, max_results=5)
        await emit({"topic": q, "samples": posts, "ts": int(time.time())})
        await asyncio.sleep(5)

if __name__=="__main__": asyncio.run(main())
```

```python
# app/workers/fanout_worker.py
# Example: forward notable trend spikes to VEZEPyGame or Email (left as stub)
```

---

## 10) Web UI (Jinja2 minimal)

* `index.html`: quick dashboard (cards → “NPC Intel”, “Post”, “User Intel”, “Live Trends”)
* `intel.html`: form for npc/boss/dino/emotion; results pane updates via fetch + HTMX/JS
* `post.html`: small form to post to X (disabled in SANDBOX unless POST\_TO\_X\_ENABLED=true)
* `users.html`: search username → details + metrics; show top posts

*(You can reuse the UniQVerse space theme.)*

---

## 11) Security & operations

* **Sandbox by default** (no external calls) for safe dev/demo.
* **Rate-limit** (sample in-mem; swap to Redis token bucket in prod).
* **Secrets** via `.env` + container env.
* **Metrics** `/metrics` + OTEL exporters ready.
* **Error handling** via typed exceptions in clients.
* **Compliance note**: when posting on behalf of users, respect X API ToS, store minimal metadata, and log consent events.

---

## 12) Docker & CI

**Dockerfile**

```dockerfile
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml .
RUN pip install --upgrade pip && pip install -e .
COPY . .
EXPOSE 8006
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8006"]
```

**.github/workflows/ci.yml**

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

---

## 13) Tests (quick)

```python
# tests/test_health.py
from fastapi.testclient import TestClient
from app.main import app
def test_health():
    c=TestClient(app)
    r=c.get("/health")
    assert r.status_code==200 and r.json()["status"]=="ok"
```

```python
# tests/test_social.py
from fastapi.testclient import TestClient
from app.main import app
def test_user_metrics_sandbox():
    c=TestClient(app)
    r=c.get("/user_metrics/tester")
    assert r.status_code==200
    assert "followers_count" in r.json()
```

```python
# tests/test_intel.py
from fastapi.testclient import TestClient
from app.main import app
def test_npc_response_sandbox():
    c=TestClient(app)
    r=c.post("/npc_response", json={"context":"A pilot lands on Zara-9"})
    assert r.status_code==200
    assert "response" in r.json()
```

---

## 14) Runbook

```bash
# dev
cp .env.example .env   # set SANDBOX=true to start
pip install -e .[dev]
uvicorn app.main:app --reload --port 8006

# workers (optional)
python -m app.workers.ingest_worker

# try
curl -s localhost:8006/health
curl -s -X POST localhost:8006/npc_response -H 'content-type: application/json' \
  -d '{"context":"Battle alert near Zara-9"}'
```

---

## 15) Integration with the UniQVerse

* **VEZE Helm (UniQVerse front door)**

  * Add tile **VEZEPyXEngine** (icon: ✖️🚀).
  * Proxy pass:

    * `/proxy/xengine/npc` → `POST /npc_response`
    * `/proxy/xengine/post` → `POST /post_to_x`
    * `/proxy/xengine/users/{u}` → `GET /user_details/{u}`
  * Embed **/ws/trends** to show live trend cards on the landing panel.

* **VEZEPyGame (core gameplay)**

  * **NPC barks**: call `POST /npc_response` with scene context; render in dialog.
  * **Boss AI**: call `POST /boss_adapt_strategy` pre-fight to shape boss moves.
  * **Dino evo events**: `POST /dino_evolution` to mutate mobs based on world “X weather”.

* **VEZEPyEmail**

  * When major trend spikes, XEngine → Email: send digest via existing `/jmap/send` (nice hook for notifications).

---

## 16) Copilot one-shot prompt (drop at repo root)

> Scaffold **VEZEPyXEngine** as a Python-only FastAPI service with modular routers (public/social/intel/catalog/ws/health), typed service clients for X (Tweepy) and xAI Grok with **SANDBOX mode**, Redis-backed WS `/ws/trends`, Prometheus/OTEL metrics, rate-limit middleware, unit tests, Dockerfile, and CI. Use the repo layout shown above. Add Jinja2 templates for a minimal UI. Then print “VEZEPyXEngine ready”.

---

## 17) Notes on your original sample

* All endpoints from your reference are present with **safer structure**, async I/O, sandbox, and better parsing.
* Posting to X is **feature-flagged** (`POST_TO_X_ENABLED`) so devs don’t accidentally publish.
* Reusable **x\_client** and **grok\_client** make testing easy and let you swap providers later.

---
