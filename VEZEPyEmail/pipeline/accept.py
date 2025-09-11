from email.message import EmailMessage
from email.utils import parseaddr, getaddresses
from pipeline.spam import score_spam
from pipeline.sieve import apply_rules  # noqa: F401 (placeholder)
from smtp.spf_dmarc import check_spf_dmarc
from smtp.dkim_sign import sign_outbound_if_needed
from streaming.queues import enqueue_inbound, enqueue_outbound
from storage.blobs import save_blob

LOCAL_DOMAIN = "vezeuniqverse.com"


async def accept_inbound(msg: EmailMessage):
    verdict = await check_spf_dmarc(msg)
    spam = await score_spam(msg)
    blob_path = await save_blob(msg)
    # route recipients
    to_list = [addr for _, addr in getaddresses([msg.get("To", "")])]
    for rcpt in to_list:
        local = rcpt.lower().split("@", 1)
        if len(local) == 2 and local[1] == LOCAL_DOMAIN:
            # In this minimal scaffold, just enqueue an event (no DB yet)
            await enqueue_inbound({
                "event": "local.accepted",
                "rcpt": rcpt,
                "blob": blob_path,
                "spam": spam,
                "spf_dmarc": verdict,
            })
        else:
            # relay to remote
            await enqueue_outbound({"raw_blob": blob_path, "rcpt": rcpt})


async def accept_submission(msg: EmailMessage):
    await sign_outbound_if_needed(msg)  # DKIM
    blob_path = await save_blob(msg)
    await enqueue_outbound({"raw_blob": blob_path, "rcpt": msg.get("To")})
