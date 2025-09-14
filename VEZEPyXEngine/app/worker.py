from __future__ import annotations

import asyncio
import json
import os
import signal
import sys

import redis.asyncio as redis
from urllib.parse import unquote


STOP = False


def _install_signals():
    def _handler(signum, frame):
        global STOP
        STOP = True
    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(s, _handler)
        except Exception:
            pass


def _bearer() -> str | None:
    tok = os.getenv("X_BEARER_TOKEN") or os.getenv("TWITTER_BEARER_TOKEN")
    if not tok:
        return None
    try:
        return unquote(tok)
    except Exception:
        return tok


async def _record_event(r: redis.Redis, event: dict):
    try:
        seq = await r.incr("xengine:activity:seq")
        event = dict(event)
        event["seq"] = int(seq)
        await r.lpush("xengine:activity", json.dumps(event))
        await r.ltrim("xengine:activity", 0, 199)
    except Exception:
        pass


async def run_once(r: redis.Redis) -> int:
    processed = 0
    for _ in range(100):
        item = await r.brpop("xengine:tasks", timeout=1)
        if not item:
            break
        try:
            (_, payload) = item
            task = json.loads(payload)
            if task.get("type") == "post":
                text = (task.get("text") or "").strip()
                post_now = bool(task.get("post_now"))
                await _record_event(r, {"type": "processing", "task": {"text": text}})
                # Decide whether to attempt real post
                do_post = post_now or (os.getenv("POST_TO_X_ENABLED", "false").lower() == "true")
                if do_post:
                    try:
                        import tweepy  # type: ignore
                        ck = os.getenv("X_CONSUMER_KEY") or os.getenv("TWITTER_CONSUMER_KEY")
                        cs = os.getenv("X_CONSUMER_SECRET") or os.getenv("TWITTER_CONSUMER_SECRET")
                        at = os.getenv("X_ACCESS_TOKEN") or os.getenv("TWITTER_ACCESS_TOKEN")
                        as_ = os.getenv("X_ACCESS_SECRET") or os.getenv("TWITTER_ACCESS_SECRET")
                        if ck and cs and at and as_:
                            client = tweepy.Client(consumer_key=ck, consumer_secret=cs,
                                                   access_token=at, access_token_secret=as_,
                                                   bearer_token=_bearer(), wait_on_rate_limit=True)
                            try:
                                resp = client.create_tweet(text=text)
                                await _record_event(r, {"type": "processed", "task": {"text": text, "posted": True, "id": getattr(resp, 'data', {}).get('id')}})
                            except Exception:
                                await _record_event(r, {"type": "processed", "task": {"text": text, "posted": False}})
                        else:
                            await _record_event(r, {"type": "processed", "task": {"text": text, "posted": False}})
                    except Exception:
                        await _record_event(r, {"type": "processed", "task": {"text": text, "posted": False}})
                else:
                    # No real post; just mark processed for demo
                    await _record_event(r, {"type": "processed", "task": {"text": text, "posted": False}})
            else:
                # Unknown task: small delay
                await asyncio.sleep(0.01)
        except Exception:
            pass
        processed += 1
    return processed


async def main():
    url = os.getenv("REDIS_URL", "redis://localhost:6379/3")
    r = redis.from_url(url, decode_responses=True)
    print("[xengine-worker] starting; redis=", url, flush=True)
    try:
        while not STOP:
            n = await run_once(r)
            if n:
                print(f"[xengine-worker] processed {n} task(s)", flush=True)
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        pass
    finally:
        try:
            await r.aclose()
        except Exception:
            pass
    print("[xengine-worker] stopped", flush=True)


if __name__ == "__main__":
    _install_signals()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
