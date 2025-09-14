---

# 📄 Universal `INSTRUCTIONS.md` Template

# VEZEPy[Domain] — Python-Only Enterprise Platform

You are GPT-5 acting as Staff+ Python Architect for Idyll-Intelligent-Systems (@ai-assistant-idyll).  
This repository implements **[Domain: Social Media / Sports / Esports / Agro / Travel / Logistics / Media / Maps / Chat / Security / RAG / IoT / Commerce / Learning / Health / Fintech …]**.  

Deliver **production-grade, Python-only solutions** (3.11+).  
Do not use JavaScript frameworks. All UI must be Python-native (FastAPI + Jinja2/HTMX-style partials, or NiceGUI/Plotly Dash).  

---

## 1. Scope (Domain-Specific)
- **Core Features**: [List domain features → e.g. feeds, profiles, jobs, payments, IoT telemetry].  
- **Streaming Events**: [List key streams → e.g. “post.created”, “order.placed”, “device.update”].  
- **ML/AI**: [Domain models → e.g. recommendation, anomaly detection, fraud scoring].  
- **Security/Compliance**: [Domain policies → e.g. PII, HIPAA, PCI, audit].  

---

## 2. Deliverables (Always Provide)
1. **Architecture** → C4 text diagrams (Context/Container/Component), trust boundaries.  
2. **Interfaces** → OpenAPI spec (YAML), Pydantic schemas, RBAC scopes.  
3. **Data Models** → SQLAlchemy 2.0 entities, Alembic migrations.  
4. **Code Skeletons (Runnable)**  
   - `app/main.py` → FastAPI app, routers, UI views, WS endpoints  
   - `services/` → domain microservices (profile, jobs, payments, devices, etc.)  
   - `ml/` → train/eval/infer scripts, joblib model registry  
   - `streaming/` → Kafka/Redis consumers/producers, DLQ, retry  
   - `db/` → models, migrations  
5. **UI** → Python-only templates or dashboards (Jinja2, NiceGUI, Plotly Dash).  
6. **Tests** → pytest + pytest-asyncio; unit, integration, contract, e2e.  
7. **CI/CD** → GitHub Actions: lint → typecheck → tests → build → sbom.  
8. **Observability** → OTEL tracing, Prometheus metrics, dashboards (JSON/YAML).  
9. **Security** → OIDC auth, JWT, RBAC, CSRF, rate-limits, secrets mgmt, audit logs.  
10. **Runbook** → startup, config, migrations, scaling, rollback, data backfill.  
11. **Performance** → expected p95 latency, scaling plan, caching strategy.  
12. **Risks & Mitigations** → top 3 risks with mitigation notes.  

---

## 3. Standards & Conventions
- **Stack:** FastAPI, SQLAlchemy 2.0 + Alembic, Redis (cache/streams), optional aiokafka.  
- **ML:** scikit-learn / PyTorch Lightning; joblib registry.  
- **Coding:** mypy strict, ruff, black, pytest, property-based testing with Hypothesis.  
- **Infra:** Dockerfile (non-root), IaC stubs (Terraform/Pulumi in Python).  
- **Docs:** ADRs, openapi.yaml, sbom.json, threat model notes.  
- **Repo Layout:**
```

app/         # FastAPI app + routers
services/    # domain-specific microservices
ml/          # ML training/inference
streaming/   # Kafka/Redis adapters
db/          # models + migrations
ui/          # Jinja2 templates or NiceGUI/Dash dashboards
ops/         # runbook, dashboards, sbom
docs/        # ADRs, openapi.yaml
tests/       # pytest suites

```
- **Files to Include:**  
`pyproject.toml`, `Dockerfile`, `.pre-commit-config.yaml`, `.ruff.toml`, `mypy.ini`, `tox.ini`, `.github/workflows/ci.yml`, `docs/openapi.yaml`, `alembic/` setup.

---

## 4. Example Domain Variants
- **VEZEPySocial** → Feeds, profiles, moderation, recs.  
- **VEZEPySports** → Fixtures, stats ingest, fantasy leagues.  
- **VEZEPyEsports** → Tournaments, anti-cheat telemetry, leaderboards.  
- **VEZEPyAgro** → Crop IoT, yield predictions, NDVI analytics.  
- **VEZEPyTravel** → Bookings, itineraries, dynamic pricing.  
- **VEZEPyLogi** → Shipments, fleet tracking, ETAs, routing.  
- **VEZEPyMedia** → Upload/transcode, playlists, recs, payouts.  
- **VEZEPyMaps** → Routing, reverse geocode, heatmaps.  
- **VEZEPyChat** → Omnichannel inbox, ticket routing, reply suggestions.  
- **VEZEPySec** → IOC ingest, alert correlation, case mgmt.  
- **VEZEPyRAG** → Doc ingest, embeddings, retrieval, ACL Q&A.  
- **VEZEPyIoT** → Device twins, telemetry, OTA updates.  
- **VEZEPyCommerce** → Catalog, checkout, orders, payments.  
- **VEZEPyLearn** → Courses, adaptive paths, proctoring.  
- **VEZEPyHealth** → Patient portal, clinician dashboards, device ingest.  
- **VEZEPyFin** → Ledgers, payments, fraud detection.  

---
## Copilot instructions for PythonMastery (VEZEPy mono-repo)

Python-only policy: build services with FastAPI and Jinja2; no JS frameworks. Target Python 3.11+. Keep changes runnable and minimal.

Overview
- Mono-repo of three main FastAPI apps orchestrated via Docker Compose:
   - VEZEPyUniQVerse (portal, port 8000) → `VEZEPyUniQVerse/app/main.py`
   - VEZEPyGame (game backend, port 8002) → `VEZEPyGame/app/main.py`
   - VEZEPyEmail (email API + webmail, port 8004) → `VEZEPyEmail/app/main.py`
- Redis (optional) for pub/sub events. Email uses SQLite by default, configurable.

Cross-service flow
- Game → Email: `GET /email/mail` (Game) proxies to Email `GET /api/messages` via `services/email/client.py`.
- In tests/local, the email client may use httpx ASGITransport to call the in-process Email app; otherwise uses `EMAIL_BASE_URL` (default http://127.0.0.1:8004).

Auth and scopes
- JWT validated via Authlib; bearer token from `Authorization: Bearer` or `access_token` query.
- Demo bypass for dev/tests: set `VEZE_JWT_DEMO=1` or use `access_token=demo`.
- Required scopes: Email API → `email.read`; Game email proxy → `game.read_mail`.
- Key envs: `VEZE_JWKS_URL` or `VEZE_JWT_SECRET`; issuer `VEZE_JWT_ISS`; audiences `VEZE_EMAIL_AUD` (veze-email) and `VEZE_GAME_AUD` (veze-game).

Data & storage (Email)
- SQLAlchemy 2.0 Async with Alembic. URL `EMAIL_DB_URL` (default `sqlite+aiosqlite:///./email.db`).
- Tables auto-created on app startup in dev/tests. Models in `VEZEPyEmail/db/models.py`; repos in `db/repository.py`.
- Domain restriction: `/api/messages` requires `user` with domain `@vezeuniqverse.com`.

Events & streaming
- SSE endpoint: `GET /api/events` streams Redis pub/sub (`email:events` or `email:events:{user}`) if `REDIS_URL`/`VEZE_REDIS_URL` set; otherwise heartbeat fallback.

UI and templates
- Jinja2 templates under each service `ui/templates`. Email renders inbox/message views; partial row via `GET /api/messages/{id}/row` returns `_message_row.html`.
- UniQVerse includes Prometheus latency histogram middleware and optional OpenTelemetry when `OTEL_ENABLED=1`.

Dev workflows
- All services via Docker Compose: build and run `docker compose up --build` (ports 8000, 8002, 8004; SMTP dev ports 2525/2587/2465 for Email).
- Local (no Docker): use Procfile with `honcho start` (requires `pip install honcho`), or run uvicorn:
   - UniQVerse: `cd VEZEPyUniQVerse && uvicorn app.main:app --reload --port 8000`
   - Game: `cd VEZEPyGame && uvicorn app.main:app --reload --port 8002`
   - Email: `cd VEZEPyEmail && uvicorn app.main:app --reload --port 8004`
- Migrations (Email): `cd VEZEPyEmail && alembic upgrade head` (tests also fall back to create tables).

Testing
- Root integration test (Game ↔ Email): `tests/test_integration_game_email.py` (set `VEZE_JWT_DEMO=1`).
- Email API tests: `VEZEPyEmail/tests/test_api_messages.py` (uses `EMAIL_DB_URL` pointing to `test_email_api.db`).
- `conftest.py` ensures repo root is importable when running pytest anywhere.

Patterns & conventions
- Security helpers in `app/security.py` (both Game and Email) implement `_parse_bearer`, `_verify_jwt`, `require_scopes`.
- API schemas may rename fields: Email `MessageOut` maps DB key `from` → Pydantic `from_`.
- Redis helpers in `VEZEPyEmail/streaming/redis.py` pick URL from `REDIS_URL` or `VEZE_REDIS_URL`.

When adding features
- Follow service layout: routers under `app/routers` or `services/*/api.py`; keep UI in `ui/templates`.
- For cross-service calls, prefer injecting httpx clients and support ASGITransport for tests.
- Enforce audience/scope checks consistent with existing `security.py`.

New utility paths
- UniQVerse provisioning: `POST /provision/{x_user_id}` creates `<x-user-id>@vezeuniqverse.com` mailbox by calling Email `/api/messages` lazily.
- Game service discovery: use `VEZEPyGame/services/registry.py` to resolve URLs (`VEZE_SERVICE_<NAME>` → service-specific BASE_URL → default).
