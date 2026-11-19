"""Billing provider port (Protocol) definition for swappable payment gateways."""

from __future__ import annotations

from typing import Any, Protocol

from app.plans import PlanId


class BillingProvider(Protocol):
    """Abstract port for payment providers (e.g. Mock, SSLCommerz, bKash, Stripe)."""

    def create_checkout(
        self, workspace_id: str, plan_id: PlanId, return_url: str
    ) -> dict[str, Any]:
        """Initiates a checkout session and returns redirect URL and session metadata."""
        ...

    def handle_webhook(
        self, payload: dict[str, Any], signature: str | None = None
    ) -> dict[str, Any]:
        """Processes incoming provider webhook payload idempotently."""
        ...

    def cancel(self, subscription_id: str) -> bool:
        """Cancels the subscription with the external payment provider."""
        ...

