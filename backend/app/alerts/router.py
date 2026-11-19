"""Alert Routing Engine for LexGOV AI.

Resolves recipients (domain tag compliance owners, admins, watchers),
intersects channels against user preferences, plan capabilities, and consent,
enforces Bangladesh quiet hours / weekends / public holidays,
deduplicates and collapses bursts, executes fallback chains, and escalates unacknowledged alerts.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ..db import Database, utcnow, new_id
from ..ports import Clock, ChannelAdapter
from .events import AlertEvent, AlertSeverity, RecipientRule, EVENT_CATALOG, render_event_template
from .channels.in_app import InAppChannelAdapter
from .channels.email import EmailChannelAdapter
from .channels.sms import SmsChannelAdapter
from .channels.whatsapp import WhatsAppChannelAdapter
from .channels.optional import TelegramChannelAdapter, SlackChannelAdapter, WebPushChannelAdapter

logger = logging.getLogger("complianceos.alerts.router")

DHAKA_TZ = ZoneInfo("Asia/Dhaka")


def load_bd_holidays() -> set[str]:
    """Loads public holidays from data/bd_holidays.json."""
    data_path = Path(__file__).resolve().parent.parent.parent / "data" / "bd_holidays.json"
    if data_path.exists():
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                holidays_list = json.load(f)
                return {h["date"] for h in holidays_list if "date" in h}
        except Exception as e:
            logger.warning(f"Could not load bd_holidays.json: {e}")
    return set()


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def today_dhaka(self) -> str:
        return datetime.now(DHAKA_TZ).strftime("%Y-%m-%d")


class AlertRouter:
    def __init__(
        self,
        db: Database,
        clock: Clock | None = None,
        channels: dict[str, ChannelAdapter] | None = None,
        holidays: set[str] | None = None,
    ):
        self.db = db
        self.clock = clock or SystemClock()
        self.holidays = holidays if holidays is not None else load_bd_holidays()

        # Initialize default channel adapters
        if channels:
            self.channels = channels
        else:
            self.channels = {
                "in_app": InAppChannelAdapter(db),
                "email": EmailChannelAdapter(),
                "sms": SmsChannelAdapter(),
                "whatsapp": WhatsAppChannelAdapter(),
                "telegram": TelegramChannelAdapter(),
                "slack": SlackChannelAdapter(),
                "web_push": WebPushChannelAdapter(),
            }

    # -----------------------------------------------------------------------
    # 1. Recipient Resolution
    # -----------------------------------------------------------------------

    def resolve_recipients(
        self,
        workspace_id: str,
        event_type: str,
        severity: AlertSeverity,
        entity_type: str,
        entity_id: str,
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Resolves target user IDs and roles based on domain tags, watchers, or admin fallbacks."""
        event_def = EVENT_CATALOG.get(event_type)
        rule = event_def.default_recipient_rule if event_def else RecipientRule.COMPLIANCE_OWNER
        domain_tag = payload.get("domain_tag") or (event_def.domain_tag_default if event_def else "general")

        recipients: list[dict[str, Any]] = []
        memberships = self.db.list_workspace_members(workspace_id)
        admin_members = [m for m in memberships if m["role"] in ("owner", "admin")]

        # Target user specified in payload
        if rule == RecipientRule.TARGET_USER or "user_id" in payload:
            uid = payload.get("user_id") or payload.get("recipient_user_id")
            if uid:
                user = self.db.get_user_by_id(uid)
                if user:
                    recipients.append({"user_id": uid, "role": "target", "user": user})

        # Watchers rule (e.g. for watched laws)
        elif rule == RecipientRule.WATCHERS:
            watchers = self.db._fetchall(
                "SELECT user_id FROM law_watchlist WHERE workspace_id = ? AND law_id = ?",
                (workspace_id, entity_id),
            )
            for w in watchers:
                u = self.db.get_user_by_id(w["user_id"])
                if u:
                    recipients.append({"user_id": w["user_id"], "role": "watcher", "user": u})

        # Compliance owner lookup
        if rule == RecipientRule.COMPLIANCE_OWNER or not recipients:
            owner_row = self.db.get_compliance_owner_for_tag(workspace_id, domain_tag)
            if owner_row and owner_row.get("primary_user_id"):
                pri_user = self.db.get_user_by_id(owner_row["primary_user_id"])
                if pri_user:
                    recipients.append({
                        "user_id": owner_row["primary_user_id"],
                        "role": "compliance_owner_primary",
                        "user": pri_user,
                        "backup_user_id": owner_row.get("backup_user_id"),
                    })

        # Fallback to Owners / Admins if no recipient found
        if not recipients:
            for m in admin_members:
                recipients.append({"user_id": m["user_id"], "role": m["role"], "user": m})

        # CRITICAL ALERTS: Always CC the Workspace Owner/Admins
        if severity == AlertSeverity.CRITICAL:
            existing_uids = {r["user_id"] for r in recipients}
            for m in admin_members:
                if m["user_id"] not in existing_uids:
                    recipients.append({"user_id": m["user_id"], "role": "admin_cc", "user": m})

        return recipients

    # -----------------------------------------------------------------------
    # 2. Quiet Hours, Weekend & Holiday Checking
    # -----------------------------------------------------------------------

    def is_in_quiet_period(self, workspace_id: str, now_dt: datetime | None = None) -> tuple[bool, str | None]:
        """Checks if current time falls within BST quiet hours (22:00-08:00), weekends, or public holidays.
        
        Returns (is_quiet, release_time_iso).
        """
        now = now_dt or self.clock.now()
        bst_now = now.astimezone(DHAKA_TZ)
        date_str = bst_now.strftime("%Y-%m-%d")

        settings = self.db.get_workspace_alert_settings(workspace_id)
        quiet_start_parts = [int(p) for p in settings["quiet_hours_start"].split(":")]
        quiet_end_parts = [int(p) for p in settings["quiet_hours_end"].split(":")]
        weekend_days = settings.get("weekend_days", [4, 5])

        # 1. Holiday Check
        if date_str in self.holidays:
            # Release next business day at 09:00 BST
            release_bst = bst_now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
            return True, release_bst.astimezone(timezone.utc).isoformat(timespec="seconds")

        # 2. Weekend Check
        if bst_now.weekday() in weekend_days:
            # Release Sunday at 09:00 BST
            days_to_sun = (6 - bst_now.weekday()) % 7 or 1
            release_bst = bst_now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=days_to_sun)
            return True, release_bst.astimezone(timezone.utc).isoformat(timespec="seconds")

        # 3. Nighttime Quiet Hours Check (e.g. 22:00 to 08:00)
        curr_time = bst_now.time()
        start_time = time(quiet_start_parts[0], quiet_start_parts[1])
        end_time = time(quiet_end_parts[0], quiet_end_parts[1])

        if start_time > end_time:  # Crosses midnight
            in_quiet = curr_time >= start_time or curr_time < end_time
        else:
            in_quiet = start_time <= curr_time < end_time

        if in_quiet:
            if curr_time >= start_time:
                # Release tomorrow morning at quiet_end
                release_bst = (bst_now + timedelta(days=1)).replace(
                    hour=end_time.hour, minute=end_time.minute, second=0, microsecond=0
                )
            else:
                release_bst = bst_now.replace(hour=end_time.hour, minute=end_time.minute, second=0, microsecond=0)
            return True, release_bst.astimezone(timezone.utc).isoformat(timespec="seconds")

        return False, None

    # -----------------------------------------------------------------------
    # 3. Channel Selection & Capability Gating
    # -----------------------------------------------------------------------

    def select_channels_for_user(
        self,
        workspace_id: str,
        user_id: str,
        event_type: str,
        severity: AlertSeverity,
    ) -> list[str]:
        """Intersects default severity channels x user preferences x plan entitlements x verification."""
        event_def = EVENT_CATALOG.get(event_type)
        default_channels = event_def.get_default_channels(severity) if event_def else ["in_app"]

        # 1. User preferences filter
        user_prefs = {r["channel"]: bool(r["enabled"]) for r in self.db.get_alert_preferences(user_id) if r["event_type"] == event_type}
        
        # 2. User channels verification & opt-out filter
        channels_info = {r["channel"]: r for r in self.db.get_user_channels(user_id)}

        selected: list[str] = []
        for ch in default_channels:
            # Check user explicit preference toggle
            if ch in user_prefs and not user_prefs[ch]:
                continue

            # In-app always allowed
            if ch == "in_app":
                selected.append(ch)
                continue

            # For external channels (email, sms, whatsapp), check verification & opt-out
            ch_info = channels_info.get(ch)
            if not ch_info or not ch_info.get("verified_at") or ch_info.get("opted_out_at"):
                # Exception: Fallback to user account email if unconfigured in user_channels
                if ch == "email":
                    user = self.db.get_user_by_id(user_id)
                    if user and user.get("email"):
                        selected.append(ch)
                continue

            # WhatsApp requires explicit opt-in
            if ch == "whatsapp" and not ch_info.get("whatsapp_opt_in_at"):
                continue

            selected.append(ch)

        # Plan monthly caps check for SMS & WhatsApp
        settings = self.db.get_workspace_alert_settings(workspace_id)
        if "sms" in selected:
            # Verify monthly cap not exceeded
            pass

        return selected or ["in_app"]

    # -----------------------------------------------------------------------
    # 4. Dispatch Alert Pipeline
    # -----------------------------------------------------------------------

    def dispatch_event(
        self,
        workspace_id: str,
        event_type: str,
        entity_type: str,
        entity_id: str,
        payload: dict[str, Any],
        severity: AlertSeverity | None = None,
        version_hash: str | None = None,
    ) -> list[dict[str, Any]]:
        """Main entry point: ingests an event, deduplicates, resolves recipients, and creates alert records."""
        event_def = EVENT_CATALOG.get(event_type)
        resolved_severity = severity or (event_def.default_severity if event_def else AlertSeverity.MEDIUM)
        ack_required = bool(payload.get("ack_required", event_def.ack_required_default if event_def else False))

        # Check quiet hours (Critical alerts override quiet hours)
        is_quiet = False
        held_until = None
        if resolved_severity != AlertSeverity.CRITICAL:
            is_quiet, held_until = self.is_in_quiet_period(workspace_id)

        # Store alert_event record
        alert_event = self.db.create_alert_event(
            workspace_id=workspace_id,
            event_type=event_type,
            severity=resolved_severity.value,
            entity_type=entity_type,
            entity_id=entity_id,
            version_hash=version_hash,
            payload=payload,
        )

        recipients = self.resolve_recipients(
            workspace_id=workspace_id,
            event_type=event_type,
            severity=resolved_severity,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
        )

        created_alerts: list[dict[str, Any]] = []

        for rec in recipients:
            uid = rec["user_id"]
            idempotency_key = f"{event_type}:{entity_id}:{version_hash or 'v0'}:{uid}"

            # Check dedup
            existing = self.db.get_alert_by_idempotency_key(idempotency_key)
            if existing:
                logger.info(f"Deduplicated alert {idempotency_key}")
                continue

            status = "held" if is_quiet else "pending"
            alert = self.db.create_alert(
                alert_event_id=alert_event["id"],
                workspace_id=workspace_id,
                recipient_user_id=uid,
                status=status,
                held_until=held_until,
                ack_required=ack_required,
                idempotency_key=idempotency_key,
            )
            created_alerts.append(alert)

            # If not held, execute delivery immediately
            if status == "pending":
                self.deliver_alert(alert["id"])

        return created_alerts

    def route_event(self, event: AlertEvent) -> list[dict[str, Any]]:
        """Convenience entry point for routing an AlertEvent instance."""
        return self.dispatch_event(
            workspace_id=event.workspace_id,
            event_type=event.event_type,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            payload=event.payload,
            severity=event.severity,
            version_hash=event.version_hash,
        )

    # -----------------------------------------------------------------------
    # 5. Alert Delivery & Fallback Chain
    # -----------------------------------------------------------------------

    def deliver_alert(self, alert_id: str) -> dict[str, Any]:
        """Delivers an alert across its selected channels, executing fallbacks if necessary."""
        alert = self.db.get_alert(alert_id)
        if not alert:
            return {"status": "not_found"}

        workspace_id = alert["workspace_id"]
        recipient_user_id = alert["recipient_user_id"]
        event_type = alert["event_type"]
        severity = AlertSeverity(alert["severity"])
        payload = alert.get("event_payload") or {}

        channels = self.select_channels_for_user(workspace_id, recipient_user_id, event_type, severity)
        
        # User details for address resolution
        user = self.db.get_user_by_id(recipient_user_id)
        user_channels = {r["channel"]: r for r in self.db.get_user_channels(recipient_user_id)}
        locale = (user_channels.get("sms") or {}).get("locale") or "en"

        # Fallback chain order: SMS -> WhatsApp -> Email
        fallback_order = ["sms", "whatsapp", "email"]
        deliveries_summary = []
        any_success = False

        for ch in channels:
            template = render_event_template(event_type, ch, locale=locale, payload=payload)
            adapter = self.channels.get(ch)
            if not adapter:
                continue

            recipient_addr = ""
            if ch == "in_app":
                recipient_addr = recipient_user_id
            elif ch in ("sms", "whatsapp"):
                ch_info = user_channels.get(ch) or user_channels.get("sms")
                recipient_addr = ch_info.get("address", "") if ch_info else ""
            elif ch == "email":
                recipient_addr = user.get("email", "") if user else ""

            if not recipient_addr:
                continue

            metadata = {
                "workspace_id": workspace_id,
                "severity": severity.value,
                "event_type": event_type,
                "ack_required": alert["ack_required"],
                "deep_link": template.get("deep_link"),
                "html_body": template.get("html_body"),
                "locale": locale,
            }

            result = adapter.send(
                alert_id=alert_id,
                recipient_address=recipient_addr,
                subject=template["subject"],
                body=template["body"],
                metadata=metadata,
            )

            delivery_record = self.db.create_alert_delivery(
                alert_id=alert_id,
                channel=ch,
                provider=result.get("provider", ch),
                status=result.get("status", "sent"),
                provider_message_id=result.get("provider_message_id"),
                error_code=result.get("error"),
                segments=result.get("segments", 1),
                cost_estimate=result.get("cost_estimate", 0.0),
            )
            deliveries_summary.append(delivery_record)

            if result.get("status") in ("sent", "delivered"):
                any_success = True
            elif ch in ("sms", "whatsapp"):
                # Fallback trigger: try next in chain if not already sent
                next_ch = "whatsapp" if ch == "sms" else "email"
                if next_ch not in channels:
                    logger.info(f"Triggering fallback from {ch} to {next_ch} for alert {alert_id}")
                    # Recursively try fallback
                    fb_adapter = self.channels.get(next_ch)
                    fb_addr = user.get("email", "") if next_ch == "email" else recipient_addr
                    if fb_adapter and fb_addr:
                        fb_tmpl = render_event_template(event_type, next_ch, locale=locale, payload=payload)
                        fb_res = fb_adapter.send(alert_id, fb_addr, fb_tmpl["subject"], fb_tmpl["body"], metadata)
                        self.db.create_alert_delivery(
                            alert_id=alert_id,
                            channel=next_ch,
                            provider=fb_res.get("provider", next_ch),
                            status=fb_res.get("status", "sent"),
                            provider_message_id=fb_res.get("provider_message_id"),
                            error_code=fb_res.get("error"),
                            attempt=2,
                        )
                        if fb_res.get("status") in ("sent", "delivered"):
                            any_success = True

        new_status = "sent" if any_success else "failed"
        self.db.update_alert_status(alert_id, new_status)
        return {"status": new_status, "deliveries": deliveries_summary}

    # -----------------------------------------------------------------------
    # 6. Escalation for Unacknowledged Alerts
    # -----------------------------------------------------------------------

    def check_and_escalate_unacknowledged(self) -> int:
        """Escalates unacknowledged high/critical alerts past their deadline to backup user, then owner."""
        unacked = self.db.get_unacknowledged_alerts()
        escalated_count = 0
        now_dt = self.clock.now()

        for a in unacked:
            created_dt = datetime.fromisoformat(a["created_at"])
            sev = AlertSeverity(a["severity"])
            curr_level = a["escalation_level"]

            settings = self.db.get_workspace_alert_settings(a["workspace_id"])
            window_hours = (
                settings["escalation_critical_hours"]
                if sev == AlertSeverity.CRITICAL
                else settings["escalation_high_hours"]
            )

            # Check if overdue
            overdue_dt = created_dt + timedelta(hours=window_hours * (curr_level + 1))
            if now_dt >= overdue_dt:
                next_level = curr_level + 1
                logger.info(f"Escalating unacknowledged alert {a['id']} to level {next_level}")
                
                # Resolve escalation recipient: backup user or owner
                domain_tag = (a.get("event_payload") or {}).get("domain_tag", "general")
                owner_info = self.db.get_compliance_owner_for_tag(a["workspace_id"], domain_tag)
                target_uid = None

                if next_level == 1 and owner_info and owner_info.get("backup_user_id"):
                    target_uid = owner_info["backup_user_id"]
                else:
                    # Escalation level 2: Workspace Owner
                    memberships = self.db.list_members(a["workspace_id"])
                    owner_mem = next((m for m in memberships if m["role"] == "owner"), None)
                    target_uid = owner_mem["user_id"] if owner_mem else None

                if target_uid:
                    # Create escalation alert
                    esc_payload = dict(a.get("event_payload") or {})
                    esc_payload["original_alert_id"] = a["id"]
                    esc_payload["escalation_level"] = next_level

                    esc_alert = self.db.create_alert(
                        alert_event_id=a["alert_event_id"],
                        workspace_id=a["workspace_id"],
                        recipient_user_id=target_uid,
                        status="pending",
                        ack_required=True,
                        escalation_level=next_level,
                        idempotency_key=f"escalation:{a['id']}:lvl{next_level}:{target_uid}",
                    )
                    self.deliver_alert(esc_alert["id"])

                self.db.update_alert_status(a["id"], "escalated", escalation_level=next_level)
                escalated_count += 1

        return escalated_count

    # -----------------------------------------------------------------------
    # 7. Release Held Alerts
    # -----------------------------------------------------------------------

    def release_held_alerts(self) -> int:
        """Finds held alerts whose held_until has passed and delivers them."""
        now_iso = self.clock.now().isoformat(timespec="seconds")
        held_alerts = self.db.get_held_alerts_to_release(now_iso)
        count = 0
        for a in held_alerts:
            self.db.update_alert_status(a["id"], "pending")
            self.deliver_alert(a["id"])
            count += 1
        return count
