from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/routes")
async def routes(origin: str, dest: str):
    # Placeholder: stub for metaverse map routing
    return {"origin": origin, "dest": dest, "path": [origin, "warp-gate", dest]}
