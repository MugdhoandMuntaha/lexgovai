"""Email Channel Adapter for LexGOV AI.

Compatible with SMTP, Amazon SES SMTP, Brevo, and Resend.
Features full UTF-8 / Bangla character encoding, multipart text/html bodies,
and configurable mock mode for offline testing.
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any
import uuid

logger = logging.getLogger("complianceos.alerts.email")


class EmailChannelAdapter:
    def __init__(
        self,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_user: str | None = None,
        smtp_pass: str | None = None,
        from_email: str | None = None,
        use_mock: bool = False,
    ):
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = smtp_user or os.getenv("SMTP_USER")
        self.smtp_pass = smtp_pass or os.getenv("SMTP_PASSWORD")
        self.from_email = from_email or os.getenv("FROM_EMAIL", "alerts@complianceos.com.bd")
        self.use_mock = use_mock or (not self.smtp_host)
        self.sent_messages: list[dict[str, Any]] = []

    def send(
        self,
        alert_id: str,
        recipient_address: str,
        subject: str,
        body: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        meta = metadata or {}
        html_body = meta.get("html_body") or f"<p>{body}</p>"
        msg_id = f"email_{uuid.uuid4().hex}"

        if self.use_mock:
            logger.info(f"[MOCK EMAIL] To: {recipient_address} | Subject: {subject}")
            record = {
                "id": msg_id,
                "to": recipient_address,
                "subject": subject,
                "body": body,
                "html_body": html_body,
            }
            self.sent_messages.append(record)
            return {
                "status": "sent",
                "provider": "smtp_mock",
                "provider_message_id": msg_id,
                "cost_estimate": 0.0,
                "segments": 1,
                "error": None,
            }

        # Real SMTP Delivery
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_email
        msg["To"] = recipient_address

        part1 = MIMEText(body, "plain", "utf-8")
        part2 = MIMEText(html_body, "html", "utf-8")
        msg.attach(part1)
        msg.attach(part2)

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                server.starttls()
                if self.smtp_user and self.smtp_pass:
                    server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.from_email, [recipient_address], msg.as_string())

            return {
                "status": "sent",
                "provider": "smtp",
                "provider_message_id": msg_id,
                "cost_estimate": 0.0,
                "segments": 1,
                "error": None,
            }
        except Exception as e:
            logger.error(f"Failed to send email to {recipient_address}: {e}")
            return {
                "status": "failed",
                "provider": "smtp",
                "provider_message_id": None,
                "cost_estimate": 0.0,
                "segments": 1,
                "error": str(e),
            }

    def parse_delivery_webhook(self, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        # Handle generic bounce/delivery event formats (e.g. SES/SendGrid/Brevo)
        event_type = payload.get("event") or payload.get("eventType") or "delivered"
        if event_type in ("bounce", "PermanentFailure", "blocked"):
            return {
                "status": "failed",
                "provider_message_id": payload.get("message_id") or payload.get("mail", {}).get("messageId"),
                "error": payload.get("reason") or "Delivery bounced",
            }
        return {
            "status": "delivered",
            "provider_message_id": payload.get("message_id") or payload.get("mail", {}).get("messageId"),
            "error": None,
        }

    def health_check(self) -> dict[str, Any]:
        if self.use_mock:
            return {"status": "healthy", "channel": "email", "mode": "mock"}
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=5) as server:
                server.noop()
            return {"status": "healthy", "channel": "email", "mode": "smtp"}
        except Exception as e:
            return {"status": "unhealthy", "channel": "email", "error": str(e)}

    def estimate_cost(self, text: str, recipient_address: str) -> dict[str, Any]:
        return {"cost_estimate": 0.0, "segments": 1, "currency": "BDT"}
