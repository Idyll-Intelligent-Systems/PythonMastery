from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/feed")
async def feed(user: str | None = None):
    # Placeholder: a basic feed stub
    return {"user": user, "items": [{"id": 1, "text": "Welcome to the UniQVerse social feed."}]}
