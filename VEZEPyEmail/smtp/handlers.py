from aiosmtpd.handlers import AsyncMessage
from email.message import EmailMessage
from pipeline.accept import accept_inbound, accept_submission


class InboundHandler(AsyncMessage):
    async def handle_message(self, message: EmailMessage) -> None:
        await accept_inbound(message)  # SPF/DMARC, spam, rules, local or relay


class SubmissionHandler(AsyncMessage):
    def __init__(self, tls_context=None, require_auth: bool = False):
        super().__init__()
        self.tls_context = tls_context
        self.require_auth = require_auth

    async def handle_message(self, message: EmailMessage) -> None:
        await accept_submission(message)  # DKIM sign + outbound queue
