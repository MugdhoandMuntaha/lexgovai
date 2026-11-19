"""Entitlement engine: resolves workspace capability levels, usage limits, and AnalysisOptions.

Single source of truth for runtime permissions. Enforced server-side.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from .db import Database, LEGACY_WORKSPACE_ID
from .plans import (
    CAPABILITIES,
    PLANS,
    PlanDefinition,
    PlanId,
    get_plan,
    is_capability_at_least,
    next_plan_with_capability,
)

# ---------------------------------------------------------------------------
# Tunable Product Assumptions for Tiered Analysis
# ---------------------------------------------------------------------------
# Assumption 1: Starter provides top 5 findings, Growth 15, Professional unlimited.
MAX_FINDINGS_BY_PLAN: dict[PlanId, int | None] = {
    "free": 0,
    "starter": 5,
    "growth": 15,
    "professional": None,
}

# Assumption 2: Action plan clauses subsetting
POLICY_DRAFTS_LIMIT_BY_LEVEL: dict[str, int | None] = {
    "off": 0,
    "basic": 3,
    "on": None,
    "advanced": None,
}

# Assumption 3: Technical operational fixes subsetting
TECHNICAL_FIXES_LIMIT_BY_LEVEL: dict[str, int | None] = {
    "off": 0,
    "basic": 5,
    "advanced": None,
}


@dataclass(frozen=True)
class LockedSection:
    section: str
    required_plan: str
    hidden_count: int


@dataclass
class AnalysisOptions:
    """Controls output post-processing based on workspace entitlements.

    Lower tiers receive a strict subset of Professional output, never degraded
    or altered content.
    """

    plan_id: PlanId
    max_findings: int | None
    action_plans_level: str
    policy_drafts_level: str
    technical_fixes_level: str
    risk_scoring_level: str
    report_download_level: str

    def apply(self, full_plan: dict[str, Any]) -> dict[str, Any]:
        """Applies tier limits to a completed action plan, recording locked sections."""
        plan = dict(full_plan)
        locked: list[dict[str, Any]] = []

        # 1. Findings capping (applied post-Critic so all remaining are verified)
        all_findings = list(plan.get("findings", []))
        if self.max_findings is not None and len(all_findings) > self.max_findings:
            plan["findings"] = all_findings[: self.max_findings]
            next_plan = "growth" if self.plan_id == "starter" else "professional"
            locked.append({
                "section": "findings",
                "required_plan": next_plan,
                "hidden_count": len(all_findings) - self.max_findings,
            })
        else:
            plan["findings"] = all_findings

        # 2. Policy drafts subsetting
        all_drafts = list(plan.get("policy_draft", []))
        draft_limit = POLICY_DRAFTS_LIMIT_BY_LEVEL.get(self.policy_drafts_level, 0)
        if draft_limit is not None and len(all_drafts) > draft_limit:
            plan["policy_draft"] = all_drafts[:draft_limit]
            next_plan = "growth" if self.policy_drafts_level == "basic" else "professional"
            if len(all_drafts) - draft_limit > 0:
                locked.append({
                    "section": "policy_draft",
                    "required_plan": next_plan,
                    "hidden_count": len(all_drafts) - draft_limit,
                })
        else:
            plan["policy_draft"] = all_drafts

        # 3. Technical fixes subsetting
        all_fixes = list(plan.get("technical_fixes", []))
        fix_limit = TECHNICAL_FIXES_LIMIT_BY_LEVEL.get(self.technical_fixes_level, 0)
        if fix_limit is not None and len(all_fixes) > fix_limit:
            plan["technical_fixes"] = all_fixes[:fix_limit]
            next_plan = "growth" if self.technical_fixes_level == "off" else "professional"
            if len(all_fixes) - fix_limit > 0:
                locked.append({
                    "section": "technical_fixes",
                    "required_plan": next_plan,
                    "hidden_count": len(all_fixes) - fix_limit,
                })
        else:
            plan["technical_fixes"] = all_fixes

        # 4. Risk scoring detail
        if self.risk_scoring_level == "basic":
            # Strip deep metrics in basic mode
            plan["risk_summary"] = {"urgency": plan.get("urgency"), "impact_score": plan.get("impact_score")}
        elif self.risk_scoring_level in ("on", "advanced"):
            # Full breakdown by issue_type and severity
            breakdown: dict[str, int] = {}
            for f in all_findings:
                k = f.get("issue_type", "gap")
                breakdown[k] = breakdown.get(k, 0) + 1
            plan["risk_summary"] = {
                "urgency": plan.get("urgency"),
                "impact_score": plan.get("impact_score"),
                "total_findings": len(all_findings),
                "breakdown": breakdown,
                "flagged_for_review_count": sum(1 for f in all_findings if f.get("flagged_for_review")),
            }

        plan["locked"] = locked
        plan["plan_tier"] = self.plan_id
        return plan


class EntitlementService:
    def __init__(self, db: Database):
        self._db = db

    def get_workspace_plan_id(self, workspace_id: str) -> PlanId:
        if workspace_id == LEGACY_WORKSPACE_ID:
            return "professional"
        sub = self._db.get_subscription(workspace_id)
        if not sub or sub.get("status") not in ("active", "trialing", "past_due"):
            return "free"
        plan_id = sub.get("plan_id", "free")
        return plan_id if plan_id in PLANS else "free"

    def get_workspace_plan(self, workspace_id: str) -> PlanDefinition:
        pid = self.get_workspace_plan_id(workspace_id)
        return get_plan(pid)

    def level(self, workspace_id: str, capability_key: str) -> str:
        plan = self.get_workspace_plan(workspace_id)
        return plan.capabilities.get(capability_key, "off")

    def has_at_least(self, workspace_id: str, capability_key: str, required_level: str) -> bool:
        current = self.level(workspace_id, capability_key)
        return is_capability_at_least(capability_key, current, required_level)

    def limit(self, workspace_id: str, metric_key: str) -> int:
        plan = self.get_workspace_plan(workspace_id)
        return plan.limits.get(metric_key, 0)

    def retention_cutoff(self, workspace_id: str) -> str | None:
        """Returns ISO cutoff timestamp.

        Records created before this timestamp are hidden.
        """
        plan = self.get_workspace_plan(workspace_id)
        days = plan.audit_history_days
        if days <= 0:
            # 0 days retention = only immediate/current session plans visible
            # Cutoff is 1 hour ago to allow the user to view the plan they just generated
            cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
            return cutoff.isoformat(timespec="seconds")
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return cutoff.isoformat(timespec="seconds")

    def derive_analysis_options(self, workspace_id: str) -> AnalysisOptions:
        plan = self.get_workspace_plan(workspace_id)
        return AnalysisOptions(
            plan_id=plan.id,
            max_findings=MAX_FINDINGS_BY_PLAN.get(plan.id),
            action_plans_level=plan.capabilities.get("action_plans", "off"),
            policy_drafts_level=plan.capabilities.get("policy_drafts", "off"),
            technical_fixes_level=plan.capabilities.get("technical_recommendations", "off"),
            risk_scoring_level=plan.capabilities.get("risk_scoring", "off"),
            report_download_level=plan.capabilities.get("report_download", "off"),
        )

