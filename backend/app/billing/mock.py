"""Mock billing provider adapter for local development and testing.

Hard-disabled in production.
"""

from __future__ import annotations

import secrets
from typing import Any

from app.db import Database, new_id, utcnow
from app.plans import PlanId, get_plan
from app.subscriptions import SubscriptionService


class MockBillingProvider:
    """Simulates instant checkout and payment webhook processing."""

    def __init__(self, db: Database, subscriptions: SubscriptionService, app_env: str = "development"):
        if app_env.lower() == "production":
            raise RuntimeError("MockBillingProvider is strictly prohibited in production environments.")
        self._db = db
        self._subscriptions = subscriptions
        self._app_env = app_env

    def create_checkout(
        self, workspace_id: str, plan_id: PlanId, return_url: str
    ) -> dict[str, Any]:
        plan = get_plan(plan_id)
        session_id = f"mock_chk_{new_id()}"

        # Immediately execute upgrade in mock mode for instant developer gratification
        sub = self._subscriptions.upgrade_plan(workspace_id, plan_id)

        # Record audit webhook event
        event_id = f"evt_{new_id()}"
        self._db.record_webhook_event(
            provider_event_id=event_id,
            provider="mock_gateway",
            payload={
                "event_id": event_id,
                "event_type": "checkout.session.completed",
                "workspace_id": workspace_id,
                "plan_id": plan_id,
                "amount_bdt": plan.price_bdt_monthly,
                "currency": "BDT",
                "status": "paid",
            },
        )

        return {
            "session_id": session_id,
            "checkout_url": f"{return_url}?session_id={session_id}&plan={plan_id}&status=success",
            "plan_id": plan_id,
            "amount_bdt": plan.price_bdt_monthly,
            "status": "completed",
            "subscription": sub,
        }

    def handle_webhook(
        self, payload: dict[str, Any], signature: str | None = None
    ) -> dict[str, Any]:
        event_id = payload.get("event_id") or payload.get("id") or new_id()
        if self._db.is_webhook_processed(event_id):
            return {"status": "ignored", "reason": "duplicate_event", "event_id": event_id}

        event_type = payload.get("event_type", "checkout.session.completed")
        workspace_id = payload.get("workspace_id")
        plan_id = payload.get("plan_id")

        if event_type in ("checkout.session.completed", "invoice.payment_succeeded"):
            if workspace_id and plan_id:
                self._subscriptions.upgrade_plan(workspace_id, plan_id)

        self._db.record_webhook_event(event_id, "mock_gateway", payload)
        return {"status": "processed", "event_id": event_id}

    def cancel(self, subscription_id: str) -> bool:
        return True

