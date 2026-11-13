export interface CitationRef {
  source: string;
  section: string;
  text_snippet: string;
  is_ocr?: boolean;
  ocr_method?: string | null;
}

export interface FindingDetail {
  id: string;
  issue: string;
  issue_type: 'gap' | 'conflict' | 'outdated_reference';
  severity: 'low' | 'medium' | 'high';
  explanation: string;
  citation: CitationRef;
  confidence: number;
  flagged_for_review: boolean;
  is_ocr?: boolean;
}

export interface LockedSection {
  section: string;
  required_plan: string;
  hidden_count: number;
}

export interface RiskSummary {
  breakdown?: Record<string, number>;
  narrative?: string;
  total?: number;
}

export interface ActionPlanResponse {
  id: string;
  company: string;
  regulation: string;
  change_summary: string;
  impact_score: number;
  urgency: 'low' | 'medium' | 'high' | 'critical';
  findings: FindingDetail[];
  policy_draft: string[];
  technical_fixes: string[];
  disclaimer: string;
  document_name: string;
  regulation_version_hash: string;
  model: string;
  created_at: string;
  plan_tier?: string;
  locked?: LockedSection[];
  risk_summary?: RiskSummary;
}

export interface CompanyProfile {
  id: string;
  company_name: string;
  industry: string;
  country: string;
  description?: string | null;
  created_at: string;
}

export interface DocumentUploadResponse {
  document_id: string;
  company_profile_id: string;
  filename: string;
  chunk_count: number;
  sections: string[];
}

export interface DiffLine {
  op: 'equal' | 'removed' | 'added';
  text: string;
}

/** Regulation texts + deterministic diff (available without an LLM). */
export interface RegulationText {
  regulation_id: string;
  version_hash: string;
  before_title: string;
  after_title: string;
  before_text: string;
  after_text: string;
  diff: DiffLine[];
}

/** Full Watcher agent output. */
export interface RegulationChangeResponse extends RegulationText {
  title: string;
  change_summary: string;
  changed_clauses: string[];
  obligations: string[];
  change_type: string;
}

export interface RegulationSummary {
  id: string;
  title: string;
  country: string;
  sector?: string | null;
  description?: string | null;
  created_at: string;
  version_count: number;
  latest_version?: string | null;
  latest_summary?: string | null;
  obligations_count: number;
}

export interface RegulationDetailResponse {
  regulation: {
    id: string;
    title: string;
    country: string;
    sector?: string | null;
    description?: string | null;
    created_at: string;
  };
  versions: {
    id: string;
    regulation_id: string;
    version_label: string;
    text: string;
    content_hash: string;
    status: string;
    created_at: string;
  }[];
  pair: RegulationText;
  latest_change?: {
    id: string;
    summary: string;
    change_type: string;
    obligations: string;
    tags: string;
    detected_at: string;
  } | null;
}

export interface HealthResponse {
  status: string;
  llm_configured: boolean;
  model: string;
  embedding_model: string;
}

export type PipelineEvent =
  | { type: 'agent_started'; agent: number; name: string }
  | { type: 'agent_completed'; agent: number; name: string; detail: string; duration_ms: number }
  | { type: 'completed'; plan_id: string; plan: ActionPlanResponse; duration_ms: number }
  | { type: 'error'; agent: number | null; message: string };

// ---------------------------------------------------------------------------
// Starter Guide & Start Fresh Types
// ---------------------------------------------------------------------------

export type StageChoice = 'exploring_idea' | 'planning_launch' | 'recently_started' | 'operating';
export type SectorChoice =
  | 'retail'
  | 'ecommerce'
  | 'software_it'
  | 'food_restaurant'
  | 'manufacturing'
  | 'professional_services'
  | 'financial_fintech'
  | 'other';
export type JurisdictionChoice = 'bangladesh' | 'international' | 'other_country';
export type CustomersChoice = 'b2c' | 'b2b' | 'both' | 'undecided';
export type DeliveryChoice = 'physical' | 'online' | 'both' | 'undecided';
export type HiringChoice = 'solo' | 'small_team' | 'growing_team' | 'unsure';
export type CollectsDataChoice = 'yes' | 'no' | 'unsure';
export type PaymentsChoice = 'cash' | 'digital' | 'both' | 'undecided';
export type FirstHelpChoice =
  | 'which_policies'
  | 'registration_basics'
  | 'employee_policies'
  | 'customer_data_policies'
  | 'general_guide';

export type PolicyTier = 'start_now' | 'soon' | 'later';

export interface StarterAnswers {
  stage: StageChoice;
  sector: SectorChoice;
  jurisdiction: JurisdictionChoice;
  customers: CustomersChoice;
  delivery: DeliveryChoice;
  hiring: HiringChoice;
  collects_data: CollectsDataChoice;
  payments: PaymentsChoice;
  first_help: FirstHelpChoice;
}

export interface StarterPolicyItem {
  id: string;
  title: string;
  tier: PolicyTier;
  reason: string;
  covers: string;
  include_points: string[];
}

export interface StarterGuideResponse {
  summary: string;
  jurisdiction_notice: string | null;
  policies: StarterPolicyItem[];
  disclaimer: string;
  model: string;
}

export interface StarterSOPRequest extends StarterAnswers {
  company_name?: string;
}

// ---------------------------------------------------------------------------
// Auth, Workspaces, Subscriptions & Metering
// ---------------------------------------------------------------------------

export type PlanId = 'free' | 'starter' | 'growth' | 'professional';

export interface User {
  id: string;
  email: string;
  full_name?: string | null;
  created_at: string;
  is_platform_admin?: boolean;
}

export interface NewsItem {
  id: string;
  title: string;
  content: string;
  sector?: string | null;
  jurisdiction: string;
  published_at: string;
  source_url?: string | null;
  regulation_id?: string | null;
  created_at: string;
}

export interface NotificationItem {
  id: string;
  workspace_id: string;
  user_id: string;
  title: string;
  body: string;
  link: string;
  channel: string;
  read_at?: string | null;
  created_at: string;
}

export interface QueueLease {
  id: string;
  type: string;
  run_at: string;
  lease_until: string;
  attempts: number;
}

export interface QueueStats {
  pending_count: number;
  running_count: number;
  completed_count: number;
  failed_count: number;
  dead_letter_count: number;
  running_leases: QueueLease[];
  last_run_by_type: Record<string, string>;
}

export interface RegulationVersionAdmin {
  id: string;
  regulation_id: string;
  regulation_title: string;
  version_label: string;
  text: string;
  status: string;
  created_at: string;
}

export interface RegulationSourceAdmin {
  id: string;
  regulation_id: string;
  name: string;
  kind: string;
  url?: string | null;
  poll_interval: number;
  enabled: boolean;
  last_checked?: string | null;
  last_error?: string | null;
}

export interface SupportTicketAdmin {
  id: string;
  workspace_id: string;
  workspace_name?: string;
  user_id: string;
  user_email?: string;
  subject: string;
  message: string;
  priority: 'urgent' | 'priority' | 'standard';
  status: 'open' | 'in_progress' | 'resolved' | 'closed';
  created_at: string;
}

export interface MonitoredSourceItem {
  id: string;
  name: string;
  regulation_id: string;
  regulation_title: string;
  sector: string;
  jurisdiction: string;
  kind: string;
  url?: string | null;
  enabled: boolean;
  last_checked?: string | null;
  last_error?: string | null;
  status: 'healthy' | 'failing';
}

export interface MonitoredSubscriptionItem {
  id: string;
  regulation_id: string;
  title: string;
  sector: string;
  country: string;
  description?: string | null;
  created_at: string;
}

export interface AssistantCitationItem {
  source: string;
  section: string;
  quote: string;
  confidence: number;
  is_verified: boolean;
}

export interface AssistantMessageItem {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: AssistantCitationItem[];
  created_at?: string;
}

export interface AssistantThreadItem {
  id: string;
  title: string;
  created_at: string;
}

export interface Workspace {
  id: string;
  name: string;
  role?: string;
  created_at: string;
}

export interface CapabilityDetailItem {
  key: string;
  display_name: string;
  category: string;
  current_level: string;
  implemented: boolean;
  description: string;
}

export interface Subscription {
  id: string;
  workspace_id: string;
  plan_id: PlanId;
  status: string;
  period_start: string;
  period_end: string;
  cancel_at_period_end: boolean;
}

export interface AuthResponse {
  user: User;
  workspace: Workspace;
  subscription: Subscription;
}

export interface MeResponse {
  user: User;
  workspace: Workspace;
  subscription: Subscription;
  plan_id?: string;
  capabilities: Record<string, CapabilityDetailItem>;
  usage?: UsageMeter[];
  limits?: Record<string, number>;
  llm_configured?: boolean;
}

export interface PlanCapabilityItem {
  key: string;
  display_name: string;
  category: string;
  level: string;
  implemented: boolean;
  description: string;
}

export interface PlanItem {
  id: PlanId;
  name: string;
  price_bdt_monthly: number;
  personalization_label: string;
  description: string;
  badge: string;
  is_featured: boolean;
  audit_history_days: number;
  capabilities: PlanCapabilityItem[];
  limits: Record<string, number>;
}

export interface CapabilityCatalogItem {
  key: string;
  display_name: string;
  category: string;
  ordered_levels: string[];
  implemented: boolean;
  description: string;
}

export interface MetricCatalogItem {
  key: string;
  display_name: string;
  kind: 'counter' | 'gauge';
  description: string;
}

export type PlanCatalogResponse = PlanItem[];

export interface UsageMeter {
  metric: string;
  display_name: string;
  kind: 'counter' | 'gauge';
  used: number;
  limit: number;
  remaining: number;
  percent_used: number;
  resets_at: string | null;
}

export interface CheckoutResponse {
  checkout_url: string;
  status: string;
  session_id: string;
}

export interface ChecklistItem {
  id: string;
  company_profile_id: string;
  title: string;
  tier: string;
  reason: string;
  done: boolean;
  done_at: string | null;
  created_at: string;
}

export class ApiError extends Error {
  code: string;
  capability?: string;
  required_level?: string;
  current_level?: string;
  required_plan?: PlanId;
  current_plan?: PlanId;
  metric?: string;
  limit?: number;
  used?: number;
  resets_at?: string | null;
  upgrade_to?: PlanId | null;
  status: number;

  constructor(status: number, message: string, data?: Record<string, unknown>) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code =
      (data?.code as string) ||
      (status === 401
        ? 'UNAUTHENTICATED'
        : status === 403
        ? 'FEATURE_NOT_IN_PLAN'
        : status === 429
        ? 'QUOTA_EXCEEDED'
        : 'API_ERROR');
    this.capability = data?.capability as string | undefined;
    this.required_level = data?.required_level as string | undefined;
    this.current_level = data?.current_level as string | undefined;
    this.required_plan = data?.required_plan as PlanId | undefined;
    this.current_plan = data?.current_plan as PlanId | undefined;
    this.metric = data?.metric as string | undefined;
    this.limit = data?.limit as number | undefined;
    this.used = data?.used as number | undefined;
    this.resets_at = data?.resets_at as string | null | undefined;
    this.upgrade_to = data?.upgrade_to as PlanId | null | undefined;
  }
}

// ---------------------------------------------------------------------------
// Phase 2 Types: Team, API Keys, Support, Reviews, Comments
// ---------------------------------------------------------------------------

export interface TeamMemberItem {
  id: string;
  workspace_id: string;
  user_id: string;
  role: 'owner' | 'admin' | 'member' | 'viewer';
  effective_role: 'owner' | 'admin' | 'member' | 'viewer';
  is_frozen: boolean;
  email: string;
  full_name?: string;
  created_at: string;
}

export interface TeamInviteItem {
  id: string;
  workspace_id: string;
  email: string;
  role: 'admin' | 'member' | 'viewer';
  expires_at: string;
  created_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
}

export interface TeamMembersResponse {
  members: TeamMemberItem[];
  seat_limit: number;
  active_count: number;
  total_count: number;
}

export interface ApiKeyItem {
  id: string;
  workspace_id: string;
  name: string;
  prefix: string;
  scopes: string[];
  last_used_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface CreatedApiKeyResponse extends ApiKeyItem {
  secret_key: string;
}

export interface SupportTicketItem {
  id: string;
  workspace_id: string;
  user_id: string;
  subject: string;
  message: string;
  priority: 'urgent' | 'priority' | 'standard';
  status: 'open' | 'in_progress' | 'resolved';
  created_at: string;
}

export interface FindingReviewItem {
  id: string;
  workspace_id: string;
  plan_id: string;
  finding_id: string;
  status: 'approved' | 'rejected' | 'edited';
  reviewer_id: string;
  note?: string | null;
  edited_citation?: string | null;
  reviewed_at: string;
}

export interface FindingReviewsResponse {
  plan_id: string;
  original_impact_score: number;
  adjusted_impact_score: number;
  reviews: FindingReviewItem[];
}

export interface CommentItem {
  id: string;
  workspace_id: string;
  resource_type: 'finding' | 'checklist_item';
  resource_id: string;
  user_id: string;
  content: string;
  full_name?: string | null;
  email?: string | null;
  created_at: string;
}

export interface LawItem {
  id: string;
  canonical_title_en: string;
  canonical_title_bn?: string | null;
  act_number?: string | null;
  year?: number | null;
  law_type: 'act' | 'ordinance' | 'sro' | 'rule' | 'circular' | 'order' | 'gazette_notice';
  issuing_body: string;
  language_available: string;
  status: 'in_force' | 'amended' | 'repealed' | 'unknown';
  status_confidence: number;
  domain_tags: string[];
  summary_ai?: string | null;
  summary_verified: boolean;
  publish_state: 'draft' | 'pending_review' | 'published' | 'rejected';
  created_at: string;
}

export interface LawSectionItem {
  id: string;
  law_version_id: string;
  parent_id?: string | null;
  level: string;
  number_label: string;
  heading?: string | null;
  text: string;
  order_index: number;
}

export interface LawVersionItem {
  id: string;
  law_id: string;
  version_hash: string;
  source_url?: string | null;
  fetched_at: string;
  extraction_method: string;
  ocr_quality?: number | null;
  is_current: boolean;
}

export interface LawRelationItem {
  id: string;
  from_law_id: string;
  to_law_id: string;
  relation: string;
  to_law_title?: string | null;
  to_law_year?: number | null;
  from_law_title?: string | null;
  from_law_year?: number | null;
}

export interface LawDetailResponse {
  law: LawItem;
  current_version?: LawVersionItem | null;
  versions: LawVersionItem[];
  relations: LawRelationItem[];
  is_watched: boolean;
}

export interface LawSearchHit {
  law_id: string;
  version_id: string;
  section_id: string;
  law_title_en: string;
  law_title_bn?: string | null;
  law_type: string;
  year?: number | null;
  number_label: string;
  heading?: string | null;
  snippet: string;
  match_source: 'fts' | 'vector' | 'hybrid';
  score: number;
}

export interface LawSourceItem {
  id: string;
  name: string;
  base_url: string;
  source_type: string;
  enabled: boolean;
  crawl_config: Record<string, unknown>;
  rate_limit: number;
  last_run_at?: string | null;
  last_status?: string | null;
}

export interface LawCoverageResponse {
  published_laws_count: number;
  pending_review_count: number;
  total_sources_count: number;
  enabled_sources_count: number;
  failed_sources_count: number;
  by_law_type: Record<string, number>;
  by_issuing_body: Record<string, number>;
  recent_runs: Array<{
    id: string;
    source_id?: string | null;
    started_at: string;
    finished_at?: string | null;
    discovered: number;
    new: number;
    changed: number;
    failed: number;
    notes?: string | null;
  }>;
  sources: LawSourceItem[];
}


