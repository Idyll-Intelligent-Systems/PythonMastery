from fastapi import APIRouter
from pydantic import BaseModel
from dataclasses import dataclass
from time import time
from heapq import heappush, heappop


def elo_update(r_a: float, r_b: float, k: float, a_won: bool) -> tuple[float, float]:
    ea = 1 / (1 + 10 ** ((r_b - r_a) / 400))
    sa = 1.0 if a_won else 0.0
    sb = 1.0 - sa
    r_a2 = r_a + k * (sa - ea)
    r_b2 = r_b + k * (sb - (1 - ea))
    return r_a2, r_b2


@dataclass(order=True)
class Ticket:
    enqueued_at: float
    user_id: str
    mmr: int
    region: str
    mode: str


class MatchQueue:
    def __init__(self):
        self._q: list[Ticket] = []

    def enqueue(self, t: Ticket):
        heappush(self._q, t)

    def dequeue(self, user_id: str):
        for i, t in enumerate(self._q):
            if t.user_id == user_id:
                self._q.pop(i)
                return True
        return False

    def try_match(self, max_delta: int = 50) -> list[Ticket] | None:
        if len(self._q) < 2:
            return None
        a = heappop(self._q)
        window = max_delta + int((time() - a.enqueued_at) / 5) * 25
        idx = next(
            (i for i, t in enumerate(self._q) if abs(t.mmr - a.mmr) <= window and t.mode == a.mode and t.region == a.region),
            -1,
        )
        if idx == -1:
            heappush(self._q, a)
            return None
        b = self._q.pop(idx)
        return [a, b]


router = APIRouter()
QUEUE = MatchQueue()


class EnqueueReq(BaseModel):
    user_id: str
    mmr: int
    mode: str
    region: str


@router.post("/enqueue")
def enqueue(r: EnqueueReq):
    QUEUE.enqueue(Ticket(time(), r.user_id, r.mmr, r.region, r.mode))
    return {"queued": True}


class DequeueReq(BaseModel):
    user_id: str


@router.post("/dequeue")
def dequeue(r: DequeueReq):
    return {"removed": QUEUE.dequeue(r.user_id)}


@router.post("/match")
def make_match():
    pair = QUEUE.try_match()
    if not pair:
        return {"found": False}
    return {
        "found": True,
        "players": [t.user_id for t in pair],
        "teams": {"A": pair[0].user_id, "B": pair[1].user_id},
        "match_id": int(time() * 1000),
    }
