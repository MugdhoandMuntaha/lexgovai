"""Usage metering, counter windows, reservation ledgers, and quota checks.

Handles COUNTER (monthly window) and GAUGE (live count) metrics with
two-phase reserve/commit/release semantics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from .db import Database, LEGACY_WORKSPACE_ID
from .entitlements import EntitlementService
from .plans import METRICS, MetricKind, PlanId, next_plan_with_higher_quota

DHAKA_TZ = ZoneInfo("Asia/Dhaka")


class QuotaExceededError(Exception):
    def __init__(self, metric: str, limit: int, used: int, resets_at: str, upgrade_to: PlanId | None):
        self.metric = metric
        self.limit = limit
        self.used = used
        self.resets_at = resets_at
        self.upgrade_to = upgrade_to
        super().__init__(
            f"Monthly quota exceeded for '{metric}'. Limit: {limit}, Used: {used}. Resets at {resets_at}."
        )


class UsageService:
    def __init__(self, db: Database, entitlements: EntitlementService):
        self._db = db
        self._entitlements = entitlements

    def resolve_window(self, workspace_id: str) -> tuple[str, str]:
        """Resolves (window_start, resets_at).

        Paid subscriptions anchor to their billing period.
        Free subscriptions anchor to calendar month in Asia/Dhaka.
        """
        sub = self._db.get_subscription(workspace_id)
        if sub and sub.get("status") in ("active", "trialing", "past_due") and sub.get("plan_id") != "free":
            return sub["period_start"], sub["period_end"]

        now_dhaka = datetime.now(DHAKA_TZ)
        start_of_month = now_dhaka.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Next month start
        if start_of_month.month == 12:
            next_month = start_of_month.replace(year=start_of_month.year + 1, month=1)
        else:
            next_month = start_of_month.replace(month=start_of_month.month + 1)

        return (
            start_of_month.astimezone(timezone.utc).isoformat(timespec="seconds"),
            next_month.astimezone(timezone.utc).isoformat(timespec="seconds"),
        )

    def get_metric_usage(self, workspace_id: str, metric: str) -> tuple[int, int, str]:
        """Returns (used, limit, resets_at)."""
        limit = self._entitlements.limit(workspace_id, metric)
        window_start, resets_at = self.resolve_window(workspace_id)
        mdef = METRICS.get(metric)

        if mdef and mdef.kind == MetricKind.GAUGE:
            if metric == "business_profiles":
                used = self._db.count_business_profiles(workspace_id)
            elif metric == "team_members":
                used = self._db.count_team_members(workspace_id)
            elif metric == "monitored_sources":
                used = self._db.count_monitored_sources(workspace_id)
            else:
                used = 0
            return used, limit, resets_at

        # Counter metric
        used = self._db.get_usage_counter(workspace_id, metric, window_start)
        return used, limit, resets_at

    def check_counter_quota(self, workspace_id: str, metric: str, amount: int = 1) -> None:
        """Verifies workspace has remaining counter quota; raises QuotaExceededError if not."""
        if workspace_id == LEGACY_WORKSPACE_ID:
            return  # Legacy workspace has unbounded developer quota

        used, limit, resets_at = self.get_metric_usage(workspace_id, metric)
        if used + amount > limit:
            current_plan = self._entitlements.get_workspace_plan_id(workspace_id)
            upgrade_to = next_plan_with_higher_quota(metric, current_plan)
            raise QuotaExceededError(metric, limit, used, resets_at, upgrade_to)

    def check_gauge_quota(self, workspace_id: str, metric: str, additional: int = 1) -> None:
        """Verifies gauge (cap) has room for additional resources."""
        if workspace_id == LEGACY_WORKSPACE_ID:
            return

        used, limit, resets_at = self.get_metric_usage(workspace_id, metric)
        if used + additional > limit:
            current_plan = self._entitlements.get_workspace_plan_id(workspace_id)
            upgrade_to = next_plan_with_higher_quota(metric, current_plan)
            raise QuotaExceededError(metric, limit, used, resets_at, upgrade_to)

    def reserve(
        self,
        workspace_id: str,
        metric: str,
        idempotency_key: str,
        amount: int = 1,
        ref: str | None = None,
    ) -> None:
        """Atomically reserves usage quota.

        Checks quota and increments the counter with status='reserved'.
        Idempotent: repeating with the same key is a no-op.
        """
        with self._db._lock:
            existing = self._db.get_usage_event(idempotency_key)
            if existing:
                return

            self.check_counter_quota(workspace_id, metric, amount)
            window_start, _ = self.resolve_window(workspace_id)

            # Atomic reservation
            self._db.increment_usage_counter(workspace_id, metric, window_start, amount)
            self._db.create_usage_event(idempotency_key, workspace_id, metric, amount, "reserved", ref)

    def commit(self, idempotency_key: str) -> None:
        """Finalizes a reserved usage event on successful execution."""
        event = self._db.get_usage_event(idempotency_key)
        if event and event["status"] == "reserved":
            self._db.update_usage_event_status(idempotency_key, "committed")
            try:
                ws_id = event["workspace_id"]
                metric = event["metric"]
                used, limit, _ = self.get_metric_usage(ws_id, metric)
                if limit > 0 and (used / limit) >= 0.8:
                    from .alerts.events import AlertEvent, AlertSeverity
                    from .alerts.router import AlertRouter
                    router = AlertRouter(db=self._db)
                    pct = round((used / limit) * 100, 1)
                    sev = AlertSeverity.HIGH if pct >= 100 else AlertSeverity.MEDIUM
                    ev = AlertEvent(
                        workspace_id=ws_id,
                        event_type="quota_nearing_limit",
                        severity=sev,
                        entity_type="metric",
                        entity_id=f"{metric}_{used}",
                        payload={
                            "metric": metric,
                            "used": used,
                            "limit": limit,
                            "percent": pct,
                        },
                    )
                    router.route_event(ev)
            except Exception:
                pass

    def release(self, idempotency_key: str) -> None:
        """Releases reserved quota on pipeline failure."""
        event = self._db.get_usage_event(idempotency_key)
        if event and event["status"] == "reserved":
            window_start, _ = self.resolve_window(event["workspace_id"])
            self._db.decrement_usage_counter(event["workspace_id"], event["metric"], window_start, event["amount"])
            self._db.update_usage_event_status(idempotency_key, "released")

    def get_usage_summary(self, workspace_id: str) -> list[dict[str, Any]]:
        """Returns structured meters for all 6 tracked metrics for UI dashboards."""
        meters = []
        for key, mdef in METRICS.items():
            used, limit, resets_at = self.get_metric_usage(workspace_id, key)
            pct = round((used / limit * 100), 1) if limit > 0 else 0.0
            meters.append({
                "metric": key,
                "display_name": mdef.display_name,
                "kind": mdef.kind.value,
                "description": mdef.description,
                "used": used,
                "limit": limit,
                "percent": min(100.0, pct),
                "resets_at": resets_at,
            })
        return meters
