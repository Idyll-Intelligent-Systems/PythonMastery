# A) Unify auth & service discovery (tiny changes)

In **UniQVerse** (`uniqverse/config/settings.py`) ensure the service URLs exist:

```python
SVC_GAME="http://veze_game:8002"
SVC_EMAIL="http://veze_email:8003"
```

Expose to clients via `/hub/services`. In **libs/veze\_sdk\_py** expose tiny clients:

```python
# libs/veze_sdk_py/email.py
import httpx, os
EMAIL_BASE = os.getenv("VEZE_EMAIL_BASE","http://localhost:8003")
async def jmap_list_inbox(user_id:int, limit:int=20):
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{EMAIL_BASE}/jmap/messages", params={"mailbox_id": 1, "limit": limit})
        r.raise_for_status(); return r.json()

async def send_smtp_submission(raw_rfc822: bytes):  # if you prefer SMTP submission, add later
    ...
```

---

# B) VEZEPyEmail — add web UI & a scoped “game token”

## 1) Web UI routes (simple, Python-only)

In **VEZEPyEmail/app/routers/pages.py**:

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return request.app.state.tpl.TemplateResponse("index.html", {"request": request})

@router.get("/inbox", response_class=HTMLResponse)
async def inbox(request: Request):
    return request.app.state.tpl.TemplateResponse("inbox.html", {"request": request})

@router.get("/compose", response_class=HTMLResponse)
async def compose(request: Request):
    return request.app.state.tpl.TemplateResponse("compose.html", {"request": request})
```

Wire in **VEZEPyEmail/app/main.py**:

```python
from app.routers import jmap, ws, pages
app.include_router(pages.router, tags=["pages"])
```

Templates (add to `app/ui/templates/`):

* `index.html`: quick links (Inbox/Compose/Settings)
* `inbox.html`: lists `/jmap/messages?mailbox_id=1`
* `compose.html`: POST to a submission endpoint you already have (or create a stub `/jmap/send` that enqueues outbound)

## 2) Game-scoped access token (app password style)

Create a **minimal token issue** endpoint for the Game to call (or for users to generate & paste into Game settings).

**VEZEPyEmail/app/routers/admin.py**

```python
from fastapi import APIRouter
from pydantic import BaseModel
import secrets, time

router = APIRouter()

class TokenOut(BaseModel):
    token: str
    scope: str
    exp: int

@router.post("/tokens/game", response_model=TokenOut)
async def issue_game_token(user_id: int = 1):  # replace with real auth
    # short-lived app token for game messaging and inbox read
    scope = "game:inbox game:send"
    exp = int(time.time()) + 3600
    token = "veze-game-" + secrets.token_urlsafe(24)
    # TODO: persist hash of token + scope + user in DB
    return TokenOut(token=token, scope=scope, exp=exp)
```

Add a tiny **token validator** (middleware or helper) used by JMAP routes when `X-Game-Token` header exists.

---

# C) VEZEPyGame — add web UI + email integration + domain allowlist

## 1) Game web UI (Jinja2 + FastAPI)

Create **Game lobby UI** with pages: `/ui/lobby`, `/ui/inbox`, `/ui/settings`.

**VEZEPyGame/app/routers/pages.py**

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return request.app.state.tpl.TemplateResponse("index.html", {"request": request})

@router.get("/ui/lobby", response_class=HTMLResponse)
async def lobby(request: Request):
    return request.app.state.tpl.TemplateResponse("lobby.html", {"request": request})

@router.get("/ui/inbox", response_class=HTMLResponse)
async def inbox(request: Request):
    return request.app.state.tpl.TemplateResponse("inbox.html", {"request": request})

@router.get("/ui/settings", response_class=HTMLResponse)
async def settings(request: Request):
    return request.app.state.tpl.TemplateResponse("settings.html", {"request": request})
```

Mount in **Game/main.py**:

```python
from app.routers import pages
app.include_router(pages.router, tags=["pages"])
```

Templates:

* `index.html`: enter game / go to lobby
* `lobby.html`: match queue, friends, notifications
* `inbox.html`: shows messages fetched from VEZEPyEmail’s JMAP via backend proxy (below)
* `settings.html`: paste **Game Token** issued from Email (saved to Game DB)

## 2) Enforce @vezeuniqverse.com on sign-up (backend guard)

**VEZEPyGame/app/routers/auth.py**

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

router = APIRouter()
ALLOWED_DOMAIN = "vezeuniqverse.com"

class SignupIn(BaseModel):
    email: EmailStr
    display_name: str
    password: str

@router.post("/auth/signup")
async def signup(body: SignupIn):
    domain = body.email.split("@")[-1].lower()
    if domain != ALLOWED_DOMAIN:
        raise HTTPException(403, "Only @vezeuniqverse.com accounts are allowed in VEZEPyGame")
    # proceed: create user, hash pass, etc.
    return {"created": True}
```

**(Optional stricter)** also verify the mailbox exists by calling VEZEPyEmail (JMAP `list_mailboxes`) with a server-to-server secret or admin check.

## 3) Store and use Email “Game Token” in Game

**DB** (add to `User` model):

* `email_game_token_hash` (store hash)
* `email_address`
* `email_linked: bool`

**Game endpoint to save token**:

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import hashlib

router = APIRouter()

class TokenIn(BaseModel):
    token: str

@router.post("/settings/email-token")
async def save_email_token(body: TokenIn, user_id:int=1):
    if not body.token.startswith("veze-game-"):
        raise HTTPException(400, "Invalid token format")
    # persist hash; mark linked
    h = hashlib.sha256(body.token.encode()).hexdigest()
    # save to DB: email_game_token_hash = h ; email_linked = True
    return {"linked": True}
```

**Game backend → Inbox proxy**: call Email service with the token

```python
# VEZEPyGame/app/routers/inbox_proxy.py
from fastapi import APIRouter, HTTPException
import httpx, os

router = APIRouter()
EMAIL_BASE = os.getenv("VEZE_EMAIL_BASE", "http://localhost:8003")

@router.get("/inbox/list")
async def inbox_list(user_id:int=1):
    # fetch token hash from DB, retrieve token (or use token per-request header workflow)
    token = ...  # look up decrypted/app token for user
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{EMAIL_BASE}/jmap/messages", params={"mailbox_id":1,"limit":20},
                        headers={"X-Game-Token": token})
        if r.status_code != 200: raise HTTPException(r.status_code, r.text)
        return r.json()
```

Wire router in **Game/main.py** and add `/ui/inbox` template that fetches `/inbox/list` via HTMX/JS and renders messages.

## 4) Send in-game mail via Email submission

**Game → Email compose proxy**:

```python
# VEZEPyGame/app/routers/compose_proxy.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
import httpx, os

router = APIRouter()
EMAIL_BASE = os.getenv("VEZE_EMAIL_BASE", "http://localhost:8003")

class ComposeIn(BaseModel):
    to: EmailStr
    subject: str
    body: str

@router.post("/inbox/compose")
async def compose(body: ComposeIn, user_id:int=1):
    token = ... # lookup token
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(f"{EMAIL_BASE}/jmap/send",
                         json={"to": body.to, "subject": body.subject, "text": body.body},
                         headers={"X-Game-Token": token})
        if r.status_code != 200: raise HTTPException(r.status_code, r.text)
        return {"sent": True}
```

**On the Email side**, implement `/jmap/send` to accept `X-Game-Token`, validate scope `game:send`, and enqueue outbound mail (you already have pipeline for outbound).

## 5) In-game notifications from Email

* In **VEZEPyEmail**, when a message arrives for a user with a **Game Token on file**, emit a global event:

```python
# after inbound store
await r.xadd("global.events", {"p": json.dumps({
  "type": "email.delivered",
  "user_id": user_id,
  "subject": msg["Subject"],
  "from": from_addr
})})
```

* In **VEZEPyGame**, add a Redis consumer that listens to `global.events` and, for `email.delivered` matching current user, raises an in-game notification (WebSocket `/ws/notify`).

---

# D) Connecting from **VEZEPyUniQVerse** (Helm + Proxy)

In **UniQVerse** add proxy routes (already have a pattern):

```python
# uniqverse/app/routers/services_proxy.py
@router.get("/proxy/game/inbox")
async def proxy_game_inbox(user: UserOut = Depends(...)):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{settings.SVC_GAME}/inbox/list", params={"user_id": user.id})
        return r.json()
```

And **Helm** has a card to **VEZEPyGame** UI. Optionally embed `/proxy/game/inbox` into UniQVerse dashboard.

---

# E) Future integrations (ready hooks)

## 1) VEZEPyQuantumTime → Game physics

* Add a **Game setting** “Use Quantum Physics” (per match).
* On match start, Game emits:

  * `qt.experiment.submitted` for a small 2-qubit circuit (e.g., H+CNOT) and subscribes to `qt.sim.finished`.
  * The **result** adjusts match RNG seeds / loot tables / special abilities (deterministically from the final state’s amplitude distribution).
* UI: **Match Lobby** shows a mini Bloch/amp bar via WS stream.

## 2) VEZEPyMaps → Game navigation

* Game asks **Maps** for path/ETA:

  * `GET {SVC_MAPS}/routing/route?origin_id=...&dest_id=...`
* Render the polyline in the **game map UI**; receive live `/ws/live` positions to animate NPCs/convoys.

## 3) VEZEPyTimeVMaps → Multiverse mode

* For special game modes, call **TimeVMaps**:

  * `POST /quantum/experiment` (world\_id/timeline\_id) → adjust “timeline jump” portals in-game
  * `GET /routing/plan` with `(world_id,timeline_id,origin,dest)` to generate “branch-aware” routes

---

# F) Minimal tests you can add immediately

**VEZEPyGame/tests/test\_email\_gate.py**

```python
from fastapi.testclient import TestClient
from app.main import app

def test_signup_domain_gate():
    c = TestClient(app)
    good = c.post("/auth/signup", json={"email":"pilot@vezeuniqverse.com","display_name":"Pilot","password":"x"}).status_code
    bad  = c.post("/auth/signup", json={"email":"foo@example.org","display_name":"P","password":"x"}).status_code
    assert good == 200 and bad == 403
```

**VEZEPyEmail/tests/test\_issue\_token.py**

```python
from fastapi.testclient import TestClient
from app.main import app

def test_issue_game_token():
    c = TestClient(app)
    r = c.post("/tokens/game")
    assert r.status_code == 200
    assert r.json()["token"].startswith("veze-game-")
```

---

# G) Copilot “one-shot” prompts

### 1) For **VEZEPyEmail** (at repo root)

> Add a Jinja2 web UI with routes `/`, `/inbox`, `/compose`. Create `app/routers/pages.py` and templates. Add `/tokens/game` endpoint (scoped app token) and wire token validation on `/jmap/*` when header `X-Game-Token` is present with scope `game:inbox` / `game:send`. Emit `global.events` on inbound delivery for users who have a game token.

### 2) For **VEZEPyGame** (at repo root)

> Add Jinja2 pages `/ui/lobby`, `/ui/inbox`, `/ui/settings`. Create `/auth/signup` that only accepts `@vezeuniqverse.com`. Add `/settings/email-token` to store an app token from VEZEPyEmail. Implement `/inbox/list` and `/inbox/compose` that call VEZEPyEmail (`/jmap/messages`, `/jmap/send`) with header `X-Game-Token`. Add a Redis consumer to `global.events` and push notifications on `email.delivered`.

### 3) For **UniQVerse** (optional)

> Add `/proxy/game/*` passthroughs for inbox list/compose and render a dashboard card that shows the latest 5 messages from the user’s in-game inbox using the proxy.

---
