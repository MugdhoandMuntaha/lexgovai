"""In-App Channel Adapter.

Stores notifications directly into the workspace notifications repository with
severity, acknowledgment state, and action deep links.
"""

from __future__ import annotations

import json
from typing import Any
from ...db import Database, new_id, utcnow


class InAppChannelAdapter:
    def __init__(self, db: Database):
        self.db = db

    def send(
        self,
        alert_id: str,
        recipient_address: str,  # recipient user_id
        subject: str,
        body: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        meta = metadata or {}
        workspace_id = meta.get("workspace_id", "")
        severity = meta.get("severity", "info")
        event_type = meta.get("event_type", "general")
        ack_required = bool(meta.get("ack_required", False))
        deep_link = meta.get("deep_link") or "/alerts"
        action_buttons = meta.get("action_buttons")
        action_btn_str = json.dumps(action_buttons) if action_buttons else None
        dedupe_key = f"in_app:{alert_id}:{recipient_address}"

        notif_id = new_id()
        now = utcnow()

        with self.db._lock:
            # Check if duplicate notification already created
            existing = self.db._fetchone("SELECT id FROM notifications WHERE dedupe_key = ?", (dedupe_key,))
            if not existing:
                self.db._conn.execute(
                    """
                    INSERT INTO notifications (id, workspace_id, user_id, title, body, link, channel, dedupe_key, created_at,
                                               severity, event_type, ack_required, deep_link, action_buttons)
                    VALUES (?, ?, ?, ?, ?, ?, 'in_app', ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        notif_id,
                        workspace_id,
                        recipient_address,
                        subject,
                        body,
                        deep_link,
                        dedupe_key,
                        now,
                        severity,
                        event_type,
                        1 if ack_required else 0,
                        deep_link,
                        action_btn_str,
                    ),
                )
                self.db._conn.commit()

        return {
            "status": "delivered",
            "provider": "in_app",
            "provider_message_id": notif_id,
            "cost_estimate": 0.0,
            "segments": 1,
            "error": None,
        }

    def parse_delivery_webhook(self, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        return {"status": "delivered", "provider_message_id": payload.get("id"), "error": None}

    def health_check(self) -> dict[str, Any]:
        return {"status": "healthy", "channel": "in_app"}

    def estimate_cost(self, text: str, recipient_address: str) -> dict[str, Any]:
        return {"cost_estimate": 0.0, "segments": 1, "currency": "BDT"}
