"""Typed Event Catalog for LexGOV AI Alert Center.

Provides typed event definitions, default severities, recipient resolution rules,
and bilingual (Bangla & English) templates for in-app, email, SMS, and WhatsApp.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AlertSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecipientRule(str, Enum):
    COMPLIANCE_OWNER = "compliance_owner"      # Tag-based primary/backup owner
    WATCHERS = "watchers"                      # Users watching specific law/regulation
    WORKSPACE_ADMINS = "workspace_admins"      # Owners and Admins of workspace
    ASSIGNED_USER = "assigned_user"            # Reviewer or assignee
    TARGET_USER = "target_user"                # Specific user (e.g. invitee, account owner)
    ALL_MEMBERS = "all_members"                # Entire workspace team


@dataclass
class AlertEvent:
    workspace_id: str
    event_type: str
    severity: AlertSeverity = AlertSeverity.MEDIUM
    entity_type: str = "general"
    entity_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    version_hash: str | None = None


@dataclass(frozen=True)
class EventDefinition:
    event_type: str
    default_severity: AlertSeverity
    default_recipient_rule: RecipientRule
    ack_required_default: bool
    domain_tag_default: str = "general"
    category: str = "compliance"  # compliance, security, billing, team, system

    def get_default_channels(self, severity: AlertSeverity | None = None) -> list[str]:
        sev = severity or self.default_severity
        if sev == AlertSeverity.CRITICAL:
            return ["in_app", "email", "sms", "whatsapp"]
        if sev == AlertSeverity.HIGH:
            return ["in_app", "email", "sms"]
        if sev == AlertSeverity.MEDIUM:
            return ["in_app", "email"]
        return ["in_app"]


EVENT_CATALOG: dict[str, EventDefinition] = {
    "regulation_change_detected": EventDefinition(
        event_type="regulation_change_detected",
        default_severity=AlertSeverity.HIGH,
        default_recipient_rule=RecipientRule.COMPLIANCE_OWNER,
        ack_required_default=True,
        category="compliance",
    ),
    "law_amendment_watched": EventDefinition(
        event_type="law_amendment_watched",
        default_severity=AlertSeverity.HIGH,
        default_recipient_rule=RecipientRule.WATCHERS,
        ack_required_default=True,
        category="compliance",
    ),
    "deadline_reminder": EventDefinition(
        event_type="deadline_reminder",
        default_severity=AlertSeverity.MEDIUM,
        default_recipient_rule=RecipientRule.COMPLIANCE_OWNER,
        ack_required_default=False,
        category="compliance",
    ),
    "analysis_completed": EventDefinition(
        event_type="analysis_completed",
        default_severity=AlertSeverity.INFO,
        default_recipient_rule=RecipientRule.TARGET_USER,
        ack_required_default=False,
        category="compliance",
    ),
    "high_risk_finding": EventDefinition(
        event_type="high_risk_finding",
        default_severity=AlertSeverity.CRITICAL,
        default_recipient_rule=RecipientRule.COMPLIANCE_OWNER,
        ack_required_default=True,
        category="compliance",
    ),
    "review_assigned": EventDefinition(
        event_type="review_assigned",
        default_severity=AlertSeverity.MEDIUM,
        default_recipient_rule=RecipientRule.ASSIGNED_USER,
        ack_required_default=False,
        category="team",
    ),
    "finding_review_needed": EventDefinition(
        event_type="finding_review_needed",
        default_severity=AlertSeverity.MEDIUM,
        default_recipient_rule=RecipientRule.COMPLIANCE_OWNER,
        ack_required_default=False,
        category="compliance",
    ),
    "export_ready": EventDefinition(
        event_type="export_ready",
        default_severity=AlertSeverity.INFO,
        default_recipient_rule=RecipientRule.TARGET_USER,
        ack_required_default=False,
        category="system",
    ),
    "source_blocked_or_failing": EventDefinition(
        event_type="source_blocked_or_failing",
        default_severity=AlertSeverity.HIGH,
        default_recipient_rule=RecipientRule.WORKSPACE_ADMINS,
        ack_required_default=False,
        category="system",
    ),
    "quota_nearing_limit": EventDefinition(
        event_type="quota_nearing_limit",
        default_severity=AlertSeverity.MEDIUM,
        default_recipient_rule=RecipientRule.WORKSPACE_ADMINS,
        ack_required_default=False,
        category="billing",
    ),
    "subscription_event": EventDefinition(
        event_type="subscription_event",
        default_severity=AlertSeverity.INFO,
        default_recipient_rule=RecipientRule.WORKSPACE_ADMINS,
        ack_required_default=False,
        category="billing",
    ),
    "team_invite": EventDefinition(
        event_type="team_invite",
        default_severity=AlertSeverity.INFO,
        default_recipient_rule=RecipientRule.TARGET_USER,
        ack_required_default=False,
        category="team",
    ),
    "security_event": EventDefinition(
        event_type="security_event",
        default_severity=AlertSeverity.HIGH,
        default_recipient_rule=RecipientRule.TARGET_USER,
        ack_required_default=False,
        category="security",
    ),
    "ack_overdue_escalation": EventDefinition(
        event_type="ack_overdue_escalation",
        default_severity=AlertSeverity.CRITICAL,
        default_recipient_rule=RecipientRule.WORKSPACE_ADMINS,
        ack_required_default=True,
        category="compliance",
    ),
}


# ---------------------------------------------------------------------------
# Bilingual Template System (Bangla + English)
# ---------------------------------------------------------------------------

def render_event_template(
    event_type: str,
    channel: str,
    locale: str = "en",
    payload: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Renders localized title, short body, full HTML/text body, and deep link for an alert."""
    p = payload or {}
    is_bn = locale.lower() == "bn"

    title_map = {
        "regulation_change_detected": (
            f"নিয়ন্ত্রক পরিবর্তন শনাক্ত: {p.get('law_title', 'আইন বা প্রবিধান')}"
            if is_bn
            else f"Regulatory Change Detected: {p.get('law_title', 'Law or Regulation')}"
        ),
        "law_amendment_watched": (
            f"আপনার নজরদারির আইনে সংশোধন: {p.get('law_title', 'আইন')}"
            if is_bn
            else f"Watched Law Amended: {p.get('law_title', 'Watched Law')}"
        ),
        "deadline_reminder": (
            f"সময়সীমা অনুস্মারক: {p.get('title', 'অনুপালন দাখিল')} ({p.get('days_left', 0)} দিন বাকি)"
            if is_bn
            else f"Deadline Reminder: {p.get('title', 'Compliance Filing')} ({p.get('days_left', 0)} days left)"
        ),
        "high_risk_finding": (
            f"জরুরি উচ্চ-ঝুঁকি শনাক্ত: {p.get('finding_title', 'মারাত্মক অসামঞ্জস্য')}"
            if is_bn
            else f"CRITICAL High-Risk Finding: {p.get('finding_title', 'Severe Non-Compliance')}"
        ),
        "analysis_completed": (
            f"এসওপি বিশ্লেষণ সম্পন্ন: {p.get('document_title', 'ডকুমেন্ট')}"
            if is_bn
            else f"SOP Analysis Completed: {p.get('document_title', 'Document')}"
        ),
        "review_assigned": (
            f"পর্যালোচনার জন্য দায়িত্ব অর্পণ: {p.get('title', 'ফাইল')}"
            if is_bn
            else f"Review Assigned: {p.get('title', 'Finding/Document')}"
        ),
        "finding_review_needed": (
            f"মানুষের পর্যালোচনা প্রয়োজন: {p.get('finding_title', 'আইনি অসামঞ্জস্য')}"
            if is_bn
            else f"Human Review Needed: {p.get('finding_title', 'Compliance Finding')}"
        ),
        "export_ready": (
            f"ডকুমেন্ট এক্সপোর্ট প্রস্তুত: {p.get('export_title', 'রিপোর্ট')}"
            if is_bn
            else f"Export Ready: {p.get('export_title', 'Document')}"
        ),
        "source_blocked_or_failing": (
            f"সতর্কতা: ক্রলার উৎস অবরুদ্ধ বা ব্যর্থ: {p.get('source_name', 'উৎস')}"
            if is_bn
            else f"Crawler Source Blocked or Failing: {p.get('source_name', 'Source')}"
        ),
        "quota_nearing_limit": (
            f"ব্যবহার কোটা সতর্কতা: {p.get('percent', 80)}% ব্যবহৃত"
            if is_bn
            else f"Usage Quota Alert: {p.get('percent', 80)}% consumed"
        ),
        "subscription_event": (
            f"সাবস্ক্রিপশন আপডেট: {p.get('event_name', 'প্ল্যান আপডেট')}"
            if is_bn
            else f"Subscription Event: {p.get('event_name', 'Plan Update')}"
        ),
        "team_invite": (
            f"ওয়ার্কস্পেস যোগদানের আমন্ত্রণ: {p.get('workspace_name', 'টিম')}"
            if is_bn
            else f"Workspace Invitation: {p.get('workspace_name', 'Team')}"
        ),
        "security_event": (
            f"নিরাপত্তা সতর্কতা: {p.get('event_desc', 'নতুন লগইন বা এপিআই কি')}"
            if is_bn
            else f"Security Alert: {p.get('event_desc', 'Unfamiliar Sign-in or API Key')}"
        ),
        "ack_overdue_escalation": (
            f"জরুরি এস্কেলেশন: অমীমাংসিত উচ্চ-ঝুঁকি সতর্কতা!"
            if is_bn
            else f"URGENT Escalation: Unacknowledged High-Risk Alert!"
        ),
    }

    subject = title_map.get(event_type, "LexGOV AI Notification" if not is_bn else "লেক্সগভ এআই বিজ্ঞপ্তি")
    deep_link = p.get("link") or p.get("action_url") or "/alerts"

    # Compact body for SMS and Push notifications
    if channel in ("sms", "web_push"):
        if is_bn:
            summary_snippet = p.get("summary_bn") or p.get("summary") or "জরুরি নিয়ন্ত্রক বিজ্ঞপ্তি।"
            body = f"[লেক্সগভ এআই] {subject}\n{summary_snippet[:100]}\nবিস্তারিত: {deep_link}"
        else:
            summary_snippet = p.get("summary_en") or p.get("summary") or "Urgent compliance alert."
            body = f"[LexGOV AI] {subject}\n{summary_snippet[:120]}\nDetails: {deep_link}"
        return {"subject": subject, "body": body, "deep_link": deep_link}

    # WhatsApp pre-approved structure
    if channel == "whatsapp":
        summary = p.get("summary") or (
            "নতুন নিয়ন্ত্রক পরিবর্তন বা জরুরি সতর্কতা যাচাই করুন।" if is_bn else "Please review this compliance alert."
        )
        body = (
            f"*LexGOV AI Alert*\n\n"
            f"*{subject}*\n\n"
            f"{summary}\n\n"
            f"🔗 View & Acknowledge: {deep_link}"
        )
        return {"subject": subject, "body": body, "deep_link": deep_link}

    # Standard In-App / Email text
    summary = p.get("summary") or (
        "অফিসিয়াল গেজেট বা পোর্টালে নতুন তথ্য শনাক্ত হয়েছে। অবিলম্বে পর্যালোচনা করুন।"
        if is_bn
        else "A new regulatory update or compliance action item has been detected. Please review."
    )
    affected_hint = p.get("affected_sops_hint")
    if affected_hint:
        summary += f"\n\nAffected SOPs: {affected_hint}"

    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; color: #0f172a; line-height: 1.5;">
        <div style="margin-bottom: 20px;">
            <span style="font-size: 20px; font-weight: 800; color: #0f172a;">LexGOV <span style="color: #059669;">AI</span></span>
            <span style="font-size: 11px; background: #e0e7ff; color: #3730a3; padding: 2px 8px; border-radius: 9999px; margin-left: 8px; font-weight: 600; text-transform: uppercase;">{p.get('severity', 'Alert').upper()}</span>
        </div>
        <h2 style="font-size: 18px; font-weight: 700; margin-bottom: 12px; color: #1e293b;">{subject}</h2>
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; margin-bottom: 20px; font-size: 14px; color: #334155;">
            {summary.replace('\n', '<br>')}
        </div>
        <div style="margin-bottom: 24px;">
            <a href="{deep_link}" style="display: inline-block; background-color: #0f172a; color: #ffffff; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-size: 13px; font-weight: 600;">
                {'সতর্কতা দেখুন ও স্বীকার করুন' if is_bn else 'View & Acknowledge Alert'} &rarr;
            </a>
        </div>
        <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 24px 0;" />
        <div style="font-size: 11px; color: #64748b;">
            © 2026 LexGOV AI Technologies Inc. Designed for Bangladeshi SME Compliance.<br>
            <a href="/settings/notifications" style="color: #6366f1; text-decoration: none;">{'বিজ্ঞপ্তি পছন্দ পরিবর্তন করুন' if is_bn else 'Manage Notification Preferences'}</a>
        </div>
    </div>
    """

    return {
        "subject": subject,
        "body": summary,
        "html_body": html_body,
        "deep_link": deep_link,
    }
