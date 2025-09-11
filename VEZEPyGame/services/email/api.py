from fastapi import APIRouter, HTTPException, Query
from .client import EmailClient

router = APIRouter()
client = EmailClient()


@router.get("/mail")
async def game_mail(user: str = Query(..., description="Game user email (must be @vezeuniqverse.com)")):
    try:
        return await client.get_messages(user=user)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"email service error: {e}")
