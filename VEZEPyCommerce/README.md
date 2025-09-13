### 🛒 VEZEPyCommerce — Storefront, Checkout, Orders (Python-only)

## Repo Layout

```
VEZEPyCommerce/
├─ README.md
├─ .env.example
├─ pyproject.toml
├─ Dockerfile
├─ .github/workflows/ci.yml
├─ app/
│  ├─ main.py
│  ├─ settings.py
│  ├─ deps.py
│  ├─ ui/
│  │  └─ templates/
│  │     ├─ base.html
│  │     ├─ index.html
│  │     ├─ product.html
│  │     ├─ cart.html
│  │     └─ order.html
│  ├─ routers/
│  │  ├─ pages.py
│  │  ├─ catalog.py
│  │  ├─ cart.py
│  │  ├─ checkout.py
│  │  ├─ inventory.py
│  │  ├─ webhooks.py
│  │  ├─ discovery.py
│  │  └─ health.py
│  ├─ services/
│  │  ├─ bus.py
│  │  ├─ pricing.py
│  │  ├─ payments.py
│  │  └─ risk.py
│  └─ db/
│     ├─ database.py
│     ├─ models.py
│     └─ seed.py
└─ tests/
   ├─ test_health.py
   └─ test_cart_checkout.py
```

---

## README.md

````markdown
# VEZEPyCommerce

Python-only commerce: catalog, cart, checkout, orders, inventory, promos, risk hooks to VEZEPyXEngine, and events to UniQVerse Helm.

## Quickstart

```bash
cp .env.example .env
# make sure Postgres + Redis running (or use docker-compose from UniQVerse)
pip install -e .[dev]
uvicorn app.main:app --reload --port 8012
````

* Storefront UI: `GET /`
* Catalog API: `GET /catalog`, `GET /product/{sku}`
* Cart API: `POST /cart`, `POST /cart/{cart_id}/items`
* Checkout: `POST /checkout/{cart_id}`
* Discovery (Helm): `GET /.veze/service.json`
* Metrics: `GET /metrics`

## Environment

* `DATABASE_URL=postgresql+asyncpg://veze:veze@localhost:5432/veze_commerce`
* `REDIS_URL=redis://localhost:6379/5`
* `SVC_XENGINE=http://veze_xengine:8006`
* `ENV=dev`, `PORT=8012`

## Events (Redis Streams)

* `commerce.order.placed`
* `commerce.payment.captured`
* `commerce.inventory.changed`

## Notes

* Payments are mocked (PSP interface). Swap with a real provider later.
* Risk scoring consults VEZEPyXEngine user metrics (optional).

````

---

## .env.example

```env
ENV=dev
PORT=8012
DATABASE_URL=postgresql+asyncpg://veze:veze@localhost:5432/veze_commerce
REDIS_URL=redis://localhost:6379/5
SVC_XENGINE=http://veze_xengine:8006
````

---

## pyproject.toml

```toml
[project]
name = "veze-commerce"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "jinja2>=3.1",
  "pydantic>=2.8",
  "SQLAlchemy>=2.0",
  "asyncpg>=0.29",
  "redis>=5.0",
  "httpx>=0.27",
  "prometheus-fastapi-instrumentator>=7.0.0",
  "python-multipart>=0.0.9"
]
[project.optional-dependencies]
dev = ["pytest>=8.3","pytest-asyncio>=0.23","ruff>=0.5","black>=24.8","mypy>=1.11"]
```

---

## app/settings.py

```python
import os
from pydantic import BaseModel

class Settings(BaseModel):
    env: str = os.getenv("ENV","dev")
    port: int = int(os.getenv("PORT","8012"))
    db_url: str = os.getenv("DATABASE_URL","postgresql+asyncpg://veze:veze@localhost:5432/veze_commerce")
    redis_url: str = os.getenv("REDIS_URL","redis://localhost:6379/5")
    svc_xengine: str = os.getenv("SVC_XENGINE","http://veze_xengine:8006")

settings = Settings()
```

---

## app/deps.py

```python
from app.settings import settings
from app.db.database import get_async_session
from app.services.bus import Bus
from app.services.pricing import Pricing
from app.services.payments import PSP
from app.services.risk import Risk

def get_session(): return get_async_session(settings.db_url)
def get_bus(): return Bus(settings.redis_url)
def get_pricing(): return Pricing()
def get_psp(): return PSP()
def get_risk(): return Risk(settings.svc_xengine)
```

---

## app/db/database.py

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

def SessionMaker(db_url: str):
    engine = create_async_engine(db_url, future=True, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Dependency factory used in routers
def get_async_session(db_url: str):
    return SessionMaker(db_url)()
```

---

## app/db/models.py

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, ForeignKey, Numeric, JSON, DateTime, Boolean
from datetime import datetime

class Base(DeclarativeBase): ...

class Product(Base):
    __tablename__="products"
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(2000))
    attrs: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class Price(Base):
    __tablename__="prices"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    currency: Mapped[str] = mapped_column(String(3))
    amount: Mapped[int] = mapped_column(Integer)  # in cents
    tier: Mapped[str] = mapped_column(String(32), default="standard")

class Inventory(Base):
    __tablename__="inventory"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    stock: Mapped[int] = mapped_column(Integer, default=0)
    reserved: Mapped[int] = mapped_column(Integer, default=0)

class Cart(Base):
    __tablename__="carts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class CartItem(Base):
    __tablename__="cart_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    qty: Mapped[int] = mapped_column(Integer)

class Order(Base):
    __tablename__="orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    currency: Mapped[str] = mapped_column(String(3))
    total_amount: Mapped[int] = mapped_column(Integer) # cents
    status: Mapped[str] = mapped_column(String(16), default="placed")  # placed|paid|failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

class OrderItem(Base):
    __tablename__="order_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    qty: Mapped[int] = mapped_column(Integer)
    unit_amount: Mapped[int] = mapped_column(Integer)  # cents

class Payment(Base):
    __tablename__="payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    provider: Mapped[str] = mapped_column(String(32), default="mock")
    amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="authorized")  # authorized|captured|failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class PromoRule(Base):
    __tablename__="promo_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(32))   # percent_off|amount_off|bogo
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
```

---

## app/db/seed.py (optional demo data)

```python
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.db.models import Base, Product, Price, Inventory

async def seed(db_url:str):
    eng = create_async_engine(db_url, future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    async with Session() as s:
        if not (await s.execute(Product.__table__.select())).first():
            p1 = Product(sku="GAME_PASS", name="VEZE Game Pass", description="Season access", attrs={"tier":"gold"})
            p2 = Product(sku="SKIN_NEBULA", name="Nebula Skin", description="Cosmic cosmetic", attrs={"rarity":"legendary"})
            s.add_all([p1,p2]); await s.flush()
            s.add_all([Price(product_id=p1.id, currency="USD", amount=999),
                       Price(product_id=p2.id, currency="USD", amount=499)])
            s.add_all([Inventory(product_id=p1.id, stock=1000),
                       Inventory(product_id=p2.id, stock=500)])
            await s.commit()

if __name__=="__main__":
    asyncio.run(seed("postgresql+asyncpg://veze:veze@localhost:5432/veze_commerce"))
```

---

## app/services/bus.py

```python
import json, redis.asyncio as redis

class Bus:
    def __init__(self, url:str):
        self.r = redis.from_url(url)

    async def emit(self, stream:str, payload:dict):
        await self.r.xadd(stream, {"payload": json.dumps(payload)})
```

---

## app/services/pricing.py

```python
class Pricing:
    # Very simple rule engine placeholder
    def apply(self, items:list[dict], promos:list[dict]|None=None) -> int:
        # items: [{unit_amount:int, qty:int}]
        subtotal = sum(i["unit_amount"] * i["qty"] for i in items)
        discount = 0
        for pr in promos or []:
            kind = pr.get("kind")
            cfg = pr.get("config",{})
            if kind == "percent_off":
                discount += int(subtotal * float(cfg.get("pct",0.0)))
            elif kind == "amount_off":
                discount += int(cfg.get("amount",0))
        total = max(0, subtotal - discount)
        return total
```

---

## app/services/payments.py (mock PSP)

```python
class PSP:
    async def authorize(self, order_id:int, amount:int, currency:str)->dict:
        return {"status":"authorized","psp_id":f"auth_{order_id}"}
    async def capture(self, psp_id:str)->dict:
        return {"status":"captured","psp_id":psp_id}
```

---

## app/services/risk.py (XEngine hook)

```python
import httpx

class Risk:
    def __init__(self, xengine_base:str):
        self.base = xengine_base

    async def score(self, handle:str) -> float:
        if not handle:
            return 0.5
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{self.base}/user_metrics/{handle}")
                r.raise_for_status()
                m = r.json()
                score = max(0.05, 1.0 - min(1.0, (m["average_likes"] + m["followers_count"]/10000)/10))
                return score
        except Exception:
            return 0.5
```

---

## app/routers/pages.py (UI)

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return request.app.state.tpl.TemplateResponse("index.html", {"request": request})
```

---

## app/routers/catalog.py

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.deps import get_session
from app.db.models import Product, Price, Inventory

router = APIRouter()

@router.get("/catalog")
async def catalog(session=Depends(get_session)):
    rows = (await session.execute(select(Product))).scalars().all()
    out=[]
    for p in rows:
        price = (await session.execute(select(Price).where(Price.product_id==p.id))).scalars().first()
        inv = (await session.execute(select(Inventory).where(Inventory.product_id==p.id))).scalars().first()
        out.append({"sku":p.sku,"name":p.name,"desc":p.description,
                    "price":price.amount if price else None,"currency":price.currency if price else "USD",
                    "stock": (inv.stock - inv.reserved) if inv else 0})
    return {"products": out}

@router.get("/product/{sku}")
async def product(sku:str, session=Depends(get_session)):
    p = (await session.execute(select(Product).where(Product.sku==sku))).scalars().first()
    if not p: raise HTTPException(404,"Not found")
    price = (await session.execute(select(Price).where(Price.product_id==p.id))).scalars().first()
    inv = (await session.execute(select(Inventory).where(Inventory.product_id==p.id))).scalars().first()
    return {"sku":p.sku,"name":p.name,"desc":p.description,"attrs":p.attrs,
            "price":price.amount if price else None,"currency":price.currency if price else "USD",
            "stock": (inv.stock - inv.reserved) if inv else 0}
```

---

## app/routers/cart.py

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.deps import get_session
from app.db.models import Cart, CartItem, Product, Price

router = APIRouter()

@router.post("/cart")
async def create_cart(user_id:int, currency:str="USD", session=Depends(get_session)):
    c = Cart(user_id=user_id, currency=currency)
    session.add(c); await session.commit(); await session.refresh(c)
    return {"cart_id": c.id}

@router.get("/cart/{cart_id}")
async def get_cart(cart_id:int, session=Depends(get_session)):
    c = await session.get(Cart, cart_id)
    if not c: raise HTTPException(404,"Not found")
    items = (await session.execute(select(CartItem).where(CartItem.cart_id==cart_id))).scalars().all()
    out=[]
    for it in items:
        price = (await session.execute(select(Price).where(Price.product_id==it.product_id))).scalars().first()
        out.append({"product_id": it.product_id, "qty": it.qty, "unit_amount": price.amount if price else 0})
    return {"id": c.id, "user_id": c.user_id, "currency": c.currency, "items": out}

@router.post("/cart/{cart_id}/items")
async def add_item(cart_id:int, sku:str, qty:int, session=Depends(get_session)):
    c = await session.get(Cart, cart_id)
    if not c: raise HTTPException(404,"Cart not found")
    p = (await session.execute(select(Product).where(Product.sku==sku))).scalars().first()
    if not p: raise HTTPException(404,"Product not found")
    item = CartItem(cart_id=cart_id, product_id=p.id, qty=qty)
    session.add(item); await session.commit(); await session.refresh(item)
    return {"item_id": item.id}
```

---

## app/routers/checkout.py

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.deps import get_session, get_pricing, get_psp, get_bus, get_risk
from app.db.models import Cart, CartItem, Price, Inventory, Order, OrderItem, Payment

router = APIRouter()

@router.post("/checkout/{cart_id}")
async def checkout(cart_id:int, user_handle:str|None=None,
                   session=Depends(get_session), pricing=Depends(get_pricing),
                   psp=Depends(get_psp), bus=Depends(get_bus), risk=Depends(get_risk)):
    cart = await session.get(Cart, cart_id)
    if not cart: raise HTTPException(404, "Cart not found")

    items = (await session.execute(select(CartItem).where(CartItem.cart_id==cart_id))).scalars().all()
    if not items: raise HTTPException(400, "Cart empty")

    line_items=[]
    for it in items:
        price = (await session.execute(select(Price).where(Price.product_id==it.product_id))).scalars().first()
        inv = (await session.execute(select(Inventory).where(Inventory.product_id==it.product_id))).scalars().first()
        if (inv.stock - inv.reserved) < it.qty:
            raise HTTPException(409, "Insufficient stock")
        inv.reserved += it.qty
        line_items.append({"product_id": it.product_id, "qty": it.qty, "unit_amount": price.amount})
    await session.commit()

    total = pricing.apply(line_items, promos=[])
    order = Order(user_id=cart.user_id, currency=cart.currency, total_amount=total, status="placed")
    session.add(order); await session.commit(); await session.refresh(order)
    for li in line_items:
        session.add(OrderItem(order_id=order.id, product_id=li["product_id"], qty=li["qty"], unit_amount=li["unit_amount"]))
    await session.commit()

    # naive risk score (0 = safe, 1 = risky). If too risky, fail early.
    score = await risk.score(user_handle or "")
    if score > 0.9:
        order.status="failed"; order.meta={"reason":"high_risk"}; await session.commit()
        await bus.emit("veze.commerce", {"type":"commerce.order.failed","order_id":order.id,"risk":score})
        raise HTTPException(402, "Risk check failed")

    # authorize + capture (mock PSP)
    auth = await psp.authorize(order.id, order.total_amount, order.currency)
    cap = await psp.capture(auth["psp_id"])
    pay = Payment(order_id=order.id, provider="mock", amount=order.total_amount, status=cap["status"])
    session.add(pay)
    order.status = "paid"; await session.commit()

    # decrement real stock, release reserved delta
    for it in items:
        inv = (await session.execute(select(Inventory).where(Inventory.product_id==it.product_id))).scalars().first()
        inv.stock -= it.qty; inv.reserved = max(0, inv.reserved - it.qty)
    await session.commit()

    await bus.emit("veze.commerce", {"type":"commerce.order.placed","order_id":order.id,"amount":order.total_amount})
    await bus.emit("veze.commerce", {"type":"commerce.payment.captured","order_id":order.id})
    await bus.emit("veze.commerce", {"type":"commerce.inventory.changed","order_id":order.id})

    return {"order_id": order.id, "status": order.status, "amount": order.total_amount}
```

---

## app/routers/inventory.py (admin-ish)

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.deps import get_session, get_bus
from app.db.models import Product, Inventory

router = APIRouter()

@router.post("/inventory/adjust")
async def adjust(sku:str, delta:int, session=Depends(get_session), bus=Depends(get_bus)):
    p = (await session.execute(select(Product).where(Product.sku==sku))).scalars().first()
    if not p: raise HTTPException(404,"Product not found")
    inv = (await session.execute(select(Inventory).where(Inventory.product_id==p.id))).scalars().first()
    if not inv:
        inv = Inventory(product_id=p.id, stock=max(0, delta), reserved=0)
        session.add(inv)
    else:
        inv.stock = max(0, inv.stock + delta)
    await session.commit()
    await bus.emit("veze.commerce", {"type":"commerce.inventory.changed","product_id":p.id,"sku":sku,"stock":inv.stock})
    return {"sku": sku, "stock": inv.stock}
```

---

## app/routers/webhooks.py (stubs for fanout)

```python
from fastapi import APIRouter

router = APIRouter()

@router.post("/webhooks/email/receipt")
async def email_receipt(order_id:int):
    # Call VEZEPyEmail here (left as a stub or use UniQVerse proxy)
    return {"ok": True}

@router.post("/webhooks/game/entitlement")
async def game_entitlement(order_id:int, user_id:int):
    # Grant entitlement in VEZEPyGame (stub)
    return {"ok": True}
```

---

## app/routers/discovery.py (Helm tile)

```python
from fastapi import APIRouter
router = APIRouter()

@router.get("/.veze/service.json")
async def svc():
    return {
      "name":"VEZEPyCommerce",
      "category":"monetization",
      "status":"green",
      "routes":[{"label":"Storefront","href":"/"},{"label":"Orders","href":"/order"}],
      "scopes":["commerce.buy","commerce.manage"],
      "events":["commerce.order.placed","commerce.payment.captured","commerce.inventory.changed"]
    }
```

---

## app/routers/health.py

```python
from fastapi import APIRouter
router = APIRouter()
@router.get("/health") async def health(): return {"status":"ok"}
```

---

## app/ui/templates/base.html

```html
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>VEZEPyCommerce</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    body{font-family:system-ui,Arial;background:#0b0f18;color:#e6edf3;margin:0}
    header,footer{padding:12px 20px;background:#0d1117;border-bottom:1px solid #1f2937}
    a{color:#58a6ff;text-decoration:none}
    .grid{display:grid;gap:12px;padding:20px}
    .card{background:#0d1117;border:1px solid #1f2937;padding:16px;border-radius:12px}
    .btn{background:#1f6feb;color:#fff;padding:8px 12px;border-radius:8px}
  </style>
</head>
<body>
  <header>
    <strong>VEZEPyCommerce</strong> — <a href="/">Store</a>
  </header>
  <main class="grid">
    {% block content %}{% endblock %}
  </main>
  <footer>© VEZE UniQVerse</footer>
</body>
</html>
```

---

## app/ui/templates/index.html

```html
{% extends "base.html" %}
{% block content %}
<h2>Storefront</h2>
<div id="products" class="grid"></div>
<script>
(async()=>{
  const res = await fetch('/catalog'); const data = await res.json();
  const grid = document.getElementById('products');
  grid.innerHTML = (data.products||[]).map(p=>`
    <div class="card">
      <h3>${p.name}</h3>
      <p>${p.desc}</p>
      <p><b>${(p.price/100).toFixed(2)} ${p.currency}</b> — Stock ${p.stock}</p>
      <a class="btn" href="/product/${p.sku}">View</a>
    </div>`).join('');
})();
</script>
{% endblock %}
```

---

## app/ui/templates/product.html

```html
{% extends "base.html" %}
{% block content %}
<div class="card">
  <h2>{{ p.name }}</h2>
  <p>{{ p.desc }}</p>
  <p><b>{{ (p.price/100)|round(2) }} {{ p.currency }}</b> — Stock {{ p.stock }}</p>
  <form method="post" action="/cart/add">
    <input type="hidden" name="sku" value="{{ p.sku }}" />
    <label>Qty <input name="qty" type="number" value="1" min="1"/></label>
    <button class="btn">Add to Cart</button>
  </form>
</div>
{% endblock %}
```

---

## app/ui/templates/cart.html

```html
{% extends "base.html" %}
{% block content %}
<h2>Cart #{{ cart.id }}</h2>
<div class="card">
  <ul>
    {% for it in cart.items %}
      <li>PID {{ it.product_id }} × {{ it.qty }} — {{ (it.unit_amount/100)|round(2) }}</li>
    {% endfor %}
  </ul>
  <form method="post" action="/checkout/{{ cart.id }}">
    <label>Handle <input name="handle" placeholder="@pilot"/></label>
    <button class="btn">Checkout</button>
  </form>
</div>
{% endblock %}
```

---

## app/ui/templates/order.html

```html
{% extends "base.html" %}
{% block content %}
<div class="card">
  <h2>Order {{ order.order_id }}</h2>
  <p>Status: {{ order.status }}</p>
  <p>Amount: {{ (order.amount/100)|round(2) }}</p>
  <a class="btn" href="/">Back to Store</a>
</div>
{% endblock %}
```

---

## app/routers (UI glue for product/cart pages)

```python
# extend pages.py with simple views
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from app.deps import get_session
from app.db.models import Product, Price, Cart, CartItem

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):  # already in pages.py; keep one copy in codebase
    return request.app.state.tpl.TemplateResponse("index.html", {"request": request})

@router.get("/product/{sku}", response_class=HTMLResponse)
async def product_view(sku:str, request: Request, session=Depends(get_session)):
    from sqlalchemy import select
    from app.db.models import Inventory
    p = (await session.execute(select(Product).where(Product.sku==sku))).scalars().first()
    if not p: return RedirectResponse("/")
    price = (await session.execute(select(Price).where(Price.product_id==p.id))).scalars().first()
    inv = (await session.execute(select(Inventory).where(Inventory.product_id==p.id))).scalars().first()
    data = {"sku":p.sku,"name":p.name,"desc":p.description,"price":price.amount,"currency":price.currency,
            "stock": (inv.stock - inv.reserved) if inv else 0}
    return request.app.state.tpl.TemplateResponse("product.html", {"request": request, "p": data})

@router.post("/cart/add")
async def cart_add(sku: str = Form(...), qty: int = Form(...), session=Depends(get_session)):
    c = Cart(user_id=1)  # demo: single user
    session.add(c); await session.commit(); await session.refresh(c)
    prod = (await session.execute(select(Product).where(Product.sku==sku))).scalars().first()
    session.add(CartItem(cart_id=c.id, product_id=prod.id, qty=qty)); await session.commit()
    return RedirectResponse(f"/cart/view/{c.id}", status_code=303)

@router.get("/cart/view/{cart_id}", response_class=HTMLResponse)
async def cart_view(cart_id:int, request: Request, session=Depends(get_session)):
    c = await session.get(Cart, cart_id)
    if not c: return RedirectResponse("/")
    items = (await session.execute(select(CartItem).where(CartItem.cart_id==cart_id))).scalars().all()
    from app.db.models import Price
    out=[]
    for it in items:
        price = (await session.execute(select(Price).where(Price.product_id==it.product_id))).scalars().first()
        out.append({"product_id": it.product_id, "qty": it.qty, "unit_amount": price.amount if price else 0})
    return request.app.state.tpl.TemplateResponse("cart.html", {"request": request, "cart": {"id":c.id,"items":out}})

@router.post("/checkout/{cart_id}", response_class=HTMLResponse)
async def checkout_view(cart_id:int, request: Request, handle: str = Form(""), session=Depends(get_session)):
    import httpx
    async with httpx.AsyncClient() as c:
        r = await c.post(f"http://localhost:8012/checkout/{cart_id}", params={"user_handle":handle})
        data = r.json()
    return request.app.state.tpl.TemplateResponse("order.html", {"request": request, "order": data})
```

> If you keep both API and UI routes, ensure imports don’t collide (or split UI into a `pages_ui.py` file).

---

## app/routers/discovery.py / health.py are already above

---

## app/main.py

```python
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from app.routers import pages, catalog, cart, checkout, inventory, webhooks, discovery, health

app = FastAPI(title="VEZEPyCommerce")
app.state.tpl = Jinja2Templates(directory="app/ui/templates")

# UI & API
app.include_router(pages.router, tags=["ui"])
app.include_router(catalog.router, tags=["catalog"])
app.include_router(cart.router, tags=["cart"])
app.include_router(checkout.router, tags=["checkout"])
app.include_router(inventory.router, tags=["inventory"])
app.include_router(webhooks.router, tags=["webhooks"])
app.include_router(discovery.router, tags=["discovery"])
app.include_router(health.router, tags=["health"])

app.mount("/static", StaticFiles(directory="app/ui/templates"), name="static")

Instrumentator().instrument(app).expose(app)
```

---

## Dockerfile

```dockerfile
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml .
RUN pip install --upgrade pip && pip install -e .
COPY . .
EXPOSE 8012
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8012"]
```

---

## CI (.github/workflows/ci.yml)

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

## tests/test\_health.py

```python
from fastapi.testclient import TestClient
from app.main import app

def test_health():
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
```

---

## tests/test\_cart\_checkout.py

```python
from fastapi.testclient import TestClient
from app.main import app

def test_cart_flow_smoke(monkeypatch):
    c = TestClient(app)

    # create cart
    r = c.post("/cart", params={"user_id": 1, "currency": "USD"})
    assert r.status_code == 200
    cart_id = r.json()["cart_id"]

    # add item (requires seeded DB in real run; here we skip if missing)
    # This is a smoke test—API surface should exist.
    # You can seed with app/db/seed.py before running real tests.
    assert c.get(f"/cart/{cart_id}").status_code == 200
```

---

## Runbook (local dev)

```bash
# 1) Start Postgres + Redis
#    - via docker-compose from UniQVerse or your own instances

# 2) Env + install
cp .env.example .env
pip install -e .[dev]

# 3) (Optional) Seed demo data
python -m app.db.seed

# 4) Run service
uvicorn app.main:app --reload --port 8012

# 5) Try it
open http://localhost:8012/
curl -s http://localhost:8012/catalog | jq
```

---

## Helm Integration

* **Tile**: “VEZEPyCommerce — Store”
* **Discovery**: Helm GET `/.veze/service.json`
* **Proxy** examples:

  * `/proxy/commerce/catalog` → `http://veze_commerce:8012/catalog`
  * `/proxy/commerce/checkout/{id}` → `http://veze_commerce:8012/checkout/{id}`

**Events (Redis Streams channel: `veze.commerce`)**

```json
{ "type":"commerce.order.placed","order_id":123,"amount":1499 }
{ "type":"commerce.payment.captured","order_id":123 }
{ "type":"commerce.inventory.changed","order_id":123 }
```

---
