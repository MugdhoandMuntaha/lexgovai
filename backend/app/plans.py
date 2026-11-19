"""Subscription plans, capability levels, usage metrics and catalog definitions.

Single source of truth for all plan pricing, capability levels and quotas.
Pure typed data, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

PlanId = Literal["free", "starter", "growth", "professional"]
MetricType = Literal["counter", "gauge"]


class MetricKind(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"


@dataclass(frozen=True)
class CapabilityDefinition:
    key: str
    display_name: str
    category: str
    ordered_levels: list[str]
    implemented: bool = True
    description: str = ""

    def level_index(self, level: str) -> int:
        try:
            return self.ordered_levels.index(level)
        except ValueError:
            raise ValueError(f"Unknown level '{level}' for capability '{self.key}'")


@dataclass(frozen=True)
class MetricDefinition:
    key: str
    display_name: str
    kind: MetricKind
    description: str


@dataclass(frozen=True)
class PlanDefinition:
    id: PlanId
    name: str
    price_bdt_monthly: int
    personalization_label: str
    description: str
    capabilities: dict[str, str]  # capability_key -> level_string
    audit_history_days: int
    limits: dict[str, int]  # metric_key -> cap
    badge: str = ""
    is_featured: bool = False


# ---------------------------------------------------------------------------
# Capabilities Catalog
# ---------------------------------------------------------------------------

CAPABILITIES: dict[str, CapabilityDefinition] = {
    # Questionnaire & Starter Guidance
    "launch_questionnaire": CapabilityDefinition(
        key="launch_questionnaire",
        display_name="Start Fresh Questionnaire",
        category="Policy Guidance",
        ordered_levels=["off", "on"],
        implemented=True,
        description="Access to the 9-question guided startup questionnaire.",
    ),
    "policy_suggestions": CapabilityDefinition(
        key="policy_suggestions",
        display_name="Starter Policy Suggestions",
        category="Policy Guidance",
        ordered_levels=["off", "on"],
        implemented=True,
        description="Prioritized list of starter policy categories based on business model.",
    ),
    "industry_guidance": CapabilityDefinition(
        key="industry_guidance",
        display_name="Industry Guidance Depth",
        category="Policy Guidance",
        ordered_levels=["general", "basic", "detailed", "advanced"],
        implemented=True,
        description="Depth of prompt and recommendations tailored to the business sector.",
    ),
    "personalized_checklist": CapabilityDefinition(
        key="personalized_checklist",
        display_name="Personalized Policy Checklist",
        category="Policy Guidance",
        ordered_levels=["off", "on"],
        implemented=True,
        description="Persisted, interactive task list derived from questionnaire answers.",
    ),
    # Monitoring & Alerts (Phase 2 placeholders)
    "ai_assistant": CapabilityDefinition(
        key="ai_assistant",
        display_name="AI Compliance Assistant",
        category="Monitoring & Assistance",
        ordered_levels=["off", "limited", "on"],
        implemented=True,
        description="Interactive conversational compliance assistant.",
    ),
    "regulatory_news": CapabilityDefinition(
        key="regulatory_news",
        display_name="Regulatory News Feed",
        category="Monitoring & Assistance",
        ordered_levels=["off", "on"],
        implemented=True,
        description="Curated regulatory announcements and SRO updates.",
    ),
    "personalized_alerts": CapabilityDefinition(
        key="personalized_alerts",
        display_name="Personalized Alerts",
        category="Monitoring & Assistance",
        ordered_levels=["off", "basic", "on"],
        implemented=True,
        description="Notifications when relevant statutory changes occur.",
    ),
    "automated_monitoring": CapabilityDefinition(
        key="automated_monitoring",
        display_name="Automated Watcher Monitoring",
        category="Monitoring & Assistance",
        ordered_levels=["off", "on"],
        implemented=True,
        description="Continuous automated surveillance of regulatory portals.",
    ),
    # RAG Benchmarking & Analysis Engine
    "impact_analysis": CapabilityDefinition(
        key="impact_analysis",
        display_name="Multi-Agent Impact Analysis",
        category="Analysis & Benchmarking",
        ordered_levels=["off", "basic", "detailed", "advanced"],
        implemented=True,
        description="5-agent pipeline benchmarking corporate SOPs against legal diffs.",
    ),
    "risk_scoring": CapabilityDefinition(
        key="risk_scoring",
        display_name="Mathematical Risk Scoring",
        category="Analysis & Benchmarking",
        ordered_levels=["off", "basic", "on", "advanced"],
        implemented=True,
        description="Severity, confidence, and overall compliance risk score (0-100).",
    ),
    "sop_upload": CapabilityDefinition(
        key="sop_upload",
        display_name="SOP Document Ingestion",
        category="Analysis & Benchmarking",
        ordered_levels=["off", "on"],
        implemented=True,
        description="Upload and vector indexing of corporate SOP documents (PDF/TXT).",
    ),
    "sop_comparison": CapabilityDefinition(
        key="sop_comparison",
        display_name="SOP Clause Comparison",
        category="Analysis & Benchmarking",
        ordered_levels=["off", "limited", "on"],
        implemented=True,
        description="Retrieval and comparison of internal clauses against legal obligations.",
    ),
    "gap_identification": CapabilityDefinition(
        key="gap_identification",
        display_name="Compliance Gap Detection",
        category="Analysis & Benchmarking",
        ordered_levels=["off", "basic", "on", "advanced"],
        implemented=True,
        description="Identifies conflicts, gaps, and outdated references.",
    ),
    "action_plans": CapabilityDefinition(
        key="action_plans",
        display_name="Remediation Action Plans",
        category="Outputs & Remediation",
        ordered_levels=["off", "limited", "on"],
        implemented=True,
        description="Synthesized remediation action plans for regulatory compliance.",
    ),
    "policy_drafts": CapabilityDefinition(
        key="policy_drafts",
        display_name="Redlined Policy Amendments",
        category="Outputs & Remediation",
        ordered_levels=["off", "basic", "on", "advanced"],
        implemented=True,
        description="Draft replacement policy clauses formulated in formal language.",
    ),
    "technical_recommendations": CapabilityDefinition(
        key="technical_recommendations",
        display_name="Technical & Operational Fixes",
        category="Outputs & Remediation",
        ordered_levels=["off", "basic", "advanced"],
        implemented=True,
        description="Concrete operational, software, and administrative action items.",
    ),
    "citations": CapabilityDefinition(
        key="citations",
        display_name="Deterministic Citation Verification",
        category="Outputs & Remediation",
        ordered_levels=["off", "on"],
        implemented=True,
        description="Verbatim string alignment verification with RapidFuzz confidence scores.",
    ),
    "deadline_reminders": CapabilityDefinition(
        key="deadline_reminders",
        display_name="Statutory Deadline Reminders",
        category="Outputs & Remediation",
        ordered_levels=["off", "basic", "on"],
        implemented=True,
        description="Automated calendar notifications before mandatory filing deadlines.",
    ),
    "report_download": CapabilityDefinition(
        key="report_download",
        display_name="Audit Report Export",
        category="Outputs & Remediation",
        ordered_levels=["off", "basic", "on", "advanced"],
        implemented=True,
        description="Export formatted Markdown compliance audit reports.",
    ),
    # Collaboration & Platform
    "team_collaboration": CapabilityDefinition(
        key="team_collaboration",
        display_name="Team Collaboration",
        category="Platform & Governance",
        ordered_levels=["off", "on"],
        implemented=True,
        description="Multi-user workspace access with role-based permissions.",
    ),
    "api_integrations": CapabilityDefinition(
        key="api_integrations",
        display_name="API Access & Webhooks",
        category="Platform & Governance",
        ordered_levels=["off", "limited"],
        implemented=True,
        description="Programmatic API endpoints and webhook notifications.",
    ),
    "priority_support": CapabilityDefinition(
        key="priority_support",
        display_name="Dedicated Support",
        category="Platform & Governance",
        ordered_levels=["off", "on"],
        implemented=True,
        description="Priority SLA with dedicated compliance engineering support.",
    ),
    "document_ocr": CapabilityDefinition(
        key="document_ocr",
        display_name="Scanned Document OCR",
        category="Analysis & Benchmarking",
        ordered_levels=["off", "basic", "on"],
        implemented=True,
        description="Verbatim OCR transcription of scanned image-only PDFs in English and Bengali.",
    ),
    "portal_crawler": CapabilityDefinition(
        key="portal_crawler",
        display_name="JavaScript Portal Web Crawler",
        category="Regulatory Sources",
        ordered_levels=["off", "on"],
        implemented=True,
        description="Headless browser crawling and link discovery for dynamic government portals.",
    ),
    "legal_library": CapabilityDefinition(
        key="legal_library",
        display_name="Bangladesh Legal Library",
        category="Legal Intelligence",
        ordered_levels=["basic", "standard", "full"],
        implemented=True,
        description="Search, browse, AI summaries, section diffs, watchlists, and grounded legal Q&A.",
    ),
    "alert_channels": CapabilityDefinition(
        key="alert_channels",
        display_name="Multi-Channel Alert Center",
        category="Monitoring & Assistance",
        ordered_levels=["in_app", "email_digest", "sms_escalation", "multichannel"],
        implemented=True,
        description="Multi-channel alert routing across in-app, email digests, SMS escalation, and WhatsApp.",
    ),
}

# ---------------------------------------------------------------------------
# Usage Metrics Catalog
# ---------------------------------------------------------------------------

METRICS: dict[str, MetricDefinition] = {
    "general_ai_questions": MetricDefinition(
        key="general_ai_questions",
        display_name="General AI Queries",
        kind=MetricKind.COUNTER,
        description="Monthly conversational and exploratory AI guidance requests.",
    ),
    "detailed_analyses": MetricDefinition(
        key="detailed_analyses",
        display_name="Detailed Compliance Analyses",
        kind=MetricKind.COUNTER,
        description="Full 5-agent RAG pipeline analysis runs per month.",
    ),
    "sop_documents": MetricDefinition(
        key="sop_documents",
        display_name="Indexed SOP Documents",
        kind=MetricKind.COUNTER,
        description="Monthly uploaded or generated SOP documents indexed into vector storage.",
    ),
    "ocr_pages": MetricDefinition(
        key="ocr_pages",
        display_name="Scanned Document OCR Pages",
        kind=MetricKind.COUNTER,
        description="Scanned gazette and SOP pages transcribed via OCR.",
    ),
    "sms_alerts": MetricDefinition(
        key="sms_alerts",
        display_name="Compliance SMS Alerts",
        kind=MetricKind.COUNTER,
        description="Monthly transactional SMS alerts dispatched via Bangladesh bulk gateways.",
    ),
    "whatsapp_alerts": MetricDefinition(
        key="whatsapp_alerts",
        display_name="WhatsApp Compliance Alerts",
        kind=MetricKind.COUNTER,
        description="Monthly WhatsApp compliance alerts dispatched via Meta Cloud API.",
    ),
    "monitored_sources": MetricDefinition(
        key="monitored_sources",
        display_name="Monitored Regulatory Sources",
        kind=MetricKind.GAUGE,
        description="Active gazettes, SROs, and regulatory feeds under watch.",
    ),
    "business_profiles": MetricDefinition(
        key="business_profiles",
        display_name="Business Profiles",
        kind=MetricKind.GAUGE,
        description="Registered company entities and operational profiles.",
    ),
    "team_members": MetricDefinition(
        key="team_members",
        display_name="Workspace Members",
        kind=MetricKind.GAUGE,
        description="Maximum user seats enabled in this workspace.",
    ),
}

# ---------------------------------------------------------------------------
# Plans Catalog
# ---------------------------------------------------------------------------

PLANS: dict[PlanId, PlanDefinition] = {
    "free": PlanDefinition(
        id="free",
        name="Free",
        price_bdt_monthly=0,
        personalization_label="General, questionnaire-based",
        description="Essential baseline compliance roadmap and Start Fresh questionnaire for early-stage ventures.",
        badge="Community",
        capabilities={
            "launch_questionnaire": "on",
            "policy_suggestions": "on",
            "industry_guidance": "general",
            "personalized_checklist": "off",
            "ai_assistant": "limited",
            "regulatory_news": "on",
            "personalized_alerts": "off",
            "automated_monitoring": "off",
            "impact_analysis": "off",
            "risk_scoring": "off",
            "sop_upload": "off",
            "sop_comparison": "off",
            "gap_identification": "off",
            "action_plans": "off",
            "policy_drafts": "off",
            "technical_recommendations": "off",
            "citations": "on",
            "deadline_reminders": "off",
            "report_download": "off",
            "team_collaboration": "off",
            "api_integrations": "off",
            "priority_support": "off",
            "document_ocr": "off",
            "portal_crawler": "off",
            "legal_library": "basic",
            "alert_channels": "in_app",
        },
        audit_history_days=0,
        limits={
            "general_ai_questions": 5,
            "detailed_analyses": 0,
            "sop_documents": 0,
            "ocr_pages": 0,
            "sms_alerts": 0,
            "whatsapp_alerts": 0,
            "monitored_sources": 0,
            "business_profiles": 1,
            "team_members": 1,
        },
    ),
    "starter": PlanDefinition(
        id="starter",
        name="Starter",
        price_bdt_monthly=999,
        personalization_label="Basic company-specific",
        description="Designed for operating micro-enterprises and small teams needing basic SOP audits and checklists.",
        badge="Popular for Micro",
        capabilities={
            "launch_questionnaire": "on",
            "policy_suggestions": "on",
            "industry_guidance": "basic",
            "personalized_checklist": "on",
            "ai_assistant": "on",
            "regulatory_news": "on",
            "personalized_alerts": "basic",
            "automated_monitoring": "off",
            "impact_analysis": "basic",
            "risk_scoring": "basic",
            "sop_upload": "on",
            "sop_comparison": "limited",
            "gap_identification": "basic",
            "action_plans": "limited",
            "policy_drafts": "basic",
            "technical_recommendations": "off",
            "citations": "on",
            "deadline_reminders": "basic",
            "report_download": "basic",
            "team_collaboration": "off",
            "api_integrations": "off",
            "priority_support": "off",
            "document_ocr": "basic",
            "portal_crawler": "off",
            "legal_library": "standard",
            "alert_channels": "email_digest",
        },
        audit_history_days=30,
        limits={
            "general_ai_questions": 30,
            "detailed_analyses": 10,
            "sop_documents": 5,
            "ocr_pages": 20,
            "sms_alerts": 0,
            "whatsapp_alerts": 0,
            "monitored_sources": 1,
            "business_profiles": 1,
            "team_members": 1,
        },
    ),
    "growth": PlanDefinition(
        id="growth",
        name="Growth",
        price_bdt_monthly=2999,
        personalization_label="Document-based",
        description="Full multi-agent RAG benchmarking, redlined policy rewrites, and 1-year compliance audit retention.",
        badge="Best for SMEs",
        is_featured=True,
        capabilities={
            "launch_questionnaire": "on",
            "policy_suggestions": "on",
            "industry_guidance": "detailed",
            "personalized_checklist": "on",
            "ai_assistant": "on",
            "regulatory_news": "on",
            "personalized_alerts": "on",
            "automated_monitoring": "on",
            "impact_analysis": "detailed",
            "risk_scoring": "on",
            "sop_upload": "on",
            "sop_comparison": "on",
            "gap_identification": "on",
            "action_plans": "on",
            "policy_drafts": "on",
            "technical_recommendations": "basic",
            "citations": "on",
            "deadline_reminders": "on",
            "report_download": "on",
            "team_collaboration": "on",
            "api_integrations": "off",
            "priority_support": "off",
            "document_ocr": "on",
            "portal_crawler": "on",
            "legal_library": "standard",
            "alert_channels": "sms_escalation",
        },
        audit_history_days=365,
        limits={
            "general_ai_questions": 100,
            "detailed_analyses": 50,
            "sop_documents": 25,
            "ocr_pages": 100,
            "sms_alerts": 100,
            "whatsapp_alerts": 0,
            "monitored_sources": 2,
            "business_profiles": 1,
            "team_members": 3,
        },
    ),
    "professional": PlanDefinition(
        id="professional",
        name="Professional",
        price_bdt_monthly=7999,
        personalization_label="Continuous and advanced",
        description="Advanced compliance engineering, unlimited finding depth, comprehensive operational fixes, and multi-profile support.",
        badge="Enterprise",
        capabilities={
            "launch_questionnaire": "on",
            "policy_suggestions": "on",
            "industry_guidance": "advanced",
            "personalized_checklist": "on",
            "ai_assistant": "on",
            "regulatory_news": "on",
            "personalized_alerts": "on",
            "automated_monitoring": "on",
            "impact_analysis": "advanced",
            "risk_scoring": "advanced",
            "sop_upload": "on",
            "sop_comparison": "on",
            "gap_identification": "advanced",
            "action_plans": "on",
            "policy_drafts": "advanced",
            "technical_recommendations": "advanced",
            "citations": "on",
            "deadline_reminders": "on",
            "report_download": "advanced",
            "team_collaboration": "on",
            "api_integrations": "limited",
            "priority_support": "on",
            "document_ocr": "on",
            "portal_crawler": "on",
            "legal_library": "full",
            "alert_channels": "multichannel",
        },
        audit_history_days=1095,
        limits={
            "general_ai_questions": 300,
            "detailed_analyses": 200,
            "sop_documents": 100,
            "ocr_pages": 500,
            "sms_alerts": 500,
            "whatsapp_alerts": 500,
            "monitored_sources": 5,
            "business_profiles": 2,
            "team_members": 10,
        },
    ),
}

ORDERED_PLANS: list[PlanId] = ["free", "starter", "growth", "professional"]


def get_plan(plan_id: str) -> PlanDefinition:
    if plan_id not in PLANS:
        raise ValueError(f"Unknown plan: '{plan_id}'")
    return PLANS[plan_id]  # type: ignore[index]


def is_capability_at_least(capability_key: str, current_level: str, required_level: str) -> bool:
    cap = CAPABILITIES.get(capability_key)
    if not cap:
        raise ValueError(f"Unknown capability '{capability_key}'")
    return cap.level_index(current_level) >= cap.level_index(required_level)


def next_plan_with_capability(capability_key: str, required_level: str) -> PlanId | None:
    """Finds the lowest tier plan that satisfies the required capability level."""
    for pid in ORDERED_PLANS:
        plan = PLANS[pid]
        current = plan.capabilities.get(capability_key, "off")
        if is_capability_at_least(capability_key, current, required_level):
            return pid
    return None


def next_plan_with_higher_quota(metric: str, current_plan: PlanId) -> PlanId | None:
    current_limit = PLANS[current_plan].limits.get(metric, 0)
    for pid in ORDERED_PLANS:
        if PLANS[pid].limits.get(metric, 0) > current_limit:
            return pid
    return None

