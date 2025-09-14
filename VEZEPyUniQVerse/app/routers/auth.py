from __future__ import annotations
import os
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from app.clients.email_client import provision_mailbox

router = APIRouter()


@router.post("/login")
async def login(request: Request):
    """
    Minimal first-login hook.
    Accepts form fields: x_user_id (required). Sets a cookie and provisions mailbox.
    """
    form = await request.form()
    x_user_id = (form.get("x_user_id") or "").strip()
    if not x_user_id:
        raise HTTPException(status_code=400, detail="x_user_id is required")

    email = f"{x_user_id}@vezeuniqverse.com"
    token = "demo" if os.getenv("VEZE_JWT_DEMO") in {"1", "true", "True"} else None
    try:
        await provision_mailbox(email, access_token=token)
    except Exception:
        # Don't block login on provisioning errors; user can retry opening Email UI
        pass

    resp = RedirectResponse(url="/helm", status_code=303)
    # Set a simple cookie marker; not a session/auth token
    resp.set_cookie(key="veze_user", value=x_user_id, httponly=True, samesite="lax")
    return resp
