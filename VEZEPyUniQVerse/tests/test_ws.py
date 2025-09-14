import asyncio
import contextlib
import socket

import pytest
from websockets.client import connect
from uvicorn import Config, Server

from app.main import app


@contextlib.asynccontextmanager
async def run_server(host: str = "127.0.0.1", port: int = 8765):
    config = Config(app, host=host, port=port, log_level="warning", ws="wsproto")
    server = Server(config=config)
    task = asyncio.create_task(server.serve())
    # wait until server started
    for _ in range(40):
        await asyncio.sleep(0.05)
        with socket.socket() as s:
            try:
                s.connect((host, port))
                break
            except OSError:
                continue
    try:
        yield
    finally:
        server.should_exit = True
        await task


@pytest.mark.asyncio
async def test_ws_echo():
    async with run_server():
        async with connect("ws://127.0.0.1:8765/ws/copilot") as ws:
            await ws.send("ping")
            msg = await asyncio.wait_for(ws.recv(), timeout=2)
            assert "echo: ping" in msg
