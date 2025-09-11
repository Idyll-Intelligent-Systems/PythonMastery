# VEZEPyCGrow — Career Growth Platform (Python Only)

## 1) Architecture (C4-in-brief)

* **Gateway + Web UI (FastAPI + Jinja2/NiceGUI/HTMX-style partials)**
  Auth, session, RBAC; public pages; member dashboards; recruiter/enterprise consoles; admin ops.
* **Core Services (FastAPI microservices, all Python)**

  * **Profile & Resume**: member profiles, resume vault (PDF/DOCX parsing → JSON), skills graph.
  * **Jobs & Search**: job ingestion, normalization, search/filter/sort, multi-tenant posting.
  * **Match & Recommend**: embeddings + rules; candidate↔job ranking, nudges.
  * **ATS Checker & Enhancer**: parse, score vs JD, rewrite suggestions, keyword coverage.
  * **Recruiter Outreach**: campaigns, sequencing, consent & compliance.
  * **Analytics**: funnel metrics, cohort views, career insights, salary curves.
* **Streaming**: Redis Streams *or* Kafka (adapters for both). Events: `resume.uploaded`, `jd.ingested`, `match.scored`, `outreach.sent`, `pii.accessed` (audited).
* **Data**: Postgres (SQLAlchemy 2.0 + Alembic), Redis (cache/sessions/streams), optional DuckDB for offline analytics.
* **Observability**: OpenTelemetry, Prometheus metrics, structured logs.
* **Security/Compliance**: OIDC, short-lived JWT, RBAC, consent tracking, PII tags, audit trails.

## 2) Repository Layout

```
VEZEPyCGrow/
├─ INSTRUCTIONS.md
├─ pyproject.toml
├─ Dockerfile
├─ .github/workflows/ci.yml
├─ docs/
│  ├─ openapi.yaml
│  ├─ adr-0001-architecture.md
│  └─ runbook.md
├─ config/
│  ├─ settings.py
│  └─ logging.py
├─ app/                       # Gateway + UI
│  ├─ main.py
│  ├─ auth.py                 # OIDC, JWT, sessions, CSRF
│  ├─ ui/
│  │  ├─ templates/{base.html,member.html,recruiter.html,admin.html}
│  │  └─ views.py
│  └─ routers/{public.py,member.py,recruiter.py,enterprise.py,admin.py,ws.py}
├─ services/
│  ├─ profile/
│  │  ├─ api.py
│  │  ├─ resume_parse.py      # PDF/DOCX→JSON (python-docx, pdfminer)
│  │  └─ skills_graph.py
│  ├─ jobs/
│  │  ├─ api.py
│  │  ├─ normalize.py
│  │  └─ search.py            # filters, ranking
│  ├─ match/
│  │  ├─ api.py               # candidate↔job scoring
│  │  ├─ features.py
│  │  └─ rank.py
│  ├─ ats/
│  │  ├─ api.py               # score, rewrite, keyword coverage
│  │  └─ rewrites.py          # Python-only heuristics + templates
│  ├─ outreach/
│  │  ├─ api.py               # recruiter campaigns, consent checks
│  │  └─ sequencer.py
│  └─ analytics/
│     ├─ api.py               # dashboards, cohort metrics
│     └─ queries.py
├─ ml/
│  ├─ embeddings.py           # sentence-transformers (pure Python API)
│  ├─ train_matcher.py        # sklean/XGB or Torch/Lightning
│  ├─ eval.py
│  └─ infer.py                # FastAPI subrouter for /ml/*
├─ streaming/
│  ├─ redis_consumer.py
│  ├─ kafka_consumer.py
│  └─ producers.py
├─ db/
│  ├─ models.py               # SQLAlchemy 2.0 models
│  └─ migrations/             # Alembic
├─ ops/
│  ├─ dashboards/             # Grafana JSON
│  └─ sbom.json
└─ tests/
   ├─ test_health.py
   ├─ test_resume_parse.py
   ├─ test_match_rank.py
   └─ test_ats_score.py
```

## 3) Data Model (SQLAlchemy 2.0 summary)

* **User**(id, email, hash, roles\[], tenant\_id, consent\_json, created\_at)
* **MemberProfile**(user\_id FK, headline, summary, locations\[], skills\[], exp\_years, visibility, salary\_expectation, updated\_at)
* **Resume**(id, user\_id, source\_file\_path, parsed\_json, version, pii\_tags\[], created\_at)
* **Job**(id, tenant\_id, title, description, location, skills\_req\[], seniority, salary\_range, jd\_vector, status, created\_at)
* **Application**(id, job\_id, user\_id, status, score, stage, created\_at)
* **MatchScore**(id, user\_id, job\_id, score, factors\_json, created\_at)
* **Campaign**(id, recruiter\_id, audience\_query\_json, message\_template, schedule, status, created\_at)
* **Event**(id, kind, actor\_id, entity, entity\_id, payload\_json, pii, created\_at)
* **ModelVersion**(id, name, path, metrics\_json, created\_at)
* **Tenant**(id, name, seats, features\_json, created\_at)

## 4) Key APIs (FastAPI)

**Public**

* `GET /health`, `GET /jobs/search?q=&loc=&skills=&seniority=&page=`
  **Member**
* `POST /profile` (create/update), `POST /resume/upload` (PDF/DOCX), `GET /recommendations`
* `POST /ats/score` (resume\_id, job\_id?) → score + gaps + rewrite suggestions
  **Recruiter/Enterprise**
* `POST /jobs` (create), `POST /outreach/campaigns`, `POST /outreach/send`
* `GET /talent/search?query=...`
  **Admin**
* `GET /analytics/*`, `POST /models/deploy`
  **Realtime**
* `WS /events` (events: match.scored, application.status, campaign.sent)

## 5) Matching & Recommendations (Python-only)

**Feature engineering (examples):**

* TF-IDF / embedding similarity between resume summary & JD.
* Skills overlap (weighted by recency, frequency).
* Seniority alignment; location/time-zone fit; salary band intersection.
* Recency of experience per skill (months).
* Penalty: missing required certs/skills; Bonus: preferred skills.

**Simple blend (rules + embeddings):**

```python
from dataclasses import dataclass

@dataclass
class Factors:
    emb_sim: float
    skills_jaccard: float
    seniority_fit: float
    location_fit: float
    salary_fit: float
    penalties: float

def blended_score(f: Factors) -> float:
    # weights tuned offline; keep sum ~ 1.0 baseline
    return (
        0.45 * f.emb_sim +
        0.25 * f.skills_jaccard +
        0.10 * f.seniority_fit +
        0.08 * f.location_fit +
        0.07 * f.salary_fit -
        0.10 * f.penalties
    )
```

**Embeddings (pure Python)**
Use `sentence-transformers` (Python API) or fallback to `scikit-learn` TF-IDF if GPU not present.

## 6) ATS Checker & Enhancer

* **Parse** resume (pdfminer + python-docx) → sections: summary, experience, education, skills.
* **Score** vs JD: coverage of **required** skills, quantifiable impact verbs, seniority, keywords in top third of doc, file structure sanity.
* **Rewrite** suggestions (Python templates + slot-fill):

  * Insert missing keywords naturally under relevant roles.
  * Convert vague bullets to SAR (Situation-Action-Result) with numbers.
* **Output**: total score (0-100), gaps\[], suggested lines\[], keyword coverage heatmap.

**ATS scoring snippet:**

```python
def ats_score(parsed_resume: dict, jd_text: str, required: set[str], preferred: set[str]) -> dict:
    text = " ".join(parsed_resume.get("sections", {}).values()).lower()
    def cov(keys): 
        hits = {k for k in keys if k.lower() in text}
        return (len(hits)/max(1,len(keys)), list(hits))
    req_cov, req_hits = cov(required)
    pref_cov, pref_hits = cov(preferred)

    # heuristics
    structure_ok = int(all(k in parsed_resume for k in ["summary","experience","education"]))
    keywords_top = int(any(k in (parsed_resume.get("summary","").lower()) for k in required))
    score = round(60*req_cov + 25*pref_cov + 10*structure_ok + 5*keywords_top, 1)

    return {
        "score": score,
        "req_coverage": req_cov, "req_hits": req_hits,
        "pref_coverage": pref_cov, "pref_hits": pref_hits,
        "structure_ok": bool(structure_ok),
        "tips": [
            "Add missing required keywords to summary and most recent role.",
            "Use numbers (%, Δ, revenue, latency) in first 2 bullets of each role."
        ],
    }
```

## 7) Search & Ranking (Jobs)

* **Index**: Postgres full-text or SQLite FTS for dev; optional RedisSearch.
* **Ranking**: text relevance + recency + salary band + company signal + remote option.
* **Filters**: location, skills, seniority, comp type.

## 8) Outreach (Recruiters)

* Audience builder: query by skills, seniority, region, availability.
* Sequencer: throttled sends, opt-out handling, consent stored on User.
* Templates: Python `format` with safe placeholders; logging + audit events.
* Rate limiting via Redis token bucket.

## 9) Realtime & Streaming

* **Redis Streams** default; Kafka optional.
* Producers on: resume upload (kick ATS & match), new JD (re-match), campaign events.
* WebSocket `/events`: push match updates; application status; outreach notifications.

## 10) Security, Privacy & Compliance (Python)

* OIDC login (`authlib`), session cookie (HttpOnly, SameSite=Lax), short-lived JWT for APIs.
* **PII tagging** on Resume/MemberProfile fields; access logged in `Event` with `pii=True`.
* **Consent** fields on User; safeguards in outreach.
* **Data minimization**: store vector embeddings without raw text where possible.
* **RBAC**: roles `member`, `recruiter`, `enterprise_admin`, `platform_admin`.
* **Rate limits** on sensitive endpoints (resume upload, search, outreach send).
* **DSR hooks** (export/delete) in admin APIs.

## 11) Observability & SLOs

* OTEL instrumentation; traces across parse→match→notify.
* Prometheus: request histograms, queue lag, match latency, ATS processing time.
* **SLO targets**:

  * API p95 < 250ms
  * ATS check p95 < 2s (PDF/DOCX parse + score)
  * Match compute p95 < 300ms for top-50 candidates
  * Outreach send correctness 100% with delivery logs

## 12) CI/CD

* GitHub Actions: `ruff` → `mypy` → `pytest` → build image → CycloneDX SBOM.
* Optional deploy to Cloud Run/App Runner; alembic migrate; smoke checks; canary.

---

## 13) Minimal wiring (copy-pasteable)

### `app/main.py`

```python
from fastapi import FastAPI
from app.routers import public, member, recruiter, enterprise, admin, ws
from services.profile.api import router as profile_router
from services.jobs.api import router as jobs_router
from services.match.api import router as match_router
from services.ats.api import router as ats_router
from services.outreach.api import router as out_router
from services.analytics.api import router as analytics_router

app = FastAPI(title="VEZEPyCGrow")

app.include_router(public.router, tags=["public"])
app.include_router(member.router, prefix="/member", tags=["member"])
app.include_router(recruiter.router, prefix="/recruiter", tags=["recruiter"])
app.include_router(enterprise.router, prefix="/enterprise", tags=["enterprise"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(ws.router, tags=["ws"])

app.include_router(profile_router, prefix="/profile", tags=["profile"])
app.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
app.include_router(match_router, prefix="/match", tags=["match"])
app.include_router(ats_router, prefix="/ats", tags=["ats"])
app.include_router(out_router, prefix="/outreach", tags=["outreach"])
app.include_router(analytics_router, prefix="/analytics", tags=["analytics"])

@app.get("/health")
def health(): return {"status": "ok"}
```

### `services/ats/api.py`

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .score import ats_score   # your function above

router = APIRouter()

class ATSReq(BaseModel):
    parsed_resume: dict
    jd_text: str
    required: list[str] = []
    preferred: list[str] = []

@router.post("/score")
def score(req: ATSReq):
    return ats_score(req.parsed_resume, req.jd_text, set(req.required), set(req.preferred))
```

### `services/match/rank.py` (blend + guardrails)

```python
def rank_candidates(candidates_factors: list[dict]) -> list[dict]:
    # each dict has 'user_id' and computed 'Factors'
    scored = []
    for c in candidates_factors:
        s = blended_score(c["factors"])
        scored.append({**c, "score": round(s, 4)})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:100]
```

---

## 14) Runbook (essentials)

* **Dev up**

  ```bash
  pip install -e .[dev]
  uvicorn app.main:app --reload
  ```
* **Start infra (optional)**: `docker compose -f infra/docker-compose.dev.yml up -d`
* **Migrations**: `alembic upgrade head`
* **Resume test**: upload → parse → ATS score → recommendations
* **Job ingest**: POST JD → normalize → embed → searchable
* **Outreach**: create campaign → dry-run audience → send (throttled)
* **Metrics**: open Prometheus/Grafana; inspect request p95 & ATS timings

---
