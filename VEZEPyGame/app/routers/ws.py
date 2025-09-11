from fastapi import APIRouter, WebSocket, WebSocketDisconnect

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
