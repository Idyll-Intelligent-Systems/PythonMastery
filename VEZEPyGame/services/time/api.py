from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/now")
async def now():
    import datetime as dt
    return {"now": dt.datetime.utcnow().isoformat() + "Z"}
