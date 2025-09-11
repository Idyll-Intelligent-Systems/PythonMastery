from email.message import EmailMessage
from pathlib import Path
import os
import time

try:
    import aiofiles  # type: ignore
except Exception:
    aiofiles = None  # type: ignore


BASE = Path(os.getenv("MAILSTORE", "/data/mail"))
BASE.mkdir(parents=True, exist_ok=True)


async def save_blob(msg: EmailMessage) -> str:
    ts = int(time.time() * 1000)
    path = BASE / f"{ts}.eml"
    raw = msg.as_bytes()
    if aiofiles is None:
        with open(path, "wb") as f:
            f.write(raw)
    else:
        async with aiofiles.open(path, "wb") as f:  # type: ignore
            await f.write(raw)
    return str(path)


async def load_blob(path: str) -> bytes:
    if aiofiles is None:
        with open(path, "rb") as f:
            return f.read()
    async with aiofiles.open(path, "rb") as f:  # type: ignore
        return await f.read()
