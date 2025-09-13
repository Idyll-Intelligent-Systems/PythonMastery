from fastapi import APIRouter, HTTPException, Query, Request
from .client import EmailClient
from app.security import _parse_bearer, _verify_jwt, _has_scopes, _fail

router = APIRouter()
client = EmailClient()

@router.get("/mail")
async def game_mail(
    request: Request,
    user: str = Query(..., description="Game user email (must be @vezeuniqverse.com)"),
    access_token: str | None = Query(None),
):
    # Perform auth only after parameter validation, so missing params yield 422 as expected by tests
    try:
        token = _parse_bearer(request.headers.get("authorization"), access_token)
        claims = _verify_jwt(token)
        if not _has_scopes(claims, ["game.read_mail"]):
            _fail("Insufficient scope", 403)
    except HTTPException:
        # Propagate HTTP exceptions intact
        raise
    except Exception as e:
        _fail(f"Invalid token: {e}")
    try:
        return await client.get_messages(user=user, access_token=access_token)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"email service error: {e}")


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}
