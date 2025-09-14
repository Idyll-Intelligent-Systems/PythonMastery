from __future__ import annotations
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os
import asyncio
import json
from typing import Any, Dict, Optional
from urllib.parse import unquote

import redis.asyncio as redis
from pydantic import BaseModel
import httpx

app = FastAPI(title="VEZEPyXEngine")

tpl_dir = os.path.join(os.path.dirname(__file__), "ui", "templates")
static_dir = os.path.join(os.path.dirname(__file__), "ui", "static")
env = Environment(loader=FileSystemLoader(tpl_dir), autoescape=select_autoescape(["html"]))

app.mount("/static", StaticFiles(directory=static_dir), name="static")

class TemplateHelper:
    def TemplateResponse(self, request: Request, name: str, ctx: dict | None = None):
        t = env.get_template(name)
        context = {"request": request}
        if ctx:
            context.update(ctx)
        return HTMLResponse(t.render(**context))

app.state.tpl = TemplateHelper()
app.state.redis = None
app.state.activity = []  # in-memory fallback buffer
app.state.creds_loaded = False


def _load_creds_from_md(path: str = "cred.md") -> Optional[Dict[str, str]]:
    """Parse a local cred.md (three fenced blocks: bearer, access token, secret) and return tokens.
    This file is intended to be mounted into the container at /app/cred.md (read-only).
    """
    try:
        # Try multiple candidates
        candidates = [path, os.path.join(os.getcwd(), path), 
                      "/app/cred.md", os.path.normpath(os.path.join(os.getcwd(), "..", "cred.md"))]
        found = None
        for p in candidates:
            if p and os.path.isfile(p):
                found = p
                break
        if not found:
            return None
        tokens: list[str] = []
        in_block = False
        with open(found, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if line.startswith("```"):
                    in_block = not in_block
                    continue
                if in_block:
                    if line:
                        tokens.append(line)
        if not tokens:
            return None
        # Expect first three meaningful tokens in order
        bearer = tokens[0] if len(tokens) >= 1 else None
        access_token = tokens[1] if len(tokens) >= 2 else None
        access_secret = tokens[2] if len(tokens) >= 3 else None
        out: Dict[str, str] = {}
        if bearer:
            out["bearer"] = bearer
        if access_token:
            out["access_token"] = access_token
        if access_secret:
            out["access_secret"] = access_secret
        return out or None
    except Exception:
        return None

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    default_handle = os.getenv("X_DEFAULT_HANDLE", "@shivaveld_idyll")
    return app.state.tpl.TemplateResponse(request, "index.html", {"default_handle": default_handle})

@app.get("/profile", response_class=HTMLResponse)
async def profile(request: Request):
    # Placeholder profile page; avatar click in UniQVerse can deep-link here
    return app.state.tpl.TemplateResponse(request, "profile.html", {})


# --- Minimal X features (sandbox) ---

def _r() -> redis.Redis | None:
    if app.state.redis is None:
        url = os.getenv("REDIS_URL", "redis://localhost:6379/3")
        try:
            app.state.redis = redis.from_url(url, decode_responses=True)
        except Exception:
            app.state.redis = None
    return app.state.redis
def _norm_handle(h: str) -> str:
    try:
        return h.lstrip("@").strip()
    except Exception:
        return h


def _x_bearer() -> Optional[str]:
    tok = os.getenv("TWITTER_BEARER_TOKEN") or os.getenv("X_BEARER_TOKEN")
    if not tok:
        return None
    # Some tokens may be URL-encoded (contain %3D etc). Decode safely.
    try:
        return unquote(tok)
    except Exception:
        return tok


async def _x_get_user(handle: str) -> Optional[Dict[str, Any]]:
    token = _x_bearer()
    if not token:
        return None
    u = _norm_handle(handle)
    url = f"https://api.twitter.com/2/users/by/username/{u}"
    params = {
        "user.fields": "public_metrics,name,username,created_at,profile_image_url",
    }
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, params=params, headers=headers)
            if r.status_code != 200:
                return None
            data = r.json()
            if not data or "data" not in data:
                return None
            user = data["data"]
            return user
    except Exception:
        return None


async def _x_get_user_metrics(handle: str) -> Optional[Dict[str, Any]]:
    user = await _x_get_user(handle)
    if not user:
        return None
    pm = (user.get("public_metrics") or {})
    return {
        "followers_count": pm.get("followers_count", 0),
        "following_count": pm.get("following_count", 0),
        "tweet_count": pm.get("tweet_count", 0),
        "listed_count": pm.get("listed_count", 0),
    }


async def _x_search_recent(q: str, max_results: int = 5) -> Optional[list[str]]:
    token = _x_bearer()
    if not token:
        return None
    url = "https://api.twitter.com/2/tweets/search/recent"
    params = {
        "query": q,
        "max_results": max(10, min(100, max_results)) if max_results else 10,
        "tweet.fields": "text,created_at,public_metrics",
    }
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, params=params, headers=headers)
            if r.status_code != 200:
                return None
            data = r.json()
            tweets = data.get("data") or []
            return [t.get("text", "").strip() for t in tweets]
    except Exception:
        return None


@app.on_event("startup")
async def _init():
    _r()
    # Try to load local credentials from cred.md if env not already provided
    try:
        if not app.state.creds_loaded:
            creds = _load_creds_from_md(os.getenv("XENGINE_CRED_FILE", "cred.md"))
            if creds:
                if not os.getenv("X_BEARER_TOKEN") and not os.getenv("TWITTER_BEARER_TOKEN") and creds.get("bearer"):
                    os.environ["X_BEARER_TOKEN"] = creds["bearer"]
                # Save user tokens for potential future POST support
                if creds.get("access_token"):
                    os.environ.setdefault("X_ACCESS_TOKEN", creds["access_token"])
                if creds.get("access_secret"):
                    os.environ.setdefault("X_ACCESS_SECRET", creds["access_secret"])
                app.state.creds_loaded = True
    except Exception:
        pass


async def _record_event(event: dict):
    """Record an activity event to Redis shared timeline, with in-memory fallback."""
    r = _r()
    event = dict(event)
    try:
        if r:
            seq = await r.incr("xengine:activity:seq")
            event["seq"] = int(seq)
            await r.lpush("xengine:activity", json.dumps(event))
            await r.ltrim("xengine:activity", 0, 199)
            return
    except Exception:
        pass
    # Fallback to in-memory buffer
    event["seq"] = (app.state.activity[-1]["seq"] + 1) if app.state.activity else 1
    app.state.activity.append(event)
    app.state.activity = app.state.activity[-200:]


@app.get("/api/trends", response_class=JSONResponse)
async def api_trends():
    # Sandbox: static list; can be replaced with real API calls if keys provided
    topics = [
        {"tag": "#VEZE", "volume": 1200},
        {"tag": "#AI", "volume": 980},
        {"tag": "#FastAPI", "volume": 640},
    ]
    return {"trends": topics}


@app.get("/api/users/{handle}", response_class=JSONResponse)
async def api_user_intel(handle: str):
    # Try real X API if token provided, else sandbox
    user = await _x_get_user(handle)
    if user:
        pm = (user.get("public_metrics") or {})
        return {
            "handle": user.get("username") or _norm_handle(handle),
            "name": user.get("name"),
            "id": user.get("id"),
            "followers": pm.get("followers_count", 0),
            "following": pm.get("following_count", 0),
            "posts": pm.get("tweet_count", 0),
            "created_at": user.get("created_at"),
            "profile_image_url": user.get("profile_image_url"),
            "source": "xapi",
        }
    # Sandbox fallback
    # Sandbox fallback
    print("[xengine] sandbox user_intel fallback for:", _norm_handle(handle))
    return {
        "handle": _norm_handle(handle),
        "followers": 1234,
        "following": 321,
        "posts": 456,
        "source": "sandbox",
    }


@app.post("/api/post", response_class=JSONResponse)
async def api_post(request: Request):
    # Queue a post task; worker may post to X if enabled
    payload = await request.body()
    try:
        body = json.loads(payload.decode() or "{}")
    except Exception:
        body = {}
    text = (body.get("text") or "").strip()
    post_now = bool(body.get("post_now"))
    if not text:
        return JSONResponse({"queued": False, "error": "text required"}, status_code=400)
    r = _r()
    if not r:
        return JSONResponse({"queued": False, "error": "redis unavailable"}, status_code=503)
    task = {"type": "post", "text": text, "post_now": post_now}
    await r.lpush("xengine:tasks", json.dumps(task))
    # Shared activity timeline
    await _record_event({"type": "queued", "text": text})
    return {"queued": True}


@app.post("/worker/run-once")
async def worker_run_once():
    r = _r()
    if not r:
        return {"processed": 0, "error": "redis unavailable"}
    processed = 0
    for _ in range(10):
        item = await r.rpop("xengine:tasks")
        if not item:
            break
        try:
            task = json.loads(item)
            # Simulate side-effect
            await asyncio.sleep(0.05)
            await _record_event({"type": "processed", "task": task})
        except Exception:
            pass
        processed += 1
    return {"processed": processed}


@app.get("/api/activity/recent", response_class=JSONResponse)
async def api_activity_recent(limit: int = 20):
    # Read from Redis if available
    r = _r()
    if r:
        try:
            # Newest first; return up to 'limit'
            raw = await r.lrange("xengine:activity", 0, max(0, limit - 1))
            events = []
            for item in raw:
                try:
                    events.append(json.loads(item))
                except Exception:
                    pass
            return {"events": events}
        except Exception:
            pass
    # Fallback to in-memory
    buf = app.state.activity[-limit:]
    return {"events": buf}


# WebSocket: activity stream (lightweight polling of in-memory buffer)
from fastapi import WebSocket


@app.websocket("/ws/activity")
async def ws_activity(ws: WebSocket):
    await ws.accept()
    try:
        # Send initial batch from Redis if available
        r = _r()
        last_seq = 0
        try:
            if r:
                raw = await r.lrange("xengine:activity", 0, 19)
                evs = []
                for item in raw:
                    try:
                        ev = json.loads(item)
                        evs.append(ev)
                        last_seq = max(last_seq, int(ev.get("seq", 0)))
                    except Exception:
                        pass
                if evs:
                    await ws.send_text(json.dumps({"events": evs}))
            else:
                if app.state.activity:
                    last_seq = app.state.activity[-1]["seq"]
                    await ws.send_text(json.dumps({"events": app.state.activity[-20:]}))
        except Exception:
            pass
        # Stream new events by polling Redis
        while True:
            await asyncio.sleep(1.0)
            try:
                if r:
                    raw = await r.lrange("xengine:activity", 0, 19)
                    newer = []
                    hi = last_seq
                    for item in raw:
                        try:
                            ev = json.loads(item)
                            seq = int(ev.get("seq", 0))
                            if seq > last_seq:
                                newer.append(ev)
                                hi = max(hi, seq)
                        except Exception:
                            pass
                    if newer:
                        await ws.send_text(json.dumps({"events": newer}))
                        last_seq = hi
                else:
                    newer = [e for e in app.state.activity if e.get("seq", 0) > last_seq]
                    if newer:
                        await ws.send_text(json.dumps({"events": newer}))
                        last_seq = newer[-1]["seq"]
            except Exception:
                pass
    except Exception:
        try:
            await ws.close()
        except Exception:
            pass


# --- Extra APIs (metrics/search/grok/catalog) ---

class GrokIn(BaseModel):
    prompt: str


@app.get("/api/users/{handle}/metrics", response_class=JSONResponse)
async def api_user_metrics(handle: str):
    # Try real metrics via X API, else sandbox
    m = await _x_get_user_metrics(handle)
    if m:
        # No averages available without extra calls; keep sandbox for averages
        return {
            **m,
            "average_likes": None,
            "average_retweets": None,
            "average_replies": None,
            "source": "xapi",
        }
    # Sandbox fallback
    # Sandbox fallback
    print("[xengine] sandbox user_metrics fallback for:", _norm_handle(handle))
    return {
        "followers_count": 1234,
        "following_count": 56,
        "tweet_count": 789,
        "listed_count": 12,
        "average_likes": 42.0,
        "average_retweets": 7.0,
        "average_replies": 3.0,
        "source": "sandbox",
    }


@app.get("/api/search", response_class=JSONResponse)
async def api_search(q: str, max_results: int = 5):
    # Try real X recent search if token present
    real = await _x_search_recent(q, max_results)
    if real is not None:
        return {"results": real, "source": "xapi"}
    # Sandbox fallback
    print("[xengine] sandbox search fallback for:", q)
    return {"results": [f"[SANDBOX] {q} sample {i}" for i in range(max_results)], "source": "sandbox"}


@app.post("/api/grok", response_class=JSONResponse)
async def api_grok(body: GrokIn):
    # Sandbox Grok response
    text = (body.prompt or "").strip()
    if not text:
        return JSONResponse({"error": "prompt required"}, status_code=400)
    return {"reply": f"[SANDBOX GROK] {text[:120]} ..."}


# Catalog endpoints (simple in-memory demo)
CATALOG = {
    "cars": {
        "cybertron-1": {"name": "Quantum Speeder", "speed": 300},
        "neon-2": {"name": "Neon Blitz", "speed": 250},
    },
    "rockets": {
        "starfire-x": {"name": "Starfire X", "range": "100 ly"},
        "nova-7": {"name": "Nova 7", "range": "Low Orbit"},
    },
    "planets": {
        "zara-9": {"name": "Zara-9", "climate": "Arid"},
        "kryon-3": {"name": "Kryon-3", "climate": "Stormy"},
    },
}


@app.get("/api/catalog/{kind}", response_class=JSONResponse)
async def api_catalog_list(kind: str):
    data = CATALOG.get(kind)
    if not data:
        return JSONResponse({"error": "not found"}, status_code=404)
    return {"items": [{"id": k, **v} for k, v in data.items()]}


@app.get("/api/catalog/{kind}/{item_id}", response_class=JSONResponse)
async def api_catalog_item(kind: str, item_id: str):
    data = CATALOG.get(kind, {}).get(item_id)
    if not data:
        return JSONResponse({"error": "not found"}, status_code=404)
    return {"id": item_id, **data}


@app.get("/api/live/status", response_class=JSONResponse)
async def api_live_status():
    """Report live data capability and posting readiness.
    - live: True if bearer token present and a probe call succeeds
    - posting_ready: True if POST_TO_X_ENABLED=true and all user-auth keys appear present
    """
    # Check bearer token and verify with a lightweight call
    token = _x_bearer()
    live = False
    reason = None
    if token:
        # Try probing using default handle; if that fails, fall back to a known public handle.
        probe_handles = []
        dh = os.getenv("X_DEFAULT_HANDLE")
        if dh:
            probe_handles.append(dh)
        probe_handles.append("twitterdev")
        for h in probe_handles:
            user = await _x_get_user(h)
            if user:
                live = True
                break
        if not live:
            reason = "bearer_probe_failed"
    else:
        reason = "no_bearer"

    # Posting readiness
    post_flag = (os.getenv("POST_TO_X_ENABLED", "false").lower() == "true")
    ck = os.getenv("X_CONSUMER_KEY") or os.getenv("TWITTER_CONSUMER_KEY")
    cs = os.getenv("X_CONSUMER_SECRET") or os.getenv("TWITTER_CONSUMER_SECRET")
    at = os.getenv("X_ACCESS_TOKEN") or os.getenv("TWITTER_ACCESS_TOKEN")
    as_ = os.getenv("X_ACCESS_SECRET") or os.getenv("TWITTER_ACCESS_SECRET")
    posting_ready = bool(post_flag and ck and cs and at and as_)

    return {
        "live": live,
        "reason": reason,
        "posting_ready": posting_ready,
        "post_flag": post_flag,
        "have_keys": {
            "consumer": bool(ck and cs),
            "access": bool(at and as_),
        },
    }
