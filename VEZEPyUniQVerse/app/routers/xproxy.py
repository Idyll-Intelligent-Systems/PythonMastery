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
    # Candidate upstreams in order of preference
    bases: list[str] = []
    env_base = os.getenv("XENGINE_INTERNAL_URL")
    if env_base:
        bases.append(env_base)
    # Docker service names and common local hosts
    bases.extend([
        "http://xengine:8006",
        "http://veze_xengine:8006",
        "http://host.docker.internal:8006",
        "http://localhost:8006",
    ])

    # Prepare outbound request
    headers = _filter_headers(request.headers.items())
    body = await request.body()
    timeout = httpx.Timeout(10.0)

    last_exc: Exception | None = None
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for base in bases:
            qs = str(request.query_params)
            target = f"{base}/{subpath}" if subpath else base
            if qs:
                target = f"{target}?{qs}"
            try:
                upstream = await client.request(
                    request.method,
                    target,
                    headers=headers,
                    content=body if body else None,
                )
                resp_headers = _filter_headers(upstream.headers.items())
                return Response(content=upstream.content, status_code=upstream.status_code, headers=resp_headers)
            except Exception as ex:  # connect/read errors
                last_exc = ex
                continue

    # If we get here, all attempts failed → return 502 with brief message
    msg = b"upstream unavailable"
    if last_exc:
        try:
            msg = f"upstream unavailable: {last_exc}".encode()
        except Exception:
            pass
    return Response(content=msg, status_code=502)


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
