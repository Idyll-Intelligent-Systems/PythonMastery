from __future__ import annotations

import os
from typing import Iterable

import httpx
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

router = APIRouter()


HOP_HEADERS = {
    "connection",
    "proxy-connection",
    "keep-alive",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def _filter_headers(headers: Iterable[tuple[str, str]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in headers:
        lk = k.lower()
        if lk in HOP_HEADERS or lk == "host":
            continue
        out[k] = v
    return out


async def _proxy(request: Request, subpath: str) -> Response:
    base = os.getenv("XENGINE_INTERNAL_URL", "http://xengine:8006")
    # Build target URL
    qs = str(request.query_params)
    target = f"{base}/{subpath}" if subpath else base
    if qs:
        target = f"{target}?{qs}"

    # Prepare outbound request
    headers = _filter_headers(request.headers.items())
    body = await request.body()

    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        upstream = await client.request(
            request.method,
            target,
            headers=headers,
            content=body if body else None,
        )

    # Map back response
    resp_headers = _filter_headers(upstream.headers.items())
    return Response(content=upstream.content, status_code=upstream.status_code, headers=resp_headers)


@router.api_route("/xengine", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def xengine_root(request: Request):
    return await _proxy(request, "")


@router.api_route("/xengine/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def xengine_path(path: str, request: Request):
    return await _proxy(request, path)


# --- WebSocket proxy (best-effort) ---
@router.websocket("/xengine/ws/{path:path}")
async def ws_proxy(ws: WebSocket, path: str):
    # Note: FastAPI does not natively proxy WS; use httpx isn't viable. For local dev, connect directly.
    # We'll close with a message instructing the client to use absolute ws:// when needed.
    await ws.accept()
    try:
        await ws.send_text("{\"error\":\"WS proxy not supported; connect to ws://localhost:8006/ws/" + path + "\"}")
    except WebSocketDisconnect:
        pass
    finally:
        await ws.close()
