"""API request/response models plus the structured-output schemas the LLM agents must return."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Auth, Workspaces, Subscriptions & Metering Models
# ---------------------------------------------------------------------------


class SignupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=150)
    password: str = Field(min_length=10, max_length=100)
    full_name: str | None = Field(default=None, max_length=100)
    company_name: str | None = Field(default=None, max_length=150)


class LoginRequest(BaseModel):
    email: str
    password: str


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=150)


class ForgotPasswordResponse(BaseModel):
    ok: bool = True
    message: str
    reset_token: str | None = None


class ResetPasswordVerifyResponse(BaseModel):
    valid: bool
    email: str


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10)
    new_password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=1, max_length=128)


class PasswordActionResponse(BaseModel):
    ok: bool = True
    message: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str | None
    created_at: str
    is_platform_admin: bool = False


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    role: str
    created_at: str


class SubscriptionResponse(BaseModel):
    id: str
    plan_id: str
    status: str
    period_start: str
    period_end: str
    cancel_at_period_end: bool


class AuthResponse(BaseModel):
    user: UserResponse
    workspace: WorkspaceResponse
    subscription: SubscriptionResponse


class CapabilityDetail(BaseModel):
    key: str
    display_name: str
    category: str
    current_level: str
    implemented: bool
    description: str


class UsageMeter(BaseModel):
    metric: str
    display_name: str
    kind: str
    description: str
    used: int
    limit: int
    percent: float
    resets_at: str


class MeResponse(BaseModel):
    user: UserResponse
    workspace: WorkspaceResponse
    subscription: SubscriptionResponse
    plan_id: str
    capabilities: dict[str, CapabilityDetail]
    usage: list[UsageMeter]
    llm_configured: bool = False


class CheckoutRequest(BaseModel):
    plan_id: str | None = None
    target_plan_id: str | None = None
    return_url: str = "/account"


class CheckoutResponse(BaseModel):
    session_id: str
    checkout_url: str
    plan_id: str
    amount_bdt: int
    status: str


class SubscriptionChangeRequest(BaseModel):
    plan_id: str


class ChecklistItemResponse(BaseModel):
    id: str
    company_profile_id: str
    title: str
    tier: str
    reason: str
    done: bool
    done_at: str | None = None
    created_at: str


class ChecklistUpdateRequest(BaseModel):
    done: bool


class FeatureGatedErrorDetail(BaseModel):
    code: Literal["FEATURE_NOT_IN_PLAN"] = "FEATURE_NOT_IN_PLAN"
    detail: str
    capability: str
    required_plan: str
    current_plan: str


class QuotaExceededErrorDetail(BaseModel):
    code: Literal["QUOTA_EXCEEDED"] = "QUOTA_EXCEEDED"
    detail: str
    metric: str
    limit: int
    used: int
    resets_at: str
    upgrade_to: str | None = None


# ---------------------------------------------------------------------------
# API models (mirrored in frontend/src/lib/types.ts)
# ---------------------------------------------------------------------------

IssueType = Literal["gap", "conflict", "outdated_reference"]
Severity = Literal["low", "medium", "high"]
Urgency = Literal["low", "medium", "high", "critical"]


class CompanyProfileCreate(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    industry: str = Field(min_length=1, max_length=200)
    country: str = Field(default="Bangladesh", max_length=100)
    description: str | None = Field(default=None, max_length=2000)


class CompanyProfile(CompanyProfileCreate):
    id: str
    created_at: str


class DocumentUploadResponse(BaseModel):
    document_id: str
    company_profile_id: str
    filename: str
    chunk_count: int
    sections: list[str]
    extraction_method: str = "text"
    ocr_confidence: float | None = None
    ocr_notes: str | None = None


class SampleDocumentRequest(BaseModel):
    company_profile_id: str


class DiffLine(BaseModel):
    op: Literal["equal", "removed", "added"]
    text: str


class RegulationChangeResponse(BaseModel):
    regulation_id: str
    title: str
    version_hash: str
    change_summary: str
    changed_clauses: list[str]
    obligations: list[str]
    change_type: str
    before_title: str
    after_title: str
    before_text: str
    after_text: str
    diff: list[DiffLine]


class AnalyzeRequest(BaseModel):
    company_profile_id: str
    document_id: str
    regulation_id: str | None = None


class CitationRef(BaseModel):
    source: str
    section: str
    text_snippet: str
    is_ocr: bool = False
    ocr_method: str | None = None


class FindingDetail(BaseModel):
    id: str
    issue: str
    issue_type: IssueType
    severity: Severity
    explanation: str
    citation: CitationRef
    confidence: float
    flagged_for_review: bool
    is_ocr: bool = False


class ActionPlanResponse(BaseModel):
    id: str
    company: str
    regulation: str
    change_summary: str
    impact_score: int
    urgency: Urgency
    findings: list[FindingDetail]
    policy_draft: list[str]
    technical_fixes: list[str]
    disclaimer: str
    document_name: str
    regulation_version_hash: str
    model: str
    created_at: str
    plan_tier: str | None = None
    locked: list[dict[str, Any]] = Field(default_factory=list)
    risk_summary: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str = "ok"


# ---------------------------------------------------------------------------
# Starter Guide Models (mirroring Start Fresh wizard)
# ---------------------------------------------------------------------------

StageChoice = Literal["exploring_idea", "planning_launch", "recently_started", "operating"]
SectorChoice = Literal[
    "retail",
    "ecommerce",
    "software_it",
    "food_restaurant",
    "manufacturing",
    "professional_services",
    "financial_fintech",
    "other",
]
JurisdictionChoice = Literal["bangladesh", "international", "other_country"]
CustomersChoice = Literal["b2c", "b2b", "both", "undecided"]
DeliveryChoice = Literal["physical", "online", "both", "undecided"]
HiringChoice = Literal["solo", "small_team", "growing_team", "unsure"]
CollectsDataChoice = Literal["yes", "no", "unsure"]
PaymentsChoice = Literal["cash", "digital", "both", "undecided"]
FirstHelpChoice = Literal[
    "which_policies",
    "registration_basics",
    "employee_policies",
    "customer_data_policies",
    "general_guide",
]

PolicyTier = Literal["start_now", "soon", "later"]


class StarterAnswers(BaseModel):
    stage: StageChoice
    sector: SectorChoice
    jurisdiction: JurisdictionChoice
    customers: CustomersChoice
    delivery: DeliveryChoice
    hiring: HiringChoice
    collects_data: CollectsDataChoice
    payments: PaymentsChoice
    first_help: FirstHelpChoice


class StarterGuideRequest(StarterAnswers):
    pass


class StarterPolicyItem(BaseModel):
    id: str
    title: str
    tier: PolicyTier
    reason: str
    covers: str
    include_points: list[str]


class StarterGuideResponse(BaseModel):
    summary: str
    jurisdiction_notice: str | None = None
    policies: list[StarterPolicyItem]
    disclaimer: str
    model: str


class StarterSOPRequest(StarterAnswers):
    company_name: str = Field(default="My Business", max_length=200)


class StarterSOPResponse(DocumentUploadResponse):
    pass


# ---------------------------------------------------------------------------
# LLM structured-output schemas. Kept to plain strings/ints so they convert cleanly
# into Gemini response schemas; values are normalised in code afterwards.
# ---------------------------------------------------------------------------


class WatcherLLMOutput(BaseModel):
    title: str = Field(description="Short title of the regulation, e.g. 'NBR VAT SRO Clause 4.2'.")
    change_summary: str = Field(description="2-4 sentence plain-language summary of what changed and why it matters.")
    change_type: str = Field(description="One of: amendment, new_obligation, repeal, clarification.")
    changed_clauses: list[str] = Field(description="One entry per changed clause: what it said before vs now.")
    obligations: list[str] = Field(
        description="Concrete obligations a business must now satisfy, each self-contained and testable."
    )


class FindingLLMOutput(BaseModel):
    issue: str = Field(description="Short headline of the compliance problem.")
    issue_type: str = Field(description="One of: gap, conflict, outdated_reference.")
    severity: str = Field(description="One of: low, medium, high.")
    explanation: str = Field(description="Why the SOP fails the new regulation and the business risk.")
    citation_source: str = Field(description="'sop' if quoting the SOP excerpt, 'regulation' if quoting the regulation.")
    citation_section: str = Field(description="Section label of the quoted text exactly as given in the context.")
    citation_text_snippet: str = Field(description="VERBATIM quote (one or two sentences) copied from the cited text.")


class AnalyzerLLMOutput(BaseModel):
    impact_score: int = Field(description="0-100 overall compliance risk if nothing changes.")
    urgency: str = Field(description="One of: low, medium, high, critical.")
    findings: list[FindingLLMOutput]


class GeneratorLLMOutput(BaseModel):
    policy_draft: list[str] = Field(
        description="Replacement SOP clause text, one complete clause per entry, ready to paste into the SOP."
    )
    technical_fixes: list[str] = Field(
        description="Concrete operational / system changes (owners, reminders, portal settings), one per entry."
    )


class StarterPolicyLLMContent(BaseModel):
    category_id: str = Field(description="Must match exactly the provided category ID.")
    covers: str = Field(description="1-2 sentences summarizing what this policy governs.")
    include_points: list[str] = Field(
        description="3 to 6 broad good-practice bullet points to include in this policy."
    )


class StarterGuideLLMOutput(BaseModel):
    summary: str = Field(
        description="2-4 sentence executive overview tailored to the business's sector and stage."
    )
    policies: list[StarterPolicyLLMContent]


# ===========================================================================
# Bangladesh Legal Library Schemas
# ===========================================================================


class LawSourceResponse(BaseModel):
    id: str
    name: str
    base_url: str
    source_type: str
    enabled: bool
    crawl_config: dict[str, Any] = Field(default_factory=dict)
    rate_limit: float = 1.0
    last_run_at: str | None = None
    last_status: str | None = None


class LawSummaryResponse(BaseModel):
    id: str
    canonical_title_en: str
    canonical_title_bn: str | None = None
    act_number: str | None = None
    year: int | None = None
    law_type: str
    issuing_body: str
    language_available: str
    status: str
    status_confidence: float
    domain_tags: list[str] = Field(default_factory=list)
    summary_ai: str | None = None
    summary_verified: bool = False
    publish_state: str
    created_at: str


class LawSectionResponse(BaseModel):
    id: str
    law_version_id: str
    parent_id: str | None = None
    level: str
    number_label: str
    heading: str | None = None
    text: str
    order_index: int = 0


class LawVersionResponse(BaseModel):
    id: str
    law_id: str
    version_hash: str
    source_url: str | None = None
    fetched_at: str
    extraction_method: str
    ocr_quality: float | None = None
    is_current: bool = True


class LawRelationResponse(BaseModel):
    id: str
    from_law_id: str
    to_law_id: str
    relation: str
    to_law_title: str | None = None
    to_law_year: int | None = None
    from_law_title: str | None = None
    from_law_year: int | None = None


class LawDetailResponse(BaseModel):
    law: LawSummaryResponse
    current_version: LawVersionResponse | None = None
    versions: list[LawVersionResponse] = Field(default_factory=list)
    relations: list[LawRelationResponse] = Field(default_factory=list)
    is_watched: bool = False


class LawSearchHit(BaseModel):
    law_id: str
    version_id: str
    section_id: str
    law_title_en: str
    law_title_bn: str | None = None
    law_type: str
    year: int | None = None
    number_label: str
    heading: str | None = None
    snippet: str
    match_source: str  # 'fts', 'vector', 'hybrid'
    score: float


class LawCoverageResponse(BaseModel):
    published_laws_count: int
    pending_review_count: int
    total_sources_count: int
    enabled_sources_count: int
    failed_sources_count: int
    by_law_type: dict[str, int]
    by_issuing_body: dict[str, int]
    recent_runs: list[dict[str, Any]]
    sources: list[dict[str, Any]]


class LawAskCitation(BaseModel):
    law_id: str
    law_title: str
    section_id: str
    section_number: str
    quote: str
    similarity_score: float = 1.0


class LawAskResponse(BaseModel):
    answer: str
    citations: list[LawAskCitation] = Field(default_factory=list)
    is_in_scope: bool = True



