from fastapi import APIRouter

router = APIRouter()


@router.get("/api")
def api_index():
    return {"app": "VEZEPyGame"}
