import os
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .deps import REQ_LAT
from .routers import pages, ws, auth, xproxy
from .clients.email_client import provision_mailbox

app = FastAPI(title="VEZEPyUniQVerse")

app.include_router(pages.router, tags=["pages"])
app.include_router(ws.router, tags=["ws"])
app.include_router(auth.router, tags=["auth"])
app.include_router(xproxy.router, tags=["proxy"])  # /xengine → xengine:8006

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "ui" / "static"
TEMPLATE_DIR = BASE_DIR / "ui" / "templates"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.state.tpl = Jinja2Templates(directory=str(TEMPLATE_DIR))
try:
	app.state.tpl.env.auto_reload = True
except Exception:
	pass
# Prometheus histogram middleware
@app.middleware("http")
async def prometheus_mw(request, call_next):
	start = time.perf_counter()
	response = await call_next(request)
	dur = time.perf_counter() - start
	path = request.url.path
	try:
		REQ_LAT.labels(
			path=path,
			method=request.method,
			status=str(response.status_code),
		).observe(dur)
	except Exception:
		pass
	return response


# Optional OpenTelemetry auto-instrumentation if available and enabled
if os.getenv("OTEL_ENABLED", "0") in {"1", "true", "True"}:
	try:
		from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
		FastAPIInstrumentor.instrument_app(app)
	except Exception:
		# If OTEL packages aren't installed, continue without instrumentation
		pass

# /health is provided by pages router


@app.post("/provision/{x_user_id}")
async def provision_identity(x_user_id: str):
	"""
	Provision a UniQVerse identity backed by an email mailbox.
	Derives <x-user-id>@vezeuniqverse.com and calls Email service to create mailbox lazily.
	"""
	if not x_user_id or any(ch.isspace() for ch in x_user_id):
		raise HTTPException(status_code=400, detail="invalid user id")
	email = f"{x_user_id}@vezeuniqverse.com"
	# Use demo token if enabled for local/dev
	token = "demo" if os.getenv("VEZE_JWT_DEMO") in {"1", "true", "True"} else None
	data = await provision_mailbox(email, access_token=token)
	return {"user": email, "provisioned": True, "messages": data.get("messages", [])}
