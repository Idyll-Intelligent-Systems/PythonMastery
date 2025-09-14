# VEZE UniQVerse Architecture Map

This document maps the entrypoint → services → integration → DB paths in the PythonMastery mono-repo.

## 1) Entrypoint Portal: VEZEPyUniQVerse (8000)

- UI & routes: `VEZEPyUniQVerse/app/main.py`, `routers/pages.py`, `routers/ws.py`.
- Service directory UI (Helm): `config/services.json` (env overrides `VEZE_SERVICE_<NAME>`).
- Prometheus middleware + optional OTEL.
- New provisioning route: `POST /provision/{x_user_id}` → derives `<x-user-id>@vezeuniqverse.com` and calls Email API to create mailbox lazily.
  - Client: `VEZEPyUniQVerse/app/clients/email_client.py` (httpx with ASGITransport in tests via `EMAIL_ASGI=1`).

## 2) Core Game Backend: VEZEPyGame (8002)

- App: `VEZEPyGame/app/main.py` includes routers for matchmaking, leaderboards, telemetry, inventory, ml, ws, public, and `email`.
- Email integration API: `VEZEPyGame/services/email/api.py` → `GET /email/mail`.
  - Security: `VEZEPyGame/app/security.py` (`_parse_bearer`, `_verify_jwt`, `require_scopes`). Requires `game.read_mail` scope.
  - Client: `VEZEPyGame/services/email/client.py` uses service registry `services/registry.py` to resolve base URL.
  - Test mode: `EMAIL_ASGI=1` uses in-process Email ASGI app.

## 3) Email Platform: VEZEPyEmail (8004, SMTP dev ports 25/587/465)

- App: `VEZEPyEmail/app/main.py`, routers `app/routers/api.py` (messages, SSE), UI (`ui/templates`).
- Security: `VEZEPyEmail/app/security.py`, requires `email.read` scope; demo bypass via `VEZE_JWT_DEMO=1` or `access_token=demo`.
- DB: SQLAlchemy async (`db/database.py`), models (`db/models.py`), repo functions (`db/repository.py`). Default `EMAIL_DB_URL=sqlite+aiosqlite:///./email.db`.
- Domain policy: `/api/messages` enforces `@vezeuniqverse.com` emails.
- Events: SSE `GET /api/events` uses Redis pub/sub channels `email:events` or per-user channel; fallback heartbeat.
- SMTP pipeline (design & stubs): `smtp/`, `pipeline/`, `streaming/queues.py` for DKIM/SPF/DMARC, spam filter, and delivery workers.

## 4) Auth & Scopes

- Demo dev/test: `VEZE_JWT_DEMO=1` or `access_token=demo`.
- Validation: JWKS (`VEZE_JWKS_URL`) or HS secret (`VEZE_JWT_SECRET`); issuer `VEZE_JWT_ISS`.
- Audiences: `VEZE_GAME_AUD` (veze-game), `VEZE_EMAIL_AUD` (veze-email).
- Scopes:
  - Game email proxy requires: `game.read_mail`.
  - Email API requires: `email.read`.

## 5) Service Discovery

- Environment-first: `VEZE_SERVICE_<NAME>` (e.g., `VEZE_SERVICE_EMAIL`).
- Fallbacks: service-specific `*_BASE_URL` env (e.g., `EMAIL_BASE_URL`) then hardcoded localhost defaults.
- Helper: `VEZEPyGame/services/registry.py`.

## 6) Tests

- Integration: `tests/test_integration_game_email.py` (sets `VEZE_JWT_DEMO=1`; seeds Email UI; calls Game → Email).
- Email API: `VEZEPyEmail/tests/test_api_messages.py` (configures `EMAIL_DB_URL` test sqlite; optional Alembic; verifies token handling).
- Path shim: root `conftest.py` makes repo importable from any cwd.

## 7) Dev & Ops

- Compose: `docker-compose.yml` (services: redis, uniqverse, game, email). Healthchecks hit `/health` endpoints.
- Procfile: `honcho start` alternative for local uvicorn.
- Email migrations: `cd VEZEPyEmail && alembic upgrade head` (tests fallback to create tables).
- Redis: `REDIS_URL` or `VEZE_REDIS_URL` enables SSE events and pipelines.

## 8) Extending the Metaverse

- Add new service routers under `VEZEPyGame/services/<domain>/api.py`.
- Expose links via UniQVerse Helm (`config/services.json`) and enforce auth with shared `security.py` helpers.
- Use email identity `<x-user-id>@vezeuniqverse.com` as the cross-service user key.
