from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/catalog")
async def catalog():
    return {"items": []}
