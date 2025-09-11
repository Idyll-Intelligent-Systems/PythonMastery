---

# VEZEPyEmail — Python-only Email Platform (@vezeuniqverse.com)

## Architecture (C4-brief)

* **Gateway & Webmail (FastAPI + Jinja2/NiceGUI)**
  Auth (OIDC/app passwords), inbox UI, compose, search, settings, admin console, OpenAPI.
* **SMTP MSA/MTA (aiosmtpd)**

  * **Submission** (587 STARTTLS / 465 SMTPS) for authenticated senders.
  * **Inbound** (25) for MX — accepts mail for `@vezeuniqverse.com`.
* **Message Pipeline**

  * **DKIM Sign** (outbound), **SPF/DMARC** check (inbound).
  * **Spam Filter** (sklearn), **Sieve-like rules**, **Attachments & virus hook**.
  * **Delivery Queue** (Redis Streams) with N-try exponential backoff, DLQ.
  * **Local delivery** (Mailbox store: Postgres metadata + object store/file store for MIME blobs).
  * **Remote delivery** (smtplib + TLS) with rate & policy control.
* **Modern Sync API: JMAP-like over HTTP**
  Mailbox/list/get/changes; send; flags; push via WebSockets. (Avoids implementing IMAP.)
* **Data**:
  Postgres (users, mailboxes, messages, rules, keys), Redis (sessions, queues), disk/object store (`/data/mail/…`) for raw RFC822.
* **Security**:
  OIDC (Authlib), app passwords, 2FA; TLS everywhere; DKIM/DMARC/SPF; outbound reputation controls; journaling & audit.
* **Observability**:
  OpenTelemetry traces; Prometheus metrics (SMTP accept rate, queue depth, spam score dist, delivery latency).

---

## Repository Layout

```
VEZEPyEmail/
├─ pyproject.toml
├─ Dockerfile
├─ .github/workflows/ci.yml
├─ docs/
│  ├─ openapi.yaml
│  └─ dns-records.md          # sample MX/SPF/DKIM/DMARC
├─ app/                       # Webmail + JMAP-like API
│  ├─ main.py
│  ├─ auth.py
│  ├─ routers/{jmap.py,admin.py,ws.py}
│  └─ ui/templates/{base.html,inbox.html,compose.html,settings.html,admin.html}
├─ smtp/
│  ├─ server.py               # aiosmtpd controller
│  ├─ handlers.py             # submission/inbound handlers
│  ├─ dkim_sign.py
│  ├─ spf_dmarc.py
│  └─ queue_outbound.py       # relay to remote MX
├─ pipeline/
│  ├─ accept.py               # parse/store envelope, enqueue filters
│  ├─ spam.py                 # sklearn model, trainer
│  ├─ sieve.py                # simple rule engine
│  ├─ deliver_local.py
│  └─ deliver_remote.py
├─ db/
│  ├─ database.py
│  ├─ models.py               # User, Domain, Mailbox, Message, Rule, Key
│  └─ migrations/             # Alembic
├─ storage/
│  ├─ blobs.py                # store/retrieve RFC822 blobs
│  └─ paths.py
├─ streaming/
│  ├─ queues.py               # Redis Streams helpers
│  ├─ inbound_worker.py       # run filters → local/remote delivery
│  ├─ outbound_worker.py      # retry/dlq for remote sends
│  └─ bounce_worker.py        # DSN/NDR handling
├─ ml/
│  ├─ spam_model.py
│  └─ train_spam.py
├─ ops/{runbook.md,dashboards/metrics.json,sbom.json}
└─ tests/{test_smtp_accept.py,test_jmap_list.py}
```

---

## pyproject.toml (key deps)

```toml
[project]
name = "veze-email"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115", "uvicorn[standard]>=0.30", "jinja2>=3.1",
  "aiosmtpd>=1.4", "email-validator>=2.1",
  "dkimpy>=1.1.5", "pyspf>=2.0.14", "authlib>=1.3",
  "SQLAlchemy>=2.0", "asyncpg>=0.29", "alembic>=1.13",
  "redis>=5.0", "httpx>=0.27", "loguru>=0.7",
  "prometheus-client>=0.20", "opentelemetry-sdk>=1.27.0",
  "opentelemetry-instrumentation-fastapi>=0.48b0",
  "opentelemetry-exporter-otlp>=1.27.0",
  "pydantic>=2.8", "python-multipart>=0.0.9",
  "scikit-learn>=1.5", "joblib>=1.4",
]

[project.optional-dependencies]
dev = ["ruff>=0.5","black>=24.8","mypy>=1.11","pytest>=8.3","pytest-asyncio>=0.23","hypothesis>=6.104"]
```

---

## Core Data Model (SQLAlchemy 2.0)

* `Domain(id, name)` → seed with `vezeuniqverse.com`
* `User(id, email_local, domain_id, display_name, pwd_hash, app_passwords[], roles[], created_at)`
* `Mailbox(id, user_id, name)` → “INBOX”, “Sent”, “Junk”, “Trash”, …
* `Message(id, mailbox_id, msg_uid, subject, from_addr, to_addrs[], date, flags[], size, spam_score, blob_path, headers_json, created_at)`
* `OutboundPolicy(id, domain_id, max_rps, max_per_day, dkim_selector, dkim_pem_path)`
* `Rule(id, user_id, match_json, action_json)` (simple Sieve subset)
* `Audit(id, actor, action, entity, entity_id, ts, meta_json)`

---

## SMTP Server (aiosmtpd) — `smtp/server.py`

```python
import asyncio, ssl
from aiosmtpd.controller import Controller
from smtp.handlers import InboundHandler, SubmissionHandler

def start_smtp():
    # Inbound MX (25)
    inbound = Controller(InboundHandler(), hostname="0.0.0.0", port=25)
    inbound.start()

    # Submission (587 STARTTLS)
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain("/certs/fullchain.pem","/certs/privkey.pem")
    submission = Controller(SubmissionHandler(tls_context=context, require_auth=True),
                            hostname="0.0.0.0", port=587, starttls=True, tls_context=context)
    submission.start()

    # SMTPS (465)
    smtps = Controller(SubmissionHandler(tls_context=context, require_auth=True),
                       hostname="0.0.0.0", port=465, ssl_context=context)
    smtps.start()
    return inbound, submission, smtps

if __name__ == "__main__":
    start_smtp()
    asyncio.get_event_loop().run_forever()
```

### Inbound & Submission Handlers — `smtp/handlers.py`

```python
from aiosmtpd.handlers import AsyncMessage
from email.message import EmailMessage
from pipeline.accept import accept_inbound, accept_submission

class InboundHandler(AsyncMessage):
    async def handle_message(self, message: EmailMessage) -> None:
        await accept_inbound(message)   # SPF/DMARC, spam, rules, local or relay

class SubmissionHandler(AsyncMessage):
    def __init__(self, tls_context=None, require_auth=False):
        super().__init__()
        self.tls_context = tls_context
        self.require_auth = require_auth
    async def handle_message(self, message: EmailMessage) -> None:
        await accept_submission(message)  # DKIM sign + outbound queue
```

---

## Accept & Pipeline — `pipeline/accept.py`

```python
from email.message import EmailMessage
from email.utils import parseaddr, getaddresses
from pipeline.spam import score_spam
from pipeline.sieve import apply_rules
from smtp.spf_dmarc import check_spf_dmarc
from smtp.dkim_sign import sign_outbound_if_needed
from streaming.queues import enqueue_inbound, enqueue_outbound
from storage.blobs import save_blob
from db.database import with_session
from db.models import Message, Mailbox, User, Domain

LOCAL_DOMAIN = "vezeuniqverse.com"

@with_session
async def accept_inbound(msg: EmailMessage, session):
    verdict = await check_spf_dmarc(msg)
    spam = await score_spam(msg)
    blob_path = await save_blob(msg)
    # route recipients
    to_list = [addr for _, addr in getaddresses([msg.get("To","")])]
    for rcpt in to_list:
        local = rcpt.lower().split("@",1)
        if len(local)==2 and local[1] == LOCAL_DOMAIN:
            # local delivery
            user_local = local[0]
            user = await User.get_by_local(session, user_local)  # pseudo
            inbox = await Mailbox.get_or_create(session, user.id, "INBOX")
            m = Message(mailbox_id=inbox.id, subject=msg.get("Subject",""), from_addr=parseaddr(msg.get("From",""))[1],
                        to_addrs=to_list, date=msg.get("Date"), flags=[], size=len(msg.as_bytes()),
                        spam_score=spam, blob_path=blob_path, headers_json=dict(msg.items()))
            session.add(m)
        else:
            # relay to remote
            await enqueue_outbound({"raw_blob": blob_path, "rcpt": rcpt})
    await session.commit()
    await enqueue_inbound({"event":"message.accepted","blob": blob_path,"spam":spam,"spf_dmarc":verdict})

async def accept_submission(msg: EmailMessage):
    await sign_outbound_if_needed(msg)          # DKIM
    blob_path = await save_blob(msg)
    await enqueue_outbound({"raw_blob": blob_path, "rcpt": msg.get("To")})
```

---

## DKIM / SPF / DMARC (stubs)

`/smtp/dkim_sign.py`

```python
import dkim
def sign_outbound_if_needed(msg):
    # load selector & key from DB or file
    selector = b"veze"
    domain = b"vezeuniqverse.com"
    with open("/keys/dkim_private.pem","rb") as f: key = f.read()
    hdrs = [b"from", b"to", b"subject", b"date", b"mime-version", b"content-type"]
    sig = dkim.sign(message=msg.as_bytes(), selector=selector, domain=domain, privkey=key, include_headers=hdrs)
    msg["DKIM-Signature"] = sig.decode()
```

`/smtp/spf_dmarc.py`

```python
import spf
def check_spf_dmarc(msg):
    # simple SPF check; DMARC alignment logic can be extended
    # ip, mailfrom, helo would be passed from SMTP session; stubbed here.
    return {"spf": "neutral", "dmarc": "none"}
```

---

## Redis Streams Queues — `streaming/queues.py`

```python
import redis.asyncio as redis, os, json
r = redis.from_url(os.getenv("REDIS_URL","redis://localhost:6379/0"))
async def enqueue_inbound(payload: dict):  await r.xadd("inbound.events", {"p": json.dumps(payload)})
async def enqueue_outbound(payload: dict): await r.xadd("outbound.queue", {"p": json.dumps(payload)})
async def enqueue_bounce(payload: dict):  await r.xadd("bounce.queue", {"p": json.dumps(payload)})
```

### Outbound delivery worker — `pipeline/deliver_remote.py`

```python
import smtplib, ssl, email, json, asyncio, os, redis.asyncio as redis
from email import policy
from storage.blobs import load_blob
r = redis.from_url(os.getenv("REDIS_URL","redis://localhost:6379/0"))

async def run():
    group, consumer = "outbound","w1"
    try: await r.xgroup_create("outbound.queue", group, id="$", mkstream=True)
    except Exception: pass
    while True:
        xs = await r.xreadgroup(group, consumer, {"outbound.queue": ">"}, count=10, block=5000)
        for _, msgs in xs or []:
            for msg_id, data in msgs:
                p = json.loads(data["p"])
                raw = await load_blob(p["raw_blob"])
                message = email.message_from_bytes(raw, policy=policy.SMTP)
                try:
                    ctx = ssl.create_default_context()
                    with smtplib.SMTP_SSL(host="mx.remote.example", port=465, context=ctx) as s:
                        s.send_message(message)
                    await r.xack("outbound.queue", group, msg_id)
                except Exception as e:
                    # let it be redelivered (retry policy handled by stream trimming schedule)
                    print("relay error", e)

if __name__ == "__main__":
    asyncio.run(run())
```

### Local delivery worker — `pipeline/deliver_local.py`

```python
# (most local delivery already done in accept_inbound; this worker can handle re-routing, rules, etc.)
```

### Bounce handler — `streaming/bounce_worker.py`

```python
# parse DSN/NDR messages and notify sender; adjust reputation
```

---

## Storage for MIME blobs — `storage/blobs.py`

```python
from email.message import EmailMessage
from pathlib import Path
import aiofiles, os, time

BASE = Path(os.getenv("MAILSTORE","/data/mail"))
BASE.mkdir(parents=True, exist_ok=True)

async def save_blob(msg: EmailMessage) -> str:
    ts = int(time.time()*1000)
    path = BASE / f"{ts}.eml"
    async with aiofiles.open(path, "wb") as f:
        await f.write(msg.as_bytes())
    return str(path)

async def load_blob(path: str) -> bytes:
    async with aiofiles.open(path, "rb") as f:
        return await f.read()
```

---

## JMAP-like API (HTTP) — `app/routers/jmap.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.database import get_session
from db.models import Mailbox, Message

router = APIRouter()

@router.get("/jmap/mailbox")
async def list_mailboxes(session: AsyncSession = Depends(get_session), user_id: int = 1):
    res = await session.execute(select(Mailbox).where(Mailbox.user_id==user_id))
    return [{"id": m.id, "name": m.name} for m in res.scalars().all()]

@router.get("/jmap/messages")
async def list_messages(mailbox_id: int, limit: int = 50, session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(Message).where(Message.mailbox_id==mailbox_id).order_by(Message.id.desc()).limit(limit))
    msgs = res.scalars().all()
    return [{
        "id": m.id, "subject": m.subject, "from": m.from_addr, "date": m.date,
        "flags": m.flags, "size": m.size, "spam_score": m.spam_score
    } for m in msgs]
```

---

## Webmail (Jinja2) — `app/ui/templates/inbox.html`

```html
{% extends "base.html" %}
{% block content %}
<h1>Inbox</h1>
<ul>
  {% for m in messages %}
    <li><b>{{m.subject}}</b> — {{m.from}} <small>{{m.date}}</small></li>
  {% endfor %}
</ul>
{% endblock %}
```

---

## Spam Classifier (sklearn) — `ml/spam_model.py`

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
import joblib, re

def train_spam(texts: list[str], labels: list[int]):
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1,2), min_df=3)
    X = vec.fit_transform(texts)
    clf = SGDClassifier(loss="log_loss", max_iter=2000, random_state=42)
    clf.fit(X, labels)
    joblib.dump((vec, clf), "ml/models/spam.joblib")

def score(text: str) -> float:
    vec, clf = joblib.load("ml/models/spam.joblib")
    X = vec.transform([text])
    proba = clf.predict_proba(X)[0,1]
    return float(proba)
```

`pipeline/spam.py`

```python
from email.message import EmailMessage
from ml.spam_model import score as score_spam_text
def score_spam(msg: EmailMessage) -> float:
    body = (msg.get_body(preferencelist=("plain","html")) or msg).get_content()
    return score_spam_text(body[:10000])
```

---

## FastAPI App — `app/main.py`

```python
from fastapi import FastAPI
from app.routers import jmap
from app.routers import ws  # notifications
app = FastAPI(title="VEZEPyEmail JMAP & Webmail")
app.include_router(jmap.router, tags=["jmap"])
app.include_router(ws.router, tags=["ws"])

@app.get("/health")
async def health(): return {"status":"ok"}
```

---

## WebSocket Notifications — `app/routers/ws.py`

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
router = APIRouter()
clients: set[WebSocket] = set()

@router.websocket("/ws/notify")
async def notify(ws: WebSocket):
    await ws.accept(); clients.add(ws)
    try:
        while True: await ws.receive_text()
    except WebSocketDisconnect:
        clients.discard(ws)

async def broadcast(event: dict):
    for c in list(clients):
        try: await c.send_json(event)
        except Exception: clients.discard(c)
```

---

## DNS Records (docs/dns-records.md — examples to set for **vezeuniqverse.com**)

* **MX**:
  `vezeuniqverse.com.  3600  MX 10  mx1.vezeuniqverse.com.` (point to your server IP)
* **A/AAAA**:
  `mx1.vezeuniqverse.com. -> <your.public.ip>`
* **SPF** (TXT):
  `v=spf1 mx include:_spf.vezeuniqverse.com -all` (or just `v=spf1 mx -all` if only your MX sends)
* **DKIM** (TXT at `veze._domainkey.vezeuniqverse.com`):
  `v=DKIM1; k=rsa; p=<public-key>`
* **DMARC** (TXT at `_dmarc.vezeuniqverse.com`):
  `v=DMARC1; p=quarantine; rua=mailto:dmarc@vezeuniqverse.com; adkim=s; aspf=s`

> You’ll also open ports 25/465/587 and ensure TLS certs in `/certs`.

---

## CI/CD & Docker

**Dockerfile**

```dockerfile
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser:appuser /app
USER appuser
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .
COPY . .
EXPOSE 8000 25 465 587
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
```

**GitHub Actions** (lint → type → test → sbom)

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

## Runbook (ops/runbook.md)

* **Dev up (webmail + JMAP):**

  ```bash
  pip install -e .[dev]
  uvicorn app.main:app --reload
  ```
* **Start SMTP:**

  ```bash
  python smtp/server.py
  ```
* **Workers (queues):**

  ```bash
  python streaming/inbound_worker.py
  python pipeline/deliver_remote.py
  python streaming/bounce_worker.py
  ```
* **Migrations:**

  ```bash
  alembic upgrade head
  ```
* **Smoke:**

  * Send a test email to `user@vezeuniqverse.com` (simulate via `smtplib.SMTP('localhost',25)`); see it appear in `GET /jmap/messages?mailbox_id=<inbox>`.
  * Compose via submission (587) using an app password; verify DKIM is added.
* **SLOs:**

  * Inbound acceptance p95 < 200ms (excluding content scanning).
  * Outbound first-attempt relay success > 98% (non-temporary).
  * Webmail list p95 < 250ms for top 50 messages.
* **Abuse/Risk:**

  * Rate-limit per user/domain; outbound quota; spam score gates; bounce rate alarms; DKIM key rotation every 90 days.

---

## Futuristic Features (all Python)

* **JMAP-native** sync (faster than IMAP), WS push for instant updates.
* **Smart triage** (priority inbox) using per-user learning from labels/opens.
* **Summarize threads** and **extract tasks** for productivity views.
* **Encrypted mail at rest** (per-user AES keys in KMS wrapper; Python hooks).
* **Journaling** to object store with WORM-like retention policy (append-only).
* **Outbound reputation** controls (auto warm-up ramp, per-ASN throttles).

---

### Want me to also add a **ready-to-run docker-compose** (Postgres, Redis, cert volume) and a **prebaked Alembic migration** so you can boot the whole stack in one command?
