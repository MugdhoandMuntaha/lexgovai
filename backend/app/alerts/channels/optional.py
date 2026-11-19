"""Optional Alert Channels (Telegram, Slack, Web Push) behind feature flags."""

from __future__ import annotations

import logging
import os
from typing import Any
import httpx

logger = logging.getLogger("complianceos.alerts.optional")


class TelegramChannelAdapter:
    def __init__(self, bot_token: str | None = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.enabled = bool(self.bot_token and os.getenv("ENABLE_TELEGRAM_ALERTS", "false").lower() == "true")

    def send(self, alert_id: str, recipient_address: str, subject: str, body: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.enabled:
            return {"status": "rejected", "provider": "telegram", "provider_message_id": None, "error": "Telegram disabled"}
        text = f"*{subject}*\n\n{body}"
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.post(url, json={"chat_id": recipient_address, "text": text, "parse_mode": "Markdown"})
                if r.status_code == 200:
                    return {"status": "delivered", "provider": "telegram", "provider_message_id": str(r.json().get("result", {}).get("message_id")), "error": None}
                return {"status": "failed", "provider": "telegram", "error": r.text[:100]}
        except Exception as e:
            return {"status": "failed", "provider": "telegram", "error": str(e)}

    def parse_delivery_webhook(self, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        return {"status": "delivered", "provider_message_id": payload.get("message_id")}

    def health_check(self) -> dict[str, Any]:
        return {"status": "healthy" if self.enabled else "disabled", "channel": "telegram"}

    def estimate_cost(self, text: str, recipient_address: str) -> dict[str, Any]:
        return {"cost_estimate": 0.0, "segments": 1, "currency": "BDT"}


class SlackChannelAdapter:
    def __init__(self, default_webhook_url: str | None = None):
        self.webhook_url = default_webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        self.enabled = bool(self.webhook_url and os.getenv("ENABLE_SLACK_ALERTS", "false").lower() == "true")

    def send(self, alert_id: str, recipient_address: str, subject: str, body: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        target_url = recipient_address if recipient_address.startswith("https://hooks.slack.com") else self.webhook_url
        if not self.enabled or not target_url:
            return {"status": "rejected", "provider": "slack", "provider_message_id": None, "error": "Slack disabled"}
        payload = {"text": f"*{subject}*\n{body}"}
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.post(target_url, json=payload)
                if r.status_code == 200:
                    return {"status": "delivered", "provider": "slack", "provider_message_id": "slack_ok", "error": None}
                return {"status": "failed", "provider": "slack", "error": r.text[:100]}
        except Exception as e:
            return {"status": "failed", "provider": "slack", "error": str(e)}

    def parse_delivery_webhook(self, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        return {"status": "delivered"}

    def health_check(self) -> dict[str, Any]:
        return {"status": "healthy" if self.enabled else "disabled", "channel": "slack"}

    def estimate_cost(self, text: str, recipient_address: str) -> dict[str, Any]:
        return {"cost_estimate": 0.0, "segments": 1, "currency": "BDT"}


class WebPushChannelAdapter:
    def __init__(self):
        self.vapid_public = os.getenv("VAPID_PUBLIC_KEY")
        self.vapid_private = os.getenv("VAPID_PRIVATE_KEY")
        self.enabled = bool(self.vapid_public and os.getenv("ENABLE_WEB_PUSH_ALERTS", "false").lower() == "true")

    def send(self, alert_id: str, recipient_address: str, subject: str, body: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.enabled:
            return {"status": "rejected", "provider": "web_push", "provider_message_id": None, "error": "Web Push disabled"}
        # Mock/simulated Web Push delivery
        return {"status": "delivered", "provider": "web_push", "provider_message_id": f"push_{alert_id}", "error": None}

    def parse_delivery_webhook(self, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        return {"status": "delivered"}

    def health_check(self) -> dict[str, Any]:
        return {"status": "healthy" if self.enabled else "disabled", "channel": "web_push"}

    def estimate_cost(self, text: str, recipient_address: str) -> dict[str, Any]:
        return {"cost_estimate": 0.0, "segments": 1, "currency": "BDT"}
