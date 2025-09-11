from __future__ import annotations
from typing import List, Dict

# In-memory seed to simulate DB-backed JMAP
_MAILBOXES = {
    # user -> mailbox id
}

_MESSAGES: Dict[int, List[Dict]] = {}


def _seed_user(user: str) -> int:
    if user not in _MAILBOXES:
        mbox_id = len(_MAILBOXES) + 1
        _MAILBOXES[user] = mbox_id
        _MESSAGES[mbox_id] = [
            {
                "id": mbox_id * 1000 + 1,
                "mailbox_id": mbox_id,
                "subject": "Welcome to VEZEPyUniQVerse",
                "from": "noreply@vezeuniqverse.com",
                "date": "2025-09-11T10:05:00Z",
                "flags": [],
                "size": 1234,
                "spam_score": 0.01,
                "snippet": "You're all set. Explore the world and check your quests!",
            },
            {
                "id": mbox_id * 1000 + 2,
                "mailbox_id": mbox_id,
                "subject": "Daily Reward Available",
                "from": "rewards@vezeuniqverse.com",
                "date": "2025-09-11T09:00:00Z",
                "flags": ["Seen"],
                "size": 1111,
                "spam_score": 0.02,
                "snippet": "Claim your shards and XP boost for today.",
            },
        ]
    return _MAILBOXES[user]


async def get_mailbox_id_for_user(user: str) -> int:
    return _seed_user(user)


async def list_messages_for_mailbox(mailbox_id: int, limit: int = 50) -> List[Dict]:
    msgs = _MESSAGES.get(mailbox_id, [])
    msgs = sorted(msgs, key=lambda m: m["id"], reverse=True)[:limit]
    # Derive unread flag
    for m in msgs:
        m["unread"] = "Seen" not in m.get("flags", [])
    return msgs
