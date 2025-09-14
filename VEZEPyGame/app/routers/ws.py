from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import Any, Dict

router = APIRouter()
clients: set[WebSocket] = set()


@router.websocket("/events")
async def events(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        clients.discard(ws)


async def broadcast(event: dict):
    for c in list(clients):
        try:
            await c.send_json(event)
        except Exception:
            clients.discard(c)


@router.post("/inputs")
async def post_inputs(payload: Dict[str, Any]):
    """Accept external input events and broadcast to all connected game clients.
    Expected shape: {"type":"input", "press":["w","shift"], "release":["q"], "impulse": {"e": true}}
    """
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="invalid payload")
    try:
        await broadcast(payload)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
