from fastapi import APIRouter

router = APIRouter()


@router.get("/{user_id}")
def get_inventory(user_id: str):
    # Dev stub inventory
    return {"user_id": user_id, "items": [
        {"sku": "starter_pack", "qty": 1},
    ]}
