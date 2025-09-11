from email.message import EmailMessage


async def score_spam(msg: EmailMessage) -> float:
    # Minimal placeholder: real implementation would call ML model
    subject = (msg.get("Subject") or "").lower()
    spammy = any(w in subject for w in ["win", "free", "prize", "lottery"])
    return 0.9 if spammy else 0.05
