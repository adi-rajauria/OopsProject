"""Simulated third-party providers.

They deliberately have APIs that do NOT match our NotificationChannel interface
(different method names, argument shapes, error types) - exactly the situation the
Adapter pattern solves. `fail=True` simulates a network outage for tests/demo.
"""

import logging
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger("itsm.providers")


@dataclass
class FakeSmtpProvider:
    host: str = "smtp.simulated.local"
    sender: str = "itsm-noreply@simulated.local"
    fail: bool = False
    outbox: list[dict] = field(default_factory=list)

    def send_mail(self, *, from_addr: str, to_addrs: list[str], subject: str, body_text: str) -> str:
        if self.fail:
            raise ConnectionError(f"SMTP host {self.host} unreachable")
        message_id = f"<{uuid.uuid4().hex}@{self.host}>"
        self.outbox.append({"id": message_id, "from": from_addr, "to": to_addrs, "subject": subject, "body": body_text})
        logger.info("[SIMULATED EMAIL] to=%s subject=%s", ",".join(to_addrs), subject)
        return message_id


@dataclass
class FakeSmsGateway:
    api_url: str = "https://sms.simulated.local/v1/messages"
    fail: bool = False
    sent: list[dict] = field(default_factory=list)

    def dispatch(self, payload: dict) -> dict:
        if self.fail:
            raise TimeoutError(f"SMS gateway {self.api_url} timed out")
        sid = f"SM{uuid.uuid4().hex[:16]}"
        self.sent.append({"sid": sid, **payload})
        logger.info("[SIMULATED SMS] to=%s text=%s", payload.get("msisdn"), payload.get("text"))
        return {"status": "QUEUED", "sid": sid}
