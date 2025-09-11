import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
clients: set[WebSocket] = set()


@router.websocket("/ws/copilot")
async def ws_copilot(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            msg = await ws.receive_text()
            # simple echo stub with role tagging
            payload = {"role": "assistant", "text": f"echo: {msg}"}
            await ws.send_text(json.dumps(payload))
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(ws)
