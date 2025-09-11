import asyncio
import ssl
from aiosmtpd.controller import Controller
from smtp.handlers import InboundHandler, SubmissionHandler


def start_smtp():
    # Inbound MX (25)
    inbound = Controller(InboundHandler(), hostname="0.0.0.0", port=25)
    inbound.start()

    # Submission (587 STARTTLS) and SMTPS (465)
    try:
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain("/certs/fullchain.pem", "/certs/privkey.pem")
    except Exception:
        context = None  # allow running without certs in dev

    if context is not None:
        submission = Controller(
            SubmissionHandler(tls_context=context, require_auth=True),
            hostname="0.0.0.0",
            port=587,
            starttls=True,
            tls_context=context,
        )
        submission.start()

        smtps = Controller(
            SubmissionHandler(tls_context=context, require_auth=True),
            hostname="0.0.0.0",
            port=465,
            ssl_context=context,
        )
        smtps.start()
    else:
        submission = None
        smtps = None

    return inbound, submission, smtps


if __name__ == "__main__":
    start_smtp()
    asyncio.get_event_loop().run_forever()
