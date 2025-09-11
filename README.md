# PythonMastery

---

# 📂 Project Tree

```
Idyll-Python-Enterprise-Skeleton/
├── INSTRUCTIONS.md
├── README.md
├── pyproject.toml
├── Dockerfile
├── tox.ini
├── mypy.ini
├── .pre-commit-config.yaml
├── .github/
│   └── workflows/
│       └── ci.yml
├── docs/
│   └── openapi.yaml
├── app/
│   ├── main.py
│   ├── routers/
│   │   ├── api.py
│   │   └── game.py
│   └── schemas/
│       └── items.py
├── ui/
│   └── templates/
│       ├── base.html
│       └── index.html
├── streaming/
│   ├── kafka_consumer.py
│   └── redis_streams_consumer.py
├── ml/
│   ├── train.py
│   ├── infer.py
│   └── eval.py
├── game/  (covered in app/routers/game.py)
├── alembic.ini
├── alembic/
│   ├── README
│   └── env.py
├── tests/
│   └── test_health.py
├── infra/
│   └── terraform/
│       └── README.md
├── ops/
│   ├── sbom.json
│   └── runbook.md
└── scripts/
    └── dev.py
```

---

# 📑 Key Files
---

## **README.md**

````markdown
# Idyll Python Enterprise Skeleton

Python-only, end-to-end skeleton: FastAPI backend, Jinja UI, streaming (Kafka/Redis), ML stubs, game service endpoints, CI/CD, observability, and security.

## Quickstart
```bash
pip install -e .[dev]
uvicorn app.main:app --reload
````

Open: [http://localhost:8000](http://localhost:8000)

````

---

## **pyproject.toml**
Includes FastAPI, SQLAlchemy, Alembic, Redis, Kafka, PyTorch/Lightning, scikit-learn, and dev tools (ruff, mypy, pytest).  

---

## **Dockerfile**
```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOME=/app

WORKDIR $APP_HOME

RUN adduser --disabled-password --gecos "" appuser && chown -R appuser:appuser $APP_HOME
USER appuser

COPY pyproject.toml README.md INSTRUCTIONS.md ./
RUN pip install --upgrade pip && pip install -e .

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
````

---

## **.github/workflows/ci.yml**

Runs lint → typecheck → pytest → SBOM build.

---

## **app/main.py**

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from loguru import logger

from app.routers import api, game
from ml.infer import router as ml_router

app = FastAPI(title="Idyll Python Enterprise API")

app.include_router(api.router, prefix="/api", tags=["api"])
app.include_router(game.router, prefix="/game", tags=["game"])
app.include_router(ml_router, tags=["ml"])

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def index():
    return "<h1>Idyll Python Enterprise</h1><p>See /docs for OpenAPI.</p>"

@app.websocket("/events")
async def events(ws: WebSocket):
    await ws.accept()
    try:
        await ws.send_json({"type": "hello", "msg": "connected"})
        while True:
            data = await ws.receive_text()
            await ws.send_text(f"echo:{data}")
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
```

---

## **app/routers/api.py**

```python
from fastapi import APIRouter
from app.schemas.items import Item

router = APIRouter()
_DB: list[Item] = []

@router.get("/items")
async def list_items() -> list[Item]:
    return _DB

@router.post("/items")
async def create_item(item: Item) -> Item:
    _DB.append(item)
    return item
```

---

## **app/routers/game.py**

```python
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class MatchRequest(BaseModel):
    player_id: str
    mmr: int

class MatchResult(BaseModel):
    match_id: str
    players: list[str]

@router.post("/match", response_model=MatchResult)
async def match(req: MatchRequest) -> MatchResult:
    return MatchResult(match_id="m_123", players=[req.player_id, "bot_1"])
```

---

## **ml/train.py**

```python
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import joblib

def train():
    X, y = load_iris(return_X_y=True, as_frame=True)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(Xtr, ytr)
    preds = clf.predict(Xte)
    acc = accuracy_score(yte, preds)
    joblib.dump(clf, "ml/model.joblib")
    print({"accuracy": acc})

if __name__ == "__main__":
    train()
```

---

## **ml/infer.py**

```python
import joblib
import numpy as np
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class PredictRequest(BaseModel):
    features: list[float]

class PredictResponse(BaseModel):
    prediction: int

_model = None
def _load_model():
    global _model
    if _model is None:
        _model = joblib.load("ml/model.joblib")
    return _model

@router.post("/ml/predict", response_model=PredictResponse)
def predict(req: PredictRequest) -> PredictResponse:
    model = _load_model()
    pred = model.predict(np.array([req.features]))[0]
    return PredictResponse(prediction=int(pred))
```

---

## **streaming/kafka\_consumer.py**

```python
import asyncio
from aiokafka import AIOKafkaConsumer

async def consume(loop, topic: str, bootstrap: str = "localhost:9092"):
    consumer = AIOKafkaConsumer(topic, loop=loop, bootstrap_servers=bootstrap, enable_auto_commit=False)
    await consumer.start()
    try:
        async for msg in consumer:
            print("consumed:", msg.value)
            await consumer.commit()
    finally:
        await consumer.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(consume(loop, "events"))
```

---

## **tests/test\_health.py**

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

# ✅ Next Steps

* Copy this folder structure into your repo.
* Run:

  ```bash
  pip install -e .[dev]
  uvicorn app.main:app --reload
  ```
* Open [http://localhost:8000](http://localhost:8000) → API docs, `/health`, `/events`.

---
