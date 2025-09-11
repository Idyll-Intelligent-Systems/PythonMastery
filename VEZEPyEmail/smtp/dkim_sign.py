def sign_outbound_if_needed(msg):
    # Dev stub: in production, attach a DKIM-Signature header
    if "DKIM-Signature" not in msg:
        msg["DKIM-Signature"] = "dev-stub"
