"""Typed feature options, level mappings, and system-wide operational constants.

Single source of truth for level-dependent behavioral options across Phase 2 capabilities.
All business rules and product assumptions are documented here as typed data structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Tunable System Constants
# ---------------------------------------------------------------------------

POLLER_MAX_BODY_BYTES: int = 5 * 1024 * 1024  # 5 MB maximum response size
POLLER_TIMEOUT_SECONDS: float = 10.0
POLLER_MIN_HOST_INTERVAL_SECONDS: float = 10.0  # Politeness interval per host
AUTO_PUBLISH_DETECTED_CHANGES: bool = False  # Candidate versions require admin review by default

DEFAULT_REMINDER_LEAD_DAYS: list[int] = [14, 7, 1]
APP_TIMEZONE: str = "Asia/Dhaka"

ASSISTANT_BURST_LIMIT_PER_MINUTE: int = 10
ASSISTANT_RETRIEVAL_TOP_K: int = 3
ASSISTANT_DISTANCE_THRESHOLD: float = 0.85

API_KEY_RATE_LIMIT_PER_MINUTE: int = 60
API_KEY_MAX_ACTIVE_PER_WORKSPACE: int = 3

ADJUSTED_SCORE_SEVERITY_WEIGHTS: dict[str, float] = {
    "high": 1.0,
    "medium": 0.5,
    "low": 0.2,
}

# ---------------------------------------------------------------------------
# Feature Options per Level
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AssistantOptions:
    """Derives grounded context and persistence constraints based on ai_assistant level."""

    level: str  # "off", "limited", "on"
    ground_in_workspace_sop: bool = False
    ground_in_past_analyses: bool = False
    max_turns: int = 2
    max_answer_length: int = 500
    persist_threads: bool = False

    @classmethod
    def from_level(cls, level: str) -> AssistantOptions:
        if level == "on":
            return cls(
                level="on",
                ground_in_workspace_sop=True,
                ground_in_past_analyses=True,
                max_turns=10,
                max_answer_length=2000,
                persist_threads=True,
            )
        elif level == "limited":
            return cls(
                level="limited",
                ground_in_workspace_sop=False,
                ground_in_past_analyses=False,
                max_turns=2,
                max_answer_length=500,
                persist_threads=False,
            )
        return cls(level="off", max_turns=0, max_answer_length=0, persist_threads=False)


@dataclass(frozen=True)
class AlertOptions:
    """Derives notification channels and matching depth from personalized_alerts level."""

    level: str  # "off", "basic", "on"
    in_app: bool = False
    email: bool = False
    semantic_matching: bool = False
    digest_mode: bool = False

    @classmethod
    def from_level(cls, level: str) -> AlertOptions:
        if level == "on":
            return cls(level="on", in_app=True, email=True, semantic_matching=True, digest_mode=True)
        elif level == "basic":
            return cls(level="basic", in_app=True, email=False, semantic_matching=False, digest_mode=False)
        return cls(level="off")


@dataclass(frozen=True)
class ReminderOptions:
    """Derives deadline sources and reminder channels from deadline_reminders level."""

    level: str  # "off", "basic", "on"
    allow_manual_due_dates: bool = False
    allow_regulation_deadlines: bool = False
    in_app_reminders: bool = False
    email_reminders: bool = False
    lead_days: list[int] = field(default_factory=lambda: [14, 7, 1])

    @classmethod
    def from_level(cls, level: str) -> ReminderOptions:
        if level == "on":
            return cls(
                level="on",
                allow_manual_due_dates=True,
                allow_regulation_deadlines=True,
                in_app_reminders=True,
                email_reminders=True,
                lead_days=[14, 7, 1],
            )
        elif level == "basic":
            return cls(
                level="basic",
                allow_manual_due_dates=True,
                allow_regulation_deadlines=False,
                in_app_reminders=True,
                email_reminders=False,
                lead_days=[1],
            )
        return cls(level="off", lead_days=[])


# ---------------------------------------------------------------------------
# Human-in-the-loop Impact Score Adjustment Formula
# ---------------------------------------------------------------------------


def calculate_adjusted_impact_score(
    original_score: int,
    findings: list[dict[str, Any]],
    reviews: dict[str, str],  # finding_id -> status ('approved', 'rejected', 'edited')
) -> int:
    """Calculates adjusted impact score after human-in-the-loop review.

    Formula:
        Weights: high=1.0, medium=0.5, low=0.2
        Total Weight = sum(weights of all original findings)
        Accepted Weight = sum(weights of findings where review != 'rejected')
        Ratio = Accepted Weight / Total Weight
        Adjusted Score = round(original_score * Ratio)

    If all findings are rejected, score is 0. If no findings exist or no rejections, score is unchanged.
    """
    if not findings or original_score <= 0:
        return original_score

    total_weight = 0.0
    accepted_weight = 0.0

    for f in findings:
        fid = f.get("id", "")
        sev = str(f.get("severity", "medium")).lower()
        w = ADJUSTED_SCORE_SEVERITY_WEIGHTS.get(sev, 0.5)
        total_weight += w

        rev_status = reviews.get(fid)
        if rev_status != "rejected":
            accepted_weight += w

    if total_weight <= 0.0:
        return original_score

    ratio = accepted_weight / total_weight
    return int(round(original_score * ratio))


# ---------------------------------------------------------------------------
# Alert Center Tunable Options & Severity Mappings
# ---------------------------------------------------------------------------

ALERT_SEVERITIES = ["info", "low", "medium", "high", "critical"]

# Factors that escalate regulation/law change severity to high or critical
ALERT_SEVERITY_MAPPINGS: dict[str, str] = {
    "criminal_penalty": "critical",
    "license_cancellation": "critical",
    "prosecution": "critical",
    "penalty_increase": "high",
    "fine_increase": "high",
    "deadline_shortened": "high",
    "new_obligation": "high",
    "procedural_change": "medium",
    "clarification": "low",
    "administrative": "info",
}

SMS_COST_ESTIMATES = {
    "non_masking": {
        "bn_per_segment_bdt": 0.35,
        "en_per_segment_bdt": 0.30,
    },
    "masking": {
        "bn_per_segment_bdt": 0.55,
        "en_per_segment_bdt": 0.50,
    },
}

DEFAULT_ALERT_ESCALATION_WINDOWS = {
    "critical_hours": 4,   # 4 business hours
    "high_hours": 24,      # 24 business hours
}

DEFAULT_QUIET_HOURS_START = "22:00"
DEFAULT_QUIET_HOURS_END = "08:00"
DEFAULT_WEEKEND_DAYS = [4, 5]  # Friday (4), Saturday (5) in Python weekday notation
