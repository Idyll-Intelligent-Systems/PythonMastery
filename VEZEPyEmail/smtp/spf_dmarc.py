async def check_spf_dmarc(msg):
    # Minimal stub. Real implementation would use smtp session params and pyspf.
    return {"spf": "neutral", "dmarc": "none"}
