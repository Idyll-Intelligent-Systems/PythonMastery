from fastapi import APIRouter, HTTPException, Query
from .client import EmailClient

router = APIRouter()
client = EmailClient()


@router.get("/mail")
async def game_mail(
    user: str = Query(..., description="Game user email (must be @vezeuniqverse.com)"),
    access_token: str | None = Query(None),
):
    try:
        return await client.get_messages(user=user, access_token=access_token)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"email service error: {e}")


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}
