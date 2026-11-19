"""Subscription lifecycle management: creation, upgrades, downgrades, cancellations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .db import Database, utcnow
from .plans import PlanId, get_plan


class SubscriptionService:
    def __init__(self, db: Database):
        self._db = db

    def ensure_free_subscription(self, workspace_id: str) -> dict[str, Any]:
        """Ensures a workspace has an active subscription record (defaults to free)."""
        sub = self._db.get_subscription(workspace_id)
        if sub:
            return sub

        now = datetime.now(timezone.utc)
        period_start = now.isoformat(timespec="seconds")
        # Free subscription window is ongoing
        period_end = (now + timedelta(days=3650)).isoformat(timespec="seconds")

        sub = self._db.create_subscription(
            workspace_id=workspace_id,
            plan_id="free",
            status="active",
            period_start=period_start,
            period_end=period_end,
            cancel_at_period_end=False,
        )
        self._db.log_subscription_event(
            subscription_id=sub["id"],
            workspace_id=workspace_id,
            event_type="subscription_created",
            new_plan="free",
            new_status="active",
        )
        return sub

    def upgrade_plan(self, workspace_id: str, new_plan_id: PlanId) -> dict[str, Any]:
        """Upgrades plan immediately upon successful checkout/payment."""
        get_plan(new_plan_id)  # Validate plan exists
        sub = self._db.get_subscription(workspace_id)
        old_plan = sub["plan_id"] if sub else "free"
        old_status = sub["status"] if sub else "none"

        now = datetime.now(timezone.utc)
        period_start = now.isoformat(timespec="seconds")
        period_end = (now + timedelta(days=30)).isoformat(timespec="seconds")

        if sub:
            self._db.update_subscription(
                workspace_id=workspace_id,
                plan_id=new_plan_id,
                status="active",
                period_start=period_start,
                period_end=period_end,
                cancel_at_period_end=False,
            )
            sub_id = sub["id"]
        else:
            created = self._db.create_subscription(
                workspace_id=workspace_id,
                plan_id=new_plan_id,
                status="active",
                period_start=period_start,
                period_end=period_end,
                cancel_at_period_end=False,
            )
            sub_id = created["id"]

        self._db.log_subscription_event(
            subscription_id=sub_id,
            workspace_id=workspace_id,
            event_type="plan_upgraded",
            old_plan=old_plan,
            new_plan=new_plan_id,
            old_status=old_status,
            new_status="active",
            metadata={"upgraded_at": period_start, "next_renewal": period_end},
        )
        return self._db.get_subscription(workspace_id)  # type: ignore[return-value]

    change_plan = upgrade_plan
    provision_free_subscription = ensure_free_subscription

    def cancel_subscription(self, workspace_id: str) -> dict[str, Any]:
        """Cancels subscription at current period end (does not delete workspace data)."""
        sub = self._db.get_subscription(workspace_id)
        if not sub:
            raise ValueError("No active subscription found for this workspace.")

        self._db.update_subscription(
            workspace_id=workspace_id,
            plan_id=sub["plan_id"],
            status=sub["status"],
            period_start=sub["period_start"],
            period_end=sub["period_end"],
            cancel_at_period_end=True,
        )
        self._db.log_subscription_event(
            subscription_id=sub["id"],
            workspace_id=workspace_id,
            event_type="subscription_canceled_at_period_end",
            old_plan=sub["plan_id"],
            new_plan=sub["plan_id"],
            old_status=sub["status"],
            new_status=sub["status"],
            metadata={"cancels_at": sub["period_end"]},
        )
        return self._db.get_subscription(workspace_id)  # type: ignore[return-value]

    change_plan = upgrade_plan
    provision_free_subscription = ensure_free_subscription

    def check_period_expiry(self, workspace_id: str) -> None:
        """Called periodically or on request to rollover or demote expired subscriptions."""
        sub = self._db.get_subscription(workspace_id)
        if not sub or sub["plan_id"] == "free":
            return

        now = datetime.now(timezone.utc)
        period_end = datetime.fromisoformat(sub["period_end"])

        if now >= period_end:
            if sub.get("cancel_at_period_end"):
                # Demote to free
                self._db.update_subscription(
                    workspace_id=workspace_id,
                    plan_id="free",
                    status="active",
                    period_start=now.isoformat(timespec="seconds"),
                    period_end=(now + timedelta(days=3650)).isoformat(timespec="seconds"),
                    cancel_at_period_end=False,
                )
                self._db.log_subscription_event(
                    subscription_id=sub["id"],
                    workspace_id=workspace_id,
                    event_type="subscription_expired_to_free",
                    old_plan=sub["plan_id"],
                    new_plan="free",
                    old_status=sub["status"],
                    new_status="active",
                )
            else:
                # Active renewal (for mock / automatic rebilling)
                next_end = (period_end + timedelta(days=30)).isoformat(timespec="seconds")
                self._db.update_subscription(
                    workspace_id=workspace_id,
                    plan_id=sub["plan_id"],
                    status="active",
                    period_start=sub["period_end"],
                    period_end=next_end,
                    cancel_at_period_end=False,
                )
                self._db.log_subscription_event(
                    subscription_id=sub["id"],
                    workspace_id=workspace_id,
                    event_type="subscription_renewed",
                    old_plan=sub["plan_id"],
                    new_plan=sub["plan_id"],
                    old_status=sub["status"],
                    new_status="active",
                    metadata={"renewed_until": next_end},
                )
